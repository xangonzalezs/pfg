"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de medición de la postura neutra del atleta durante la calibración corporal.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from core.analysis.geometry import Point, angle_at, distance, midpoint
from core.analysis.landmarks import (
    IDX_LEFT_ANKLE,
    IDX_LEFT_ELBOW,
    IDX_LEFT_HIP,
    IDX_LEFT_KNEE,
    IDX_LEFT_SHOULDER,
    IDX_LEFT_WRIST,
    IDX_RIGHT_ANKLE,
    IDX_RIGHT_ELBOW,
    IDX_RIGHT_HIP,
    IDX_RIGHT_KNEE,
    IDX_RIGHT_SHOULDER,
    IDX_RIGHT_WRIST,
    as_point,
    visible,
)
from core.config.personalization import NeutralAngles
from core.config.thresholds import CalibrationThresholds
from core.models.landmark_result import Landmark, LandmarkResult
from core.models.view_mode import ViewMode

# Cadena de un lado del cuerpo necesaria para las medidas sagitales.
_LATERAL_SIDES: tuple[tuple[int, int, int, int], ...] = (
    (IDX_LEFT_SHOULDER, IDX_LEFT_HIP, IDX_LEFT_KNEE, IDX_LEFT_ANKLE),
    (IDX_RIGHT_SHOULDER, IDX_RIGHT_HIP, IDX_RIGHT_KNEE, IDX_RIGHT_ANKLE),
)

# Brazo del mismo lado, opcional: su ausencia no invalida la captura.
_LATERAL_ARMS: dict[int, tuple[int, int]] = {
    IDX_LEFT_SHOULDER: (IDX_LEFT_ELBOW, IDX_LEFT_WRIST),
    IDX_RIGHT_SHOULDER: (IDX_RIGHT_ELBOW, IDX_RIGHT_WRIST),
}

# De frente se miden longitudes, que exigen los dos lados visibles.
_FRONTAL_REQUIRED: tuple[int, ...] = (
    IDX_LEFT_SHOULDER,
    IDX_RIGHT_SHOULDER,
    IDX_LEFT_HIP,
    IDX_RIGHT_HIP,
    IDX_LEFT_KNEE,
    IDX_RIGHT_KNEE,
    IDX_LEFT_ANKLE,
    IDX_RIGHT_ANKLE,
)

# Longitud mínima del tronco en la imagen para que las proporciones sean fiables.
_MIN_TRUNK_LENGTH = 0.02


class CalibrationCaptureError(Exception):
    # La captura no cumple los criterios y debe repetirse.

    def __init__(self, view: ViewMode, summary: CaptureSummary) -> None:
        self.view = view
        self.summary = summary
        super().__init__(
            f"La captura {view.value} no es utilizable: "
            f"{summary.valid_frames} de {summary.total_frames} fotogramas válidos."
        )


@dataclass(frozen=True)
class CaptureSummary:
    # Calidad de una captura, que el entrenador consulta al validarla.

    total_frames: int
    valid_frames: int

    @property
    def validity_rate(self) -> float:
        # Proporción de fotogramas utilizables, de 0 a 1.

        if self.total_frames == 0:
            return 0.0
        return self.valid_frames / self.total_frames


@dataclass(frozen=True)
class NeutralPoseMeasurement:
    # Medidas extraídas de la postura neutra del atleta.
    # Un valor None significa que no pudo medirse, no que sea nulo.

    knee_deg: float | None = None
    back_arch_deg: float | None = None
    elbow_deg: float | None = None
    legs_trunk_ratio: float | None = None
    shoulder_width_ratio: float | None = None
    lateral: CaptureSummary = CaptureSummary(0, 0)
    frontal: CaptureSummary = CaptureSummary(0, 0)

    @property
    def neutral_angles(self) -> NeutralAngles:
        # Ángulos en la forma que espera la derivación de umbrales.

        return NeutralAngles(
            knee_deg=self.knee_deg,
            back_arch_deg=self.back_arch_deg,
            elbow_deg=self.elbow_deg,
        )


def is_frame_valid(
    landmark_result: LandmarkResult, view: ViewMode, thresholds: CalibrationThresholds
) -> bool:
    # Comprueba si un fotograma es utilizable para la captura indicada.

    if view is ViewMode.LATERAL:
        return _visible_side(landmark_result, thresholds) is not None
    return all(
        visible(landmark_result, index, thresholds.min_visibility) is not None
        for index in _FRONTAL_REQUIRED
    )


def measure_neutral_pose(
    lateral_frames: list[LandmarkResult],
    frontal_frames: list[LandmarkResult],
    thresholds: CalibrationThresholds,
) -> NeutralPoseMeasurement:
    # Reduce las dos capturas a las medidas de la postura neutra.

    lateral = _summarize(lateral_frames, ViewMode.LATERAL, thresholds)
    frontal = _summarize(frontal_frames, ViewMode.FRONTAL, thresholds)

    back_arch, knee, elbow = _measure_lateral(lateral_frames, thresholds)
    legs_trunk, shoulder_width = _measure_frontal(frontal_frames, thresholds)

    return NeutralPoseMeasurement(
        knee_deg=knee,
        back_arch_deg=back_arch,
        elbow_deg=elbow,
        legs_trunk_ratio=legs_trunk,
        shoulder_width_ratio=shoulder_width,
        lateral=lateral,
        frontal=frontal,
    )



def _summarize(
    frames: list[LandmarkResult], view: ViewMode, thresholds: CalibrationThresholds
) -> CaptureSummary:
    # Cuenta los fotogramas utilizables y rechaza la captura si no llegan.

    valid = sum(1 for frame in frames if is_frame_valid(frame, view, thresholds))
    summary = CaptureSummary(total_frames=len(frames), valid_frames=valid)

    if valid < thresholds.min_frames or summary.validity_rate < thresholds.min_validity_rate:
        raise CalibrationCaptureError(view, summary)

    return summary


def _visible_side(landmark_result: LandmarkResult, thresholds: CalibrationThresholds
) -> tuple[Landmark, Landmark, Landmark, Landmark] | None:
    # Lado del cuerpo con la cadena sagital completa y mejor visibilidad.
    # El brazo no interviene. su ausencia deja el codo sin medir, no invalida la captura.

    best: tuple[float, tuple[Landmark, ...]] | None = None

    for side in _LATERAL_SIDES:
        points = [visible(landmark_result, i, thresholds.min_visibility) for i in side]
        if any(point is None for point in points):
            continue
        quality = min(point.visibility for point in points)
        if best is None or quality > best[0]:
            best = (quality, tuple(points))

    if best is None:
        return None
    return best[1]



def _measure_lateral(frames: list[LandmarkResult], thresholds: CalibrationThresholds
) -> tuple[float | None, float | None, float | None]:
    # Arqueo dorsal, extensión de rodilla y extensión de codo.

    back_arch: list[float] = []
    knee: list[float] = []
    elbow: list[float] = []

    for frame in frames:
        side = _visible_side(frame, thresholds)
        if side is None:
            continue

        shoulder, hip, knee_point, ankle = side

        trunk = angle_at(as_point(hip), as_point(shoulder), as_point(ankle))
        if trunk is not None:
            back_arch.append(trunk)

        flexion = angle_at(as_point(knee_point), as_point(hip), as_point(ankle))
        if flexion is not None:
            knee.append(flexion)

        arm = _measure_elbow(frame, shoulder, thresholds)
        if arm is not None:
            elbow.append(arm)

    return _median(back_arch), _median(knee), _median(elbow)


def _measure_elbow(
    landmark_result: LandmarkResult,
    shoulder: Landmark,
    thresholds: CalibrationThresholds,
) -> float | None:
    # Ángulo hombro-codo-muñeca del mismo lado que la cadena elegida.

    elbow_index, wrist_index = _LATERAL_ARMS[shoulder.index]
    elbow = visible(landmark_result, elbow_index, thresholds.min_visibility)
    wrist = visible(landmark_result, wrist_index, thresholds.min_visibility)
    if elbow is None or wrist is None:
        return None

    return angle_at(as_point(elbow), as_point(shoulder), as_point(wrist))




def _measure_frontal(frames: list[LandmarkResult], thresholds: CalibrationThresholds
) -> tuple[float | None, float | None]:
    # Proporción entre la longitud de las piernas y la del tronco, y anchura de hombros relativa al tronco. 

    legs_trunk: list[float] = []
    shoulder_width: list[float] = []

    for frame in frames:
        points = {
            index: visible(frame, index, thresholds.min_visibility)
            for index in _FRONTAL_REQUIRED
        }
        if any(point is None for point in points.values()):
            continue

        def center(left: int, right: int) -> Point:
            return midpoint(as_point(points[left]), as_point(points[right]))

        shoulders = center(IDX_LEFT_SHOULDER, IDX_RIGHT_SHOULDER)
        hips = center(IDX_LEFT_HIP, IDX_RIGHT_HIP)
        trunk = distance(shoulders, hips)
        if trunk < _MIN_TRUNK_LENGTH:
            continue

        left_leg = distance(
            as_point(points[IDX_LEFT_HIP]), as_point(points[IDX_LEFT_KNEE])
        ) + distance(
            as_point(points[IDX_LEFT_KNEE]), as_point(points[IDX_LEFT_ANKLE])
        )
        right_leg = distance(
            as_point(points[IDX_RIGHT_HIP]), as_point(points[IDX_RIGHT_KNEE])
        ) + distance(
            as_point(points[IDX_RIGHT_KNEE]), as_point(points[IDX_RIGHT_ANKLE])
        )

        legs_trunk.append((left_leg + right_leg) / 2.0 / trunk)
        shoulder_width.append(
            distance(
                as_point(points[IDX_LEFT_SHOULDER]),
                as_point(points[IDX_RIGHT_SHOULDER]),
            )
            / trunk
        )

    return _median(legs_trunk), _median(shoulder_width)


def _median(values: list[float]) -> float | None:
    # Mediana de las medidas, o None si no se pudo medir ninguna.

    if not values:
        return None
    return statistics.median(values)