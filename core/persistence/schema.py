"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo del esquema físico de la base de datos.

"""

from __future__ import annotations

from enum import Enum

from core.models.analysis_result import TechnicalError
from core.models.calibration_status import CalibrationStatus, ThresholdsApplied
from core.models.user_role import UserRole
from core.models.view_mode import ViewMode

# Versión del esquema, para detectar una base de datos de otra versión.
SCHEMA_VERSION = 1


def _check(column: str, enum: type[Enum]) -> str:
    # Construye la cláusula CHECK desde el enumerado.
    # de esta forma el vocabulario de la columna y el del código no pueden desincronizarse.

    values = ", ".join(f"'{member.value}'" for member in enum)
    return f"CHECK ({column} IN ({values}))"


_USERS = f"""
CREATE TABLE IF NOT EXISTS users (
    user_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    username               TEXT    NOT NULL UNIQUE,
    password_hash          TEXT    NOT NULL,
    role                   TEXT    NOT NULL {_check("role", UserRole)},
    full_name              TEXT    NOT NULL,
    email                  TEXT    UNIQUE,
    profile_photo_filename TEXT,
    assigned_trainer_id    INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    created_at             TEXT    NOT NULL
)
"""

_CALIBRATION_PROFILES = f"""
CREATE TABLE IF NOT EXISTS calibration_profiles (
    profile_id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                     INTEGER NOT NULL
                                REFERENCES users(user_id) ON DELETE CASCADE,
    created_at                  TEXT    NOT NULL,
    status                      TEXT    NOT NULL
                                {_check("status", CalibrationStatus)},
    neutral_knee_angle_deg      REAL,
    neutral_back_arch_angle_deg REAL,
    neutral_elbow_angle_deg     REAL,
    legs_trunk_ratio            REAL,
    shoulder_width_ratio        REAL,
    reviewed_by                 INTEGER
                                REFERENCES users(user_id) ON DELETE SET NULL,
    reviewed_at                 TEXT,
    review_note                 TEXT,
    frontal_image               TEXT,
    lateral_image               TEXT
)
"""

_CALIBRATION_THRESHOLDS = """
CREATE TABLE IF NOT EXISTS calibration_thresholds (
    profile_id    INTEGER NOT NULL
                  REFERENCES calibration_profiles(profile_id) ON DELETE CASCADE,
    threshold_key TEXT    NOT NULL,
    value         REAL    NOT NULL,
    PRIMARY KEY (profile_id, threshold_key)
)
"""

_SESSIONS = f"""
CREATE TABLE IF NOT EXISTS sessions (
    session_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id              INTEGER NOT NULL
                         REFERENCES users(user_id) ON DELETE CASCADE,
    timestamp            TEXT    NOT NULL,
    total_duration_s     REAL    NOT NULL,
    total_hold_time_s    REAL    NOT NULL,
    hold_attempts        INTEGER NOT NULL,
    mean_alignment_score REAL,
    view_mode            TEXT    NOT NULL {_check("view_mode", ViewMode)},
    thresholds_applied   TEXT    NOT NULL
                         {_check("thresholds_applied", ThresholdsApplied)}
)
"""

_SESSION_ERRORS = f"""
CREATE TABLE IF NOT EXISTS session_errors (
    error_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL
                    REFERENCES sessions(session_id) ON DELETE CASCADE,
    error_type      TEXT    NOT NULL {_check("error_type", TechnicalError)},
    measured_value  REAL    NOT NULL,
    threshold_value REAL    NOT NULL,
    offset_s        REAL    NOT NULL
)
"""

TABLES: tuple[str, ...] = (
    _USERS,
    _CALIBRATION_PROFILES,
    _CALIBRATION_THRESHOLDS,
    _SESSIONS,
    _SESSION_ERRORS,
)

# Los dos primeros responden a las consultas dominantes del sistema. 
# los dos últimos son además la restricción de unicidad.
INDEXES: tuple[str, ...] = (
    """
    CREATE INDEX IF NOT EXISTS idx_sessions_user_timestamp
        ON sessions (user_id, timestamp DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_session_errors_session
        ON session_errors (session_id, error_type)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_users_trainer
        ON users (assigned_trainer_id)
    """,
    f"""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_calibration_validated
        ON calibration_profiles (user_id)
        WHERE status = '{CalibrationStatus.VALIDATED.value}'
    """,
    f"""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_calibration_pending
        ON calibration_profiles (user_id)
        WHERE status = '{CalibrationStatus.PENDING.value}'
    """,
)

TABLE_NAMES: tuple[str, ...] = (
    "users",
    "calibration_profiles",
    "calibration_thresholds",
    "sessions",
    "session_errors",
)

INDEX_NAMES: tuple[str, ...] = (
    "idx_sessions_user_timestamp",
    "idx_session_errors_session",
    "idx_users_trainer",
    "idx_calibration_validated",
    "idx_calibration_pending",
)