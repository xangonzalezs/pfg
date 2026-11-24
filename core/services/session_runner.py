"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo del hilo que alimenta el servicio de sesión con los fotogramas.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

import numpy as np

from core.services.session_service import FrameOutcome, SessionService
from core.vision.frame_source import CaptureError, EndOfVideoError, FrameSource
from core.vision.pose_detector import PoseDetector, PoseDetectorError


@dataclass(frozen=True)
class RunnerFrame:
    # Lo que el hilo publica. la imagen y su resultado juntos.
    # Van en un mismo objeto para que la interfaz no pueda leer una imagen y el análisis del fotograma siguiente.

    image: np.ndarray
    outcome: FrameOutcome


class SessionRunner:
    # Lee fotogramas en un hilo propio y publica el último resultado.

    def __init__(
        self,
        source: FrameSource,
        detector: PoseDetector,
        service: SessionService,
    ) -> None:
        self._source = source
        self._detector = detector
        self._service = service

        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._latest: RunnerFrame | None = None
        self._failure: str | None = None
        self._source_exhausted = False

    @property
    def is_running(self) -> bool:
        # Indica si el hilo sigue leyendo fotogramas.

        return self._thread is not None and self._thread.is_alive()

    @property
    def failure(self) -> str | None:
        # Motivo por el que el bucle terminó, si no fue a petición.

        with self._lock:
            return self._failure

    @property
    def source_exhausted(self) -> bool:
        # Indica si un archivo de vídeo llegó a su final.

        with self._lock:
            return self._source_exhausted

    def latest(self) -> RunnerFrame | None:
        # Último fotograma procesado, con su imagen, sin bloquear a quien pregunta. 
        # La interfaz lo consulta de forma periódica y lee solo esto.

        with self._lock:
            return self._latest

    def start(self) -> None:
        # Arranca el hilo de lectura.

        if self.is_running:
            return

        self._stop.clear()
        with self._lock:
            self._failure = None
            self._source_exhausted = False

        self._thread = threading.Thread(
            target=self._loop, name="session-runner", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        # Pide la parada y espera a que el hilo termine.


        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None


    def _loop(self) -> None:
        # Lee, estima y entrega al servicio hasta que se pide parar.

        while not self._stop.is_set():
            try:
                frame = self._source.read()
            except EndOfVideoError:
                self._note(exhausted=True)
                return
            except CaptureError as error:
                self._note(failure=str(error))
                return

            try:
                landmark_result = self._detector.detect(frame.image, frame.timestamp_ms)
            except PoseDetectorError as error:
                if not self._service.note_failure():
                    self._note(failure=str(error))
                    return
                continue

            outcome = self._service.process(landmark_result)
            with self._lock:
                self._latest = RunnerFrame(image=frame.image, outcome=outcome)

    def _note(self, *, failure: str | None = None, exhausted: bool = False) -> None:
        # Deja constancia de por qué terminó el bucle.

        with self._lock:
            if failure is not None:
                self._failure = failure
            self._source_exhausted = exhausted