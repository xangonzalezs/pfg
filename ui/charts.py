"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de cálculo de las representaciones del resumen de sesión.
"""

from __future__ import annotations

from collections import Counter

from core.models.analysis_result import TechnicalError
from core.persistence.session_repository import ErrorOccurrence

# Escala fija de la evolución de la puntuación.
SCORE_MIN = 0.0
SCORE_MAX = 100.0


def score_polyline(
    scores: list[float],
    width: int,
    height: int,
    *,
    padding: int = 8,
) -> list[tuple[float, float]]:
    # Puntos de la línea de evolución de la puntuación dentro de un recuadro.
    # El eje vertical va de 0 a 100 y no del mínimo al máximo observados.

    if not scores or width <= 2 * padding or height <= 2 * padding:
        return []

    inner_w = width - 2 * padding
    inner_h = height - 2 * padding

    if len(scores) == 1:
        y = _y_for(scores[0], padding, inner_h)
        return [(padding, y), (padding + inner_w, y)]

    step = inner_w / (len(scores) - 1)
    return [
        (padding + index * step, _y_for(value, padding, inner_h))
        for index, value in enumerate(scores)
    ]


def _y_for(value: float, padding: int, inner_h: int) -> float:
    # Traduce una puntuación a una coordenada vertical, con el cero abajo.

    clamped = max(SCORE_MIN, min(SCORE_MAX, value))
    ratio = (clamped - SCORE_MIN) / (SCORE_MAX - SCORE_MIN)
    return padding + inner_h * (1.0 - ratio)


def error_counts(
    occurrences: list[ErrorOccurrence],
) -> list[tuple[TechnicalError, int]]:
    # Recuento de ocurrencias por tipo, de la más frecuente a la menos.

    counter = Counter(occurrence.error_type for occurrence in occurrences)
    order = {error: index for index, error in enumerate(TechnicalError)}
    return sorted(counter.items(), key=lambda item: (-item[1], order[item[0]]))


def top_errors(
    occurrences: list[ErrorOccurrence], limit: int = 3
) -> list[tuple[TechnicalError, int]]:
    # Los errores más frecuentes de una sesión.

    if limit < 1:
        return []
    return error_counts(occurrences)[:limit]


def bar_widths(
    counts: list[tuple[TechnicalError, int]], width: int
) -> list[tuple[TechnicalError, int, int]]:
    # Anchura de la barra de cada error, proporcional al más frecuente.

    if not counts or width <= 0:
        return []

    highest = max(count for _, count in counts)
    if highest <= 0:
        return [(error, count, 0) for error, count in counts]

    return [
        (error, count, max(1, round(width * count / highest)))
        for error, count in counts
    ]