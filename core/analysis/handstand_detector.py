"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de detección de la posición invertida.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.analysis.geometry import Point, deviation_from_vertical, distance
from core.analysis.landmarks import joint_point
from core.config.thresholds import HandstandThresholds
from core.models.landmark_result import LandmarkResult

# Cadena corporal del cuerpo invertido, de las manos hacia los pies. En la imagen cada eslabón queda sobre el anterior.
_CHAIN: tuple[str, ...] = ("wrists", "shoulders", "hips", "ankles")

# Articulación que sustituye a los tobillos cuando los pies salen del encuadre. Acorta la cadena sin alterar su sentido.
_ANKLES_FALLBACK = "knees"


@dataclass(frozen=True)
class HandstandState:
    # Estado de la detección tras procesar un fotograma.

    is_inverted: bool
    in_handstand: bool
    body_length: float | None = None
    tilt_deg: float | None = None
    confirming_frames: int = 0

    @property
    def is_confirming(self) -> bool:
        # Indica si hay una inversión en curso aún sin confirmar.

        return self.is_inverted and not self.in_handstand


class HandstandDetector:
    # Reconoce y sostiene el estado de pino a lo largo de la sesión.

    def __init__(
        self,
        thresholds: HandstandThresholds,
        *,
        min_visibility: float = 0.5,
    ) -> None:
        # Los umbrales son obligatorios y proceden de la configuración externa (NFR-13).

        self._t = thresholds
        self._min_visibility = min_visibility
        self._confirmed = False
        self._inverted_frames = 0
        self._missing_frames = 0

    @property
    def in_handstand(self) -> bool:
        # Indica si el pino está confirmado.

        return self._confirmed

    def reset(self) -> None:
        # Olvida el estado acumulado.

        self._confirmed = False
        self._inverted_frames = 0
        self._missing_frames = 0

    def update(self, landmark_result: LandmarkResult) -> HandstandState:
        # Procesa un fotograma y actualiza el estado de la detección.

        chain, body_length, tilt = self._measure(landmark_result)
        is_inverted = self._is_inverted(chain, body_length, tilt)

        self._advance(is_inverted)

        return HandstandState(
            is_inverted=is_inverted,
            in_handstand=self._confirmed,
            body_length=body_length,
            tilt_deg=tilt,
            confirming_frames=self._inverted_frames,
        )

    def _measure(
        self, landmark_result: LandmarkResult
    ) -> tuple[dict[str, Point] | None, float | None, float | None]:
        # Obtiene la cadena corporal, su longitud y su inclinación.
        # La cadena es None si falta algún eslabón. el orden vertical no puede comprobarse con huecos.
 
        chain: dict[str, Point] = {}

        for joint in _CHAIN:
            point = joint_point(landmark_result, joint, self._min_visibility)
            if point is None and joint == "ankles":
                point = joint_point(
                    landmark_result, _ANKLES_FALLBACK, self._min_visibility
                )
            if point is None:
                return None, None, None
            chain[joint] = point

        body_length = distance(chain["wrists"], chain[_CHAIN[-1]])
        tilt = deviation_from_vertical(chain[_CHAIN[-1]], chain["wrists"])

        return chain, body_length, tilt

    def _is_inverted(
        self,
        chain: dict[str, Point] | None,
        body_length: float | None,
        tilt: float | None,
    ) -> bool:
        # Comprueba las tres condiciones geométricas del fotograma.

        if chain is None or body_length is None or tilt is None:
            return False

        if body_length < self._t.min_body_length:
            return False

        if tilt > self._t.max_tilt_deg:
            return False

        return self._is_ordered(chain)

    def _is_ordered(self, chain: dict[str, Point]) -> bool:
        # Verifica que cada eslabón queda por encima del anterior.

        margin = self._t.order_margin

        for lower, upper in zip(_CHAIN, _CHAIN[1:]):
            if chain[lower][1] <= chain[upper][1] + margin:
                return False

        return True

    # --- Confirmación y tolerancia ----------------------------------------

    def _advance(self, is_inverted: bool) -> None:
        # Aplica la confirmación por persistencia y la tolerancia a pérdidas.
        # Ambas ventanas van en fotogramas (NFR-24), así que un archivo de vídeo se interpreta igual que la cámara.

        if is_inverted:
            self._missing_frames = 0
            if self._confirmed:
                return
            self._inverted_frames += 1
            if self._inverted_frames >= self._t.confirmation_frames:
                self._confirmed = True
            return

        self._inverted_frames = 0

        if not self._confirmed:
            return

        self._missing_frames += 1
        if self._missing_frames > self._t.grace_frames:
            self._confirmed = False
            self._missing_frames = 0