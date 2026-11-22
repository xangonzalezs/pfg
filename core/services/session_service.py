"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo del servicio que coordina una sesión de práctica fotograma a fotograma.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

from core.analysis.handstand_analyzer import HandstandAnalyzer
from core.feedback.feedback_engine import NO_FEEDBACK, FeedbackEngine, FeedbackResult
from core.models.analysis_result import AnalysisResult, TechnicalError
from core.models.calibration_status import ThresholdsApplied
from core.models.landmark_result import LandmarkResult
from core.models.view_mode import ViewMode
from core.persistence.session_repository import ErrorOccurrence, SessionRepository

# Puntos visibles exigidos para considerar al atleta encuadrado.
MIN_VISIBLE_LANDMARKS = 10

# Reentradas dentro de esta ventana continúan el intento en curso en lugar de contar como uno nuevo. 
# Va en milisegundos porque mide movimiento del atleta.
REENTRY_WINDOW_MS = 1500

# Fallos consecutivos del estimador tras los que la sesión se da por perdida.
MAX_CONSECUTIVE_FAILURES = 30


class SessionState(Enum):
    # Ciclo de vida de una sesión.

    IDLE = auto()
    # La fuente está activa pero la sesión no ha empezado. se comprueba el encuadre del atleta.
    PREPARING = auto()
    ACTIVE = auto()
    FINISHED = auto()
    # Terminó por un fallo de la fuente.
    FAILED = auto()


@dataclass(frozen=True)
class FrameOutcome:
    # Resultado de un fotograma, que es lo que la interfaz consume.

    landmark_result: LandmarkResult
    analysis: AnalysisResult
    feedback: FeedbackResult = NO_FEEDBACK
    hold_time_s: float = 0.0
    total_hold_time_s: float = 0.0
    is_framed: bool = False


@dataclass
class SessionMetrics:
    # Métricas que se acumulan a lo largo de la sesión.

    total_hold_ms: int = 0
    hold_attempts: int = 0
    scores: list[float] = field(default_factory=list)
    occurrences: list[ErrorOccurrence] = field(default_factory=list)

    @property
    def mean_score(self) -> float | None:
        # Puntuación media, o None si no hubo ninguna postura evaluable.

        if not self.scores:
            return None
        return sum(self.scores) / len(self.scores)


class SessionService:
    # Coordina análisis, feedback y registro de una sesión.

    def __init__(
        self,
        analyzer: HandstandAnalyzer,
        feedback: FeedbackEngine,
        sessions: SessionRepository,
        *,
        view_mode: ViewMode,
        thresholds_applied: ThresholdsApplied,
        user_id: int,
    ) -> None:
        self._analyzer = analyzer
        self._feedback = feedback
        self._sessions = sessions
        self._view_mode = view_mode
        self._thresholds_applied = thresholds_applied
        self._user_id = user_id

        self._state = SessionState.IDLE
        self._metrics = SessionMetrics()

        # Marcas de la sesión, todas tomadas de los fotogramas.
        self._first_ms: int | None = None
        self._last_ms: int | None = None
        self._hold_start_ms: int | None = None
        self._last_hold_end_ms: int | None = None

        # Errores activos en el fotograma anterior.
        self._previous_errors: set[TechnicalError] = set()
        # Puntuaciones de la fase en curso, que son las que deciden el refuerzo.
        self._phase_scores: list[float] = []
        self._failures = 0

    @property
    def state(self) -> SessionState:
        # Estado del ciclo de vida.

        return self._state

    @property
    def metrics(self) -> SessionMetrics:
        # Métricas acumuladas hasta el último fotograma procesado.

        return self._metrics

    @property
    def view_mode(self) -> ViewMode:
        # Vista que rige toda la sesión..

        return self._view_mode

    def prepare(self) -> None:
        # Entra en comprobación de encuadre, antes de empezar a registrar.

        self._state = SessionState.PREPARING

    def start(self) -> None:
        # Comienza la sesión. A partir de aquí se acumulan métricas.

        self._state = SessionState.ACTIVE
        self._feedback.reset()

    def process(self, landmark_result: LandmarkResult) -> FrameOutcome:
        # Procesa un fotograma ya estimado y devuelve lo que la interfaz pinta.

        if self._state is SessionState.PREPARING:
            return self._prepare_frame(landmark_result)
        if self._state is not SessionState.ACTIVE:
            return FrameOutcome(
                landmark_result=landmark_result, analysis=AnalysisResult()
            )

        timestamp_ms = landmark_result.timestamp_ms
        self._mark_time(timestamp_ms)

        analysis = self._analyzer.analyze(landmark_result)
        hold_ms = self._update_hold_phase(analysis, timestamp_ms)
        self._accumulate(analysis, timestamp_ms)
        feedback = self._feedback.process(analysis, timestamp_ms)

        return FrameOutcome(
            landmark_result=landmark_result,
            analysis=analysis,
            feedback=feedback,
            hold_time_s=hold_ms / 1000.0,
            total_hold_time_s=self._metrics.total_hold_ms / 1000.0,
            is_framed=True,
        )

    def note_failure(self) -> bool:
        # Registra un fallo del estimador y dice si la sesión puede continuar.

        self._failures += 1
        if self._failures >= MAX_CONSECUTIVE_FAILURES:
            self._state = SessionState.FAILED
            return False
        return True

    def finish(self, *, failed: bool = False) -> int | None:
        # Cierra la sesión y la registra.
        if self._state is SessionState.ACTIVE:
            self._close_hold_phase(self._last_ms)

        self._state = SessionState.FAILED if failed else SessionState.FINISHED

        if self._first_ms is None or self._last_ms is None:
            return None

        record = self._sessions.save(
            self._user_id,
            total_duration_s=(self._last_ms - self._first_ms) / 1000.0,
            total_hold_time_s=self._metrics.total_hold_ms / 1000.0,
            hold_attempts=self._metrics.hold_attempts,
            view_mode=self._view_mode,
            thresholds_applied=self._thresholds_applied,
            mean_alignment_score=self._metrics.mean_score,
            errors=self._metrics.occurrences,
        )
        return record.session_id


    def _prepare_frame(self, landmark_result: LandmarkResult) -> FrameOutcome:
        # En preparación solo se comprueba que el atleta esté en el encuadre.

        visible = sum(
            1 for point in landmark_result.landmarks if point.visibility >= 0.5
        )
        return FrameOutcome(
            landmark_result=landmark_result,
            analysis=AnalysisResult(),
            is_framed=visible >= MIN_VISIBLE_LANDMARKS,
        )

    def _mark_time(self, timestamp_ms: int) -> None:
        # La duración de la sesión es la que abarcan sus fotogramas.

        if self._first_ms is None:
            self._first_ms = timestamp_ms
        self._last_ms = timestamp_ms
        self._failures = 0

    def _update_hold_phase(self, analysis: AnalysisResult, timestamp_ms: int) -> int:
        # Detecta la entrada y la salida de la fase de mantenimiento.

        if analysis.in_handstand and self._hold_start_ms is None:
            if not self._is_reentry(timestamp_ms):
                self._metrics.hold_attempts += 1
                self._phase_scores = []
            self._hold_start_ms = timestamp_ms

        elif not analysis.in_handstand and self._hold_start_ms is not None:
            self._last_hold_end_ms = timestamp_ms
            self._close_hold_phase(timestamp_ms)

        if self._hold_start_ms is None:
            return 0
        return timestamp_ms - self._hold_start_ms

    def _is_reentry(self, timestamp_ms: int) -> bool:
        # Una salida muy breve continúa el intento en lugar de abrir otro.

        if self._last_hold_end_ms is None:
            return False
        return timestamp_ms - self._last_hold_end_ms < REENTRY_WINDOW_MS

    def _close_hold_phase(self, timestamp_ms: int | None) -> None:
        # Suma la duración de la fase y decide el refuerzo.

        if self._hold_start_ms is None or timestamp_ms is None:
            return

        self._metrics.total_hold_ms += timestamp_ms - self._hold_start_ms
        self._hold_start_ms = None

        # El refuerzo valora la fase que acaba de terminar, no la sesión entera.
        if self._phase_scores:
            mean = sum(self._phase_scores) / len(self._phase_scores)
            self._feedback.notify_hold_ended(mean)
        self._phase_scores = []

    def _accumulate(self, analysis: AnalysisResult, timestamp_ms: int) -> None:
        # Acumula puntuaciones y registra las ocurrencias de error.

        if analysis.in_handstand and analysis.alignment_score is not None:
            self._metrics.scores.append(analysis.alignment_score)
            self._phase_scores.append(analysis.alignment_score)

        current = {error.error_type for error in analysis.active_errors}
        origin_ms = self._first_ms if self._first_ms is not None else timestamp_ms
        offset_s = (timestamp_ms - origin_ms) / 1000.0

        # Se registra una fila por activación y no una por fotograma.
        for error in analysis.active_errors:
            if error.error_type in self._previous_errors:
                continue
            self._metrics.occurrences.append(
                ErrorOccurrence(
                    error_type=error.error_type,
                    measured_value=error.measured_value,
                    threshold_value=error.threshold_value,
                    offset_s=offset_s,
                )
            )

        self._previous_errors = current