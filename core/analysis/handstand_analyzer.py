"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de coordinación del análisis de un fotograma.
"""

from __future__ import annotations

from core.analysis.alignment_analyzer import AlignmentAnalyzer
from core.analysis.error_selection import ErrorSelector
from core.analysis.handstand_detector import HandstandDetector, HandstandState
from core.analysis.stability_analyzer import StabilityAnalyzer
from core.config.thresholds import AlignmentThresholds, GenericThresholds
from core.models.analysis_result import (
    AnalysisResult,
    DetectedError,
    ErrorMeasurement,
    TechnicalError,
)
from core.models.landmark_result import LandmarkResult
from core.models.view_mode import ViewMode


class HandstandAnalyzer:
    # Analiza la postura del pino fotograma a fotograma.

    def __init__(
        self,
        detector: HandstandDetector,
        alignment: AlignmentAnalyzer,
        stability: StabilityAnalyzer,
        selector: ErrorSelector,
    ) -> None:
        self._detector = detector
        self._alignment = alignment
        self._stability = stability
        self._selector = selector
        self._state = HandstandState(is_inverted=False, in_handstand=False)

    @classmethod
    def from_thresholds(
        cls, thresholds: GenericThresholds, view_mode: ViewMode
    ) -> HandstandAnalyzer:
        # Construye el conjunto completo a partir de la configuración.

        return cls(
            detector=HandstandDetector(thresholds.handstand),
            alignment=AlignmentAnalyzer(thresholds.alignment, view_mode),
            stability=StabilityAnalyzer(
                window_size=thresholds.stability.window_size,
                instability_threshold=thresholds.stability.instability_threshold,
                instability_noise=thresholds.stability.noise,
            ),
            selector=ErrorSelector(view_mode, thresholds.error_selection),
        )

    @property
    def view_mode(self) -> ViewMode:
        # Vista desde la que se analiza.

        return self._alignment.view_mode

    @property
    def handstand_state(self) -> HandstandState:
        # Estado de la detección tras el último fotograma.

        return self._state

    def set_view_mode(self, view_mode: ViewMode) -> None:
        # Cambia la vista y descarta el estado acumulado con la anterior.

        self._alignment.set_view_mode(view_mode)
        self._selector = ErrorSelector(view_mode, self._selector.thresholds)
        self.reset()

    def apply_thresholds(self, thresholds: AlignmentThresholds) -> None:
        # Sustituye los umbrales de alineación por los personalizados.

        self._alignment.set_thresholds(thresholds)

    def reset(self) -> None:
        # Olvida la detección, la ventana de estabilidad y los errores activos.

        self._detector.reset()
        self._stability.reset()
        self._selector.reset()
        self._state = HandstandState(is_inverted=False, in_handstand=False)

    def analyze(self, landmark_result: LandmarkResult) -> AnalysisResult:
        # Analiza un fotograma y devuelve los errores que deben comunicarse.

        self._state = self._detector.update(landmark_result)

        # La ventana de estabilidad se alimenta siempre, para que no arranque vacía al confirmarse el pino.
        stability = self._stability.update(landmark_result)

        if not self._state.in_handstand:
            # Entre intentos los errores activos no se conservan.
            self._selector.reset()
            return AnalysisResult(in_handstand=False)

        report = self._alignment.analyze(landmark_result)

        measurements = dict(report.measurements)
        if stability.measurement is not None:
            measurements[TechnicalError.INSTABILITY] = stability.measurement

        severities = {
            error: measurement.severity
            for error, measurement in measurements.items()
        }

        return AnalysisResult(
            alignment_score=report.score,
            active_errors=self._detected_errors(
                self._selector.select(severities), measurements
            ),
            in_handstand=True,
            segment_deviations=report.segment_deviations,
        )

    @staticmethod
    def _detected_errors(
        active: list[TechnicalError],
        measurements: dict[TechnicalError, ErrorMeasurement],
    ) -> list[DetectedError]:
        # Convierte los errores activos en ocurrencias con su evidencia.

        return [
            measurements[error].to_detected_error()
            for error in active
            if error in measurements
        ]