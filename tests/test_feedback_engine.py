import pytest

from core.config.thresholds import FeedbackThresholds
from core.feedback.feedback_engine import (
    ERROR_PRIORITY,
    FeedbackEngine,
    FeedbackPriorityError,
    _check_priority_covers_every_error,
)
from core.feedback.message_catalog import MessageCatalog, load_catalog, required_keys
from core.models.analysis_result import AnalysisResult, DetectedError, TechnicalError

UMBRALES = FeedbackThresholds(
    confirmation_frames=3,
    grace_frames=5,
    repeat_cooldown_ms=8000,
    not_analyzing_cooldown_ms=10000,
    positive_score_threshold=80.0,
)

# Cadencia nominal, para traducir fotogramas a marcas de tiempo.
MS_POR_FOTOGRAMA = 33


class _ReproductorFalso:
    # Sustituye al reproductor: registra qué suena y si está ocupado.

    def __init__(self, *, ocupado: bool = False):
        self.ocupado = ocupado
        self.reproducidas: list[str] = []

    @property
    def is_playing(self) -> bool:
        return self.ocupado

    def play(self, filename: str) -> None:
        self.reproducidas.append(filename)


@pytest.fixture
def catalogo(tmp_path):
    import json

    ruta = tmp_path / "feedback_messages.json"
    datos = {clave: f"Texto de {clave}." for clave in required_keys()}
    ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    return load_catalog(ruta)


def _motor(catalogo, reproductor=None, umbrales=UMBRALES):
    reproductor = reproductor or _ReproductorFalso()
    return FeedbackEngine(catalogo, reproductor, umbrales), reproductor


def _resultado(*errores, score=70.0, en_pino=True):
    return AnalysisResult(
        alignment_score=score,
        active_errors=[
            DetectedError(error_type=error, measured_value=10.0, threshold_value=8.0)
            for error in errores
        ],
        in_handstand=en_pino,
    )


def _procesar(motor, resultado, fotogramas=1, desde=0):
    # Alimenta el motor con fotogramas consecutivos y devuelve lo emitido.

    emitidos = []
    for i in range(fotogramas):
        salida = motor.process(resultado, (desde + i) * MS_POR_FOTOGRAMA)
        if salida.emitted:
            emitidos.append(salida)
    return emitidos



def test_el_orden_cubre_todos_los_errores_definidos():
    # Un error ausente del orden quedaría medido pero nunca verbalizado.
    assert set(ERROR_PRIORITY) == set(TechnicalError)


def test_el_orden_no_repite_ningun_error():
    assert len(ERROR_PRIORITY) == len(set(ERROR_PRIORITY))


def test_un_orden_incompleto_se_rechaza_al_cargar(monkeypatch):
    import core.feedback.feedback_engine as modulo

    monkeypatch.setattr(modulo, "ERROR_PRIORITY", (TechnicalError.BACK_ARCH,))

    with pytest.raises(FeedbackPriorityError, match="PELVIS_POSITION"):
        _check_priority_covers_every_error()


def test_las_asimetrias_lateralizadas_van_primero():
    # Son las correcciones más concretas: un lado y una dirección.
    asimetrias = {
        TechnicalError.LEFT_SHOULDER_LOW,
        TechnicalError.RIGHT_SHOULDER_LOW,
        TechnicalError.LEFT_HIP_LOW,
        TechnicalError.RIGHT_HIP_LOW,
    }

    assert set(ERROR_PRIORITY[:4]) == asimetrias


def test_la_cadena_corporal_va_del_apoyo_hacia_los_pies():
    cadena = [
        TechnicalError.ELBOW_NOT_EXTENDED,
        TechnicalError.HEAD_FORWARD,
        TechnicalError.NO_SHRUG,
        TechnicalError.BACK_ARCH,
        TechnicalError.PELVIS_POSITION,
        TechnicalError.LEGS_NOT_STRAIGHT,
        TechnicalError.FEET_NOT_EXTENDED,
    ]

    assert list(ERROR_PRIORITY[4:11]) == cadena


def test_la_inestabilidad_va_ultima():
    # Es consecuencia del conjunto, no una desviación de un segmento.
    assert ERROR_PRIORITY[-1] is TechnicalError.INSTABILITY


def test_se_emite_el_error_de_mayor_prioridad(catalogo):
    motor, reproductor = _motor(catalogo)

    _procesar(
        motor,
        _resultado(TechnicalError.INSTABILITY, TechnicalError.LEFT_HIP_LOW),
        fotogramas=3,
    )

    assert reproductor.reproducidas == ["left_hip_low.mp3"]


def test_solo_se_emite_un_mensaje_por_fotograma(catalogo):
    # El atleta no puede atender a dos correcciones a la vez.
    motor, reproductor = _motor(catalogo)

    emitidos = _procesar(
        motor,
        _resultado(TechnicalError.BACK_ARCH, TechnicalError.FEET_NOT_EXTENDED),
        fotogramas=3,
    )

    assert len(emitidos) == 1
    assert len(reproductor.reproducidas) == 1


def test_un_error_sin_confirmar_no_se_emite(catalogo):
    motor, reproductor = _motor(catalogo)

    _procesar(motor, _resultado(TechnicalError.BACK_ARCH), fotogramas=2)

    assert reproductor.reproducidas == []


def test_un_error_se_emite_al_alcanzar_los_fotogramas_exigidos(catalogo):
    motor, reproductor = _motor(catalogo)

    _procesar(motor, _resultado(TechnicalError.BACK_ARCH), fotogramas=3)

    assert reproductor.reproducidas == ["back_arch.mp3"]


def test_unos_destellos_aislados_nunca_se_emiten(catalogo):
    # Es lo que descarta las activaciones puntuales del detector.
    motor, reproductor = _motor(catalogo)
    arqueo = _resultado(TechnicalError.BACK_ARCH)
    ausente = _resultado()
    fotograma = 0

    for _ in range(10):
        for _ in range(UMBRALES.confirmation_frames - 1):
            motor.process(arqueo, fotograma * MS_POR_FOTOGRAMA)
            fotograma += 1
        for _ in range(UMBRALES.grace_frames + 1):
            motor.process(ausente, fotograma * MS_POR_FOTOGRAMA)
            fotograma += 1

    assert reproductor.reproducidas == []


def test_un_error_intermitente_pero_real_acaba_confirmandose(catalogo):
    #  los fotogramas que confirman un error no han de ser contiguos.
    motor, reproductor = _motor(catalogo)
    arqueo = _resultado(TechnicalError.BACK_ARCH)

    for fotograma in range(10):
        motor.process(arqueo, fotograma * 2 * MS_POR_FOTOGRAMA)
        motor.process(_resultado(), (fotograma * 2 + 1) * MS_POR_FOTOGRAMA)

    assert reproductor.reproducidas == ["back_arch.mp3"]



def test_una_ausencia_breve_conserva_el_progreso(catalogo):
    # Una micropérdida de detección no destruye lo acumulado.
    motor, reproductor = _motor(catalogo)
    arqueo = _resultado(TechnicalError.BACK_ARCH)

    _procesar(motor, arqueo, fotogramas=2)
    _procesar(motor, _resultado(), fotogramas=UMBRALES.grace_frames, desde=2)
    _procesar(motor, arqueo, fotogramas=1, desde=10)

    assert reproductor.reproducidas == ["back_arch.mp3"]


def test_una_ausencia_prolongada_reinicia_el_progreso(catalogo):
    motor, reproductor = _motor(catalogo)
    arqueo = _resultado(TechnicalError.BACK_ARCH)

    _procesar(motor, arqueo, fotogramas=2)
    _procesar(motor, _resultado(), fotogramas=UMBRALES.grace_frames + 1, desde=2)
    _procesar(motor, arqueo, fotogramas=1, desde=20)

    assert reproductor.reproducidas == []


def test_las_ventanas_se_cuentan_en_fotogramas_y_no_en_tiempo(catalogo):
    # el mismo número de fotogramas confirma el error con independencia del intervalo que abarquen.
    motor, reproductor = _motor(catalogo)
    arqueo = _resultado(TechnicalError.BACK_ARCH)

    for marca in (0, 5000, 100000):
        motor.process(arqueo, marca)

    assert reproductor.reproducidas == ["back_arch.mp3"]



def test_un_error_continuado_se_dice_una_sola_vez(catalogo):
    motor, reproductor = _motor(catalogo)

    _procesar(motor, _resultado(TechnicalError.BACK_ARCH), fotogramas=100)

    assert reproductor.reproducidas == ["back_arch.mp3"]


def test_un_error_sin_resolver_se_repite_tras_la_espera(catalogo):
    motor, reproductor = _motor(catalogo)
    arqueo = _resultado(TechnicalError.BACK_ARCH)

    motor.process(arqueo, 0)
    motor.process(arqueo, 1)
    motor.process(arqueo, 2)
    motor.process(arqueo, UMBRALES.repeat_cooldown_ms - 1)
    motor.process(arqueo, UMBRALES.repeat_cooldown_ms + 2)

    assert reproductor.reproducidas == ["back_arch.mp3", "back_arch.mp3"]


def test_un_error_corregido_y_repetido_se_dice_de_nuevo(catalogo):
    # Indica que el atleta lo corrigió y volvió a caer en él.
    motor, reproductor = _motor(catalogo)
    arqueo = _resultado(TechnicalError.BACK_ARCH)

    _procesar(motor, arqueo, fotogramas=3)
    _procesar(motor, _resultado(), fotogramas=UMBRALES.grace_frames + 1, desde=3)
    _procesar(motor, arqueo, fotogramas=3, desde=20)

    assert reproductor.reproducidas == ["back_arch.mp3", "back_arch.mp3"]


def test_la_espera_se_mide_sobre_la_marca_del_fotograma(catalogo):
    # Y no sobre el reloj del equipo
    # así el análisis de un archivo produce la misma secuencia de mensajes a cualquier velocidad de procesamiento.
    arqueo = _resultado(TechnicalError.BACK_ARCH)
    marcas = [0, 33, 66, 4000, 9000, 12000]

    rapido, player_rapido = _motor(catalogo)
    lento, player_lento = _motor(catalogo)

    for marca in marcas:
        rapido.process(arqueo, marca)
    for marca in marcas:
        lento.process(arqueo, marca)

    assert player_rapido.reproducidas == player_lento.reproducidas
    assert len(player_rapido.reproducidas) == 2



def test_no_se_emite_nada_mientras_suena_otra_locucion(catalogo):
    motor, reproductor = _motor(catalogo, _ReproductorFalso(ocupado=True))

    _procesar(motor, _resultado(TechnicalError.BACK_ARCH), fotogramas=10)

    assert reproductor.reproducidas == []


def test_al_terminar_la_locucion_se_emite_la_correccion(catalogo):
    motor, reproductor = _motor(catalogo, _ReproductorFalso(ocupado=True))

    _procesar(motor, _resultado(TechnicalError.BACK_ARCH), fotogramas=5)
    reproductor.ocupado = False
    _procesar(motor, _resultado(TechnicalError.BACK_ARCH), fotogramas=1, desde=5)

    assert reproductor.reproducidas == ["back_arch.mp3"]



def test_fuera_del_pino_no_se_emite_nada(catalogo):
    motor, reproductor = _motor(catalogo)

    _procesar(
        motor,
        _resultado(TechnicalError.BACK_ARCH, en_pino=False),
        fotogramas=10,
    )

    assert reproductor.reproducidas == []


def test_bajar_del_pino_descarta_la_persistencia_acumulada(catalogo):
    motor, reproductor = _motor(catalogo)
    arqueo = _resultado(TechnicalError.BACK_ARCH)

    _procesar(motor, arqueo, fotogramas=2)
    motor.process(_resultado(en_pino=False), 100)
    _procesar(motor, arqueo, fotogramas=2, desde=10)

    assert reproductor.reproducidas == []


def test_en_un_intento_nuevo_la_correccion_se_repite(catalogo):
    motor, reproductor = _motor(catalogo)
    arqueo = _resultado(TechnicalError.BACK_ARCH)

    _procesar(motor, arqueo, fotogramas=3)
    motor.process(_resultado(en_pino=False), 1000)
    _procesar(motor, arqueo, fotogramas=3, desde=40)

    assert reproductor.reproducidas == ["back_arch.mp3", "back_arch.mp3"]


def test_sin_puntuacion_se_avisa_de_que_no_se_evalua(catalogo):
    # El silencio no debe confundirse con una ejecución correcta.
    motor, reproductor = _motor(catalogo)

    motor.process(_resultado(score=None), 0)

    assert reproductor.reproducidas == ["not_analyzing.mp3"]


def test_el_aviso_de_no_evaluacion_no_se_repite_en_cada_fotograma(catalogo):
    motor, reproductor = _motor(catalogo)

    _procesar(motor, _resultado(score=None), fotogramas=50)

    assert reproductor.reproducidas == ["not_analyzing.mp3"]


def test_el_aviso_de_no_evaluacion_se_repite_tras_su_espera(catalogo):
    motor, reproductor = _motor(catalogo)
    sin_puntuacion = _resultado(score=None)

    motor.process(sin_puntuacion, 0)
    motor.process(sin_puntuacion, UMBRALES.not_analyzing_cooldown_ms - 1)
    motor.process(sin_puntuacion, UMBRALES.not_analyzing_cooldown_ms)

    assert len(reproductor.reproducidas) == 2


def test_el_aviso_de_no_evaluacion_no_compite_con_una_locucion(catalogo):
    motor, reproductor = _motor(catalogo, _ReproductorFalso(ocupado=True))

    motor.process(_resultado(score=None), 0)

    assert reproductor.reproducidas == []


def test_al_recuperar_la_puntuacion_se_vuelve_a_corregir(catalogo):
    motor, reproductor = _motor(catalogo)

    motor.process(_resultado(score=None), 0)
    _procesar(motor, _resultado(TechnicalError.BACK_ARCH), fotogramas=3, desde=1)

    assert reproductor.reproducidas == ["not_analyzing.mp3", "back_arch.mp3"]



def test_una_ejecucion_suficiente_recibe_refuerzo(catalogo):
    motor, reproductor = _motor(catalogo)

    resultado = motor.notify_hold_ended(85.0)

    assert resultado.emitted
    assert reproductor.reproducidas == ["positive.mp3"]


def test_una_ejecucion_insuficiente_no_recibe_refuerzo(catalogo):
    motor, reproductor = _motor(catalogo)

    motor.notify_hold_ended(UMBRALES.positive_score_threshold - 0.1)

    assert reproductor.reproducidas == []


def test_el_refuerzo_no_se_superpone_a_una_locucion(catalogo):
    motor, reproductor = _motor(catalogo, _ReproductorFalso(ocupado=True))

    motor.notify_hold_ended(95.0)

    assert reproductor.reproducidas == []


def test_el_refuerzo_no_se_asocia_a_ningun_error(catalogo):
    motor, _ = _motor(catalogo)

    assert motor.notify_hold_ended(90.0).error is None


def test_reiniciar_permite_emitir_de_nuevo_la_misma_correccion(catalogo):
    motor, reproductor = _motor(catalogo)
    arqueo = _resultado(TechnicalError.BACK_ARCH)

    _procesar(motor, arqueo, fotogramas=3)
    motor.reset()
    _procesar(motor, arqueo, fotogramas=3, desde=3)

    assert reproductor.reproducidas == ["back_arch.mp3", "back_arch.mp3"]


def test_reiniciar_olvida_el_aviso_de_no_evaluacion(catalogo):
    motor, reproductor = _motor(catalogo)

    motor.process(_resultado(score=None), 0)
    motor.reset()
    motor.process(_resultado(score=None), 1)

    assert len(reproductor.reproducidas) == 2



def test_cada_error_del_orden_tiene_su_mensaje_en_el_catalogo():
    # Verifica el catálogo que se despliega contra el orden real de emisión.
    catalogo = load_catalog()

    for error in ERROR_PRIORITY:
        assert catalogo.for_error(error).text.strip()