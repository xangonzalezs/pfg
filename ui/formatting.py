"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de formateo de los valores que muestra la interfaz.
"""

from __future__ import annotations

from datetime import datetime

NOT_AVAILABLE = "—"


def duration(seconds: float | None) -> str:
    # Duración legible: segundos hasta el minuto, y minutos y segundos a partir de ahí.

    if seconds is None or seconds < 0:
        return NOT_AVAILABLE

    total = int(round(seconds))
    if total < 60:
        return f"{total} s"

    minutes, remainder = divmod(total, 60)
    if remainder == 0:
        return f"{minutes} min"
    return f"{minutes} min {remainder} s"


def score(value: float | None) -> str:
    # Puntuación con un decimal o un guion si no hubo postura evaluable.
    if value is None:
        return NOT_AVAILABLE
    return f"{value:.1f}"


def percentage(part: float, whole: float) -> str:
    # Proporción en tanto por ciento, sin decimales.

    if whole <= 0:
        return NOT_AVAILABLE
    return f"{round(100.0 * part / whole)} %"


def timestamp(iso_value: str | None) -> str:
    # Marca ISO-8601 en hora local y formato legible.
    # Las marcas se persisten en UTC.

    moment = parse_timestamp(iso_value)
    if moment is None:
        return NOT_AVAILABLE
    return moment.astimezone().strftime("%d/%m/%Y %H:%M")


def day(iso_value: str | None) -> str:
    # Solo la fecha, para agrupar sesiones en el histórico.

    moment = parse_timestamp(iso_value)
    if moment is None:
        return NOT_AVAILABLE
    return moment.astimezone().strftime("%d/%m/%Y")


def parse_timestamp(iso_value: str | None) -> datetime | None:
    # Convierte una marca persistida, o None si no es legible.

    if not iso_value:
        return None
    try:
        return datetime.fromisoformat(iso_value)
    except (TypeError, ValueError):
        return None