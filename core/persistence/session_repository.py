"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de acceso a las sesiones de práctica y a sus errores registrados.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from core.models.analysis_result import TechnicalError
from core.models.calibration_status import ThresholdsApplied
from core.models.view_mode import ViewMode
from core.persistence.database import Database, DatabaseError, utc_now


@dataclass(frozen=True)
class ErrorOccurrence:
    # Una ocurrencia de error durante una sesión.

    error_type: TechnicalError
    measured_value: float
    threshold_value: float
    offset_s: float
    error_id: int | None = None


@dataclass(frozen=True)
class SessionRecord:
    # Sesión de práctica registrada.

    session_id: int
    user_id: int
    timestamp: str
    total_duration_s: float
    total_hold_time_s: float
    hold_attempts: int
    view_mode: ViewMode
    thresholds_applied: ThresholdsApplied
    mean_alignment_score: float | None = None
    errors: list[ErrorOccurrence] = field(default_factory=list)


class SessionRepository:
    # Registro y consulta de las sesiones de práctica.

    _COLUMNS = (
        "session_id, user_id, timestamp, total_duration_s, total_hold_time_s, "
        "hold_attempts, mean_alignment_score, view_mode, thresholds_applied"
    )

    def __init__(self, database: Database) -> None:
        self._db = database

    def save(
        self,
        user_id: int,
        *,
        total_duration_s: float,
        total_hold_time_s: float,
        hold_attempts: int,
        view_mode: ViewMode,
        thresholds_applied: ThresholdsApplied,
        mean_alignment_score: float | None = None,
        errors: list[ErrorOccurrence] | None = None,
        timestamp: str | None = None,
    ) -> SessionRecord:
        # Registra una sesión con todas sus ocurrencias de error.

        with self._db.transaction() as connection:
            cursor = connection.execute(
                "INSERT INTO sessions (user_id, timestamp, total_duration_s, "
                "total_hold_time_s, hold_attempts, mean_alignment_score, "
                "view_mode, thresholds_applied) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    user_id,
                    timestamp or utc_now(),
                    total_duration_s,
                    total_hold_time_s,
                    hold_attempts,
                    mean_alignment_score,
                    view_mode.value,
                    thresholds_applied.value,
                ),
            )
            session_id = int(cursor.lastrowid)
            self._insert_errors(connection, session_id, errors or [])

        saved = self.get(session_id)
        if saved is None:
            raise DatabaseError("No se pudo recuperar la sesión registrada.")
        return saved

    def get(self, session_id: int) -> SessionRecord | None:
        # Sesión por su identificador, con sus errores.

        row = self._db.connection.execute(
            f"SELECT {self._COLUMNS} FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return self._to_session(row) if row is not None else None

    def recent_for(self, user_id: int, limit: int = 10) -> list[SessionRecord]:
        # Últimas sesiones de un atleta, de más reciente a más antigua.

        if limit < 1:
            raise DatabaseError(f"El límite debe ser al menos 1; se recibió {limit}.")

        rows = self._db.connection.execute(
            f"SELECT {self._COLUMNS} FROM sessions WHERE user_id = ? "
            "ORDER BY timestamp DESC, session_id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [self._to_session(row) for row in rows]

    def count_for(self, user_id: int) -> int:
        # Número de sesiones registradas de un atleta.

        row = self._db.connection.execute(
            "SELECT COUNT(*) FROM sessions WHERE user_id = ?", (user_id,)
        ).fetchone()
        return int(row[0])

    def errors_of(self, session_id: int) -> list[ErrorOccurrence]:
        # Ocurrencias de error de una sesión, en orden cronológico.

        rows = self._db.connection.execute(
            "SELECT error_id, error_type, measured_value, threshold_value, offset_s "
            "FROM session_errors WHERE session_id = ? ORDER BY offset_s, error_id",
            (session_id,),
        ).fetchall()
        return [self._to_occurrence(row) for row in rows]

    def error_counts_for(self, user_id: int) -> dict[TechnicalError, int]:
        # Ocurrencias de cada tipo de error de un atleta em tpdas sus sesiones.

        rows = self._db.connection.execute(
            "SELECT e.error_type, COUNT(*) AS total "
            "FROM session_errors AS e JOIN sessions AS s "
            "ON s.session_id = e.session_id "
            "WHERE s.user_id = ? GROUP BY e.error_type ORDER BY total DESC",
            (user_id,),
        ).fetchall()
        return {
            TechnicalError(row["error_type"]): int(row["total"]) for row in rows
        }

    def delete(self, session_id: int) -> bool:
        # Elimina una sesión y sus errores.

        with self._db.transaction() as connection:
            cursor = connection.execute(
                "DELETE FROM sessions WHERE session_id = ?", (session_id,)
            )
        return cursor.rowcount > 0


    @staticmethod
    def _insert_errors(
        connection: sqlite3.Connection,
        session_id: int,
        errors: list[ErrorOccurrence],
    ) -> None:
        # Inserta las ocurrencias de una sesión.

        connection.executemany(
            "INSERT INTO session_errors (session_id, error_type, measured_value, "
            "threshold_value, offset_s) VALUES (?, ?, ?, ?, ?)",
            [
                (
                    session_id,
                    error.error_type.value,
                    error.measured_value,
                    error.threshold_value,
                    error.offset_s,
                )
                for error in errors
            ],
        )

    @staticmethod
    def _to_occurrence(row: sqlite3.Row) -> ErrorOccurrence:
        # Traduce una fila de error a la entidad del dominio.

        return ErrorOccurrence(
            error_id=int(row["error_id"]),
            error_type=TechnicalError(row["error_type"]),
            measured_value=float(row["measured_value"]),
            threshold_value=float(row["threshold_value"]),
            offset_s=float(row["offset_s"]),
        )

    def _to_session(self, row: sqlite3.Row) -> SessionRecord:
        # Traduce una fila de sesión a la entidad del dominio.

        session_id = int(row["session_id"])
        return SessionRecord(
            session_id=session_id,
            user_id=int(row["user_id"]),
            timestamp=row["timestamp"],
            total_duration_s=float(row["total_duration_s"]),
            total_hold_time_s=float(row["total_hold_time_s"]),
            hold_attempts=int(row["hold_attempts"]),
            mean_alignment_score=row["mean_alignment_score"],
            view_mode=ViewMode.from_string(row["view_mode"]),
            thresholds_applied=ThresholdsApplied.from_string(
                row["thresholds_applied"]
            ),
            errors=self.errors_of(session_id),
        )