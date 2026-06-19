from sqlmodel import Session

from app.db import create_db_and_tables, engine
from app.services.seed import seed_demo_data


def main() -> None:
    create_db_and_tables()
    with Session(engine) as session:
        seed_demo_data(session)
    print("Database initialized with demo data.")


if __name__ == "__main__":
    main()
