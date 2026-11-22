"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Estado del proceso de validación de una calibración.
"""

from __future__ import annotations

from enum import Enum


class CalibrationStatus(Enum):
    # Estado de una calibración. La ausencia de calibración no es un estado. se representa por la ausencia de fila.

    PENDING = "pending"
    VALIDATED = "validated"
    REJECTED = "rejected"
    # Fue validada y dejó de estar vigente al validarse una posterior.
    SUPERSEDED = "superseded"

    @classmethod
    def from_string(cls, value: str) -> "CalibrationStatus":
        # Convierte un valor persistido a CalibrationStatus.

        try:
            return cls(value.lower().strip())
        except (AttributeError, ValueError):
            raise ValueError(f"Estado de calibración no reconocido: {value!r}") from None


class ThresholdsApplied(Enum):
    # Tipo de umbrales con que se ejecutó una sesión. 
    # Condiciona la comparabilidad de puntuaciones, por eso se persiste con ella.

    GENERIC = "generic"
    PERSONALIZED = "personalized"

    @classmethod
    def from_string(cls, value: str) -> "ThresholdsApplied":
        # Convierte un valor persistido a ThresholdsApplied.

        try:
            return cls(value.lower().strip())
        except (AttributeError, ValueError):
            raise ValueError(f"Tipo de umbrales no reconocido: {value!r}") from None