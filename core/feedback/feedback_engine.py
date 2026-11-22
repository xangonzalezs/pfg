"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo del motor de selección y emisión del feedback correctivo.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.config.thresholds import FeedbackThresholds
from core.feedback.audio_player import AudioPlayer
from core.feedback.message_catalog import FeedbackMessage, MessageCatalog
from core.models.analysis_result import AnalysisResult, TechnicalError

# Orden global de emisión, único e independiente de la vista (4.5.2).
# Primero las asimetrías, por concretas; después la cadena corporal del apoyo
# hacia los pies; al final la inestabilidad, consecuencia del conjunto.
ERROR_PRIORITY: tuple[TechnicalError, ...] = (
    TechnicalError.LEFT_SHOULDER_LOW,
    TechnicalError.RIGHT_SHOULDER_LOW,
    TechnicalError.LEFT_HIP_LOW,
    TechnicalError.RIGHT_HIP_LOW,
    TechnicalError.ELBOW_NOT_EXTENDED,
    TechnicalError.HEAD_FORWARD,
    TechnicalError.NO_SHRUG,
    TechnicalError.BACK_ARCH,
    TechnicalError.PELVIS_POSITION,
    TechnicalError.LEGS_NOT_STRAIGHT,
    TechnicalError.FEET_NOT_EXTENDED,
    TechnicalError.INSTABILITY,
)


class FeedbackPriorityError(Exception):
    # El orden de emisión no se corresponde con los errores definidos.

    pass


def _check_priority_covers_every_error() -> None:

    missing = [error.name for error in TechnicalError if error not in ERROR_PRIORITY]
    if missing:
        raise FeedbackPriorityError(
            f"ERROR_PRIORITY no incluye: {', '.join(missing)}. Todo error técnico "
            f"debe ocupar una posición en el orden de emisión."
        )

    if len(ERROR_PRIORITY) != len(set(ERROR_PRIORITY)):
        raise FeedbackPriorityError("ERROR_PRIORITY contiene errores repetidos.")


_check_priority_covers_every_error()


@dataclass(frozen=True)
class FeedbackResult:
    # Resultado de procesar un fotograma: el mensaje emitido, si lo hubo.

    message: FeedbackMessage | None = None
    error: TechnicalError | None = None

    @property
    def emitted(self) -> bool:
        # Indica si se ha emitido un mensaje en este fotograma.

        return self.message is not None


NO_FEEDBACK = FeedbackResult()


class FeedbackEngine:
    # Decide qué desviación se comunica, cuándo y una sola vez.

    def __init__(
        self,
        catalog: MessageCatalog,
        player: AudioPlayer,
        thresholds: FeedbackThresholds,
    ) -> None:
        self._catalog = catalog
        self._player = player
        self._thresholds = thresholds


        self._frames: dict[TechnicalError, int] = {}
        self._absent: dict[TechnicalError, int] = {}
        self._announced: dict[TechnicalError, bool] = {}
        self._last_emitted_ms: dict[TechnicalError, int] = {}
        self._last_not_analyzing_ms: int | None = None

    def process(self, result: AnalysisResult, timestamp_ms: int) -> FeedbackResult:
        # Evalúa un fotograma y emite un mensaje si procede.
        # La marca es la del fotograma y no la del reloj del equipo.

        if not result.in_handstand:
            self._clear_tracking()
            return NO_FEEDBACK

        active = {error.error_type for error in result.active_errors}
        self._update_tracking(active)

        if not result.is_valid:
            return self._emit_not_analyzing(timestamp_ms)

        selected = self._select(active)
        if selected is None:
            return NO_FEEDBACK

        if not self._should_emit(selected, timestamp_ms):
            return NO_FEEDBACK

        if self._player.is_playing:
            return NO_FEEDBACK

        return self._emit(selected, timestamp_ms)

    def notify_hold_ended(self, mean_score: float) -> FeedbackResult:
        # Emite el refuerzo al concluir una fase de mantenimiento suficiente.

        if mean_score < self._thresholds.positive_score_threshold:
            return NO_FEEDBACK
        if self._player.is_playing:
            return NO_FEEDBACK

        message = self._catalog.positive
        self._player.play(message.audio_filename)
        return FeedbackResult(message=message)

    def reset(self) -> None:
        # Reinicia el estado del motor al comenzar una sesión.

        self._clear_tracking()
        self._last_emitted_ms.clear()
        self._last_not_analyzing_ms = None


    def _clear_tracking(self) -> None:
        # Olvida la persistencia acumulada, no las emisiones ya realizadas.

        self._frames.clear()
        self._absent.clear()
        self._announced.clear()

    def _update_tracking(self, active: set[TechnicalError]) -> None:
        # Lleva la cuenta de la persistencia de cada error.

        for error in active:
            self._frames[error] = self._frames.get(error, 0) + 1
            self._absent[error] = 0

        for error in list(self._frames):
            if error in active:
                continue
            self._absent[error] = self._absent.get(error, 0) + 1
            if self._absent[error] > self._thresholds.grace_frames:
                # Agotada la tolerancia, el error se considera resuelto y puede volver a a anunciarse.
                self._frames[error] = 0
                self._announced[error] = False

    def _select(self, active: set[TechnicalError]) -> TechnicalError | None:
        # Error de mayor prioridad entre los que ya están confirmados.

        for error in ERROR_PRIORITY:
            if error not in active:
                continue
            if self._frames.get(error, 0) >= self._thresholds.confirmation_frames:
                return error
        return None

    def _should_emit(self, error: TechnicalError, timestamp_ms: int) -> bool:
        # Un error se dice una vez y se le deja al atleta tiempo de aplicarlo.

        if not self._announced.get(error, False):
            return True

        last = self._last_emitted_ms.get(error)
        if last is None:
            return True
        return timestamp_ms - last >= self._thresholds.repeat_cooldown_ms

    def _emit(self, error: TechnicalError, timestamp_ms: int) -> FeedbackResult:
        # Reproduce la corrección y anota que ya se ha dicho.

        self._announced[error] = True
        self._last_emitted_ms[error] = timestamp_ms

        message = self._catalog.for_error(error)
        self._player.play(message.audio_filename)
        return FeedbackResult(message=message, error=error)

    def _emit_not_analyzing(self, timestamp_ms: int) -> FeedbackResult:
        # Avisa de que la postura no se está evaluando.

        last = self._last_not_analyzing_ms
        if last is not None:
            if timestamp_ms - last < self._thresholds.not_analyzing_cooldown_ms:
                return NO_FEEDBACK

        if self._player.is_playing:
            return NO_FEEDBACK

        self._last_not_analyzing_ms = timestamp_ms
        message = self._catalog.not_analyzing
        self._player.play(message.audio_filename)
        return FeedbackResult(message=message)