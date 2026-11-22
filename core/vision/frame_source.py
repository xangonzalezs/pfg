"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo del contrato común a las fuentes de fotogramas.

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np


class CaptureError(Exception):
    # La fuente no puede seguir entregando fotogramas.

    pass


class EndOfVideoError(CaptureError):
    # El archivo de vídeo ha terminado. No es un fallo, sino el final normal.

    pass


@dataclass(frozen=True)
class CapturedFrame:
    # Un fotograma con la marca de tiempo que le corresponde.
  
    image: np.ndarray
    timestamp_ms: int


@runtime_checkable
class FrameSource(Protocol):
    # Fuente de fotogramas para el análisis.

    def read(self) -> CapturedFrame:
        # Siguiente fotograma en formato BGR, o CaptureError si no hay más.

        ...

    def close(self) -> None:
        # Libera los recursos. Debe poder invocarse más de una vez.

        ...

    @property
    def is_open(self) -> bool:
        # Indica si la fuente está lista para entregar fotogramas.

        ...