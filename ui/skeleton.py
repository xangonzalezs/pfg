"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de superposición del esqueleto detectado sobre el fotograma.
"""

from __future__ import annotations

import cv2
import numpy as np

from core.analysis import landmarks as lm
from core.models.landmark_result import LandmarkResult
from ui.frames import mirror
from ui.theme import bgr_for_score

# Visibilidad por debajo de la cual un punto no se dibuja.
MIN_VISIBILITY = lm.DEFAULT_MIN_VISIBILITY

LINE_THICKNESS = 3
JOINT_RADIUS = 4

# Segmentos del esqueleto según índices de MediaPipe.
CONNECTIONS: tuple[tuple[int, int], ...] = (
    # Brazos, del apoyo al hombro.
    (lm.IDX_LEFT_WRIST, lm.IDX_LEFT_ELBOW),
    (lm.IDX_LEFT_ELBOW, lm.IDX_LEFT_SHOULDER),
    (lm.IDX_RIGHT_WRIST, lm.IDX_RIGHT_ELBOW),
    (lm.IDX_RIGHT_ELBOW, lm.IDX_RIGHT_SHOULDER),
    # Cintura escapular y pélvica.
    (lm.IDX_LEFT_SHOULDER, lm.IDX_RIGHT_SHOULDER),
    (lm.IDX_LEFT_HIP, lm.IDX_RIGHT_HIP),
    # Tronco.
    (lm.IDX_LEFT_SHOULDER, lm.IDX_LEFT_HIP),
    (lm.IDX_RIGHT_SHOULDER, lm.IDX_RIGHT_HIP),
    # Piernas, de la cadera a la punta del pie.
    (lm.IDX_LEFT_HIP, lm.IDX_LEFT_KNEE),
    (lm.IDX_LEFT_KNEE, lm.IDX_LEFT_ANKLE),
    (lm.IDX_LEFT_ANKLE, lm.IDX_LEFT_FOOT_INDEX),
    (lm.IDX_RIGHT_HIP, lm.IDX_RIGHT_KNEE),
    (lm.IDX_RIGHT_KNEE, lm.IDX_RIGHT_ANKLE),
    (lm.IDX_RIGHT_ANKLE, lm.IDX_RIGHT_FOOT_INDEX),
)


def draw_skeleton(
    frame: np.ndarray,
    landmark_result: LandmarkResult,
    score: float | None = None,
    *,
    min_visibility: float = MIN_VISIBILITY,
) -> np.ndarray:
    # Devuelve una copia del fotograma con el esqueleto superpuesto.

    canvas = frame.copy()
    if not landmark_result.landmarks:
        return canvas

    height, width = canvas.shape[:2]
    color = bgr_for_score(score)
    points = _pixel_points(landmark_result, width, height, min_visibility)

    for start, end in CONNECTIONS:
        if start in points and end in points:
            cv2.line(canvas, points[start], points[end], color, LINE_THICKNESS)

    for point in points.values():
        cv2.circle(canvas, point, JOINT_RADIUS, color, -1)

    return canvas

def overlay(
    frame: np.ndarray,
    landmark_result: LandmarkResult,
    score: float | None = None,
    *,
    mirrored: bool = False,
) -> np.ndarray:
    # Devuelve una copia del fotograma con el esqueleto superpuesto.

    canvas = draw_skeleton(frame, landmark_result, score)
    return mirror(canvas) if mirrored else canvas


def _pixel_points(
    landmark_result: LandmarkResult,
    width: int,
    height: int,
    min_visibility: float,
) -> dict[int, tuple[int, int]]:
    # Traduce los puntos visibles a coordenadas de píxel.

    points: dict[int, tuple[int, int]] = {}
    for point in landmark_result.landmarks:
        if point.visibility < min_visibility:
            continue
        x = int(round(point.x * width))
        y = int(round(point.y * height))
        if 0 <= x < width and 0 <= y < height:
            points[point.index] = (x, y)
    return points