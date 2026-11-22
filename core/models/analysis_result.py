"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Modelos de datos para el resultado del análisis del pino.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TechnicalError(Enum):
    # Errores técnicos detectables durante la ejecución del pino.

    BACK_ARCH = "back_arch"
    PELVIS_POSITION = "pelvis_position"
    NO_SHRUG = "no_shrug"
    INSTABILITY = "instability"
    LEGS_NOT_STRAIGHT = "legs_not_straight"
    HEAD_FORWARD = "head_forward"
    FEET_NOT_EXTENDED = "feet_not_extended"
    ELBOW_NOT_EXTENDED = "elbow_not_extended"

    # Asimetrías laterales (vista frontal).
    LEFT_SHOULDER_LOW = "left_shoulder_low"
    RIGHT_SHOULDER_LOW = "right_shoulder_low"
    LEFT_HIP_LOW = "left_hip_low"
    RIGHT_HIP_LOW = "right_hip_low"


@dataclass
class DetectedError:
    # Desviación detectada en un fotograma, con valor numérico.

    error_type: TechnicalError
    measured_value: float
    threshold_value: float

@dataclass
class ErrorMeasurement:
    # Medición de un parámetro postural concreto en un fotograma.

    error_type: TechnicalError
    measured_value: float
    threshold_value: float
    severity: float

    def to_detected_error(self) -> DetectedError:
        # Construye el error detectado que corresponde a esta medición, descartando la severidad.

        return DetectedError(
            error_type=self.error_type,
            measured_value=self.measured_value,
            threshold_value=self.threshold_value,
        )

@dataclass
class AnalysisResult:
    # Resultado del análisis de la postura del pino para un fotograma.

    alignment_score: float | None = None
    active_errors: list[DetectedError] = field(default_factory=list)
    in_handstand: bool = False
    segment_deviations: dict[str, float] = field(default_factory=dict)

    @property
    def has_errors(self) -> bool:
        # Indica si hay algún error técnico activo en este fotograma.

        return len(self.active_errors) > 0

    @property
    def error_types(self) -> list[TechnicalError]:
        # Tipos de los errores activos, sin valor numérico.

        return [error.error_type for error in self.active_errors]

    @property
    def is_valid(self) -> bool:
        # Indica si el resultado contiene una puntuación calculable.

        return self.alignment_score is not None
