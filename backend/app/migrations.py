from sqlalchemy import inspect, text
from sqlmodel import Session

from app.db import engine


def run_sqlite_migrations() -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    with Session(engine) as session:
        if "projectentity" in table_names:
            project_columns = {column["name"] for column in inspector.get_columns("projectentity")}
            if "media_root" not in project_columns:
                session.exec(text("ALTER TABLE projectentity ADD COLUMN media_root TEXT DEFAULT ''"))
            if "selected_theme_id" not in project_columns:
                session.exec(
                    text("ALTER TABLE projectentity ADD COLUMN selected_theme_id TEXT DEFAULT ''")
                )
            if "style_notes" not in project_columns:
                session.exec(text("ALTER TABLE projectentity ADD COLUMN style_notes TEXT DEFAULT ''"))
                session.exec(
                    text(
                        """
                        UPDATE projectentity
                        SET
                          style_notes = substr(style_preference, instr(style_preference, '；补充：') + length('；补充：')),
                          style_preference = substr(style_preference, 1, instr(style_preference, '；补充：') - 1)
                        WHERE instr(style_preference, '；补充：') > 0
                        """
                    )
                )

        if "assetentity" in table_names:
            asset_columns = {column["name"] for column in inspector.get_columns("assetentity")}
            if "relative_path" not in asset_columns:
                session.exec(text("ALTER TABLE assetentity ADD COLUMN relative_path TEXT DEFAULT ''"))

        session.commit()
