"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Rol de una cuenta del sistema.
"""

from __future__ import annotations

from enum import Enum


class UserRole(Enum):
    # Rol de la cuenta, que determina las vistas y acciones permitidas (FR-001).

    ATHLETE = "athlete"
    TRAINER = "trainer"
    ADMIN = "admin"

    @classmethod
    def from_string(cls, value: str) -> "UserRole":
        # Convierte un valor persistido a UserRole.

        try:
            return cls(value.lower().strip())
        except (AttributeError, ValueError):
            raise ValueError(f"Rol no reconocido: {value!r}") from None