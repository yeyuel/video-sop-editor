from __future__ import annotations

from sqlalchemy import inspect, text
from sqlmodel import Session

from app.db import engine


def _ensure_schema_version_table(session: Session) -> None:
    session.exec(
        text(
            """
            CREATE TABLE IF NOT EXISTS schemaversionentity (
                id INTEGER PRIMARY KEY,
                version INTEGER NOT NULL DEFAULT 0
            )
            """
        )
    )
    row = session.exec(text("SELECT COUNT(*) FROM schemaversionentity")).one()
    if row[0] == 0:
        session.exec(text("INSERT INTO schemaversionentity (id, version) VALUES (1, 0)"))


def _current_version(session: Session) -> int:
    row = session.exec(text("SELECT version FROM schemaversionentity WHERE id = 1")).first()
    return int(row[0]) if row else 0


def _set_version(session: Session, version: int) -> None:
    session.exec(
        text("UPDATE schemaversionentity SET version = :version WHERE id = 1").bindparams(
            version=version
        )
    )


def _migration_001_legacy_columns(session: Session) -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

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

    if "rhythmplanentity" in table_names:
        rhythm_columns = {column["name"] for column in inspector.get_columns("rhythmplanentity")}
        if "audio_file_name" not in rhythm_columns:
            session.exec(
                text("ALTER TABLE rhythmplanentity ADD COLUMN audio_file_name TEXT DEFAULT ''")
            )
        if "audio_file_path" not in rhythm_columns:
            session.exec(
                text("ALTER TABLE rhythmplanentity ADD COLUMN audio_file_path TEXT DEFAULT ''")
            )
        if "analysis_source" not in rhythm_columns:
            session.exec(
                text(
                    "ALTER TABLE rhythmplanentity ADD COLUMN analysis_source TEXT DEFAULT 'manual'"
                )
            )
        if "analysis_notes" not in rhythm_columns:
            session.exec(
                text("ALTER TABLE rhythmplanentity ADD COLUMN analysis_notes TEXT DEFAULT '[]'")
            )


def _migration_002_rhythm_analysis_metrics(session: Session) -> None:
    inspector = inspect(engine)
    if "rhythmplanentity" not in inspector.get_table_names():
        return

    rhythm_columns = {column["name"] for column in inspector.get_columns("rhythmplanentity")}
    if "detected_bpm" not in rhythm_columns:
        session.exec(
            text("ALTER TABLE rhythmplanentity ADD COLUMN detected_bpm INTEGER DEFAULT 0")
        )
    if "audio_duration_sec" not in rhythm_columns:
        session.exec(
            text("ALTER TABLE rhythmplanentity ADD COLUMN audio_duration_sec REAL DEFAULT 0")
        )


def _migration_003_rhythm_raw_beats(session: Session) -> None:
    inspector = inspect(engine)
    if "rhythmplanentity" not in inspector.get_table_names():
        return

    rhythm_columns = {column["name"] for column in inspector.get_columns("rhythmplanentity")}
    if "raw_beat_points" not in rhythm_columns:
        session.exec(
            text("ALTER TABLE rhythmplanentity ADD COLUMN raw_beat_points TEXT DEFAULT '[]'")
        )


def _migration_004_rhythm_coarse_beats(session: Session) -> None:
    inspector = inspect(engine)
    if "rhythmplanentity" not in inspector.get_table_names():
        return

    rhythm_columns = {column["name"] for column in inspector.get_columns("rhythmplanentity")}
    if "coarse_beat_points" not in rhythm_columns:
        session.exec(
            text("ALTER TABLE rhythmplanentity ADD COLUMN coarse_beat_points TEXT DEFAULT '[]'")
        )


def _migration_005_llm_provider_config(session: Session) -> None:
    inspector = inspect(engine)
    if "llmproviderconfigentity" not in inspector.get_table_names():
        session.exec(
            text(
                """
                CREATE TABLE llmproviderconfigentity (
                    id TEXT PRIMARY KEY,
                    provider_id TEXT NOT NULL UNIQUE,
                    auth_type TEXT DEFAULT 'api_key',
                    base_url TEXT DEFAULT '',
                    model TEXT DEFAULT '',
                    api_key TEXT DEFAULT '',
                    status TEXT DEFAULT 'not_configured'
                )
                """
            )
        )


def _migration_006_app_settings(session: Session) -> None:
    inspector = inspect(engine)
    if "appsettingentity" not in inspector.get_table_names():
        session.exec(
            text(
                """
                CREATE TABLE appsettingentity (
                    key TEXT PRIMARY KEY,
                    value TEXT DEFAULT ''
                )
                """
            )
        )


def _migration_007_theme_evidence(session: Session) -> None:
    inspector = inspect(engine)
    if "themeentity" not in inspector.get_table_names():
        return

    theme_columns = {column["name"] for column in inspector.get_columns("themeentity")}
    if "used_locations" not in theme_columns:
        session.exec(text("ALTER TABLE themeentity ADD COLUMN used_locations TEXT DEFAULT '[]'"))
    if "used_asset_ids" not in theme_columns:
        session.exec(text("ALTER TABLE themeentity ADD COLUMN used_asset_ids TEXT DEFAULT '[]'"))


def _migration_008_auth_sessions(session: Session) -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    if "userentity" in table_names:
        user_columns = {column["name"] for column in inspector.get_columns("userentity")}
        if "created_at" not in user_columns:
            session.exec(text("ALTER TABLE userentity ADD COLUMN created_at TEXT DEFAULT ''"))

    if "authsessionentity" not in table_names:
        session.exec(
            text(
                """
                CREATE TABLE authsessionentity (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked INTEGER NOT NULL DEFAULT 0
                )
                """
            )
        )


def _migration_009_encrypt_llm_api_keys(session: Session) -> None:
    from sqlmodel import select

    from app.models.entities import LlmProviderConfigEntity
    from app.services.secret_vault import encrypt_api_key_if_needed, is_encrypted

    if "llmproviderconfigentity" not in inspect(engine).get_table_names():
        return

    rows = session.exec(select(LlmProviderConfigEntity)).all()
    for row in rows:
        if row.api_key and not is_encrypted(row.api_key):
            row.api_key = encrypt_api_key_if_needed(row.api_key)
            session.add(row)


def _migration_010_project_location_validation(session: Session) -> None:
    inspector = inspect(engine)
    if "projectentity" not in inspector.get_table_names():
        return

    project_columns = {column["name"] for column in inspector.get_columns("projectentity")}
    if "validate_location_order" not in project_columns:
        session.exec(
            text(
                "ALTER TABLE projectentity ADD COLUMN validate_location_order INTEGER NOT NULL DEFAULT 0"
            )
        )


def _migration_011_rhythm_bgm_recommendations(session: Session) -> None:
    inspector = inspect(engine)
    if "rhythmplanentity" not in inspector.get_table_names():
        return

    rhythm_columns = {column["name"] for column in inspector.get_columns("rhythmplanentity")}
    if "recommended_bgm" not in rhythm_columns:
        session.exec(text("ALTER TABLE rhythmplanentity ADD COLUMN recommended_bgm TEXT DEFAULT '[]'"))
    if "selected_bgm_id" not in rhythm_columns:
        session.exec(text("ALTER TABLE rhythmplanentity ADD COLUMN selected_bgm_id TEXT DEFAULT ''"))
    if "bgm_phase" not in rhythm_columns:
        session.exec(text("ALTER TABLE rhythmplanentity ADD COLUMN bgm_phase TEXT DEFAULT 'empty'"))


MIGRATIONS: list[tuple[int, str, object]] = [
    (1, "001_legacy_columns", _migration_001_legacy_columns),
    (2, "002_rhythm_analysis_metrics", _migration_002_rhythm_analysis_metrics),
    (3, "003_rhythm_raw_beats", _migration_003_rhythm_raw_beats),
    (4, "004_rhythm_coarse_beats", _migration_004_rhythm_coarse_beats),
    (5, "005_llm_provider_config", _migration_005_llm_provider_config),
    (6, "006_app_settings", _migration_006_app_settings),
    (7, "007_theme_evidence", _migration_007_theme_evidence),
    (8, "008_auth_sessions", _migration_008_auth_sessions),
    (9, "009_encrypt_llm_api_keys", _migration_009_encrypt_llm_api_keys),
    (10, "010_project_location_validation", _migration_010_project_location_validation),
    (11, "011_rhythm_bgm_recommendations", _migration_011_rhythm_bgm_recommendations),
]


def run_migrations() -> None:
    with Session(engine) as session:
        _ensure_schema_version_table(session)
        session.commit()

        current_version = _current_version(session)
        for version, _name, migration in MIGRATIONS:
            if version <= current_version:
                continue
            migration(session)
            _set_version(session, version)
            session.commit()
