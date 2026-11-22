"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de graduación de la severidad de las desviaciones y determinación de los errores activos en cada fotograma.
"""

from __future__ import annotations

from core.config.thresholds import ErrorSelectionThresholds
from core.models.analysis_result import TechnicalError
from core.models.view_mode import ViewMode

# Errores evaluables en cada modo de vista.
_RELEVANT_LATERAL: frozenset[TechnicalError] = frozenset(
    {
        TechnicalError.HEAD_FORWARD,
        TechnicalError.BACK_ARCH,
        TechnicalError.PELVIS_POSITION,
        TechnicalError.LEGS_NOT_STRAIGHT,
        TechnicalError.ELBOW_NOT_EXTENDED,
        TechnicalError.FEET_NOT_EXTENDED,
        TechnicalError.INSTABILITY,
    }
)

_RELEVANT_FRONTAL: frozenset[TechnicalError] = frozenset(
    {
        TechnicalError.NO_SHRUG,
        TechnicalError.LEFT_SHOULDER_LOW,
        TechnicalError.RIGHT_SHOULDER_LOW,
        TechnicalError.LEFT_HIP_LOW,
        TechnicalError.RIGHT_HIP_LOW,
        TechnicalError.ELBOW_NOT_EXTENDED,
        TechnicalError.INSTABILITY,
    }
)

# Pares causa-consecuencia. Cuando ambos están activos se conserva la causa y se descarta el síntoma.
_CONSEQUENCE_PAIRS: tuple[tuple[TechnicalError, TechnicalError], ...] = (
    (TechnicalError.PELVIS_POSITION, TechnicalError.BACK_ARCH),
)

# Pares mutuamente excluyentes.
_EXCLUSIVE_PAIRS: tuple[tuple[TechnicalError, TechnicalError], ...] = (
    (TechnicalError.LEFT_SHOULDER_LOW, TechnicalError.RIGHT_SHOULDER_LOW),
    (TechnicalError.LEFT_HIP_LOW, TechnicalError.RIGHT_HIP_LOW),
)

# Severidad en la que termina el tramo suave de la curva.
_MODERATE_SEVERITY = 60.0

# Fracción del intervalo útil que superado el umbral lleva la severidad de 60 a 100.
_SATURATION_FRACTION = 0.5


def severity_from_metric(value: float, threshold: float, noise: float) -> float:
    # Gradúa de 0 a 100 la gravedad de una desviación.

    interval = threshold - noise
    if interval <= 0.0:
        # Configuración degenerada: sin intervalo no hay nada que graduar.
        return 0.0 if value <= noise else 100.0

    if value <= noise:
        return 0.0

    if value <= threshold:
        return ((value - noise) / interval) * _MODERATE_SEVERITY

    excess = value - threshold
    saturation = interval * _SATURATION_FRACTION
    extra = min(
        100.0 - _MODERATE_SEVERITY,
        (excess / saturation) * (100.0 - _MODERATE_SEVERITY),
    )
    return _MODERATE_SEVERITY + extra


class ErrorSelector:
    # Determina el conjunto de errores activos de cada fotograma.

    def __init__(
        self,
        view_mode: ViewMode,
        thresholds: ErrorSelectionThresholds,
    ) -> None:
        self._view_mode = view_mode
        self._t = thresholds
        self._relevant = (
            _RELEVANT_FRONTAL if view_mode is ViewMode.FRONTAL else _RELEVANT_LATERAL
        )
        self._active: dict[TechnicalError, bool] = {
            error: False for error in self._relevant
        }

    @property
    def view_mode(self) -> ViewMode:
        # Vista para la que se ha configurado el selector.

        return self._view_mode

    @property
    def thresholds(self) -> ErrorSelectionThresholds:
        # Umbrales en uso.

        return self._t

    @property
    def relevant_errors(self) -> frozenset[TechnicalError]:
        # Errores evaluables en esta vista.

        return self._relevant

    def reset(self) -> None:
        # Olvida qué errores estaban activos.

        for error in self._active:
            self._active[error] = False

    def is_active(self, error: TechnicalError) -> bool:
        # Indica si un error está activo según la histéresis, antes de aplicar supresión de redundancias.

        return self._active.get(error, False)

    def select(self, severities: dict[TechnicalError, float]) -> list[TechnicalError]:
        # Devuelve los errores activos del fotograma, sin redundancias.

        self._update_activation(severities)

        active = {
            error: severities[error]
            for error, is_on in self._active.items()
            if is_on and error in severities
        }

        survivors = self._suppress_redundant(active)

        return [error for error in TechnicalError if error in survivors]

    def _update_activation(self, severities: dict[TechnicalError, float]) -> None:
        # Aplica la histéresis a cada error medido en este fotograma.

        minimum = self._t.min_severity_to_report
        deactivation = minimum * self._t.hysteresis_factor

        for error, severity in severities.items():
            if error not in self._active:
                continue

            if self._active[error]:
                if severity < deactivation:
                    self._active[error] = False
            elif severity >= minimum:
                self._active[error] = True

    def _suppress_redundant(
        self, active: dict[TechnicalError, float]
    ) -> set[TechnicalError]:
        # Descarta los errores que no aportan información frente a otro.

        survivors = set(active)

        for cause, consequence in _CONSEQUENCE_PAIRS:
            if cause in survivors and consequence in survivors:
                survivors.discard(consequence)

        for first, second in _EXCLUSIVE_PAIRS:
            if first in survivors and second in survivors:
                # Ante severidades iguales se conserva el primero del par para que el resultado sea determinista.
                discarded = (
                    second if active[first] >= active[second] else first
                )
                survivors.discard(discarded)

        return survivors