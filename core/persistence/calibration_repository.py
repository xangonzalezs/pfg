"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de acceso a las calibraciones y a sus umbrales ajustados.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from core.models.calibration_status import CalibrationStatus
from core.persistence.database import Database, DatabaseError, utc_now


@dataclass(frozen=True)
class CalibrationProfile:
    # Calibración de un atleta, con el estado de su validación.

    profile_id: int
    user_id: int
    status: CalibrationStatus
    created_at: str = ""
    neutral_knee_angle_deg: float | None = None
    neutral_back_arch_angle_deg: float | None = None
    neutral_elbow_angle_deg: float | None = None
    legs_trunk_ratio: float | None = None
    shoulder_width_ratio: float | None = None
    reviewed_by: int | None = None
    reviewed_at: str | None = None
    review_note: str | None = None
    frontal_image: str | None = None
    lateral_image: str | None = None
    # Umbrales que el entrenador ajustó a mano antes de validar.
    adjusted_thresholds: dict[str, float] = field(default_factory=dict)


class DuplicatePendingError(DatabaseError):
    # El atleta ya tiene una calibración pendiente de validación.

    pass


class CalibrationRepository:
    # Creación, validación y consulta de las calibraciones.

    _COLUMNS = (
        "profile_id, user_id, created_at, status, neutral_knee_angle_deg, "
        "neutral_back_arch_angle_deg, neutral_elbow_angle_deg, legs_trunk_ratio, "
        "shoulder_width_ratio, reviewed_by, reviewed_at, review_note, "
        "frontal_image, lateral_image"
    )

    def __init__(self, database: Database) -> None:
        self._db = database

    def create_pending(
        self,
        user_id: int,
        *,
        knee_deg: float | None = None,
        back_arch_deg: float | None = None,
        elbow_deg: float | None = None,
        legs_trunk_ratio: float | None = None,
        shoulder_width_ratio: float | None = None,
        frontal_image: str | None = None,
        lateral_image: str | None = None,
    ) -> CalibrationProfile:
        # Registra una calibración pendiente de validación.

        try:
            with self._db.transaction() as connection:
                cursor = connection.execute(
                    "INSERT INTO calibration_profiles ("
                    "user_id, created_at, status, neutral_knee_angle_deg, "
                    "neutral_back_arch_angle_deg, neutral_elbow_angle_deg, "
                    "legs_trunk_ratio, shoulder_width_ratio, frontal_image, "
                    "lateral_image) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        user_id,
                        utc_now(),
                        CalibrationStatus.PENDING.value,
                        knee_deg,
                        back_arch_deg,
                        elbow_deg,
                        legs_trunk_ratio,
                        shoulder_width_ratio,
                        frontal_image,
                        lateral_image,
                    ),
                )
        except DatabaseError as error:
            if "idx_calibration_pending" in str(error) or "UNIQUE" in str(error):
                raise DuplicatePendingError(
                    f"La cuenta {user_id} ya tiene una calibración pendiente."
                ) from error
            raise

        created = self.get(int(cursor.lastrowid))
        if created is None:
            raise DatabaseError("No se pudo recuperar la calibración creada.")
        return created

    def validate(
        self,
        profile_id: int,
        reviewed_by: int,
        *,
        thresholds: dict[str, float] | None = None,
        note: str | None = None,
    ) -> CalibrationProfile:
        # Valida una calibración y pasa a sustituida la que estuviera vigente.

        profile = self._require(profile_id)

        with self._db.transaction() as connection:
            # hay que retirar la vigente antes de promover la nueva.
            # Si no, el índice único parcial rechazaría la segunda.
            connection.execute(
                "UPDATE calibration_profiles SET status = ? "
                "WHERE user_id = ? AND status = ?",
                (
                    CalibrationStatus.SUPERSEDED.value,
                    profile.user_id,
                    CalibrationStatus.VALIDATED.value,
                ),
            )
            connection.execute(
                "UPDATE calibration_profiles SET status = ?, reviewed_by = ?, "
                "reviewed_at = ?, review_note = ? WHERE profile_id = ?",
                (
                    CalibrationStatus.VALIDATED.value,
                    reviewed_by,
                    utc_now(),
                    note,
                    profile_id,
                ),
            )
            self._replace_thresholds(connection, profile_id, thresholds or {})

        return self._require(profile_id)

    def reject(
        self, profile_id: int, reviewed_by: int, *, note: str | None = None
    ) -> CalibrationProfile:
        # Rechaza una calibración, sin tocar la que estuviera vigente.

        self._require(profile_id)

        with self._db.transaction() as connection:
            connection.execute(
                "UPDATE calibration_profiles SET status = ?, reviewed_by = ?, "
                "reviewed_at = ?, review_note = ? WHERE profile_id = ?",
                (
                    CalibrationStatus.REJECTED.value,
                    reviewed_by,
                    utc_now(),
                    note,
                    profile_id,
                ),
            )

        return self._require(profile_id)

    def get(self, profile_id: int) -> CalibrationProfile | None:
        # Calibración por su identificador, con sus umbrales ajustados.

        row = self._db.connection.execute(
            f"SELECT {self._COLUMNS} FROM calibration_profiles WHERE profile_id = ?",
            (profile_id,),
        ).fetchone()
        return self._to_profile(row) if row is not None else None

    def validated_for(self, user_id: int) -> CalibrationProfile | None:
        # Calibración vigente de un atleta, que decide si practica con umbrales personalizados.

        return self._by_status(user_id, CalibrationStatus.VALIDATED)

    def pending_for(self, user_id: int) -> CalibrationProfile | None:
        # Calibración a la espera de que su entrenador decida.

        return self._by_status(user_id, CalibrationStatus.PENDING)

    def history_for(self, user_id: int) -> list[CalibrationProfile]:
        # Todas las calibraciones de un atleta, de más reciente a antigua.

        rows = self._db.connection.execute(
            f"SELECT {self._COLUMNS} FROM calibration_profiles "
            "WHERE user_id = ? ORDER BY created_at DESC, profile_id DESC",
            (user_id,),
        ).fetchall()
        return [self._to_profile(row) for row in rows]

    def pending_for_trainer(self, trainer_id: int) -> list[CalibrationProfile]:
        # Calibraciones pendientes de los atletas que supervisa un entrenador.

        rows = self._db.connection.execute(
            f"SELECT c.profile_id, c.user_id, c.created_at, c.status, "
            "c.neutral_knee_angle_deg, c.neutral_back_arch_angle_deg, "
            "c.neutral_elbow_angle_deg, c.legs_trunk_ratio, "
            "c.shoulder_width_ratio, c.reviewed_by, c.reviewed_at, "
            "c.review_note, c.frontal_image, c.lateral_image "
            "FROM calibration_profiles AS c JOIN users AS u ON u.user_id = c.user_id "
            "WHERE u.assigned_trainer_id = ? AND c.status = ? "
            "ORDER BY c.created_at",
            (trainer_id, CalibrationStatus.PENDING.value),
        ).fetchall()
        return [self._to_profile(row) for row in rows]

    def thresholds_of(self, profile_id: int) -> dict[str, float]:
        # Umbrales ajustados de una calibración.

        rows = self._db.connection.execute(
            "SELECT threshold_key, value FROM calibration_thresholds "
            "WHERE profile_id = ? ORDER BY threshold_key",
            (profile_id,),
        ).fetchall()
        return {row["threshold_key"]: float(row["value"]) for row in rows}

    def delete(self, profile_id: int) -> bool:
        # Elimina una calibración y sus umbrales ajustados.

        with self._db.transaction() as connection:
            cursor = connection.execute(
                "DELETE FROM calibration_profiles WHERE profile_id = ?",
                (profile_id,),
            )
        return cursor.rowcount > 0

    def _by_status(self, user_id: int, status: CalibrationStatus) -> CalibrationProfile | None:
        # A lo sumo hay una calibración por atleta en estos dos estados.

        row = self._db.connection.execute(
            f"SELECT {self._COLUMNS} FROM calibration_profiles "
            "WHERE user_id = ? AND status = ?",
            (user_id, status.value),
        ).fetchone()
        return self._to_profile(row) if row is not None else None

    def _require(self, profile_id: int) -> CalibrationProfile:
        # Calibración existente, o DatabaseError.

        profile = self.get(profile_id)
        if profile is None:
            raise DatabaseError(f"No existe la calibración {profile_id}.")
        return profile

    @staticmethod
    def _replace_thresholds(
        connection: sqlite3.Connection,
        profile_id: int,
        thresholds: dict[str, float],
    ) -> None:
        # Sustituye los umbrales ajustados por el conjunto recibido.

        connection.execute(
            "DELETE FROM calibration_thresholds WHERE profile_id = ?", (profile_id,)
        )
        connection.executemany(
            "INSERT INTO calibration_thresholds (profile_id, threshold_key, value) "
            "VALUES (?, ?, ?)",
            [(profile_id, key, float(value)) for key, value in thresholds.items()],
        )

    def _to_profile(self, row: sqlite3.Row) -> CalibrationProfile:
        # Traduce una fila a la entidad del dominio.

        profile_id = int(row["profile_id"])
        return CalibrationProfile(
            profile_id=profile_id,
            user_id=int(row["user_id"]),
            status=CalibrationStatus.from_string(row["status"]),
            created_at=row["created_at"],
            neutral_knee_angle_deg=row["neutral_knee_angle_deg"],
            neutral_back_arch_angle_deg=row["neutral_back_arch_angle_deg"],
            neutral_elbow_angle_deg=row["neutral_elbow_angle_deg"],
            legs_trunk_ratio=row["legs_trunk_ratio"],
            shoulder_width_ratio=row["shoulder_width_ratio"],
            reviewed_by=(
                int(row["reviewed_by"]) if row["reviewed_by"] is not None else None
            ),
            reviewed_at=row["reviewed_at"],
            review_note=row["review_note"],
            frontal_image=row["frontal_image"],
            lateral_image=row["lateral_image"],
            adjusted_thresholds=self.thresholds_of(profile_id),
        )