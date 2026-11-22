"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de estimación de la pose a partir de los fotogramas capturados.

"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from core.models.landmark_result import Landmark, LandmarkResult

# Confianza mínima exigida al detector, al seguimiento y a la presencia.
MIN_CONFIDENCE: float = 0.5


class PoseDetectorError(Exception):
    # El estimador de pose no pudo inicializarse o procesar un fotograma.

    pass


class PoseLandmarkerBackend(Protocol):
    # Envoltura del estimador real, para poder sustituirlo en las pruebas.
    # Devuelve los puntos de la pose detectada, o una lista vacía si no hay.

    def detect(self, frame: np.ndarray, timestamp_ms: int) -> list[Any]:
        ...

    def close(self) -> None:
        ...


class PoseDetector:
    # Traduce un fotograma en los puntos anatómicos del atleta.

    def __init__(
        self,
        model_path: str | Path,
        *,
        backend_factory: Callable[[bytes], PoseLandmarkerBackend] | None = None,
    ) -> None:
        # backend_factory permite construir el detector sin MediaPipe.
        # hace comprobable esta clase sin el modelo.

        self._model_path = Path(model_path)
        self._backend_factory = backend_factory or _create_mediapipe_backend
        self._backend: PoseLandmarkerBackend | None = None
        self._last_timestamp_ms: int | None = None

    @property
    def is_ready(self) -> bool:
        # Indica si el modelo está cargado.

        return self._backend is not None

    def initialize(self) -> None:
        # Carga el modelo. Puede invocarse más de una vez sin efecto.

        if self._backend is not None:
            return

        if not self._model_path.is_file():
            raise PoseDetectorError(
                f"No se encuentra el modelo de estimación de pose: {self._model_path}. "
                "Ejecute scripts/download_model.py para descargarlo."
            )

        try:
            # El modelo se lee en memoria y se entrega como búfer en lugar de por ruta.
            model_buffer = self._model_path.read_bytes()
            self._backend = self._backend_factory(model_buffer)
        except PoseDetectorError:
            raise
        except Exception as exc:
            self._backend = None
            raise PoseDetectorError(
                f"No se pudo cargar el modelo de estimación de pose: {exc}"
            ) from exc

    def detect(self, frame: np.ndarray, timestamp_ms: int) -> LandmarkResult:
        # Estima la pose de un fotograma.

        if self._backend is None:
            raise PoseDetectorError("El estimador de pose no está inicializado.")

        self._check_timestamp(timestamp_ms)

        try:
            landmarks = self._backend.detect(frame, timestamp_ms)
        except Exception as exc:
            raise PoseDetectorError(
                f"Fallo al estimar la pose del fotograma {timestamp_ms} ms: {exc}"
            ) from exc

        self._last_timestamp_ms = timestamp_ms

        return LandmarkResult(
            landmarks=[
                Landmark(
                    index=index,
                    x=float(point.x),
                    y=float(point.y),
                    z=float(getattr(point, "z", 0.0)),
                    visibility=float(getattr(point, "visibility", 0.0)),
                )
                for index, point in enumerate(landmarks)
            ],
            timestamp_ms=timestamp_ms,
        )

    def reset(self) -> None:
        # Olvida la última marca de tiempo, para empezar una fuente nueva.

        self._last_timestamp_ms = None

    def close(self) -> None:
        # Libera el modelo. Puede invocarse más de una vez.

        if self._backend is not None:
            self._backend.close()
            self._backend = None
        self._last_timestamp_ms = None

    def _check_timestamp(self, timestamp_ms: int) -> None:
        # El seguimiento temporal exige marcas estrictamente crecientes.

        if (
            self._last_timestamp_ms is not None
            and timestamp_ms <= self._last_timestamp_ms
        ):
            raise PoseDetectorError(
                f"La marca de tiempo debe crecer: {timestamp_ms} ms no supera "
                f"la anterior de {self._last_timestamp_ms} ms."
            )


class _MediaPipeBackend:
    # Estimador real, apoyado en PoseLandmarker de MediaPipe Tasks.

    def __init__(self, model_buffer: bytes) -> None:
        import mediapipe as mp
        from mediapipe.tasks.python.core.base_options import BaseOptions
        from mediapipe.tasks.python.vision import (
            PoseLandmarker,
            PoseLandmarkerOptions,
            RunningMode,
        )

        self._mp = mp
        options = PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_buffer=model_buffer),
            running_mode=RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=MIN_CONFIDENCE,
            min_pose_presence_confidence=MIN_CONFIDENCE,
            min_tracking_confidence=MIN_CONFIDENCE,
        )
        self._landmarker = PoseLandmarker.create_from_options(options)

    def detect(self, frame: np.ndarray, timestamp_ms: int) -> list[Any]:
        # MediaPipe espera RGB; OpenCV entrega BGR.

        import cv2

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = self._mp.Image(
            image_format=self._mp.ImageFormat.SRGB, data=rgb
        )
        result = self._landmarker.detect_for_video(image, timestamp_ms)

        if not result.pose_landmarks:
            return []
        return list(result.pose_landmarks[0])

    def close(self) -> None:
        self._landmarker.close()


def _create_mediapipe_backend(model_buffer: bytes) -> PoseLandmarkerBackend:
    # Construye el estimador real. 
    # La importación de MediaPipe ocurre aquí y no al cargar el módulo.

    return _MediaPipeBackend(model_buffer)