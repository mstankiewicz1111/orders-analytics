from app.db import SessionLocal
from app.sync_service import sync_all


def main() -> None:
    db = SessionLocal()
    try:
        result = sync_all(db)
        print(result)
    finally:
        db.close()


if __name__ == '__main__':
    main()
