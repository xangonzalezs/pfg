"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Modo de vista de la cámara para el análisis del pino.
"""

from __future__ import annotations

from enum import Enum


class ViewMode(Enum):
    # Modo de vista de la cámara durante la sesión de entrenamiento.

    LATERAL = "lateral"
    FRONTAL = "frontal"

    @classmethod
    def from_string(cls, value: str | None) -> "ViewMode":
        # Convierte una cadena persistida a ViewMode.

        if value is None:
            return cls.LATERAL

        normalized = value.lower().strip() if isinstance(value, str) else ""

        if normalized == "posterior":
            return cls.FRONTAL

        try:
            return cls(normalized)
        except ValueError:
            return cls.LATERAL
