from sqlalchemy import text
from sqlalchemy.orm import Session

ALLOWED_SORTS = {
    'id': 'id',
    'symbol_kolor': 'symbol_kolor',
    'm1': 'm1_stan_dyspozycyjny',
    'rezerwacje': 'rezerwacje',
}
ALLOWED_DIRS = {'asc', 'desc'}


BASE_TABLE_CTE = """
WITH aggregated AS (
    SELECT
        p.product_id AS id,
        (p.symbol || '-' || p.kolor) AS symbol_kolor,
        COALESCE(SUM(s.quantity - s.reserved_orders), 0) AS m1_stan_dyspozycyjny,
        COALESCE(SUM(s.reserved_orders), 0) AS rezerwacje
    FROM production_products_cache p
    LEFT JOIN product_stock_current s
      ON s.product_id = p.product_id
     AND s.stock_id = 1
    WHERE p.expires_at > NOW()
    {filters}
    GROUP BY p.product_id, p.symbol, p.kolor
)
"""


def _build_filters(q: str | None) -> tuple[str, dict[str, str]]:
    params: dict[str, str] = {}
    filters = ''
    if q:
        filters += """
        AND (
          CAST(p.product_id AS TEXT) ILIKE :q
          OR p.symbol ILIKE :q
          OR p.kolor ILIKE :q
        )
        """
        params['q'] = f'%{q}%'
    return filters, params


def _normalize_sort(sort: str | None, direction: str | None) -> tuple[str, str]:
    sort_key = ALLOWED_SORTS.get(sort or 'id', 'id')
    sort_dir = direction if direction in ALLOWED_DIRS else 'asc'
    return sort_key, sort_dir


def get_table_rows(
    db: Session,
    q: str | None = None,
    sort: str | None = None,
    direction: str | None = None,
    page: int = 1,
    per_page: int = 100,
):
    filters, params = _build_filters(q)
    sort_key, sort_dir = _normalize_sort(sort, direction)
    offset = max(page - 1, 0) * per_page

    sql = (
        BASE_TABLE_CTE.format(filters=filters)
        + f"""
        SELECT id, symbol_kolor, m1_stan_dyspozycyjny, rezerwacje
        FROM aggregated
        ORDER BY {sort_key} {sort_dir}, id ASC
        LIMIT :limit OFFSET :offset
        """
    )
    params.update({'limit': per_page, 'offset': offset})
    return db.execute(text(sql), params).mappings().all()


def count_table_rows(db: Session, q: str | None = None) -> int:
    filters, params = _build_filters(q)
    sql = BASE_TABLE_CTE.format(filters=filters) + "SELECT COUNT(*) FROM aggregated"
    return int(db.execute(text(sql), params).scalar() or 0)



def get_all_table_rows(
    db: Session,
    q: str | None = None,
    sort: str | None = None,
    direction: str | None = None,
):
    filters, params = _build_filters(q)
    sort_key, sort_dir = _normalize_sort(sort, direction)
    sql = (
        BASE_TABLE_CTE.format(filters=filters)
        + f"""
        SELECT id, symbol_kolor, m1_stan_dyspozycyjny, rezerwacje
        FROM aggregated
        ORDER BY {sort_key} {sort_dir}, id ASC
        """
    )
    return db.execute(text(sql), params).mappings().all()



def get_last_sync_runs(db: Session, limit: int = 10):
    return db.execute(
        text(
            """
            SELECT id, started_at, finished_at, status, products_found,
                   batches_processed, rows_written_current, rows_written_history, error_message
            FROM sync_runs
            ORDER BY id DESC
            LIMIT :limit
            """
        ),
        {'limit': limit},
    ).mappings().all()
