"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de análisis de estabilidad durante el pino.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum

from core.analysis.error_selection import severity_from_metric
from core.analysis.geometry import Point, centroid
from core.analysis.landmarks import (
    IDX_LEFT_HIP,
    IDX_LEFT_SHOULDER,
    IDX_RIGHT_HIP,
    IDX_RIGHT_SHOULDER,
    as_point,
    visible,
)
from core.models.analysis_result import ErrorMeasurement, TechnicalError
from core.models.landmark_result import LandmarkResult



class ReferencePoint(Enum):
    # Conjunto de puntos anatómicos con el que se calcula el centroide.

    HIPS = "hips"
    LEFT_HIP = "left_hip"
    RIGHT_HIP = "right_hip"
    SHOULDERS = "shoulders"
    LEFT_SHOULDER = "left_shoulder"
    RIGHT_SHOULDER = "right_shoulder"


# Referencias por orden de preferencia con los índices que la componen.
_REFERENCES: tuple[tuple[ReferencePoint, tuple[int, ...]], ...] = (
    (ReferencePoint.HIPS, (IDX_LEFT_HIP, IDX_RIGHT_HIP)),
    (ReferencePoint.LEFT_HIP, (IDX_LEFT_HIP,)),
    (ReferencePoint.RIGHT_HIP, (IDX_RIGHT_HIP,)),
    (ReferencePoint.SHOULDERS, (IDX_LEFT_SHOULDER, IDX_RIGHT_SHOULDER)),
    (ReferencePoint.LEFT_SHOULDER, (IDX_LEFT_SHOULDER,)),
    (ReferencePoint.RIGHT_SHOULDER, (IDX_RIGHT_SHOULDER,)),
)


@dataclass
class StabilityResult:
    # Resultado del análisis de estabilidad para el fotograma actual.

    is_unstable: bool
    dispersion: float | None
    threshold: float
    history_size: int
    reference: ReferencePoint | None
    measurement: ErrorMeasurement | None = None

    @property
    def is_evaluable(self) -> bool:
        # Indica si el fotograma ha producido una medida de estabilidad.

        return self.dispersion is not None


def _population_variance(values: list[float]) -> float:
    # Varianza poblacional de una serie de valores.

    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    return sum((v - mean) ** 2 for v in values) / n


class StabilityAnalyzer:
    # Detecta oscilaciones excesivas del cuerpo durante el pino.

    def __init__(
        self,
        *,
        window_size: int,
        instability_threshold: float,
        instability_noise: float,
        min_visibility: float = 0.5,
        max_missing_frames: int = 5,
    ) -> None:
        # Los tres primeros no tienen valor por defecto. proceden de la configuración externa.

        if window_size < 2:
            raise ValueError("La ventana debe contener al menos dos fotogramas.")
        if instability_threshold <= 0.0:
            raise ValueError("El umbral de inestabilidad debe ser positivo.")
        if instability_noise < 0.0:
            raise ValueError("La zona muerta no puede ser negativa.")
        if instability_noise >= instability_threshold:
            raise ValueError(
                "La zona muerta debe ser menor que el umbral de inestabilidad; "
                "de otro modo no existiría un intervalo en el que graduar la severidad."
            )

        self._window_size = window_size
        self._instability_threshold = instability_threshold
        self._instability_noise = instability_noise
        self._min_visibility = min_visibility
        self._max_missing_frames = max_missing_frames

        self._x_history: deque[float] = deque(maxlen=window_size)
        self._y_history: deque[float] = deque(maxlen=window_size)
        self._reference: ReferencePoint | None = None
        self._missing_frames = 0

    def update(self, landmark_result: LandmarkResult) -> StabilityResult:
        # Incorpora el fotograma actual a la ventana y evalúa la estabilidad.

        centroid = self._compute_centroid(landmark_result)

        if centroid is None:
            return self._handle_missing_reference()

        reference, mid_x, mid_y = centroid
        self._missing_frames = 0

        if reference is not self._reference:
            self._x_history.clear()
            self._y_history.clear()
            self._reference = reference

        self._x_history.append(mid_x)
        self._y_history.append(mid_y)

        if len(self._x_history) < 2:
            return self._result(is_unstable=False, dispersion=None)

        variance = _population_variance(list(self._x_history)) + _population_variance(
            list(self._y_history)
        )
        dispersion = round(variance ** 0.5, 6)

        return self._result(
            is_unstable=dispersion > self._instability_threshold,
            dispersion=dispersion,
        )

    def reset(self) -> None:
        # Vacía la ventana y olvida la referencia en uso.

        self._x_history.clear()
        self._y_history.clear()
        self._reference = None
        self._missing_frames = 0

    @property
    def history_size(self) -> int:
        # Número de observaciones acumuladas en la ventana.

        return len(self._x_history)

    @property
    def reference(self) -> ReferencePoint | None:
        # Conjunto de puntos con el que se está midiendo, si hay alguno.

        return self._reference

    def _compute_centroid(
        self, landmark_result: LandmarkResult
    ) -> tuple[ReferencePoint, float, float] | None:
        # Centroide del conjunto de referencia elegido para este fotograma,

        if self._reference is not None:
            centroid = self._centroid_for(landmark_result, self._reference)
            if centroid is not None:
                return centroid

        for reference, indices in _REFERENCES:
            centroid = self._centroid_for(landmark_result, reference, indices)
            if centroid is not None:
                return centroid

        return None

    def _centroid_for(
        self,
        landmark_result: LandmarkResult,
        reference: ReferencePoint,
        indices: tuple[int, ...] | None = None,
    ) -> tuple[ReferencePoint, float, float] | None:
        # Centroide de un conjunto concreto, o None si le falta algún punto.

        if indices is None:
            indices = dict(_REFERENCES)[reference]

        points: list[Point] = []
        for index in indices:
            landmark = visible(landmark_result, index, self._min_visibility)
            if landmark is None:
                return None
            points.append(as_point(landmark))

        x, y = centroid(points)
        return reference, x, y

    def _handle_missing_reference(self) -> StabilityResult:
        # Resuelve un fotograma sin puntos de referencia fiables.

        self._missing_frames += 1

        if self._missing_frames > self._max_missing_frames:
            self._x_history.clear()
            self._y_history.clear()
            self._reference = None

        return self._result(is_unstable=False, dispersion=None)

    def _result(self, *, is_unstable: bool, dispersion: float | None) -> StabilityResult:
        # Construye el resultado con el estado actual del analizador.

        return StabilityResult(
            is_unstable=is_unstable,
            dispersion=dispersion,
            threshold=self._instability_threshold,
            history_size=len(self._x_history),
            reference=self._reference,
            measurement=self._measurement(dispersion),
        )

    def _measurement(self, dispersion: float | None) -> ErrorMeasurement | None:
        # Expresa la dispersión medida como medición de un error técnico.

        if dispersion is None:
            return None

        return ErrorMeasurement(
            error_type=TechnicalError.INSTABILITY,
            measured_value=dispersion,
            threshold_value=self._instability_threshold,
            severity=severity_from_metric(
                dispersion,
                self._instability_threshold,
                self._instability_noise,
            ),
        )