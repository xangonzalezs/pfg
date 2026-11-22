"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo del servicio que coordina el proceso de calibración corporal.
"""

from __future__ import annotations

import dataclasses

from core.calibration.neutral_pose import (
    NeutralPoseMeasurement,
    is_frame_valid,
    measure_neutral_pose,
)
from core.config.personalization import (
    PERSONALIZABLE_PARAMETERS,
    CalibrationOutcome,
    NeutralAngles,
    build_calibrated,
)
from core.config.thresholds import (
    AlignmentThresholds,
    GenericThresholds,
    ParameterThreshold,
)
from core.models.calibration_status import ThresholdsApplied
from core.models.landmark_result import LandmarkResult
from core.models.view_mode import ViewMode
from core.persistence.calibration_repository import (
    CalibrationProfile,
    CalibrationRepository,
)


class CalibrationServiceError(Exception):
    # La calibración no puede completarse o validarse en su estado actual.

    pass


class CalibrationService:
    # Coordina las dos capturas, la medición de la postura neutra, la derivación de umbrales y su persistencia.

    def __init__(
        self, repository: CalibrationRepository, thresholds: GenericThresholds
    ) -> None:
        self._repository = repository
        self._thresholds = thresholds
        self._frames: dict[ViewMode, list[LandmarkResult]] = {
            ViewMode.LATERAL: [],
            ViewMode.FRONTAL: [],
        }
        self._valid: dict[ViewMode, int] = {ViewMode.LATERAL: 0, ViewMode.FRONTAL: 0}


    def reset(self) -> None:
        # Descarta lo capturado, para empezar de nuevo.

        for view in self._frames:
            self._frames[view] = []
            self._valid[view] = 0

    def submit(self, view: ViewMode, landmark_result: LandmarkResult) -> bool:
        # Añade un fotograma a una captura y dice si es utilizable.


        usable = is_frame_valid(landmark_result, view, self._thresholds.calibration)
        self._frames[view].append(landmark_result)
        if usable:
            self._valid[view] += 1
        return usable

    def captured(self, view: ViewMode) -> tuple[int, int]:
        # Fotogramas utilizables y totales de una captura.

        return self._valid[view], len(self._frames[view])

    def is_ready(self, view: ViewMode) -> bool:
        # Indica si una captura cumple ya sus criterios de aceptación.

        criteria = self._thresholds.calibration
        usable, total = self.captured(view)
        if usable < criteria.min_frames:
            return False
        return usable >= total * criteria.min_validity_rate


    def measure(self) -> NeutralPoseMeasurement:
        # Reduce las dos capturas a las medidas de la postura neutra.

        return measure_neutral_pose(
            self._frames[ViewMode.LATERAL],
            self._frames[ViewMode.FRONTAL],
            self._thresholds.calibration,
        )

    def complete(
        self,
        user_id: int,
        *,
        frontal_image: str | None = None,
        lateral_image: str | None = None,
    ) -> CalibrationProfile:
        # Mide y guarda la calibración como pendiente de validación.


        measurement = self.measure()
        profile = self._repository.create_pending(
            user_id,
            knee_deg=measurement.knee_deg,
            back_arch_deg=measurement.back_arch_deg,
            elbow_deg=measurement.elbow_deg,
            legs_trunk_ratio=measurement.legs_trunk_ratio,
            shoulder_width_ratio=measurement.shoulder_width_ratio,
            frontal_image=frontal_image,
            lateral_image=lateral_image,
        )
        self.reset()
        return profile


    def proposed(self, profile: CalibrationProfile) -> CalibrationOutcome:
        # Umbrales que la derivación propone para una calibración, con la explicación de cómo se llegó a cada uno.

        return build_calibrated(
            self._thresholds.alignment,
            self._neutral_angles(profile),
            self._thresholds.personalization,
        )

    def validate(
        self,
        profile_id: int,
        trainer_id: int,
        *,
        overrides: dict[str, float] | None = None,
        note: str | None = None,
    ) -> CalibrationProfile:
        # Valida una calibración, conservando solo los umbrales que el entrenador haya modificado.

        self._check_overrides(overrides or {})
        return self._repository.validate(
            profile_id, trainer_id, thresholds=overrides or {}, note=note
        )

    def reject(
        self, profile_id: int, trainer_id: int, *, note: str | None = None
    ) -> CalibrationProfile:
        # Rechaza una calibración sin alterar la que estuviera vigente.

        return self._repository.reject(profile_id, trainer_id, note=note)


    def thresholds_for(
        self, user_id: int
    ) -> tuple[AlignmentThresholds, ThresholdsApplied]:
        # Umbrales con que un atleta practica, y de qué clase son.

        profile = self._repository.validated_for(user_id)
        if profile is None:
            return self._thresholds.alignment, ThresholdsApplied.GENERIC

        derived = self.proposed(profile).thresholds
        return (
            self._apply_overrides(derived, profile.adjusted_thresholds),
            ThresholdsApplied.PERSONALIZED,
        )


    @staticmethod
    def _neutral_angles(profile: CalibrationProfile) -> NeutralAngles:
        # Ángulos neutros en la forma que espera la derivación.

        return NeutralAngles(
            knee_deg=profile.neutral_knee_angle_deg,
            back_arch_deg=profile.neutral_back_arch_angle_deg,
            elbow_deg=profile.neutral_elbow_angle_deg,
        )

    @staticmethod
    def _check_overrides(overrides: dict[str, float]) -> None:
        # Un ajuste sobre un parámetro no personalizable quedaría almacenado sin que nada lo leyera nunca.

        unknown = sorted(set(overrides) - set(PERSONALIZABLE_PARAMETERS))
        if unknown:
            raise CalibrationServiceError(
                f"Parámetros no personalizables: {', '.join(unknown)}."
            )
        negative = sorted(name for name, value in overrides.items() if value <= 0)
        if negative:
            raise CalibrationServiceError(
                f"Un umbral ajustado debe ser positivo: {', '.join(negative)}."
            )

    @staticmethod
    def _apply_overrides(
        derived: AlignmentThresholds, overrides: dict[str, float]
    ) -> AlignmentThresholds:
        # Sustituye el umbral de los parámetros ajustados, conservando su
        # zona muerta, que no es cosa del entrenador.

        if not overrides:
            return derived

        parameters = dict(derived.parameters)
        for name, value in overrides.items():
            if name not in parameters:
                continue
            parameters[name] = ParameterThreshold(
                threshold=value, noise=parameters[name].noise
            )
        return dataclasses.replace(derived, parameters=parameters)