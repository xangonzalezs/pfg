"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de derivación de umbrales personalizados a partir de la calibración corporal.

"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import Enum

from core.config.thresholds import (
    PERSONALIZABLE_PARAMETERS,
    STRAIGHT_ANGLE_DEG,
    AlignmentThresholds,
    ParameterThreshold,
    PersonalizationLimits,
)


@dataclass(frozen=True)
class NeutralAngles:
    # Ángulos articulares medidos sobre la postura neutra de la calibración.
    # Un valor a None significa que la captura no permitió medirlo.

    knee_deg: float | None = None
    back_arch_deg: float | None = None
    elbow_deg: float | None = None

    def get(self, parameter: str) -> float | None:
        # Ángulo neutro correspondiente a un parámetro personalizable.

        return {
            "knee_bend": self.knee_deg,
            "back_arch": self.back_arch_deg,
            "elbow_bend": self.elbow_deg,
        }[parameter]


class PersonalizationStatus(Enum):
    # Resultado de intentar personalizar un parámetro.

    # El ángulo neutro era verosímil y ha producido un umbral más tolerante.
    PERSONALIZED = "personalized"

    # Como el anterior, pero el límite de seguridad ha acotado el resultado.
    CAPPED = "capped"

    # El ángulo era verosímil pero no implica desviación residual. Se conserva el umbral genérico.
    UNCHANGED = "unchanged"

    # La calibración no pudo medir el ángulo.
    NOT_MEASURED = "not_measured"

    # El ángulo queda fuera del rango fisiológico esperado y se descarta.
    IMPLAUSIBLE = "implausible"


@dataclass(frozen=True)
class ParameterOutcome:
    # Qué se ha hecho con un parámetro y con qué dato.

    status: PersonalizationStatus
    threshold: float
    neutral_angle_deg: float | None = None

    @property
    def is_personalized(self) -> bool:
        return self.status in (
            PersonalizationStatus.PERSONALIZED,
            PersonalizationStatus.CAPPED,
        )


@dataclass(frozen=True)
class CalibrationOutcome:
    # Umbrales derivados y la explicación de cómo se ha llegado a ellos.

    thresholds: AlignmentThresholds
    outcomes: dict[str, ParameterOutcome]

    @property
    def personalized_parameters(self) -> tuple[str, ...]:
        # Parámetros cuyo umbral difiere del genérico.

        return tuple(
            name
            for name, outcome in self.outcomes.items()
            if outcome.is_personalized
        )

    @property
    def is_personalized(self) -> bool:
        # Indica si la calibración ha alterado algún umbral.

        return bool(self.personalized_parameters)


def build_calibrated(
    base: AlignmentThresholds,
    neutral: NeutralAngles,
    limits: Mapping[str, PersonalizationLimits],
) -> CalibrationOutcome:
    # Construye los umbrales personalizados a partir de la postura neutra.

    parameters = dict(base.parameters)
    outcomes: dict[str, ParameterOutcome] = {}

    for name in PERSONALIZABLE_PARAMETERS:
        generic = parameters[name]
        limit = limits[name]
        angle = neutral.get(name)

        if angle is None:
            outcomes[name] = ParameterOutcome(
                status=PersonalizationStatus.NOT_MEASURED,
                threshold=generic.threshold,
            )
            continue

        if not limit.is_plausible(angle):
            outcomes[name] = ParameterOutcome(
                status=PersonalizationStatus.IMPLAUSIBLE,
                threshold=generic.threshold,
                neutral_angle_deg=angle,
            )
            continue

        residual = max(0.0, STRAIGHT_ANGLE_DEG - angle)
        proposed = generic.threshold + residual
        threshold = min(limit.max_threshold_deg, proposed)

        if residual == 0.0:
            status = PersonalizationStatus.UNCHANGED
        elif threshold < proposed:
            status = PersonalizationStatus.CAPPED
        else:
            status = PersonalizationStatus.PERSONALIZED

        parameters[name] = ParameterThreshold(
            threshold=threshold, noise=generic.noise
        )
        outcomes[name] = ParameterOutcome(
            status=status, threshold=threshold, neutral_angle_deg=angle
        )

    return CalibrationOutcome(
        thresholds=replace(base, parameters=parameters),
        outcomes=outcomes,
    )
