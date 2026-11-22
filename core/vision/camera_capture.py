"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de lectura de fotogramas desde la cámara del equipo.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import cv2

from core.vision.frame_source import CaptureError, CapturedFrame


class CameraCapture:
    # Entrega los fotogramas de una cámara conectada al equipo.

    def __init__(
        self,
        index: int = 0,
        *,
        capture_factory: Callable[[int], cv2.VideoCapture] = cv2.VideoCapture,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._index = index
        self._capture_factory = capture_factory
        self._clock = clock

        self._capture: cv2.VideoCapture | None = None
        self._origin: float | None = None

    @property
    def index(self) -> int:
        # Dispositivo que se está usando.

        return self._index

    @property
    def is_open(self) -> bool:
        # Indica si la cámara está abierta.

        return self._capture is not None

    def open(self) -> None:
        # Abre la cámara y fija el origen de tiempos de la sesión.

        if self._capture is not None:
            return

        capture = self._capture_factory(self._index)
        if not capture.isOpened():
            capture.release()
            raise CaptureError(f"No se pudo abrir la cámara {self._index}.")

        self._capture = capture
        self._origin = self._clock()

    def read(self) -> CapturedFrame:
        # Siguiente fotograma, o CaptureError si la cámara deja de responder.

        if self._capture is None or self._origin is None:
            raise CaptureError("La cámara no está abierta.")

        ok, image = self._capture.read()
        if not ok or image is None:
            raise CaptureError(f"La cámara {self._index} dejó de entregar fotogramas.")

        # En directo la marca es el tiempo transcurrido desde que se abrió la cámara.
        timestamp_ms = round((self._clock() - self._origin) * 1000.0)

        return CapturedFrame(image=image, timestamp_ms=timestamp_ms)

    def close(self) -> None:
        # Libera la cámara. Puede invocarse más de una vez.

        if self._capture is not None:
            self._capture.release()
            self._capture = None
            self._origin = None