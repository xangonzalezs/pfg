"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de operaciones geométricas sobre coordenadas del plano de imagen.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

# Punto del plano de imagen en coordenadas normalizadas.
# origen en la esquina superior izquierda del fotograma. Y creciente hacia abajo.
Point = tuple[float, float]


def midpoint(a: Point, b: Point) -> Point:
    # Punto medio del segmento que une a y b.

    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def centroid(points: Sequence[Point]) -> Point:
    # Centro geométrico de un conjunto de puntos.

    if not points:
        raise ValueError("El centroide de un conjunto vacío de puntos no existe.")

    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )


def distance(a: Point, b: Point) -> float:
    # Distancia euclídea entre dos puntos.

    return math.hypot(b[0] - a[0], b[1] - a[1])


def angle_at(vertex: Point, a: Point, b: Point) -> float | None:
    # Ángulo formado en el vértice entre los segmentos que van hacia a y
    # hacia b, en grados y en el intervalo [0, 180].

    ax, ay = a[0] - vertex[0], a[1] - vertex[1]
    bx, by = b[0] - vertex[0], b[1] - vertex[1]

    mag_a = math.hypot(ax, ay)
    mag_b = math.hypot(bx, by)
    if mag_a == 0.0 or mag_b == 0.0:
        return None

    # Coseno del ángulo mediante el producto escalar normalizado. 
    cos_angle = max(-1.0, min(1.0, (ax * bx + ay * by) / (mag_a * mag_b)))

    return math.degrees(math.acos(cos_angle))


def deviation_from_vertical(top: Point, bottom: Point) -> float:
    # Desviación angular de un segmento respecto al eje vertical del
    # fotograma, en grados.

    dx = bottom[0] - top[0]
    dy = bottom[1] - top[1]

    length = math.hypot(dx, dy)
    if length == 0.0:
        return 0.0

    return math.degrees(math.asin(min(1.0, abs(dx) / length)))


def deviation_from_horizontal(a: Point, b: Point) -> float:
    # Desviación angular de un segmento respecto al eje horizontal del
    # fotograma, en grados.

    dx = b[0] - a[0]
    dy = b[1] - a[1]

    length = math.hypot(dx, dy)
    if length == 0.0:
        return 0.0

    return math.degrees(math.asin(min(1.0, abs(dy) / length)))


def distance_to_line(point: Point, start: Point, end: Point) -> float:
    # Distancia perpendicular de un punto a la recta que pasa por start y
    # end. 

    lx = end[0] - start[0]
    ly = end[1] - start[1]

    length = math.hypot(lx, ly)
    if length == 0.0:
        return distance(point, start)

    # Módulo del producto vectorial de los dos vectores que parten de start,
    # Doble del aárea del rectángulo.
    cross = abs(lx * (start[1] - point[1]) - ly * (start[0] - point[0]))

    return cross / length
