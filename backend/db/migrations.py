from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
import logging


def ensure_medical_profiles_schema(engine: Engine) -> None:
    """Ensure DB schema matches the ORM for medical_profiles table.

    - Adds created_at and updated_at columns if missing
    - Adds index on user_id if missing

    This function is idempotent and safe to run on startup.
    """
    try:
        insp = inspect(engine)
        tables = set(insp.get_table_names())
        if "medical_profiles" not in tables:
            return

        columns = {col["name"] for col in insp.get_columns("medical_profiles")}
        alters = []
        if "created_at" not in columns:
            alters.append("ADD COLUMN created_at DATETIME NULL")
        if "updated_at" not in columns:
            alters.append("ADD COLUMN updated_at DATETIME NULL")

        if alters:
            stmt = f"ALTER TABLE medical_profiles {', '.join(alters)}"
            logging.info(f"Applying schema patch: {stmt}")
            with engine.begin() as conn:
                conn.execute(text(stmt))

        existing_indexes = {idx.get("name") for idx in insp.get_indexes("medical_profiles")}
        idx_name = "ix_medical_profiles_user_id"
        if idx_name not in existing_indexes:
            try:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE medical_profiles ADD INDEX {idx_name} (user_id)"))
                logging.info(f"Created missing index {idx_name} on medical_profiles(user_id)")
            except Exception:
                logging.exception("Failed to create index on medical_profiles(user_id). Continuing.")
    except Exception:
        logging.exception("Error ensuring medical_profiles schema; continuing without blocking startup.")


def ensure_uploaded_files_schema(engine: Engine) -> None:
    """Ensure DB schema matches the ORM for uploaded_files table.

    - Adds accepted column if missing
    - Ensures indexes on user_id and status

    Idempotent and safe to run on startup.
    """
    try:
        insp = inspect(engine)
        tables = set(insp.get_table_names())
        if "uploaded_files" not in tables:
            return

        columns = {col["name"] for col in insp.get_columns("uploaded_files")}
        alters = []
        if "accepted" not in columns:
            alters.append("ADD COLUMN accepted TINYINT(1) NOT NULL DEFAULT 0")
        if "display_name" not in columns:
            alters.append("ADD COLUMN display_name VARCHAR(255) NULL")
        if "last_retry_at" not in columns:
            alters.append("ADD COLUMN last_retry_at DATETIME NULL")
        if "retry_count" not in columns:
            alters.append("ADD COLUMN retry_count INT NOT NULL DEFAULT 0")
        if alters:
            stmt = f"ALTER TABLE uploaded_files {', '.join(alters)}"
            logging.info(f"Applying schema patch: {stmt}")
            with engine.begin() as conn:
                conn.execute(text(stmt))

        existing_indexes = {idx.get("name") for idx in insp.get_indexes("uploaded_files")}
        if "ix_uploaded_files_user_id" not in existing_indexes:
            try:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE uploaded_files ADD INDEX ix_uploaded_files_user_id (user_id)"))
                logging.info("Created missing index ix_uploaded_files_user_id on uploaded_files(user_id)")
            except Exception:
                logging.exception("Failed to create index ix_uploaded_files_user_id. Continuing.")
        if "ix_uploaded_files_status" not in existing_indexes:
            try:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE uploaded_files ADD INDEX ix_uploaded_files_status (status)"))
                logging.info("Created missing index ix_uploaded_files_status on uploaded_files(status)")
            except Exception:
                logging.exception("Failed to create index ix_uploaded_files_status. Continuing.")
    except Exception:
        logging.exception("Error ensuring uploaded_files schema; continuing without blocking startup.")


def ensure_prescriptions_schema(engine: Engine) -> None:
    """Ensure DB schema matches the ORM for prescriptions table.

    - Adds accepted (bool) and accepted_at (datetime) columns if missing
    - Ensures indexes on user_id, file_id, accepted

    Idempotent and safe to run on startup.
    """
    try:
        insp = inspect(engine)
        tables = set(insp.get_table_names())
        if "prescriptions" not in tables:
            return

        columns = {col["name"] for col in insp.get_columns("prescriptions")}
        alters = []
        if "accepted" not in columns:
            alters.append("ADD COLUMN accepted TINYINT(1) NOT NULL DEFAULT 0")
        if "accepted_at" not in columns:
            alters.append("ADD COLUMN accepted_at DATETIME NULL")

        if alters:
            stmt = f"ALTER TABLE prescriptions {', '.join(alters)}"
            logging.info(f"Applying schema patch: {stmt}")
            with engine.begin() as conn:
                conn.execute(text(stmt))

        existing_indexes = {idx.get("name") for idx in insp.get_indexes("prescriptions")}
        # Ensure commonly used indexes
        if "ix_prescriptions_user_id" not in existing_indexes:
            try:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE prescriptions ADD INDEX ix_prescriptions_user_id (user_id)"))
                logging.info("Created missing index ix_prescriptions_user_id on prescriptions(user_id)")
            except Exception:
                logging.exception("Failed to create index ix_prescriptions_user_id. Continuing.")
        if "ix_prescriptions_file_id" not in existing_indexes:
            try:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE prescriptions ADD INDEX ix_prescriptions_file_id (file_id)"))
                logging.info("Created missing index ix_prescriptions_file_id on prescriptions(file_id)")
            except Exception:
                logging.exception("Failed to create index ix_prescriptions_file_id. Continuing.")
        if "ix_prescriptions_accepted" not in existing_indexes:
            try:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE prescriptions ADD INDEX ix_prescriptions_accepted (accepted)"))
                logging.info("Created missing index ix_prescriptions_accepted on prescriptions(accepted)")
            except Exception:
                logging.exception("Failed to create index ix_prescriptions_accepted. Continuing.")
    except Exception:
        logging.exception("Error ensuring prescriptions schema; continuing without blocking startup.")


def ensure_medication_schedules_schema(engine: Engine) -> None:
    """Ensure indexes exist for medication_schedules; create table is handled by Base.metadata.create_all.
    Safe to run on startup.
    """
    try:
        insp = inspect(engine)
        tables = set(insp.get_table_names())
        if "medication_schedules" not in tables:
            return
        existing_indexes = {idx.get("name") for idx in insp.get_indexes("medication_schedules")}
        if "ix_medication_schedules_user_id" not in existing_indexes:
            try:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE medication_schedules ADD INDEX ix_medication_schedules_user_id (user_id)"))
            except Exception:
                logging.exception("Failed to create index ix_medication_schedules_user_id. Continuing.")
        if "ix_medication_schedules_file_id" not in existing_indexes:
            try:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE medication_schedules ADD INDEX ix_medication_schedules_file_id (file_id)"))
            except Exception:
                logging.exception("Failed to create index ix_medication_schedules_file_id. Continuing.")
    except Exception:
        logging.exception("Error ensuring medication_schedules schema; continuing.")
