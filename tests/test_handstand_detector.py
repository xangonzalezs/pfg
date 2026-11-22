import math

import pytest

from core.analysis.handstand_detector import HandstandDetector, HandstandState
from core.analysis.landmarks import (
    IDX_LEFT_ANKLE,
    IDX_LEFT_HIP,
    IDX_LEFT_KNEE,
    IDX_LEFT_SHOULDER,
    IDX_LEFT_WRIST,
    IDX_RIGHT_ANKLE,
    IDX_RIGHT_HIP,
    IDX_RIGHT_KNEE,
    IDX_RIGHT_SHOULDER,
    IDX_RIGHT_WRIST,
)
from core.config.thresholds import (
    DEFAULT_THRESHOLDS_PATH,
    HandstandThresholds,
    load_thresholds,
)
from core.models.landmark_result import Landmark, LandmarkResult

UMBRALES = HandstandThresholds(
    order_margin=0.03,
    min_body_length=0.10,
    max_tilt_deg=20.0,
    confirmation_frames=9,
    grace_frames=5,
)

VISIBLE = 0.9
OCULTO = 0.1

CONFIRMACION = UMBRALES.confirmation_frames
GRACIA = UMBRALES.grace_frames

_PARES = {
    "wrists": (IDX_LEFT_WRIST, IDX_RIGHT_WRIST),
    "shoulders": (IDX_LEFT_SHOULDER, IDX_RIGHT_SHOULDER),
    "hips": (IDX_LEFT_HIP, IDX_RIGHT_HIP),
    "knees": (IDX_LEFT_KNEE, IDX_RIGHT_KNEE),
    "ankles": (IDX_LEFT_ANKLE, IDX_RIGHT_ANKLE),
}

# Alturas de un pino correcto: las manos abajo y los pies arriba.
_PINO = {
    "wrists": 0.90,
    "shoulders": 0.70,
    "hips": 0.50,
    "knees": 0.30,
    "ankles": 0.10,
}


def _detector(**kwargs) -> HandstandDetector:
    umbrales = kwargs.pop("thresholds", UMBRALES)
    return HandstandDetector(umbrales, **kwargs)


def _cuerpo(
    alturas: dict[str, float] | None = None,
    *,
    x: float = 0.5,
    desplazamientos: dict[str, float] | None = None,
    ausentes: tuple[str, ...] = (),
    un_solo_lado: tuple[str, ...] = (),
    semianchura: float = 0.05,
) -> LandmarkResult:
    # Cuerpo invertido a partir de la altura de cada articulación.

    alturas = dict(_PINO if alturas is None else alturas)
    desplazamientos = desplazamientos or {}

    landmarks: list[Landmark] = []
    for nombre, (izquierdo, derecho) in _PARES.items():
        if nombre not in alturas:
            continue
        centro = x + desplazamientos.get(nombre, 0.0)
        y = alturas[nombre]
        visible = OCULTO if nombre in ausentes else VISIBLE
        landmarks.append(
            Landmark(index=izquierdo, x=centro - semianchura, y=y, z=0.0, visibility=visible)
        )
        landmarks.append(
            Landmark(
                index=derecho,
                x=centro + semianchura,
                y=y,
                z=0.0,
                visibility=OCULTO if nombre in un_solo_lado else visible,
            )
        )

    return LandmarkResult(landmarks=landmarks, timestamp_ms=0)


def _alimentar(
    detector: HandstandDetector, n: int, cuerpo: LandmarkResult | None = None
) -> HandstandState:
    estado = None
    for _ in range(n):
        estado = detector.update(_cuerpo() if cuerpo is None else cuerpo)
    return estado


def _inclinado(grados: float) -> LandmarkResult:
    # Cuerpo recto girado respecto a la vertical en torno a las muñecas.
    radianes = math.radians(grados)
    alturas: dict[str, float] = {}
    desplazamientos: dict[str, float] = {}
    for nombre, altura in _PINO.items():
        largo = _PINO["wrists"] - altura
        alturas[nombre] = _PINO["wrists"] - largo * math.cos(radianes)
        desplazamientos[nombre] = largo * math.sin(radianes)
    return _cuerpo(alturas, desplazamientos=desplazamientos)


def test_un_pino_correcto_se_reconoce_como_inversion():
    estado = _detector().update(_cuerpo())
    assert estado.is_inverted


def test_una_persona_de_pie_no_es_una_inversion():
    de_pie = {
        "wrists": 0.60,
        "shoulders": 0.30,
        "hips": 0.50,
        "knees": 0.70,
        "ankles": 0.90,
    }
    assert not _detector().update(_cuerpo(de_pie)).is_inverted


def test_la_cadena_debe_estar_ordenada_en_todos_sus_eslabones():
    # Tronco invertido con las piernas sin subir, como en la entrada al pino.
    sin_subir = dict(_PINO, hips=0.05)
    assert not _detector().update(_cuerpo(sin_subir)).is_inverted


def test_una_separacion_menor_que_el_margen_no_cuenta_como_orden():
    # Un cuerpo agachado puede dejar los puntos ordenados por azar.
    apenas = {
        "wrists": 0.52,
        "shoulders": 0.50,
        "hips": 0.48,
        "knees": 0.46,
        "ankles": 0.44,
    }
    assert not _detector().update(_cuerpo(apenas)).is_inverted


def test_sin_un_eslabon_de_la_cadena_no_se_detecta_inversion():
    assert not _detector().update(_cuerpo(ausentes=("shoulders",))).is_inverted


def test_en_vista_lateral_basta_un_lado_de_cada_articulacion():
    cuerpo = _cuerpo(un_solo_lado=tuple(_PARES))
    assert _detector().update(cuerpo).is_inverted


def test_sin_tobillos_se_recurre_a_las_rodillas():
    # Los pies salen del encuadre con frecuencia; la cadena se acorta.
    estado = _detector().update(_cuerpo(ausentes=("ankles",)))
    assert estado.is_inverted


def test_sin_tobillos_ni_rodillas_no_se_detecta_inversion():
    cuerpo = _cuerpo(ausentes=("ankles", "knees"))
    assert not _detector().update(cuerpo).is_inverted



def test_un_cuerpo_demasiado_pequeno_en_la_imagen_se_descarta():
    # Lejos de la cámara el ruido del estimador domina la medida.
    pequeno = {
        "wrists": 0.54,
        "shoulders": 0.525,
        "hips": 0.51,
        "knees": 0.495,
        "ankles": 0.48,
    }
    assert not _detector().update(_cuerpo(pequeno)).is_inverted


def test_la_longitud_corporal_viaja_en_el_estado():
    estado = _detector().update(_cuerpo())
    assert estado.body_length == pytest.approx(0.80)


def test_una_inclinacion_moderada_se_admite():
    estado = _detector().update(_inclinado(15.0))
    assert estado.is_inverted
    assert estado.tilt_deg == pytest.approx(15.0, abs=0.01)


def test_una_inclinacion_excesiva_se_rechaza():
    assert not _detector().update(_inclinado(35.0)).is_inverted


def test_el_limite_de_inclinacion_es_inclusivo():
    assert _detector().update(_inclinado(20.0)).is_inverted
    assert not _detector().update(_inclinado(20.5)).is_inverted


def test_la_inclinacion_no_distingue_el_lado():
    izquierda = _detector().update(_inclinado(-15.0))
    derecha = _detector().update(_inclinado(15.0))
    assert izquierda.tilt_deg == pytest.approx(derecha.tilt_deg, abs=0.01)
    assert izquierda.is_inverted and derecha.is_inverted



def test_un_solo_fotograma_invertido_no_confirma_el_pino():
    estado = _detector().update(_cuerpo())
    assert estado.is_inverted
    assert not estado.in_handstand
    assert estado.is_confirming


def test_el_pino_se_confirma_al_alcanzar_la_ventana():
    detector = _detector()
    assert not _alimentar(detector, CONFIRMACION - 1).in_handstand
    assert detector.update(_cuerpo()).in_handstand


def test_la_cuenta_de_confirmacion_viaja_en_el_estado():
    detector = _detector()
    estado = _alimentar(detector, 4)
    assert estado.confirming_frames == 4


def test_una_inversion_interrumpida_reinicia_la_cuenta():
    detector = _detector()
    _alimentar(detector, CONFIRMACION - 1)

    detector.update(_cuerpo(ausentes=("shoulders",)))

    assert not _alimentar(detector, CONFIRMACION - 1).in_handstand
    assert detector.update(_cuerpo()).in_handstand


def test_la_ventana_se_cuenta_en_fotogramas_y_no_en_tiempo():
    rapido = _detector()
    lento = _detector()

    for i in range(CONFIRMACION):
        cuerpo = _cuerpo()
        veloz = LandmarkResult(landmarks=cuerpo.landmarks, timestamp_ms=i * 1)
        pausado = LandmarkResult(landmarks=cuerpo.landmarks, timestamp_ms=i * 1000)
        estado_rapido = rapido.update(veloz)
        estado_lento = lento.update(pausado)

    assert estado_rapido.in_handstand
    assert estado_lento.in_handstand


def test_una_perdida_breve_no_cancela_el_pino():
    detector = _detector()
    _alimentar(detector, CONFIRMACION)

    for _ in range(GRACIA):
        estado = detector.update(_cuerpo(ausentes=("shoulders",)))

    assert estado.in_handstand
    assert not estado.is_inverted


def test_una_perdida_prolongada_cancela_el_pino():
    detector = _detector()
    _alimentar(detector, CONFIRMACION)

    for _ in range(GRACIA + 1):
        estado = detector.update(_cuerpo(ausentes=("shoulders",)))

    assert not estado.in_handstand
    assert not detector.in_handstand


def test_recuperar_la_inversion_restaura_la_tolerancia():
    # Dos pérdidas breves separadas por fotogramas válidos no se suman.
    detector = _detector()
    _alimentar(detector, CONFIRMACION)

    for _ in range(GRACIA):
        detector.update(_cuerpo(ausentes=("shoulders",)))
    detector.update(_cuerpo())
    for _ in range(GRACIA):
        estado = detector.update(_cuerpo(ausentes=("shoulders",)))

    assert estado.in_handstand


def test_un_pino_confirmado_no_vuelve_a_necesitar_confirmacion():
    detector = _detector()
    _alimentar(detector, CONFIRMACION)

    for _ in range(GRACIA + 1):
        detector.update(_cuerpo(ausentes=("shoulders",)))

    assert not detector.in_handstand
    assert not _alimentar(detector, CONFIRMACION - 1).in_handstand


def test_reset_olvida_el_estado():
    detector = _detector()
    _alimentar(detector, CONFIRMACION)

    detector.reset()

    assert not detector.in_handstand
    assert not detector.update(_cuerpo()).in_handstand



def test_la_calidad_de_la_ejecucion_no_interviene_en_la_deteccion():
    malo = dict(_PINO)
    desplazamientos = {"shoulders": 0.06, "hips": -0.07, "knees": 0.08, "ankles": -0.05}
    estado = _detector().update(_cuerpo(malo, desplazamientos=desplazamientos))

    assert estado.is_inverted


def test_una_rodilla_flexionada_no_impide_detectar_el_pino():
    # Con la pierna muy flexionada el tobillo baja de la rodilla.
    flexionada = dict(_PINO, ankles=0.34)
    estado = _detector().update(_cuerpo(flexionada))

    assert estado.is_inverted



def test_el_detector_funciona_con_la_configuracion_del_proyecto():
    umbrales = load_thresholds(DEFAULT_THRESHOLDS_PATH).handstand
    detector = HandstandDetector(umbrales)

    for _ in range(umbrales.confirmation_frames):
        estado = detector.update(_cuerpo())

    assert estado.in_handstand


def test_los_umbrales_no_tienen_valor_por_defecto():
    with pytest.raises(TypeError):
        HandstandDetector()