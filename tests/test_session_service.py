import pytest

from core.feedback.feedback_engine import NO_FEEDBACK
from core.models.analysis_result import AnalysisResult, DetectedError, TechnicalError
from core.models.calibration_status import ThresholdsApplied
from core.models.landmark_result import Landmark, LandmarkResult
from core.models.user_role import UserRole
from core.models.view_mode import ViewMode
from core.persistence.database import IN_MEMORY, Database
from core.persistence.password import MIN_ITERATIONS
from core.persistence.session_repository import SessionRepository
from core.persistence.user_repository import UserRepository
from core.services.session_service import (
    MAX_CONSECUTIVE_FAILURES,
    MIN_VISIBLE_LANDMARKS,
    REENTRY_WINDOW_MS,
    SessionService,
    SessionState,
)

MS = 33


class _AnalizadorGuionizado:
    # Devuelve un análisis prefijado por fotograma
    # De esta forma la prueba controla la secuencia sin depender de la capa de análisis.

    def __init__(self, guion):
        self._guion = list(guion)
        self._i = -1

    def analyze(self, landmark_result):
        self._i += 1
        return self._guion[min(self._i, len(self._guion) - 1)]


class _FeedbackFalso:
    def __init__(self):
        self.refuerzos: list[float] = []
        self.marcas: list[int] = []
        self.reiniciado = False

    def process(self, analysis, timestamp_ms):
        self.marcas.append(timestamp_ms)
        return NO_FEEDBACK

    def notify_hold_ended(self, mean_score):
        self.refuerzos.append(round(mean_score, 1))
        return NO_FEEDBACK

    def reset(self):
        self.reiniciado = True


@pytest.fixture
def entorno():
    db = Database(IN_MEMORY)
    db.open()
    users = UserRepository(db, iterations=MIN_ITERATIONS)
    atleta = users.create("atleta", "c", UserRole.ATHLETE, "Atleta")
    yield SessionRepository(db), atleta.user_id
    db.close()


def _error(tipo, medido=11.0, umbral=8.0):
    return DetectedError(
        error_type=tipo, measured_value=medido, threshold_value=umbral
    )


def _pino(score=75.0, *errores):
    return AnalysisResult(
        alignment_score=score,
        in_handstand=True,
        active_errors=[_error(e) for e in errores],
    )


FUERA = AnalysisResult(in_handstand=False)
SIN_EVALUAR = AnalysisResult(in_handstand=True, alignment_score=None)


def _servicio(entorno, guion, feedback=None, **cambios):
    sessions, atleta = entorno
    feedback = feedback or _FeedbackFalso()
    opciones = {
        "view_mode": ViewMode.LATERAL,
        "thresholds_applied": ThresholdsApplied.GENERIC,
        "user_id": atleta,
    }
    opciones.update(cambios)
    servicio = SessionService(
        _AnalizadorGuionizado(guion), feedback, sessions, **opciones
    )
    return servicio, feedback, sessions


def _correr(servicio, fotogramas, desde=0):
    for i in range(fotogramas):
        servicio.process(
            LandmarkResult(landmarks=[], timestamp_ms=(desde + i) * MS)
        )



def test_una_sesion_nace_inactiva(entorno):
    servicio, _, _ = _servicio(entorno, [FUERA])

    assert servicio.state is SessionState.IDLE


def test_sin_arrancar_no_se_acumula_nada(entorno):
    servicio, _, _ = _servicio(entorno, [_pino()])

    _correr(servicio, 10)

    assert servicio.metrics.hold_attempts == 0


def test_arrancar_reinicia_el_motor_de_feedback(entorno):
    # Entre sesiones no se conservan las correcciones ya dichas.
    servicio, feedback, _ = _servicio(entorno, [FUERA])

    servicio.start()

    assert feedback.reiniciado


def test_la_vista_rige_toda_la_sesion(entorno):
    # no se puede cambiar a mitad de sesión.
    servicio, _, _ = _servicio(entorno, [FUERA], view_mode=ViewMode.FRONTAL)

    assert servicio.view_mode is ViewMode.FRONTAL



def _puntos(n, visibilidad=0.9):
    return [
        Landmark(index=i, x=0.5, y=0.5, z=0.0, visibility=visibilidad)
        for i in range(n)
    ]


def test_en_preparacion_un_atleta_visible_esta_encuadrado(entorno):
    servicio, _, _ = _servicio(entorno, [FUERA])
    servicio.prepare()

    salida = servicio.process(
        LandmarkResult(landmarks=_puntos(MIN_VISIBLE_LANDMARKS), timestamp_ms=0)
    )

    assert salida.is_framed


def test_en_preparacion_pocos_puntos_no_bastan(entorno):
    # es lo que avisa al atleta de que recoloque la cámara.
    servicio, _, _ = _servicio(entorno, [FUERA])
    servicio.prepare()

    salida = servicio.process(
        LandmarkResult(landmarks=_puntos(MIN_VISIBLE_LANDMARKS - 1), timestamp_ms=0)
    )

    assert not salida.is_framed


def test_un_punto_poco_visible_no_cuenta(entorno):
    servicio, _, _ = _servicio(entorno, [FUERA])
    servicio.prepare()

    salida = servicio.process(
        LandmarkResult(landmarks=_puntos(20, visibilidad=0.1), timestamp_ms=0)
    )

    assert not salida.is_framed


def test_en_preparacion_no_se_analiza_ni_se_acumula(entorno):
    servicio, feedback, _ = _servicio(entorno, [_pino()])
    servicio.prepare()

    _correr(servicio, 5)

    assert feedback.marcas == []
    assert servicio.metrics.hold_attempts == 0



def test_entrar_en_pino_abre_un_intento(entorno):
    servicio, _, _ = _servicio(entorno, [FUERA] + [_pino()] * 3)
    servicio.start()

    _correr(servicio, 4)

    assert servicio.metrics.hold_attempts == 1


def test_el_tiempo_de_la_fase_sale_de_las_marcas(entorno):
    servicio, _, _ = _servicio(entorno, [_pino()] * 4)
    servicio.start()

    salida = None
    for i in range(4):
        salida = servicio.process(
            LandmarkResult(landmarks=[], timestamp_ms=i * 1000)
        )

    assert salida.hold_time_s == pytest.approx(3.0)


def test_dos_fases_separadas_son_dos_intentos(entorno):
    guion = [_pino()] * 3 + [FUERA] * 60 + [_pino()] * 3
    servicio, _, _ = _servicio(entorno, guion)
    servicio.start()

    _correr(servicio, len(guion))

    assert servicio.metrics.hold_attempts == 2


def test_una_salida_muy_breve_continua_el_mismo_intento(entorno):
    # Una micropérdida no debe inflar el recuento de intentos.
    breve = max(1, REENTRY_WINDOW_MS // MS // 2)
    guion = [_pino()] * 3 + [FUERA] * breve + [_pino()] * 3
    servicio, _, _ = _servicio(entorno, guion)
    servicio.start()

    _correr(servicio, len(guion))

    assert servicio.metrics.hold_attempts == 1


def test_el_tiempo_total_suma_las_fases(entorno):
    servicio, _, _ = _servicio(entorno, [_pino()] * 3 + [FUERA])
    servicio.start()

    for i in range(4):
        servicio.process(LandmarkResult(landmarks=[], timestamp_ms=i * 1000))

    assert servicio.metrics.total_hold_ms == 3000


def test_fuera_del_pino_el_tiempo_de_fase_es_cero(entorno):
    servicio, _, _ = _servicio(entorno, [FUERA])
    servicio.start()

    assert servicio.process(
        LandmarkResult(landmarks=[], timestamp_ms=0)
    ).hold_time_s == 0.0



def test_el_refuerzo_valora_la_fase_y_no_la_sesion(entorno):
    # Un primer intento malo no debe empañar el segundo, ni al contrario.
    guion = [_pino(40.0)] * 3 + [FUERA] * 60 + [_pino(90.0)] * 3 + [FUERA]
    servicio, feedback, _ = _servicio(entorno, guion)
    servicio.start()

    _correr(servicio, len(guion))

    assert feedback.refuerzos == [40.0, 90.0]


def test_una_fase_sin_puntuaciones_no_pide_refuerzo(entorno):
    guion = [SIN_EVALUAR] * 3 + [FUERA]
    servicio, feedback, _ = _servicio(entorno, guion)
    servicio.start()

    _correr(servicio, len(guion))

    assert feedback.refuerzos == []


def test_cerrar_la_sesion_cierra_la_fase_abierta(entorno):
    # Si el atleta termina estando en pino, esa fase cuenta igual.
    servicio, feedback, _ = _servicio(entorno, [_pino(85.0)] * 3)
    servicio.start()
    _correr(servicio, 3)

    servicio.finish()

    assert feedback.refuerzos == [85.0]



def test_una_desviacion_persistente_es_una_sola_ocurrencia(entorno):
    # Se registra el flanco de activación, no un fotograma por segundo.
    guion = [_pino(70.0, TechnicalError.BACK_ARCH)] * 50
    servicio, _, _ = _servicio(entorno, guion)
    servicio.start()

    _correr(servicio, len(guion))

    assert len(servicio.metrics.occurrences) == 1


def test_la_ocurrencia_guarda_su_evidencia_numerica(entorno):
    # tipo, valor medido, umbral e instante.
    servicio, _, _ = _servicio(entorno, [_pino(70.0, TechnicalError.BACK_ARCH)])
    servicio.start()

    _correr(servicio, 1)
    ocurrencia = servicio.metrics.occurrences[0]

    assert ocurrencia.error_type is TechnicalError.BACK_ARCH
    assert ocurrencia.measured_value == pytest.approx(11.0)
    assert ocurrencia.threshold_value == pytest.approx(8.0)
    assert ocurrencia.offset_s == pytest.approx(0.0)


def test_el_instante_es_relativo_al_inicio_de_la_sesion(entorno):
    guion = [_pino(70.0)] * 30 + [_pino(70.0, TechnicalError.BACK_ARCH)]
    servicio, _, _ = _servicio(entorno, guion)
    servicio.start()

    for i in range(len(guion)):
        servicio.process(LandmarkResult(landmarks=[], timestamp_ms=i * 100))

    assert servicio.metrics.occurrences[0].offset_s == pytest.approx(3.0)


def test_una_desviacion_corregida_y_repetida_son_dos_ocurrencias(entorno):
    arqueo = _pino(70.0, TechnicalError.BACK_ARCH)
    guion = [arqueo] * 3 + [_pino(70.0)] * 3 + [arqueo] * 3
    servicio, _, _ = _servicio(entorno, guion)
    servicio.start()

    _correr(servicio, len(guion))

    assert len(servicio.metrics.occurrences) == 2


def test_dos_errores_simultaneos_son_dos_ocurrencias(entorno):
    guion = [
        _pino(60.0, TechnicalError.BACK_ARCH, TechnicalError.LEGS_NOT_STRAIGHT)
    ] * 5
    servicio, _, _ = _servicio(entorno, guion)
    servicio.start()

    _correr(servicio, len(guion))

    assert {o.error_type for o in servicio.metrics.occurrences} == {
        TechnicalError.BACK_ARCH,
        TechnicalError.LEGS_NOT_STRAIGHT,
    }



def test_la_media_promedia_las_puntuaciones_en_pino(entorno):
    servicio, _, _ = _servicio(entorno, [_pino(60.0), _pino(80.0)])
    servicio.start()

    _correr(servicio, 2)

    assert servicio.metrics.mean_score == pytest.approx(70.0)


def test_sin_posturas_evaluables_no_hay_media(entorno):
    # Un cero sería indistinguible de una ejecución pésima.
    servicio, _, _ = _servicio(entorno, [FUERA] * 10)
    servicio.start()

    _correr(servicio, 10)

    assert servicio.metrics.mean_score is None



def test_la_sesion_se_registra_al_terminar(entorno):
    servicio, _, sessions = _servicio(
        entorno, [_pino(70.0, TechnicalError.BACK_ARCH)] * 5
    )
    servicio.start()
    _correr(servicio, 5)

    session_id = servicio.finish()
    registrada = sessions.get(session_id)

    assert registrada.hold_attempts == 1
    assert len(registrada.errors) == 1
    assert registrada.mean_alignment_score == pytest.approx(70.0)


def test_la_duracion_registrada_es_la_que_abarcan_los_fotogramas(entorno):
    servicio, _, sessions = _servicio(entorno, [_pino()] * 5)
    servicio.start()
    for i in range(5):
        servicio.process(LandmarkResult(landmarks=[], timestamp_ms=i * 1000))

    registrada = sessions.get(servicio.finish())

    assert registrada.total_duration_s == pytest.approx(4.0)


def test_el_contexto_se_registra_con_la_sesion(entorno):
    servicio, _, sessions = _servicio(
        entorno,
        [_pino()],
        view_mode=ViewMode.FRONTAL,
        thresholds_applied=ThresholdsApplied.PERSONALIZED,
    )
    servicio.start()
    _correr(servicio, 1)

    registrada = sessions.get(servicio.finish())

    assert registrada.view_mode is ViewMode.FRONTAL
    assert registrada.thresholds_applied is ThresholdsApplied.PERSONALIZED


def test_una_sesion_sin_fotogramas_no_se_registra(entorno):
    servicio, _, _ = _servicio(entorno, [FUERA])
    servicio.start()

    assert servicio.finish() is None


def test_terminar_deja_la_sesion_finalizada(entorno):
    servicio, _, _ = _servicio(entorno, [_pino()])
    servicio.start()
    _correr(servicio, 1)

    servicio.finish()

    assert servicio.state is SessionState.FINISHED



def test_una_sesion_interrumpida_conserva_lo_registrado(entorno):
    # la termina y guarda lo registrado hasta entonces.
    servicio, _, sessions = _servicio(
        entorno, [_pino(70.0, TechnicalError.BACK_ARCH)] * 5
    )
    servicio.start()
    _correr(servicio, 5)

    session_id = servicio.finish(failed=True)

    assert sessions.get(session_id) is not None
    assert servicio.state is SessionState.FAILED


def test_unos_pocos_fallos_del_estimador_no_terminan_la_sesion(entorno):
    servicio, _, _ = _servicio(entorno, [_pino()])
    servicio.start()

    assert servicio.note_failure()
    assert servicio.state is SessionState.ACTIVE


def test_demasiados_fallos_seguidos_dan_la_sesion_por_perdida(entorno):
    # Sin este límite un estimador roto giraría el bucle indefinidamente.
    servicio, _, _ = _servicio(entorno, [_pino()])
    servicio.start()

    for _ in range(MAX_CONSECUTIVE_FAILURES):
        continuar = servicio.note_failure()

    assert not continuar
    assert servicio.state is SessionState.FAILED


def test_un_fotograma_correcto_reinicia_la_cuenta_de_fallos(entorno):
    servicio, _, _ = _servicio(entorno, [_pino()] * 50)
    servicio.start()

    for _ in range(MAX_CONSECUTIVE_FAILURES - 1):
        servicio.note_failure()
    _correr(servicio, 1)

    assert servicio.note_failure()



def test_el_servicio_no_consulta_ningun_reloj(entorno):
    # La misma secuencia de marcas produce el mismo resultado. 
    # hace reproducible el análisis de un archivo a cualquier velocidad.
    guion = [FUERA] + [_pino(70.0, TechnicalError.BACK_ARCH)] * 5 + [FUERA]
    marcas = [0, 10, 500, 1200, 1800, 5000, 9000]

    resultados = []
    for _ in range(2):
        servicio, feedback, sessions = _servicio(entorno, guion)
        servicio.start()
        for marca in marcas:
            servicio.process(LandmarkResult(landmarks=[], timestamp_ms=marca))
        servicio.finish()
        resultados.append(
            (
                servicio.metrics.total_hold_ms,
                servicio.metrics.hold_attempts,
                [o.offset_s for o in servicio.metrics.occurrences],
                feedback.refuerzos,
            )
        )

    assert resultados[0] == resultados[1]


def test_la_marca_del_fotograma_llega_al_motor_de_feedback(entorno):
    servicio, feedback, _ = _servicio(entorno, [_pino()])
    servicio.start()

    servicio.process(LandmarkResult(landmarks=[], timestamp_ms=4321))

    assert feedback.marcas == [4321]