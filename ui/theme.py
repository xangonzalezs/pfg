"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de la paleta y correspondencia entre puntuación y color.
"""

from __future__ import annotations

from dataclasses import dataclass

# Identidad de la aplicación.
APP_NAME = "HandstandApp"
COLOR_BACKGROUND = "#1C2230"
COLOR_SURFACE = "#262E3F"
COLOR_TEXT = "#F3F5F8"
COLOR_TEXT_MUTED = "#8FA3BF"
COLOR_ACCENT = "#F5A524"

# Avisos persistentes de la pantalla de práctica.
COLOR_WARNING = "#F5A524"
COLOR_ERROR = "#E5484D"


@dataclass(frozen=True)
class ScoreBand:
    # Una de las cuatro bandas en que se reparte la puntuación.

    minimum: float
    label: str
    hex_color: str
    bgr: tuple[int, int, int]


# Cuatro bandas del verde al rojo.
SCORE_BANDS: tuple[ScoreBand, ...] = (
    ScoreBand(80.0, "Correcta", "#30A46C", (108, 164, 48)),
    ScoreBand(60.0, "Aceptable", "#9BBF2E", (46, 191, 155)),
    ScoreBand(40.0, "Mejorable", "#F5A524", (36, 165, 245)),
    ScoreBand(0.0, "Deficiente", "#E5484D", (77, 72, 229)),
)

# Color del esqueleto cuando no hay puntuación que representar.
COLOR_NO_SCORE_HEX = "#8FA3BF"
COLOR_NO_SCORE_BGR = (191, 163, 143)


def band_for_score(score: float | None) -> ScoreBand | None:
    # Banda que corresponde a una puntuación, o None si no hay puntuación.

    if score is None:
        return None

    value = max(0.0, min(100.0, float(score)))
    for band in SCORE_BANDS:
        if value >= band.minimum:
            return band
    return SCORE_BANDS[-1]


def color_for_score(score: float | None) -> str:
    # Color hexadecimal de una puntuación, para los widgets.

    band = band_for_score(score)
    return band.hex_color if band is not None else COLOR_NO_SCORE_HEX


def bgr_for_score(score: float | None) -> tuple[int, int, int]:
    # Color BGR de una puntuación, para dibujar sobre el fotograma.

    band = band_for_score(score)
    return band.bgr if band is not None else COLOR_NO_SCORE_BGR


def label_for_score(score: float | None) -> str:
    # Nombre de la banda, para que el color no sea el único portador de la información.

    band = band_for_score(score)
    return band.label if band is not None else "Sin evaluar"