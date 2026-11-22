"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de lectura de fotogramas desde un archivo de vídeo.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import cv2

from core.vision.frame_source import CaptureError, CapturedFrame, EndOfVideoError

# Cadencia que se aplica cuando el archivo no declara una plausible.
DEFAULT_FPS: float = 25.0

# Cadencias fuera de este intervalo se consideran metadatos poco fiables.
_MIN_FPS: float = 1.0
_MAX_FPS: float = 120.0

# Tamaño máximo del archivo que el usuario aporta.
MAX_VIDEO_BYTES: int = 200 * 1024 * 1024


class VideoFileCapture:
    # Entrega los fotogramas de un archivo de vídeo.

    def __init__(
        self,
        path: str | Path,
        *,
        realtime: bool = True,
        capture_factory: Callable[[str], cv2.VideoCapture] = cv2.VideoCapture,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        # realtime pausa entre fotogramas para reproducir a la cadencia original. 

        self._path = Path(path)
        self._realtime = realtime
        self._capture_factory = capture_factory
        self._clock = clock
        self._sleep = sleep

        self._capture: cv2.VideoCapture | None = None
        self._fps = DEFAULT_FPS
        self._frame_index = 0
        self._last_read: float | None = None

    @property
    def path(self) -> Path:
        # Archivo que se está leyendo.

        return self._path

    @property
    def fps(self) -> float:
        # Cadencia efectiva, declarada por el archivo o la de respaldo.

        return self._fps

    @property
    def is_open(self) -> bool:
        # Indica si el archivo está abierto.

        return self._capture is not None

    def open(self) -> None:
        # Abre el archivo y determina su cadencia.

        if self._capture is not None:
            return

        if not self._path.is_file():
            raise CaptureError(f"El archivo de vídeo no existe: {self._path}")

        # el tamaño se comprueba antes de abrir, no después.
        tamano = self._path.stat().st_size
        if tamano > MAX_VIDEO_BYTES:
            raise CaptureError(
                f"El archivo de vídeo supera el máximo admitido "
                f"({tamano / 1024 / 1024:.0f} MB sobre "
                f"{MAX_VIDEO_BYTES // 1024 // 1024} MB): {self._path}"
            )

        # El archivo se valida por su contenido y no por su extensión.
        capture = self._capture_factory(str(self._path))
        if not capture.isOpened():
            capture.release()
            raise CaptureError(f"No se pudo abrir el archivo de vídeo: {self._path}")

        self._capture = capture
        self._fps = self._read_fps(capture)
        self._frame_index = 0
        self._last_read = None

    def read(self) -> CapturedFrame:
        # Siguiente fotograma, o EndOfVideoError al acabar el archivo.

        if self._capture is None:
            raise CaptureError("El archivo de vídeo no está abierto.")

        self._wait_for_cadence()

        ok, image = self._capture.read()
        if not ok or image is None:
            raise EndOfVideoError(f"Fin del vídeo: {self._path}")

        # el mismo archivo produce las mismas marcas siempre.
        timestamp_ms = round(self._frame_index * 1000.0 / self._fps)
        self._frame_index += 1

        return CapturedFrame(image=image, timestamp_ms=timestamp_ms)

    def close(self) -> None:
        # Libera el archivo. Puede invocarse más de una vez.

        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def _read_fps(self, capture: cv2.VideoCapture) -> float:
        # Cadencia declarada por el archivo.

        declared = capture.get(cv2.CAP_PROP_FPS)
        if declared != declared or not _MIN_FPS <= declared <= _MAX_FPS:
            return DEFAULT_FPS
        return float(declared)

    def _wait_for_cadence(self) -> None:
        # Espera lo que falte para respetar la cadencia original.

        if not self._realtime:
            return

        now = self._clock()
        if self._last_read is not None:
            remaining = (1.0 / self._fps) - (now - self._last_read)
            if remaining > 0:
                self._sleep(remaining)

        self._last_read = self._clock()