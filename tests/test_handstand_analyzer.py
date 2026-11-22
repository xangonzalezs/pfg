import math

import pytest

from core.analysis.handstand_analyzer import HandstandAnalyzer
from core.analysis.landmarks import (
    IDX_LEFT_ANKLE,
    IDX_LEFT_EAR,
    IDX_LEFT_HIP,
    IDX_LEFT_KNEE,
    IDX_LEFT_SHOULDER,
    IDX_LEFT_WRIST,
    IDX_RIGHT_ANKLE,
    IDX_RIGHT_EAR,
    IDX_RIGHT_HIP,
    IDX_RIGHT_KNEE,
    IDX_RIGHT_SHOULDER,
    IDX_RIGHT_WRIST,
)
from core.config.personalization import NeutralAngles, build_calibrated
from core.config.thresholds import (
    DEFAULT_THRESHOLDS_PATH,
    load_thresholds,
)
from core.models.analysis_result import DetectedError, TechnicalError
from core.models.landmark_result import Landmark, LandmarkResult
from core.models.view_mode import ViewMode

UMBRALES = load_thresholds(DEFAULT_THRESHOLDS_PATH)
CONFIRMACION = UMBRALES.handstand.confirmation_frames
GRACIA = UMBRALES.handstand.grace_frames

VISIBLE = 0.9
OCULTO = 0.1

_PARES = {
    "wrists": (IDX_LEFT_WRIST, IDX_RIGHT_WRIST),
    "shoulders": (IDX_LEFT_SHOULDER, IDX_RIGHT_SHOULDER),
    "hips": (IDX_LEFT_HIP, IDX_RIGHT_HIP),
    "knees": (IDX_LEFT_KNEE, IDX_RIGHT_KNEE),
    "ankles": (IDX_LEFT_ANKLE, IDX_RIGHT_ANKLE),
}

_PINO = {
    "wrists": 0.90,
    "shoulders": 0.70,
    "hips": 0.50,
    "knees": 0.30,
    "ankles": 0.10,
}


def _analizador(vista: ViewMode = ViewMode.LATERAL) -> HandstandAnalyzer:
    return HandstandAnalyzer.from_thresholds(UMBRALES, vista)


def _cuerpo(
    *,
    desplazamientos: dict[str, float] | None = None,
    alturas: dict[str, float] | None = None,
    ausentes: tuple[str, ...] = (),
    separacion_oreja: float = 0.044,
    semianchura: float = 0.10,
) -> LandmarkResult:

    alturas = dict(_PINO if alturas is None else alturas)
    desplazamientos = desplazamientos or {}

    landmarks: list[Landmark] = []
    for nombre, (izquierdo, derecho) in _PARES.items():
        if nombre not in alturas:
            continue
        centro = 0.5 + desplazamientos.get(nombre, 0.0)
        y = alturas[nombre]
        visibilidad = OCULTO if nombre in ausentes else VISIBLE
        landmarks.append(
            Landmark(index=izquierdo, x=centro - semianchura, y=y, z=0.0, visibility=visibilidad)
        )
        landmarks.append(
            Landmark(index=derecho, x=centro + semianchura, y=y, z=0.0, visibility=visibilidad)
        )

    hombros = 0.5 + desplazamientos.get("shoulders", 0.0)
    for indice, lado in ((IDX_LEFT_EAR, -1.0), (IDX_RIGHT_EAR, 1.0)):
        landmarks.append(
            Landmark(
                index=indice,
                x=hombros + lado * semianchura,
                y=alturas["shoulders"] + separacion_oreja,
                z=0.0,
                visibility=VISIBLE,
            )
        )

    return LandmarkResult(landmarks=landmarks, timestamp_ms=0)


def _sostener(analizador: HandstandAnalyzer, n: int = CONFIRMACION, **kwargs):
    resultado = None
    for _ in range(n):
        resultado = analizador.analyze(_cuerpo(**kwargs))
    return resultado


def _arqueado(grados: float) -> LandmarkResult:
    # Arqueo sin desplazamiento pélvico. solo se mueven los tobillos.
    desplazamiento = 0.4 * math.tan(math.radians(grados))
    return _cuerpo(desplazamientos={"ankles": desplazamiento})



def test_sin_pino_no_se_evalua_la_postura():
    resultado = _analizador().analyze(_cuerpo())

    assert not resultado.in_handstand
    assert resultado.alignment_score is None
    assert resultado.active_errors == []
    assert resultado.segment_deviations == {}


def test_la_puntuacion_aparece_al_confirmarse_el_pino():
    resultado = _sostener(_analizador())

    assert resultado.in_handstand
    assert resultado.alignment_score is not None
    assert resultado.is_valid


def test_el_estado_de_la_deteccion_queda_accesible():
    analizador = _analizador()
    analizador.analyze(_cuerpo())

    assert analizador.handstand_state.is_confirming
    assert not analizador.handstand_state.in_handstand


def test_una_persona_de_pie_no_produce_analisis():
    de_pie = {
        "wrists": 0.60,
        "shoulders": 0.30,
        "hips": 0.50,
        "knees": 0.70,
        "ankles": 0.90,
    }
    resultado = _sostener(_analizador(), alturas=de_pie)

    assert not resultado.in_handstand



def test_los_errores_activos_llegan_como_ocurrencias_con_evidencia():
    analizador = _analizador()
    for _ in range(CONFIRMACION):
        resultado = analizador.analyze(_arqueado(20.0))

    assert resultado.has_errors
    for error in resultado.active_errors:
        assert isinstance(error, DetectedError)
        assert error.measured_value is not None
        assert error.threshold_value is not None


def test_un_pino_correcto_no_produce_errores():
    resultado = _sostener(_analizador())
    assert not resultado.has_errors


def test_el_arqueo_dorsal_se_comunica_cuando_supera_el_umbral():
    analizador = _analizador()
    for _ in range(CONFIRMACION):
        resultado = analizador.analyze(_arqueado(20.0))

    assert TechnicalError.BACK_ARCH in resultado.error_types


def test_la_inestabilidad_se_integra_con_los_errores_de_alineacion():
    analizador = _analizador()
    for i in range(CONFIRMACION + UMBRALES.stability.window_size):
        oscilacion = 0.09 if i % 2 else -0.09
        resultado = analizador.analyze(
            _cuerpo(desplazamientos={nombre: oscilacion for nombre in _PARES})
        )

    assert TechnicalError.INSTABILITY in resultado.error_types


def test_la_vista_decide_que_errores_se_comunican():
    lateral = _sostener(_analizador(ViewMode.LATERAL), CONFIRMACION)
    frontal = _sostener(_analizador(ViewMode.FRONTAL), CONFIRMACION)

    assert TechnicalError.NO_SHRUG not in lateral.error_types
    assert TechnicalError.BACK_ARCH not in frontal.error_types



def test_una_ejecucion_mala_sigue_siendo_un_pino_y_recibe_correccion():
    analizador = _analizador()
    desplazamientos = {"shoulders": 0.05, "hips": -0.06, "knees": 0.05, "ankles": -0.04}

    for _ in range(CONFIRMACION * 6):
        resultado = analizador.analyze(_cuerpo(desplazamientos=desplazamientos))

    assert resultado.in_handstand
    assert resultado.alignment_score < 60.0
    assert resultado.has_errors



def test_perder_el_pino_olvida_los_errores_activos():
    # Lo corregido en un intento no sigue comunicándose en el siguiente.
    analizador = _analizador()
    for _ in range(CONFIRMACION):
        analizador.analyze(_arqueado(20.0))

    for _ in range(GRACIA + 2):
        analizador.analyze(_cuerpo(ausentes=("shoulders",)))

    assert not analizador.handstand_state.in_handstand
    primero = None
    for _ in range(CONFIRMACION):
        primero = analizador.analyze(_cuerpo())

    assert not primero.has_errors


def test_reset_devuelve_el_analizador_a_su_estado_inicial():
    analizador = _analizador()
    _sostener(analizador)

    analizador.reset()

    assert not analizador.handstand_state.in_handstand
    assert not analizador.analyze(_cuerpo()).in_handstand


def test_una_perdida_breve_no_interrumpe_el_analisis():
    analizador = _analizador()
    _sostener(analizador)

    for _ in range(GRACIA):
        resultado = analizador.analyze(_cuerpo(ausentes=("shoulders",)))

    assert resultado.in_handstand



def test_los_umbrales_personalizados_relajan_la_correccion():
    personalizados = build_calibrated(
        UMBRALES.alignment,
        NeutralAngles(back_arch_deg=168.0),
        UMBRALES.personalization,
    ).thresholds

    generico = _analizador()
    personalizado = _analizador()
    personalizado.apply_thresholds(personalizados)

    for _ in range(CONFIRMACION):
        con_generico = generico.analyze(_arqueado(6.0))
        con_personalizado = personalizado.analyze(_arqueado(6.0))

    assert TechnicalError.BACK_ARCH in con_generico.error_types
    assert TechnicalError.BACK_ARCH not in con_personalizado.error_types


def test_el_cambio_de_umbrales_no_altera_la_deteccion_del_pino():
    analizador = _analizador()
    _sostener(analizador)

    analizador.apply_thresholds(UMBRALES.alignment)

    assert analizador.handstand_state.in_handstand


def test_cambiar_de_vista_descarta_el_estado_anterior():
    analizador = _analizador(ViewMode.LATERAL)
    _sostener(analizador)

    analizador.set_view_mode(ViewMode.FRONTAL)

    assert analizador.view_mode is ViewMode.FRONTAL
    assert not analizador.handstand_state.in_handstand


def test_el_analizador_recuerda_su_vista():
    assert _analizador(ViewMode.FRONTAL).view_mode is ViewMode.FRONTAL