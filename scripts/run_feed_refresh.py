import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from app.db import SessionLocal
from app.sync_service import refresh_products_cache

def main() -> None:
    db = SessionLocal()
    try:
        result = refresh_products_cache(db, force=True)
        print(
            'Feed cache refresh finished: '
            f"products_found={result['products_found']}, "
            f"used_cached_data={result['used_cached_data']}, "
            f"refreshed_at={result['refreshed_at']}, "
            f"expires_at={result['expires_at']}"
        )
    finally:
        db.close()


if __name__ == '__main__':
    main()
