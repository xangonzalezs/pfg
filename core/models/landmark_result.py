"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de 
la técnica en ejercicios posturales. UNED

Modelos de datos para el resultado de detección de pose.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Landmark:
    # Punto clave del cuerpo humano detectado en un fotograma.

    index: int
    x: float
    y: float
    z: float
    visibility: float


@dataclass
class LandmarkResult:
    #Resultado de la detección de pose para un fotograma.

    landmarks: list[Landmark] = field(default_factory=list)
    timestamp_ms: int = 0

    @property
    def has_detection(self) -> bool:
        # Indica si se detectó al menos un landmark en el fotograma.

        return len(self.landmarks) > 0

    def get_landmark(self, index: int) -> Landmark | None:
        # Devuelve el landmark con el índice indicado, si existe.

        for lm in self.landmarks:
            if lm.index == index:
                return lm
        return None
