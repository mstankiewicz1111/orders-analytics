from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from .feed import iter_production_products
from .idosell import IdosellClient
from .settings import settings


APP_TZ = ZoneInfo(settings.app_timezone)


def chunked(items: list[int], size: int):
    for index in range(0, len(items), size):
        yield items[index:index + size]



def create_sync_run(db: Session) -> int:
    run_id = db.execute(
        text(
            """
            INSERT INTO sync_runs (started_at, status)
            VALUES (NOW(), 'running')
            RETURNING id
            """
        )
    ).scalar_one()
    db.commit()
    return run_id



def finalize_sync_run(
    db: Session,
    run_id: int,
    *,
    status: str,
    products_found: int = 0,
    batches_processed: int = 0,
    rows_written_current: int = 0,
    rows_written_history: int = 0,
    error_message: str | None = None,
) -> None:
    db.execute(
        text(
            """
            UPDATE sync_runs
            SET finished_at = NOW(),
                status = :status,
                products_found = :products_found,
                batches_processed = :batches_processed,
                rows_written_current = :rows_written_current,
                rows_written_history = :rows_written_history,
                error_message = :error_message
            WHERE id = :run_id
            """
        ),
        {
            'run_id': run_id,
            'status': status,
            'products_found': products_found,
            'batches_processed': batches_processed,
            'rows_written_current': rows_written_current,
            'rows_written_history': rows_written_history,
            'error_message': error_message,
        },
    )
    db.commit()



def refresh_products_cache(db: Session, *, force: bool = False) -> dict:
    existing_count = db.execute(
        text("SELECT COUNT(*) FROM production_products_cache WHERE expires_at > NOW()")
    ).scalar_one()

    if existing_count > 0 and not force:
        return {
            'products_found': int(existing_count),
            'used_cached_data': True,
            'refreshed_at': None,
            'expires_at': None,
        }

    db.execute(text("TRUNCATE TABLE production_products_cache"))
    db.commit()

    fetched_at = datetime.now(APP_TZ)
    expires_at = fetched_at + timedelta(hours=settings.feed_cache_ttl_hours)

    rows = list(iter_production_products())
    for row in rows:
        db.execute(
            text(
                """
                INSERT INTO production_products_cache (product_id, symbol, kolor, fetched_at, expires_at)
                VALUES (:product_id, :symbol, :kolor, :fetched_at, :expires_at)
                """
            ),
            {
                **row,
                'fetched_at': fetched_at,
                'expires_at': expires_at,
            },
        )

    db.commit()

    return {
        'products_found': len(rows),
        'used_cached_data': False,
        'refreshed_at': fetched_at,
        'expires_at': expires_at,
    }



def ensure_products_cache(db: Session) -> int:
    result = refresh_products_cache(db, force=False)
    return int(result['products_found'])



def sync_all(db: Session) -> dict:
    run_id = create_sync_run(db)
    try:
        products_found = ensure_products_cache(db)
        product_ids = [
            row[0]
            for row in db.execute(
                text(
                    """
                    SELECT product_id
                    FROM production_products_cache
                    WHERE expires_at > NOW()
                    ORDER BY product_id
                    """
                )
            ).all()
        ]

        db.execute(text("TRUNCATE TABLE product_stock_current"))
        db.commit()

        client = IdosellClient()
        now = datetime.now(APP_TZ)
        snapshot_date = now.date()

        batches_processed = 0
        rows_written_current = 0
        rows_written_history = 0

        for batch in chunked(product_ids, settings.sync_batch_size):
            payload = client.fetch_stocks(batch)
            batches_processed += 1

            for item in payload.get('results', []):
                product_id = int(item['ident']['identValue'])
                stocks = item.get('quantities', {}).get('stocks', [])

                for stock in stocks:
                    if stock.get('stock_id') != 1:
                        continue

                    for size in stock.get('sizes', []):
                        size_id = str(size.get('size_id', '')).strip()
                        quantity = int(size.get('quantity', 0) or 0)
                        reserved_orders = int((size.get('reservations') or {}).get('order', 0) or 0)

                        db.execute(
                            text(
                                """
                                INSERT INTO product_stock_current
                                    (product_id, stock_id, size_id, quantity, reserved_orders, fetched_at)
                                VALUES
                                    (:product_id, 1, :size_id, :quantity, :reserved_orders, :fetched_at)
                                """
                            ),
                            {
                                'product_id': product_id,
                                'size_id': size_id,
                                'quantity': quantity,
                                'reserved_orders': reserved_orders,
                                'fetched_at': now,
                            },
                        )
                        rows_written_current += 1

                        db.execute(
                            text(
                                """
                                INSERT INTO product_stock_history
                                    (snapshot_date, product_id, stock_id, size_id, quantity, reserved_orders, fetched_at)
                                VALUES
                                    (:snapshot_date, :product_id, 1, :size_id, :quantity, :reserved_orders, :fetched_at)
                                ON CONFLICT (snapshot_date, product_id, stock_id, size_id)
                                DO UPDATE SET
                                    quantity = EXCLUDED.quantity,
                                    reserved_orders = EXCLUDED.reserved_orders,
                                    fetched_at = EXCLUDED.fetched_at
                                """
                            ),
                            {
                                'snapshot_date': snapshot_date,
                                'product_id': product_id,
                                'size_id': size_id,
                                'quantity': quantity,
                                'reserved_orders': reserved_orders,
                                'fetched_at': now,
                            },
                        )
                        rows_written_history += 1

            db.commit()

        finalize_sync_run(
            db,
            run_id,
            status='success',
            products_found=products_found,
            batches_processed=batches_processed,
            rows_written_current=rows_written_current,
            rows_written_history=rows_written_history,
        )
        return {
            'run_id': run_id,
            'products_found': products_found,
            'batches_processed': batches_processed,
            'rows_written_current': rows_written_current,
            'rows_written_history': rows_written_history,
        }
    except Exception as exc:  # noqa: BLE001
        finalize_sync_run(db, run_id, status='failed', error_message=str(exc))
        raise
