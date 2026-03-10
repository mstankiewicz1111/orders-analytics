import os
import sys
from sqlalchemy import text

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from app.db import SessionLocal
from app.sync_service import refresh_products_cache


def main():
    db = SessionLocal()

    run_id = db.execute(text("""
        INSERT INTO feed_sync_runs (started_at, status)
        VALUES (NOW(),'running')
        RETURNING id
    """)).scalar()

    db.commit()

    try:
        result = refresh_products_cache(db, force=True)

        db.execute(text("""
            UPDATE feed_sync_runs
            SET finished_at = NOW(),
                status = 'success',
                products_found = :products_found
            WHERE id = :id
        """), {
            "id": run_id,
            "products_found": result["products_found"]
        })

        db.commit()

        print(
            f"Feed cache refresh finished: "
            f"products_found={result['products_found']}"
        )

    except Exception as e:

        db.execute(text("""
            UPDATE feed_sync_runs
            SET finished_at = NOW(),
                status = 'failed',
                error_message = :msg
            WHERE id = :id
        """), {
            "id": run_id,
            "msg": str(e)
        })

        db.commit()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
