"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de acceso a los puntos anatómicos estimados sobre el fotograma.
"""

from __future__ import annotations

from core.analysis.geometry import Point, midpoint
from core.models.landmark_result import Landmark, LandmarkResult

# Índices de los puntos anatómicos según la convención de MediaPipe Pose.
IDX_LEFT_EAR = 7
IDX_RIGHT_EAR = 8
IDX_LEFT_SHOULDER = 11
IDX_RIGHT_SHOULDER = 12
IDX_LEFT_ELBOW = 13
IDX_RIGHT_ELBOW = 14
IDX_LEFT_WRIST = 15
IDX_RIGHT_WRIST = 16
IDX_LEFT_HIP = 23
IDX_RIGHT_HIP = 24
IDX_LEFT_KNEE = 25
IDX_RIGHT_KNEE = 26
IDX_LEFT_ANKLE = 27
IDX_RIGHT_ANKLE = 28
IDX_LEFT_FOOT_INDEX = 31
IDX_RIGHT_FOOT_INDEX = 32

# Visibilidad mínima exigida a un punto antes de utilizarlo.
DEFAULT_MIN_VISIBILITY = 0.5

# Articulaciones de las que se obtiene un punto medio, de las manos a los pies.
JOINT_PAIRS: dict[str, tuple[int, int]] = {
    "wrists": (IDX_LEFT_WRIST, IDX_RIGHT_WRIST),
    "shoulders": (IDX_LEFT_SHOULDER, IDX_RIGHT_SHOULDER),
    "hips": (IDX_LEFT_HIP, IDX_RIGHT_HIP),
    "knees": (IDX_LEFT_KNEE, IDX_RIGHT_KNEE),
    "ankles": (IDX_LEFT_ANKLE, IDX_RIGHT_ANKLE),
}


def as_point(landmark: Landmark) -> Point:
    # Coordenadas de un punto anatómico, sin el resto de sus atributos.

    return (landmark.x, landmark.y)


def visible(
    landmark_result: LandmarkResult,
    index: int,
    min_visibility: float = DEFAULT_MIN_VISIBILITY,
) -> Landmark | None:
    # Punto anatómico con visibilidad suficiente, o None.

    landmark = landmark_result.get_landmark(index)
    if landmark is None or landmark.visibility < min_visibility:
        return None
    return landmark


def visible_pair(
    landmark_result: LandmarkResult,
    left_index: int,
    right_index: int,
    min_visibility: float = DEFAULT_MIN_VISIBILITY,
) -> tuple[Landmark, Landmark] | None:
    # Los dos puntos de un par homólogo, o None si falta alguno.

    left = visible(landmark_result, left_index, min_visibility)
    right = visible(landmark_result, right_index, min_visibility)
    if left is None or right is None:
        return None
    return left, right


def joint_point(
    landmark_result: LandmarkResult,
    joint: str,
    min_visibility: float = DEFAULT_MIN_VISIBILITY,
) -> Point | None:
    # Punto medio de una articulación, o None si no hay ningún lado visible.
    # Con un solo lado visible se emplea ese lado. Vista lateral.

    left_index, right_index = JOINT_PAIRS[joint]
    left = visible(landmark_result, left_index, min_visibility)
    right = visible(landmark_result, right_index, min_visibility)

    if left is not None and right is not None:
        return midpoint(as_point(left), as_point(right))
    if left is not None:
        return as_point(left)
    if right is not None:
        return as_point(right)
    return None


def joint_points(
    landmark_result: LandmarkResult,
    min_visibility: float = DEFAULT_MIN_VISIBILITY,
) -> dict[str, Point]:
    # Punto medio de cada articulación disponible en el fotograma.

    points: dict[str, Point] = {}
    for joint in JOINT_PAIRS:
        point = joint_point(landmark_result, joint, min_visibility)
        if point is not None:
            points[joint] = point
    return points