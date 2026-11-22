"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de análisis de la alineación corporal durante el pino.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.analysis.error_selection import severity_from_metric
from core.analysis.geometry import (
    Point,
    angle_at,
    deviation_from_horizontal,
    deviation_from_vertical,
    distance,
    distance_to_line,
)
from core.config.thresholds import SEGMENT_NAMES, AlignmentThresholds
from core.models.analysis_result import ErrorMeasurement, TechnicalError
from core.analysis.landmarks import (
    IDX_LEFT_ANKLE,
    IDX_LEFT_EAR,
    IDX_LEFT_ELBOW,
    IDX_LEFT_FOOT_INDEX,
    IDX_LEFT_HIP,
    IDX_LEFT_KNEE,
    IDX_LEFT_SHOULDER,
    IDX_LEFT_WRIST,
    IDX_RIGHT_ANKLE,
    IDX_RIGHT_EAR,
    IDX_RIGHT_ELBOW,
    IDX_RIGHT_FOOT_INDEX,
    IDX_RIGHT_HIP,
    IDX_RIGHT_KNEE,
    IDX_RIGHT_SHOULDER,
    IDX_RIGHT_WRIST,
    as_point,
    joint_points,
    visible,
    visible_pair,
)
from core.models.landmark_result import Landmark, LandmarkResult
from core.models.view_mode import ViewMode

# Cada línea corporal se define por las dos articulaciones que une.
_SEGMENTS: dict[str, tuple[str, str]] = {
    "wrists_shoulders": ("wrists", "shoulders"),
    "shoulders_hips": ("shoulders", "hips"),
    "hips_knees": ("hips", "knees"),
    "knees_ankles": ("knees", "ankles"),
}

# Líneas sin las cuales no se emite puntuación.
# definen la alineación esencial del pino
_REQUIRED_SEGMENTS: frozenset[str] = frozenset({"wrists_shoulders", "shoulders_hips"})

# Cadenas articulares de los parámetros comunes a las dos vistas.
_ELBOW_CHAINS: tuple[tuple[int, int, int], ...] = (
    (IDX_LEFT_SHOULDER, IDX_LEFT_ELBOW, IDX_LEFT_WRIST),
    (IDX_RIGHT_SHOULDER, IDX_RIGHT_ELBOW, IDX_RIGHT_WRIST),
)

# La flexión plantar ocurre en el plano sagital, de modo que la cadena del pie solo es medible de perfil.
_FOOT_CHAINS: tuple[tuple[int, int, int], ...] = (
    (IDX_LEFT_KNEE, IDX_LEFT_ANKLE, IDX_LEFT_FOOT_INDEX),
    (IDX_RIGHT_KNEE, IDX_RIGHT_ANKLE, IDX_RIGHT_FOOT_INDEX),
)


@dataclass
class AlignmentReport:
    # Resultado del análisis de alineación para un fotograma.

    score: float | None = None
    segment_deviations: dict[str, float] = field(default_factory=dict)
    measurements: dict[TechnicalError, ErrorMeasurement] = field(default_factory=dict)

    @property
    def is_evaluable(self) -> bool:
        # Indica si el fotograma ha producido una puntuación.

        return self.score is not None

    @property
    def severities(self) -> dict[TechnicalError, float]:
        # Severidades de los parámetros medidos, para el selector de errores.

        return {
            error: measurement.severity
            for error, measurement in self.measurements.items()
        }


class AlignmentAnalyzer:
    # Mide la alineación corporal y los parámetros posturales del fotograma.

    def __init__(
        self,
        thresholds: AlignmentThresholds,
        view_mode: ViewMode,
        *,
        min_visibility: float = 0.5,
    ) -> None:
        # Los umbrales son obligatorios y proceden de la configuración externa.
        self._t = thresholds
        self._view_mode = view_mode
        self._min_visibility = min_visibility

    @property
    def thresholds(self) -> AlignmentThresholds:
        # Umbrales en uso.

        return self._t

    @property
    def view_mode(self) -> ViewMode:
        # Vista desde la que se está analizando.

        return self._view_mode

    def set_thresholds(self, thresholds: AlignmentThresholds) -> None:
        # Sustituye los umbrales por los personalizados de un atleta calibrado.
 
        self._t = thresholds

    def set_view_mode(self, view_mode: ViewMode) -> None:
        # Cambia la vista, y con ella los parámetros evaluables (BR-04).

        self._view_mode = view_mode

    def analyze(self, landmark_result: LandmarkResult) -> AlignmentReport:
        # Evalúa la alineación del fotograma actual.

        joints = joint_points(landmark_result, self._min_visibility)
        deviations = self._compute_deviations(joints)

        if not _REQUIRED_SEGMENTS.issubset(deviations):
            return AlignmentReport()

        trunk_length = distance(joints["shoulders"], joints["hips"])
        if trunk_length < self._t.min_trunk_length:
            return AlignmentReport()

        penalty = self._compute_segment_penalty(deviations)
        score = round(max(0.0, 100.0 - penalty), 1)

        measurements = self._measure_parameters(
            landmark_result, joints, trunk_length
        )

        return AlignmentReport(
            score=score,
            segment_deviations=deviations,
            measurements=measurements,
        )


    def _compute_deviations(self, joints: dict[str, Point]) -> dict[str, float]:
        # Desviación respecto a la vertical de cada línea medible.

        deviations: dict[str, float] = {}

        for segment, (top, bottom) in _SEGMENTS.items():
            if top in joints and bottom in joints:
                deviations[segment] = deviation_from_vertical(
                    joints[top], joints[bottom]
                )

        return deviations

    def _compute_segment_penalty(self, deviations: dict[str, float]) -> float:
        # Penalización media ponderada de las líneas medidas, de 0 a 100.

        weights = self._t.segment_weights
        noise = self._t.noise_threshold_deg
        maximum = self._t.max_segment_deviation_deg
        exponent = self._t.score_exponent

        weighted_penalty = 0.0
        total_weight = 0.0

        for segment in SEGMENT_NAMES:
            if segment not in deviations:
                continue

            weight = weights[segment]
            deviation = deviations[segment]

            if deviation <= noise:
                penalty = 0.0
            elif deviation >= maximum:
                penalty = 100.0
            else:
                ratio = (deviation - noise) / (maximum - noise)
                penalty = (ratio**exponent) * 100.0

            weighted_penalty += weight * penalty
            total_weight += weight

        if total_weight == 0.0:
            return 0.0

        return weighted_penalty / total_weight


    def _measure_parameters(
        self,
        landmark_result: LandmarkResult,
        joints: dict[str, Point],
        trunk_length: float,
    ) -> dict[TechnicalError, ErrorMeasurement]:
        # Mide los parámetros observables desde la vista activa.

        if self._view_mode is ViewMode.LATERAL:
            measurements = self._measure_sagittal(
                landmark_result, joints, trunk_length
            )
        else:
            measurements = self._measure_frontal(landmark_result)

        measurements.update(self._measure_common(landmark_result))

        return measurements


    def _measure_common(self, landmark_result: LandmarkResult) -> dict[TechnicalError, ErrorMeasurement]:
        # Parámetros observables desde cualquier perspectiva.

        measurements: dict[TechnicalError, ErrorMeasurement] = {}

        measurement = self._measure_chain_angle(
            landmark_result,
            _ELBOW_CHAINS,
            "elbow_bend",
            TechnicalError.ELBOW_NOT_EXTENDED,
        )
        if measurement is not None:
            measurements[TechnicalError.ELBOW_NOT_EXTENDED] = measurement

        return measurements

    def _measure_chain_angle(
        self,
        landmark_result: LandmarkResult,
        chains: tuple[tuple[int, int, int], ...],
        parameter: str,
        error: TechnicalError,
    ) -> ErrorMeasurement | None:
        # Desviación respecto a la línea recta del ángulo medido en el vértice de cada cadena, quedándose con la peor de ellas.

        worst: ErrorMeasurement | None = None

        for first_index, vertex_index, last_index in chains:
            first = self._visible(landmark_result, first_index)
            vertex = self._visible(landmark_result, vertex_index)
            last = self._visible(landmark_result, last_index)
            if first is None or vertex is None or last is None:
                continue

            angle = angle_at(
                as_point(vertex), as_point(first), as_point(last)
            )
            if angle is None:
                continue

            candidate = self._measurement(error, parameter, abs(180.0 - angle))
            if worst is None or candidate.severity > worst.severity:
                worst = candidate

        return worst


    def _measure_sagittal(
        self,
        landmark_result: LandmarkResult,
        joints: dict[str, Point],
        trunk_length: float,
    ) -> dict[TechnicalError, ErrorMeasurement]:
        # Parámetros observables de perfil.

        measurements: dict[TechnicalError, ErrorMeasurement] = {}

        for error, measurement in (
            (
                TechnicalError.FEET_NOT_EXTENDED,
                self._measure_chain_angle(
                    landmark_result,
                    _FOOT_CHAINS,
                    "foot_extension",
                    TechnicalError.FEET_NOT_EXTENDED,
                ),
            ),
            (TechnicalError.BACK_ARCH, self._measure_back_arch(joints)),
            (TechnicalError.PELVIS_POSITION, self._measure_pelvis_shift(joints, trunk_length)),
            (
                TechnicalError.HEAD_FORWARD,
                self._measure_head_forward(landmark_result, joints, trunk_length),
            ),
            (TechnicalError.LEGS_NOT_STRAIGHT, self._measure_legs(landmark_result)),
        ):
            if measurement is not None:
                measurements[error] = measurement

        return measurements

    def _measure_back_arch(self, joints: dict[str, Point]) -> ErrorMeasurement | None:
        # Arqueo dorsal: desviación del ángulo hombros-caderas-tobillos

        if "ankles" not in joints:
            return None

        angle = angle_at(joints["hips"], joints["shoulders"], joints["ankles"])
        if angle is None:
            return None

        return self._measurement(TechnicalError.BACK_ARCH, "back_arch", 180.0 - angle)

    def _measure_pelvis_shift(self, joints: dict[str, Point], trunk_length: float) -> ErrorMeasurement | None:
        # Desplazamiento pélvico: distancia de las caderas al eje que une hombros y rodillas, normalizada por la longitud del tronco.

        if "knees" not in joints:
            return None

        shift = distance_to_line(
            joints["hips"], joints["shoulders"], joints["knees"]
        )
        return self._measurement(
            TechnicalError.PELVIS_POSITION, "pelvis_shift", shift / trunk_length
        )

    def _measure_head_forward(
        self,
        landmark_result: LandmarkResult,
        joints: dict[str, Point],
        trunk_length: float,
    ) -> ErrorMeasurement | None:
        # Cabeza adelantada: separación horizontal entre la oreja y el hombro del mismo lado, normalizada por la longitud del tronco.
  
        candidates: list[tuple[float, float]] = []  # (visibilidad, separación)

        for ear_index, shoulder_index in (
            (IDX_LEFT_EAR, IDX_LEFT_SHOULDER),
            (IDX_RIGHT_EAR, IDX_RIGHT_SHOULDER),
        ):
            ear = self._visible(landmark_result, ear_index)
            shoulder = self._visible(landmark_result, shoulder_index)
            if ear is None or shoulder is None:
                continue
            candidates.append(
                (min(ear.visibility, shoulder.visibility), abs(ear.x - shoulder.x))
            )

        if not candidates:
            return None

        candidates.sort(reverse=True)
        separation = candidates[0][1]

        return self._measurement(
            TechnicalError.HEAD_FORWARD, "head_forward", separation / trunk_length
        )

    def _measure_legs(self, landmark_result: LandmarkResult) -> ErrorMeasurement | None:
        # Piernas no rectas. Combina la flexión de la rodilla y la pierna estirada pero desplazada.
    
        worst: ErrorMeasurement | None = None

        for hip_index, knee_index, ankle_index in (
            (IDX_LEFT_HIP, IDX_LEFT_KNEE, IDX_LEFT_ANKLE),
            (IDX_RIGHT_HIP, IDX_RIGHT_KNEE, IDX_RIGHT_ANKLE),
        ):
            hip = self._visible(landmark_result, hip_index)
            knee = self._visible(landmark_result, knee_index)
            ankle = self._visible(landmark_result, ankle_index)
            if hip is None or knee is None or ankle is None:
                continue

            hip_point = as_point(hip)
            knee_point = as_point(knee)
            ankle_point = as_point(ankle)

            candidates: list[ErrorMeasurement] = []

            angle = angle_at(knee_point, hip_point, ankle_point)
            if angle is not None:
                candidates.append(
                    self._measurement(
                        TechnicalError.LEGS_NOT_STRAIGHT,
                        "knee_bend",
                        abs(180.0 - angle),
                    )
                )

            candidates.append(
                self._measurement(
                    TechnicalError.LEGS_NOT_STRAIGHT,
                    "leg_tilt",
                    deviation_from_vertical(hip_point, ankle_point),
                )
            )

            for candidate in candidates:
                if worst is None or candidate.severity > worst.severity:
                    worst = candidate

        return worst


    def _measure_frontal(
        self, landmark_result: LandmarkResult
    ) -> dict[TechnicalError, ErrorMeasurement]:
        # Parámetros observables de frente.

        measurements: dict[TechnicalError, ErrorMeasurement] = {}

        shoulders = self._visible_pair(
            landmark_result, IDX_LEFT_SHOULDER, IDX_RIGHT_SHOULDER
        )
        if shoulders is not None:
            left, right = shoulders
            width = distance(as_point(left), as_point(right))
            if width >= self._t.min_pair_width:
                measurements.update(
                    self._measure_asymmetry(
                        left,
                        right,
                        "shoulder_tilt",
                        TechnicalError.LEFT_SHOULDER_LOW,
                        TechnicalError.RIGHT_SHOULDER_LOW,
                    )
                )
                shrug = self._measure_shrug(landmark_result, left, right, width)
                if shrug is not None:
                    measurements[TechnicalError.NO_SHRUG] = shrug

        hips = self._visible_pair(landmark_result, IDX_LEFT_HIP, IDX_RIGHT_HIP)
        if hips is not None:
            left, right = hips
            if distance(as_point(left), as_point(right)) >= self._t.min_pair_width:
                measurements.update(
                    self._measure_asymmetry(
                        left,
                        right,
                        "hip_tilt",
                        TechnicalError.LEFT_HIP_LOW,
                        TechnicalError.RIGHT_HIP_LOW,
                    )
                )

        return measurements

    def _measure_asymmetry(
        self,
        left: Landmark,
        right: Landmark,
        parameter: str,
        left_low: TechnicalError,
        right_low: TechnicalError,
    ) -> dict[TechnicalError, ErrorMeasurement]:
        # Asimetría de un par de puntos homólogos.

        tilt = deviation_from_horizontal(as_point(left), as_point(right))

        lower, higher = (
            (left_low, right_low) if left.y > right.y else (right_low, left_low)
        )

        measured = self._measurement(lower, parameter, tilt)

        return {
            lower: measured,
            higher: ErrorMeasurement(
                error_type=higher,
                measured_value=measured.measured_value,
                threshold_value=measured.threshold_value,
                severity=0.0,
            ),
        }

    def _measure_shrug(
        self,
        landmark_result: LandmarkResult,
        left_shoulder: Landmark,
        right_shoulder: Landmark,
        shoulder_width: float,
    ) -> ErrorMeasurement | None:
        # Falta de elevación escapular: distancia de cada oreja a su hombro, normalizada por la anchura de hombros.

        ratios: list[float] = []

        for ear_index, shoulder in (
            (IDX_LEFT_EAR, left_shoulder),
            (IDX_RIGHT_EAR, right_shoulder),
        ):
            ear = self._visible(landmark_result, ear_index)
            if ear is None:
                continue
            ratios.append(
                distance(as_point(ear), as_point(shoulder)) / shoulder_width
            )

        if not ratios:
            return None

        return self._measurement(
            TechnicalError.NO_SHRUG, "shrug", sum(ratios) / len(ratios)
        )

  
    def _measurement(self, error: TechnicalError, parameter: str, value: float) -> ErrorMeasurement:
        # Construye la medición de un parámetro a partir de su valor bruto.

        limits = self._t.parameters[parameter]
        return ErrorMeasurement(
            error_type=error,
            measured_value=round(value, 4),
            threshold_value=limits.threshold,
            severity=severity_from_metric(value, limits.threshold, limits.noise),
        )

    def _visible(self, landmark_result: LandmarkResult, index: int) -> Landmark | None:
        # Punto anatómico con visibilidad suficiente, o None.

        return visible(landmark_result, index, self._min_visibility)

    def _visible_pair(
        self, landmark_result: LandmarkResult, left_index: int, right_index: int
    ) -> tuple[Landmark, Landmark] | None:
        # Los dos puntos de un par homólogo, o None si falta alguno.

        return visible_pair(
            landmark_result, left_index, right_index, self._min_visibility
        )