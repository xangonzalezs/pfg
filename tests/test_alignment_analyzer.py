import math

import pytest

from core.analysis.alignment_analyzer import AlignmentAnalyzer
from core.config.thresholds import AlignmentThresholds, ParameterThreshold
from core.models.analysis_result import TechnicalError
from core.models.landmark_result import Landmark, LandmarkResult
from core.models.view_mode import ViewMode

_IDX_LEFT_EAR = 7
_IDX_RIGHT_EAR = 8
_IDX_LEFT_SHOULDER = 11
_IDX_RIGHT_SHOULDER = 12
_IDX_LEFT_ELBOW = 13
_IDX_RIGHT_ELBOW = 14
_IDX_LEFT_WRIST = 15
_IDX_RIGHT_WRIST = 16
_IDX_LEFT_HIP = 23
_IDX_RIGHT_HIP = 24
_IDX_LEFT_KNEE = 25
_IDX_RIGHT_KNEE = 26
_IDX_LEFT_ANKLE = 27
_IDX_RIGHT_ANKLE = 28
_IDX_LEFT_FOOT_INDEX = 31
_IDX_RIGHT_FOOT_INDEX = 32

_PARES = {
    "wrists": (_IDX_LEFT_WRIST, _IDX_RIGHT_WRIST),
    "shoulders": (_IDX_LEFT_SHOULDER, _IDX_RIGHT_SHOULDER),
    "hips": (_IDX_LEFT_HIP, _IDX_RIGHT_HIP),
    "knees": (_IDX_LEFT_KNEE, _IDX_RIGHT_KNEE),
    "ankles": (_IDX_LEFT_ANKLE, _IDX_RIGHT_ANKLE),
}

VISIBLE = 0.9
OCULTO = 0.1

UMBRALES = AlignmentThresholds(
    segment_weights={
        "wrists_shoulders": 0.40,
        "shoulders_hips": 0.30,
        "hips_knees": 0.20,
        "knees_ankles": 0.10,
    },
    noise_threshold_deg=2.0,
    max_segment_deviation_deg=12.0,
    score_exponent=1.5,
    min_trunk_length=0.02,
    min_pair_width=0.02,
    parameters={
        "back_arch": ParameterThreshold(threshold=8.0, noise=3.0),
        "pelvis_shift": ParameterThreshold(threshold=0.07, noise=0.02),
        "head_forward": ParameterThreshold(threshold=0.10, noise=0.03),
        "knee_bend": ParameterThreshold(threshold=10.0, noise=3.0),
        "leg_tilt": ParameterThreshold(threshold=8.0, noise=2.5),
        "shoulder_tilt": ParameterThreshold(threshold=8.6, noise=1.7),
        "hip_tilt": ParameterThreshold(threshold=8.6, noise=1.7),
        "shrug": ParameterThreshold(threshold=0.30, noise=0.22),
        "elbow_bend": ParameterThreshold(threshold=10.0, noise=3.0),
        "foot_extension": ParameterThreshold(threshold=45.0, noise=30.0),
    },
)

_SAGITALES = {
    TechnicalError.BACK_ARCH,
    TechnicalError.PELVIS_POSITION,
    TechnicalError.HEAD_FORWARD,
    TechnicalError.LEGS_NOT_STRAIGHT,
}


def _analizador(view_mode: ViewMode = ViewMode.LATERAL, **kwargs) -> AlignmentAnalyzer:
    return AlignmentAnalyzer(
        kwargs.pop("thresholds", UMBRALES), view_mode, **kwargs
    )


# --- Cuerpos simétricos, para las líneas corporales --------------------


def _cuerpo(
    posiciones: dict[str, float],
    *,
    ausentes: tuple[str, ...] = (),
    un_solo_lado: tuple[str, ...] = (),
    semianchura: float = 0.05,
) -> LandmarkResult:
    # Construye un cuerpo invertido a partir de la coordenada x de cada articulación.
    # Las y se reparten de arriba abajo con separaciones iguales, de modo que cada línea mide 0.2 en vertical.

    alturas = {
        "wrists": 0.9,
        "shoulders": 0.7,
        "hips": 0.5,
        "knees": 0.3,
        "ankles": 0.1,
    }

    landmarks: list[Landmark] = []
    for nombre, (izquierdo, derecho) in _PARES.items():
        x = posiciones[nombre]
        y = alturas[nombre]
        visibilidad = OCULTO if nombre in ausentes else VISIBLE
        landmarks.append(
            Landmark(index=izquierdo, x=x - semianchura, y=y, z=0.0, visibility=visibilidad)
        )
        derecha_visible = visibilidad
        if nombre in un_solo_lado:
            derecha_visible = OCULTO
        landmarks.append(
            Landmark(index=derecho, x=x + semianchura, y=y, z=0.0, visibility=derecha_visible)
        )

    # Orejas alineadas con su hombro la cabeza no introduce desviación.
    for indice, lado in ((_IDX_LEFT_EAR, -1.0), (_IDX_RIGHT_EAR, 1.0)):
        landmarks.append(
            Landmark(
                index=indice,
                x=posiciones["shoulders"] + lado * semianchura,
                y=0.8,
                z=0.0,
                visibility=VISIBLE,
            )
        )

    return LandmarkResult(landmarks=landmarks, timestamp_ms=0)


def _recto(**extra) -> LandmarkResult:
    # Cuerpo perfectamente vertical: todas las articulaciones en x = 0.5.
    return _cuerpo({nombre: 0.5 for nombre in _PARES}, **extra)


def _inclinado(grados: float, articulacion: str) -> LandmarkResult:
    # Desplaza una articulación para que la línea que llega a ella forme el
    # ángulo pedido con la vertical. La separación vertical es 0.2.
    desplazamiento = 0.2 * math.tan(math.radians(grados))
    posiciones = {nombre: 0.5 for nombre in _PARES}
    orden = ["wrists", "shoulders", "hips", "knees", "ankles"]
    for nombre in orden[orden.index(articulacion) :]:
        posiciones[nombre] = 0.5 + desplazamiento
    return _cuerpo(posiciones)


def _penalizacion_esperada(grados: float) -> float:
    # Penalización de una línea aislada, según la fórmula documentada.
    ratio = (grados - UMBRALES.noise_threshold_deg) / (
        UMBRALES.max_segment_deviation_deg - UMBRALES.noise_threshold_deg
    )
    return (ratio**UMBRALES.score_exponent) * 100.0


# --- Cuerpos de perfil, para los parámetros posturales -----------------


_Punto = tuple[float, float]

_HOMBRO: _Punto = (0.5, 0.7)
_CADERA: _Punto = (0.5, 0.5)
_RODILLA: _Punto = (0.5, 0.3)
_TOBILLO: _Punto = (0.5, 0.1)
_MUNECA: _Punto = (0.5, 0.9)


def _perfil(
    *,
    muneca: _Punto | None = _MUNECA,
    hombro: _Punto | None = _HOMBRO,
    cadera: _Punto | None = _CADERA,
    rodilla: _Punto | None = _RODILLA,
    tobillo: _Punto | None = _TOBILLO,
    codo: _Punto | None = None,
    punta: _Punto | None = None,
    oreja: _Punto | None = None,
    visibilidad_oreja: float = VISIBLE,
    derecha: dict[int, _Punto] | None = None,
) -> LandmarkResult:
    # Cuerpo visto de perfil. Un punto a None queda fuera del fotograma.
    # La oreja, si no se indica otra posición, se alinea con el hombro.

    if oreja is None and hombro is not None:
        oreja = (hombro[0], hombro[1] + 0.1)

    puntos: dict[int, _Punto | None] = {
        _IDX_LEFT_WRIST: muneca,
        _IDX_LEFT_SHOULDER: hombro,
        _IDX_LEFT_HIP: cadera,
        _IDX_LEFT_KNEE: rodilla,
        _IDX_LEFT_ANKLE: tobillo,
        _IDX_LEFT_ELBOW: codo,
        _IDX_LEFT_FOOT_INDEX: punta,
    }

    landmarks = [
        Landmark(index=indice, x=punto[0], y=punto[1], z=0.0, visibility=VISIBLE)
        for indice, punto in puntos.items()
        if punto is not None
    ]

    if oreja is not None:
        landmarks.append(
            Landmark(
                index=_IDX_LEFT_EAR,
                x=oreja[0],
                y=oreja[1],
                z=0.0,
                visibility=visibilidad_oreja,
            )
        )

    for indice, punto in (derecha or {}).items():
        landmarks.append(
            Landmark(index=indice, x=punto[0], y=punto[1], z=0.0, visibility=VISIBLE)
        )

    return LandmarkResult(landmarks=landmarks, timestamp_ms=0)


def _arqueado(grados: float) -> LandmarkResult:
    # Cuerpo cuyo ángulo hombros-caderas-tobillos se desvía de los 180° en los grados pedidos.
    radianes = math.radians(grados)
    tobillo = (
        _CADERA[0] + 0.4 * math.sin(radianes),
        _CADERA[1] - 0.4 * math.cos(radianes),
    )
    rodilla = ((_CADERA[0] + tobillo[0]) / 2.0, (_CADERA[1] + tobillo[1]) / 2.0)
    return _perfil(rodilla=rodilla, tobillo=tobillo)


def _desplazamiento_para(proporcion: float, tronco_vertical: float) -> float:
    # Desplazamiento horizontal de las caderas que produce la proporción pedida entre la distancia al eje y la longitud del tronco.
    return tronco_vertical * proporcion / math.sqrt(1.0 - proporcion**2)


def _pelvis_desplazada(
    proporcion: float, *, tronco_vertical: float = 0.2
) -> LandmarkResult:
    # Caderas separadas del eje hombros-rodillas.
    desplazamiento = _desplazamiento_para(proporcion, tronco_vertical)
    centro = _CADERA[1]
    return _perfil(
        hombro=(0.5, centro + tronco_vertical),
        cadera=(0.5 + desplazamiento, centro),
        rodilla=(0.5, centro - tronco_vertical),
        tobillo=(0.5, centro - 2.0 * tronco_vertical),
        muneca=(0.5, centro + 2.0 * tronco_vertical),
    )


def _pierna(
    cadera: _Punto, *, flexion: float = 0.0, inclinacion: float = 0.0
) -> tuple[_Punto, _Punto]:
    # Rodilla y tobillo de una pierna con la flexión y la inclinación pedidas.
    muslo = math.radians(inclinacion)
    pantorrilla = math.radians(inclinacion + flexion)
    rodilla = (
        cadera[0] + 0.2 * math.sin(muslo),
        cadera[1] - 0.2 * math.cos(muslo),
    )
    tobillo = (
        rodilla[0] + 0.2 * math.sin(pantorrilla),
        rodilla[1] - 0.2 * math.cos(pantorrilla),
    )
    return rodilla, tobillo


# --- Cuerpos de frente, para los parámetros del plano frontal ----------
#

_ANCHURA_HOMBROS = 0.2
_CENTRO_HOMBROS: _Punto = (0.5, 0.70)


def _par(centro: _Punto, anchura: float, inclinacion: float = 0.0) -> tuple[_Punto, _Punto]:
    # Dos puntos homólogos separados por la anchura pedida y girados los
    # grados indicados respecto a la horizontal.
    radianes = math.radians(inclinacion)
    dx = anchura / 2.0 * math.cos(radianes)
    dy = anchura / 2.0 * math.sin(radianes)
    return (centro[0] - dx, centro[1] - dy), (centro[0] + dx, centro[1] + dy)


def _frontal(
    *,
    hombros: float = 0.0,
    caderas: float = 0.0,
    anchura_hombros: float = _ANCHURA_HOMBROS,
    separacion_orejas: float | tuple[float, float] | None = 0.044,
    visibilidad_orejas: float = VISIBLE,
    ocultos: tuple[int, ...] = (),
) -> LandmarkResult:
    # Cuerpo invertido visto de frente.

    hombro_izq, hombro_der = _par(_CENTRO_HOMBROS, anchura_hombros, hombros)
    cadera_izq, cadera_der = _par((0.5, 0.50), 0.14, caderas)
    muneca_izq, muneca_der = _par((0.5, 0.90), anchura_hombros)
    rodilla_izq, rodilla_der = _par((0.5, 0.30), 0.10)
    tobillo_izq, tobillo_der = _par((0.5, 0.10), 0.10)

    puntos: dict[int, _Punto] = {
        _IDX_LEFT_SHOULDER: hombro_izq,
        _IDX_RIGHT_SHOULDER: hombro_der,
        _IDX_LEFT_HIP: cadera_izq,
        _IDX_RIGHT_HIP: cadera_der,
        _IDX_LEFT_WRIST: muneca_izq,
        _IDX_RIGHT_WRIST: muneca_der,
        _IDX_LEFT_KNEE: rodilla_izq,
        _IDX_RIGHT_KNEE: rodilla_der,
        _IDX_LEFT_ANKLE: tobillo_izq,
        _IDX_RIGHT_ANKLE: tobillo_der,
    }

    landmarks = [
        Landmark(index=i, x=p[0], y=p[1], z=0.0, visibility=OCULTO if i in ocultos else VISIBLE)
        for i, p in puntos.items()
    ]

    if separacion_orejas is not None:
        if isinstance(separacion_orejas, tuple):
            sep_izq, sep_der = separacion_orejas
        else:
            sep_izq = sep_der = separacion_orejas
        for indice, hombro, sep in (
            (_IDX_LEFT_EAR, hombro_izq, sep_izq),
            (_IDX_RIGHT_EAR, hombro_der, sep_der),
        ):
            landmarks.append(
                Landmark(
                    index=indice,
                    x=hombro[0],
                    y=hombro[1] + sep,
                    z=0.0,
                    visibility=visibilidad_orejas,
                )
            )

    return LandmarkResult(landmarks=landmarks, timestamp_ms=0)


_ASIMETRIAS = {
    TechnicalError.LEFT_SHOULDER_LOW,
    TechnicalError.RIGHT_SHOULDER_LOW,
    TechnicalError.LEFT_HIP_LOW,
    TechnicalError.RIGHT_HIP_LOW,
}


def _piernas(flexion: float = 0.0, inclinacion: float = 0.0) -> LandmarkResult:
    rodilla, tobillo = _pierna(_CADERA, flexion=flexion, inclinacion=inclinacion)
    return _perfil(rodilla=rodilla, tobillo=tobillo)


# --- Líneas corporales y puntuación global -----------------------------


def test_un_cuerpo_vertical_obtiene_la_puntuacion_maxima():
    informe = _analizador().analyze(_recto())
    assert informe.score == pytest.approx(100.0)
    assert informe.is_evaluable


def test_se_miden_las_cuatro_lineas_corporales():
    informe = _analizador().analyze(_recto())
    assert set(informe.segment_deviations) == {
        "wrists_shoulders",
        "shoulders_hips",
        "hips_knees",
        "knees_ankles",
    }


def test_una_desviacion_dentro_de_la_zona_muerta_no_penaliza():
    # Por debajo del umbral de ruido la desviación se atribuye al estimador.
    informe = _analizador().analyze(_inclinado(1.5, "shoulders"))
    assert informe.segment_deviations["wrists_shoulders"] == pytest.approx(1.5, abs=0.01)
    assert informe.score == pytest.approx(100.0)


def test_una_desviacion_intermedia_penaliza_segun_su_peso():
    # Solo se inclina la línea muñecas-hombros, de peso 0.40.
    # El resto del cuerpo acompaña el desplazamiento y queda vertical.
    informe = _analizador().analyze(_inclinado(7.0, "shoulders"))

    esperada = 100.0 - 0.40 * _penalizacion_esperada(7.0)
    assert informe.score == pytest.approx(esperada, abs=0.1)


def test_una_desviacion_por_encima_del_maximo_satura_la_penalizacion():
    # A 30° la línea recibe los 100 puntos de penalización, no más.
    informe = _analizador().analyze(_inclinado(30.0, "shoulders"))
    assert informe.score == pytest.approx(60.0, abs=0.1)


def test_la_puntuacion_nunca_baja_de_cero():
    # Las cuatro líneas saturadas suman 100 de penalización.
    posiciones = {"wrists": 0.5, "shoulders": 0.8, "hips": 0.2, "knees": 0.8, "ankles": 0.2}
    informe = _analizador().analyze(_cuerpo(posiciones))
    assert informe.score == pytest.approx(0.0)


def test_la_penalizacion_se_normaliza_por_el_peso_disponible():
    analizador = _analizador()

    completo = analizador.analyze(_inclinado(7.0, "shoulders"))

    posiciones = {nombre: 0.5 for nombre in _PARES}
    desplazamiento = 0.2 * math.tan(math.radians(7.0))
    for nombre in ("shoulders", "hips", "knees", "ankles"):
        posiciones[nombre] = 0.5 + desplazamiento
    parcial = analizador.analyze(
        _cuerpo(posiciones, ausentes=("knees", "ankles"))
    )

    assert set(parcial.segment_deviations) == {"wrists_shoulders", "shoulders_hips"}

    # Con normalización, la línea desviada pesa 0.40/0.70 en lugar de 0.40.
    # La puntuación parcial es peor que la completa.
    esperada = 100.0 - (0.40 / 0.70) * _penalizacion_esperada(7.0)
    assert parcial.score == pytest.approx(esperada, abs=0.1)
    assert parcial.score < completo.score


def test_en_vista_lateral_basta_un_lado_de_cada_articulacion():
    # Los puntos homólogos se solapan y el más alejado queda ocluido.
    informe = _analizador().analyze(_recto(un_solo_lado=tuple(_PARES)))
    assert informe.is_evaluable
    assert informe.score == pytest.approx(100.0)
    assert len(informe.segment_deviations) == 4


def test_sin_la_linea_del_tronco_no_hay_puntuacion():
    informe = _analizador().analyze(_recto(ausentes=("hips",)))
    assert informe.score is None
    assert not informe.is_evaluable


def test_sin_las_munecas_no_hay_puntuacion():
    informe = _analizador().analyze(_recto(ausentes=("wrists",)))
    assert informe.score is None


def test_sin_las_piernas_si_hay_puntuacion():
    # Es la situación habitual cuando los pies salen del encuadre.
    informe = _analizador().analyze(_recto(ausentes=("knees", "ankles")))
    assert informe.is_evaluable
    assert set(informe.segment_deviations) == {"wrists_shoulders", "shoulders_hips"}


def test_un_tronco_implausible_invalida_la_medida():
    # Hombros y caderas prácticamente superpuestos.
    posiciones = {nombre: 0.5 for nombre in _PARES}
    cuerpo = _cuerpo(posiciones)
    comprimido = LandmarkResult(
        landmarks=[
            Landmark(
                index=lm.index,
                x=lm.x,
                y=0.7 if lm.index in (_IDX_LEFT_HIP, _IDX_RIGHT_HIP) else lm.y,
                z=lm.z,
                visibility=lm.visibility,
            )
            for lm in cuerpo.landmarks
        ],
        timestamp_ms=0,
    )

    assert _analizador().analyze(comprimido).score is None


def test_un_cuerpo_sin_puntos_no_produce_puntuacion():
    vacio = LandmarkResult(landmarks=[], timestamp_ms=0)
    informe = _analizador().analyze(vacio)
    assert informe.score is None
    assert informe.segment_deviations == {}


def test_la_desviacion_es_siempre_positiva():
    # La medida dice cuánto se inclina la línea, no hacia qué lado.
    izquierda = _analizador().analyze(_inclinado(-7.0, "shoulders"))
    derecha = _analizador().analyze(_inclinado(7.0, "shoulders"))
    assert izquierda.segment_deviations["wrists_shoulders"] == pytest.approx(
        derecha.segment_deviations["wrists_shoulders"], abs=0.01
    )
    assert izquierda.score == pytest.approx(derecha.score)


# --- Parámetros posturales: caso general -------------------------------


def test_un_cuerpo_recto_mide_todos_los_parametros_sin_desviacion():
    informe = _analizador().analyze(_perfil())

    assert set(informe.measurements) == _SAGITALES
    assert all(medida.severity == 0.0 for medida in informe.measurements.values())


def test_un_fotograma_no_evaluable_no_produce_mediciones():
    # Sin puntuación de alineación no hay postura que medir.
    informe = _analizador().analyze(_perfil(muneca=None))
    assert informe.score is None
    assert informe.measurements == {}


def test_las_severidades_se_exponen_para_el_selector():
    informe = _analizador().analyze(_arqueado(5.5))

    assert informe.severities[TechnicalError.BACK_ARCH] == pytest.approx(30.0)
    assert set(informe.severities) == set(informe.measurements)


def test_un_parametro_no_medible_no_aparece_con_severidad_nula():
    #  una severidad 0 afirmaría que la postura es correcta y desactivaría el error.
    informe = _analizador().analyze(_perfil(tobillo=None))

    assert TechnicalError.BACK_ARCH not in informe.measurements
    assert TechnicalError.LEGS_NOT_STRAIGHT not in informe.measurements
    assert informe.is_evaluable


def test_cada_medicion_acompana_el_umbral_que_se_le_aplico():
    informe = _analizador().analyze(_arqueado(10.0))
    medida = informe.measurements[TechnicalError.BACK_ARCH]

    assert medida.error_type is TechnicalError.BACK_ARCH
    assert medida.threshold_value == pytest.approx(8.0)
    assert medida.measured_value == pytest.approx(10.0, abs=0.01)


def test_la_medicion_se_convierte_en_el_error_detectado():
    informe = _analizador().analyze(_arqueado(10.0))
    detectado = informe.measurements[TechnicalError.BACK_ARCH].to_detected_error()

    assert detectado.error_type is TechnicalError.BACK_ARCH
    assert detectado.measured_value == pytest.approx(10.0, abs=0.01)
    assert detectado.threshold_value == pytest.approx(8.0)


# --- Arqueo dorsal ------------------------------------------------------


def test_el_arqueo_se_mide_como_desviacion_de_la_linea_recta():
    # Mitad entre la zona muerta (3°) y el umbral (8°).
    medida = _analizador().analyze(_arqueado(5.5)).measurements[
        TechnicalError.BACK_ARCH
    ]

    assert medida.measured_value == pytest.approx(5.5, abs=0.01)
    assert medida.severity == pytest.approx(30.0)


def test_un_arqueo_dentro_de_la_zona_muerta_se_mide_pero_no_puntua():
    medida = _analizador().analyze(_arqueado(2.0)).measurements[
        TechnicalError.BACK_ARCH
    ]

    assert medida.measured_value == pytest.approx(2.0, abs=0.01)
    assert medida.severity == 0.0


def test_un_arqueo_pronunciado_satura_la_severidad():
    medida = _analizador().analyze(_arqueado(20.0)).measurements[
        TechnicalError.BACK_ARCH
    ]
    assert medida.severity == pytest.approx(100.0)


def test_el_arqueo_necesita_los_tobillos():
    informe = _analizador().analyze(_perfil(tobillo=None))
    assert TechnicalError.BACK_ARCH not in informe.measurements


# --- Desplazamiento pélvico --------------------------------------------


def test_el_desplazamiento_pelvico_se_mide_respecto_al_eje_del_cuerpo():
    # Mitad entre la zona muerta (0.02) y el umbral (0.07).
    medida = _analizador().analyze(_pelvis_desplazada(0.045)).measurements[
        TechnicalError.PELVIS_POSITION
    ]

    assert medida.measured_value == pytest.approx(0.045, abs=0.001)
    assert medida.severity == pytest.approx(30.0)


def test_el_desplazamiento_pelvico_no_depende_del_tamano_del_atleta():
    # La normalización por la longitud del tronco hace la medida independiente de la estatura y de la distancia a la cámara.
    analizador = _analizador()

    cerca = analizador.analyze(_pelvis_desplazada(0.045, tronco_vertical=0.2))
    lejos = analizador.analyze(_pelvis_desplazada(0.045, tronco_vertical=0.1))

    assert cerca.measurements[TechnicalError.PELVIS_POSITION].measured_value == (
        pytest.approx(
            lejos.measurements[TechnicalError.PELVIS_POSITION].measured_value,
            abs=0.001,
        )
    )


def test_el_desplazamiento_pelvico_necesita_las_rodillas():
    informe = _analizador().analyze(_perfil(rodilla=None))
    assert TechnicalError.PELVIS_POSITION not in informe.measurements


# --- Cabeza adelantada --------------------------------------------------


def test_la_cabeza_adelantada_se_mide_respecto_al_hombro():
    # 0.013 sobre un tronco de 0.2 son 0.065, mitad entre la zona muerta (0.03) y el umbral (0.10).
    cuerpo = _perfil(oreja=(_HOMBRO[0] + 0.013, _HOMBRO[1] + 0.1))
    medida = _analizador().analyze(cuerpo).measurements[TechnicalError.HEAD_FORWARD]

    assert medida.measured_value == pytest.approx(0.065, abs=0.001)
    assert medida.severity == pytest.approx(30.0)


def test_se_elige_el_lado_de_la_cabeza_de_mayor_visibilidad():
    # La oreja izquierda apenas se distingue; la derecha, claramente.
    cuerpo = _perfil(
        oreja=(_HOMBRO[0] + 0.004, _HOMBRO[1] + 0.1),
        visibilidad_oreja=0.6,
        derecha={
            _IDX_RIGHT_SHOULDER: _HOMBRO,
            _IDX_RIGHT_EAR: (_HOMBRO[0] + 0.013, _HOMBRO[1] + 0.1),
        },
    )
    medida = _analizador().analyze(cuerpo).measurements[TechnicalError.HEAD_FORWARD]

    assert medida.measured_value == pytest.approx(0.065, abs=0.001)


def test_sin_orejas_visibles_no_se_mide_la_cabeza():
    informe = _analizador().analyze(_perfil(visibilidad_oreja=OCULTO))

    assert TechnicalError.HEAD_FORWARD not in informe.measurements
    # Los demás parámetros se siguen midiendo.
    assert TechnicalError.BACK_ARCH in informe.measurements


# --- Piernas no rectas --------------------------------------------------


def test_la_flexion_de_rodilla_se_mide_como_desviacion_de_la_extension():
    medida = _analizador().analyze(_piernas(flexion=7.0)).measurements[
        TechnicalError.LEGS_NOT_STRAIGHT
    ]

    assert medida.measured_value == pytest.approx(7.0, abs=0.01)
    # El umbral que acompaña a la medida identifica el defecto que ha prevalecido. 10° es el de la flexión de rodilla.
    assert medida.threshold_value == pytest.approx(10.0)
    assert medida.severity == pytest.approx(60.0 * 4.0 / 7.0)


def test_una_pierna_recta_pero_inclinada_tambien_es_un_defecto():
    # La rodilla está extendida, pero la pierna no prolonga el tronco.
    medida = _analizador().analyze(_piernas(inclinacion=5.25)).measurements[
        TechnicalError.LEGS_NOT_STRAIGHT
    ]

    assert medida.measured_value == pytest.approx(5.25, abs=0.01)
    assert medida.threshold_value == pytest.approx(8.0)
    assert medida.severity == pytest.approx(30.0)


def test_de_las_dos_piernas_manda_la_peor():
    # Corregir la pierna que está mejor no mejoraría la postura.
    rodilla_izq, tobillo_izq = _pierna(_CADERA, flexion=5.0)
    rodilla_der, tobillo_der = _pierna(_CADERA, flexion=8.0)

    cuerpo = _perfil(
        rodilla=rodilla_izq,
        tobillo=tobillo_izq,
        derecha={
            _IDX_RIGHT_HIP: _CADERA,
            _IDX_RIGHT_KNEE: rodilla_der,
            _IDX_RIGHT_ANKLE: tobillo_der,
        },
    )
    medida = _analizador().analyze(cuerpo).measurements[
        TechnicalError.LEGS_NOT_STRAIGHT
    ]

    assert medida.measured_value == pytest.approx(8.0, abs=0.01)


def test_las_piernas_necesitan_la_cadena_completa():
    informe = _analizador().analyze(_perfil(rodilla=None))
    assert TechnicalError.LEGS_NOT_STRAIGHT not in informe.measurements




# --- Parámetros del plano frontal --------------------------------------


def test_de_frente_se_miden_los_parametros_del_plano_frontal():
    informe = _analizador(ViewMode.FRONTAL).analyze(_frontal())

    assert set(informe.measurements) == _ASIMETRIAS | {TechnicalError.NO_SHRUG}


def test_una_postura_simetrica_no_presenta_asimetrias():
    informe = _analizador(ViewMode.FRONTAL).analyze(_frontal())

    for error in _ASIMETRIAS:
        assert informe.measurements[error].severity == 0.0


def test_la_asimetria_se_mide_en_grados_respecto_a_la_horizontal():
    # A mitad de camino entre la zona muerta (1.7°) y el umbral (8.6°).
    informe = _analizador(ViewMode.FRONTAL).analyze(_frontal(hombros=5.15))
    medida = informe.measurements[TechnicalError.RIGHT_SHOULDER_LOW]

    assert medida.measured_value == pytest.approx(5.15, abs=0.01)
    assert medida.severity == pytest.approx(30.0)


def test_se_senala_el_hombro_que_queda_mas_bajo_en_la_imagen():
    # En posición invertida, el lado más bajo es el que ha cedido hacia el suelo.
    analizador = _analizador(ViewMode.FRONTAL)

    derecho = analizador.analyze(_frontal(hombros=6.0)).measurements
    izquierdo = analizador.analyze(_frontal(hombros=-6.0)).measurements

    assert derecho[TechnicalError.RIGHT_SHOULDER_LOW].severity > 0.0
    assert derecho[TechnicalError.LEFT_SHOULDER_LOW].severity == 0.0
    assert izquierdo[TechnicalError.LEFT_SHOULDER_LOW].severity > 0.0
    assert izquierdo[TechnicalError.RIGHT_SHOULDER_LOW].severity == 0.0


def test_la_asimetria_devuelve_siempre_los_dos_errores_del_par():
    # el error contrario puede desactivarse cuando el atleta corrige pasándose al lado opuesto.
   
    informe = _analizador(ViewMode.FRONTAL).analyze(_frontal(hombros=20.0))

    assert TechnicalError.LEFT_SHOULDER_LOW in informe.measurements
    assert TechnicalError.RIGHT_SHOULDER_LOW in informe.measurements
    assert informe.measurements[TechnicalError.LEFT_SHOULDER_LOW].severity == 0.0


def test_la_magnitud_de_la_asimetria_describe_la_linea_no_el_lado():
    # Los dos errores del par comparten el valor medido y el umbral, porque la inclinación es una propiedad de la línea que une los dos puntos.
    medidas = _analizador(ViewMode.FRONTAL).analyze(_frontal(hombros=6.0)).measurements

    bajo = medidas[TechnicalError.RIGHT_SHOULDER_LOW]
    alto = medidas[TechnicalError.LEFT_SHOULDER_LOW]

    assert alto.measured_value == bajo.measured_value
    assert alto.threshold_value == bajo.threshold_value


def test_las_asimetrias_de_hombros_y_caderas_son_independientes():
    informe = _analizador(ViewMode.FRONTAL).analyze(_frontal(hombros=10.0))

    assert informe.measurements[TechnicalError.RIGHT_SHOULDER_LOW].severity > 0.0
    assert informe.measurements[TechnicalError.RIGHT_HIP_LOW].severity == 0.0
    assert informe.measurements[TechnicalError.LEFT_HIP_LOW].severity == 0.0


def test_la_asimetria_de_caderas_se_mide_igual_que_la_de_hombros():
    informe = _analizador(ViewMode.FRONTAL).analyze(_frontal(caderas=5.15))
    medida = informe.measurements[TechnicalError.RIGHT_HIP_LOW]

    assert medida.measured_value == pytest.approx(5.15, abs=0.01)
    assert medida.severity == pytest.approx(30.0)


def test_sin_los_dos_hombros_visibles_no_se_mide_su_asimetria():
    # De frente no se admite sustituir un lado por el otro.
    informe = _analizador(ViewMode.FRONTAL).analyze(
        _frontal(hombros=20.0, ocultos=(_IDX_RIGHT_SHOULDER,))
    )

    assert TechnicalError.LEFT_SHOULDER_LOW not in informe.measurements
    assert TechnicalError.RIGHT_SHOULDER_LOW not in informe.measurements
    # Las caderas siguen siendo evaluables.
    assert TechnicalError.LEFT_HIP_LOW in informe.measurements


def test_sin_las_dos_caderas_visibles_no_se_mide_su_asimetria():
    informe = _analizador(ViewMode.FRONTAL).analyze(
        _frontal(caderas=20.0, ocultos=(_IDX_LEFT_HIP,))
    )

    assert TechnicalError.LEFT_HIP_LOW not in informe.measurements
    assert TechnicalError.RIGHT_HIP_LOW not in informe.measurements
    assert TechnicalError.LEFT_SHOULDER_LOW in informe.measurements


def test_unos_hombros_demasiado_juntos_no_se_evaluan():
    informe = _analizador(ViewMode.FRONTAL).analyze(_frontal(anchura_hombros=0.01))

    assert TechnicalError.LEFT_SHOULDER_LOW not in informe.measurements
    assert TechnicalError.NO_SHRUG not in informe.measurements


# --- Activación escapular ----------------------------------------------


def test_la_falta_de_activacion_escapular_se_normaliza_por_la_anchura():
    # 0.052 sobre una anchura de 0.2 son 0.26, mitad entre la
    # zona muerta (0.22) y el umbral (0.30).
    informe = _analizador(ViewMode.FRONTAL).analyze(_frontal(separacion_orejas=0.052))
    medida = informe.measurements[TechnicalError.NO_SHRUG]

    assert medida.measured_value == pytest.approx(0.26, abs=0.001)
    assert medida.severity == pytest.approx(30.0)


def test_unos_hombros_cerca_de_las_orejas_no_producen_severidad():
    # Distancia pequeña entre oreja y hombro. la cintura escapular está elevada, que es la postura buscada.
    informe = _analizador(ViewMode.FRONTAL).analyze(_frontal(separacion_orejas=0.030))

    assert informe.measurements[TechnicalError.NO_SHRUG].severity == 0.0


def test_unos_hombros_hundidos_saturan_la_severidad():
    informe = _analizador(ViewMode.FRONTAL).analyze(_frontal(separacion_orejas=0.090))

    assert informe.measurements[TechnicalError.NO_SHRUG].severity == pytest.approx(100.0)


def test_se_promedian_los_dos_lados_de_la_activacion_escapular():
    # De frente ambas orejas son igual de visibles, así que promediarlas reduce el ruido

    informe = _analizador(ViewMode.FRONTAL).analyze(
        _frontal(separacion_orejas=(0.044, 0.060))
    )

    assert informe.measurements[TechnicalError.NO_SHRUG].measured_value == (
        pytest.approx(0.26, abs=0.001)
    )


def test_con_una_sola_oreja_visible_se_mide_con_ella():
    informe = _analizador(ViewMode.FRONTAL).analyze(
        _frontal(separacion_orejas=0.052, ocultos=(_IDX_RIGHT_EAR,))
    )

    assert informe.measurements[TechnicalError.NO_SHRUG].measured_value == (
        pytest.approx(0.26, abs=0.001)
    )


def test_sin_orejas_visibles_no_se_mide_la_activacion_escapular():
    informe = _analizador(ViewMode.FRONTAL).analyze(_frontal(separacion_orejas=None))

    assert TechnicalError.NO_SHRUG not in informe.measurements
    # Las asimetrías siguen midiéndose.
    assert TechnicalError.LEFT_SHOULDER_LOW in informe.measurements


def test_en_vista_frontal_no_se_miden_los_parametros_sagitales():
    # Un arqueo dorsal no es observable de frente: medirlo produciría un valor sin sentido físico.
    informe = _analizador(ViewMode.FRONTAL).analyze(_frontal())

    assert informe.is_evaluable
    for error in (
        TechnicalError.BACK_ARCH,
        TechnicalError.PELVIS_POSITION,
        TechnicalError.HEAD_FORWARD,
        TechnicalError.LEGS_NOT_STRAIGHT,
    ):
        assert error not in informe.measurements


def test_de_perfil_no_se_miden_los_parametros_del_plano_frontal():
    informe = _analizador(ViewMode.LATERAL).analyze(_frontal(hombros=20.0))

    for error in _ASIMETRIAS | {TechnicalError.NO_SHRUG}:
        assert error not in informe.measurements


def test_el_analizador_recuerda_su_vista():
    assert _analizador(ViewMode.FRONTAL).view_mode is ViewMode.FRONTAL


def test_al_cambiar_de_vista_cambian_los_parametros_medidos():
    analizador = _analizador(ViewMode.FRONTAL)
    cuerpo = _frontal(hombros=20.0)

    assert TechnicalError.RIGHT_SHOULDER_LOW in analizador.analyze(cuerpo).measurements

    analizador.set_view_mode(ViewMode.LATERAL)
    medidas = analizador.analyze(cuerpo).measurements

    assert TechnicalError.RIGHT_SHOULDER_LOW not in medidas
    assert TechnicalError.BACK_ARCH in medidas


def test_los_umbrales_no_tienen_valor_por_defecto():
    with pytest.raises(TypeError):
        AlignmentAnalyzer()


# --- Contrato con el selector de errores --------------------------------


def test_corregir_al_lado_contrario_desactiva_la_asimetria_anterior():
    # Si el lado que deja de estar bajo no se declarase con severidad nula, la histéresis lo mantendría activo
    from core.analysis.error_selection import ErrorSelector
    from core.config.thresholds import ErrorSelectionThresholds

    analizador = _analizador(ViewMode.FRONTAL)
    selector = ErrorSelector(
        ViewMode.FRONTAL,
        ErrorSelectionThresholds(min_severity_to_report=15.0, hysteresis_factor=0.7),
    )

    derecho = selector.select(analizador.analyze(_frontal(hombros=12.0)).severities)
    izquierdo = selector.select(analizador.analyze(_frontal(hombros=-12.0)).severities)
    nivelado = selector.select(analizador.analyze(_frontal()).severities)

    assert derecho == [TechnicalError.RIGHT_SHOULDER_LOW]
    assert izquierdo == [TechnicalError.LEFT_SHOULDER_LOW]
    assert nivelado == []



def _cadena(
    vertice: _Punto,
    direccion: float,
    desviacion: float,
    largo_primero: float,
    largo_ultimo: float,
) -> tuple[_Punto, _Punto]:
    # Los dos extremos de una cadena articular cuyo ángulo en el vértice es 180° menos la desviación pedida. 
    def extremo(grados: float, largo: float) -> _Punto:
        radianes = math.radians(grados)
        return (
            vertice[0] + largo * math.sin(radianes),
            vertice[1] + largo * math.cos(radianes),
        )

    return (
        extremo(direccion, largo_primero),
        extremo(direccion + 180.0 - desviacion, largo_ultimo),
    )


def _con_codos(flexion: float, flexion_derecha: float | None = None) -> LandmarkResult:
    # Cuerpo de perfil con el codo situado entre hombro y muñeca.
    codo = (0.5, 0.80)
    hombro, muneca = _cadena(codo, 180.0, flexion, 0.1, 0.1)
    cuerpo = _perfil(hombro=hombro, muneca=muneca, codo=codo)

    if flexion_derecha is None:
        return cuerpo

    codo_der = (0.5, 0.80)
    hombro_der, muneca_der = _cadena(codo_der, 180.0, flexion_derecha, 0.1, 0.1)
    return _perfil(
        hombro=hombro,
        muneca=muneca,
        codo=codo,
        derecha={
            _IDX_RIGHT_SHOULDER: hombro_der,
            _IDX_RIGHT_ELBOW: codo_der,
            _IDX_RIGHT_WRIST: muneca_der,
        },
    )


def _con_pies(
    desviacion: float,
    *,
    giro: float = 0.0,
    desviacion_derecha: float | None = None,
) -> LandmarkResult:
    # Cuerpo de perfil con la punta del pie.
    tobillo = _TOBILLO
    rodilla, punta = _cadena(tobillo, giro, desviacion, 0.2, 0.05)
    cuerpo = _perfil(rodilla=rodilla, tobillo=tobillo, punta=punta)

    if desviacion_derecha is None:
        return cuerpo

    _, punta_der = _cadena(tobillo, giro, desviacion_derecha, 0.2, 0.05)
    return _perfil(
        rodilla=rodilla,
        tobillo=tobillo,
        punta=punta,
        derecha={
            _IDX_RIGHT_KNEE: rodilla,
            _IDX_RIGHT_ANKLE: tobillo,
            _IDX_RIGHT_FOOT_INDEX: punta_der,
        },
    )


# --- Extensión del codo -------------------------------------------------


def test_un_codo_extendido_se_mide_sin_desviacion():
    medida = _analizador().analyze(_con_codos(0.0)).measurements[
        TechnicalError.ELBOW_NOT_EXTENDED
    ]

    assert medida.measured_value == pytest.approx(0.0, abs=0.01)
    assert medida.severity == 0.0


def test_la_flexion_del_codo_se_mide_como_desviacion_de_la_extension():
    # Mitad entre la zona muerta (3°) y el umbral (10°).
    medida = _analizador().analyze(_con_codos(6.5)).measurements[
        TechnicalError.ELBOW_NOT_EXTENDED
    ]

    assert medida.measured_value == pytest.approx(6.5, abs=0.01)
    assert medida.threshold_value == pytest.approx(10.0)
    assert medida.severity == pytest.approx(30.0)


def test_un_codo_muy_flexionado_satura_la_severidad():
    medida = _analizador().analyze(_con_codos(30.0)).measurements[
        TechnicalError.ELBOW_NOT_EXTENDED
    ]
    assert medida.severity == pytest.approx(100.0)


def test_de_los_dos_codos_manda_el_peor():
    medida = _analizador().analyze(_con_codos(5.0, 9.0)).measurements[
        TechnicalError.ELBOW_NOT_EXTENDED
    ]
    assert medida.measured_value == pytest.approx(9.0, abs=0.01)


def test_el_codo_necesita_hombro_codo_y_muneca():
    informe = _analizador().analyze(_perfil())
    assert TechnicalError.ELBOW_NOT_EXTENDED not in informe.measurements


def test_el_codo_se_mide_en_las_dos_vistas():
    for vista in (ViewMode.LATERAL, ViewMode.FRONTAL):
        informe = _analizador(vista).analyze(_con_codos(6.5))
        assert TechnicalError.ELBOW_NOT_EXTENDED in informe.measurements


# --- Extensión de los tobillos ------------------------------------------


def test_un_empeine_estirado_no_produce_severidad():
    medida = _analizador().analyze(_con_pies(25.0)).measurements[
        TechnicalError.FEET_NOT_EXTENDED
    ]

    assert medida.measured_value == pytest.approx(25.0, abs=0.01)
    assert medida.severity == 0.0


def test_un_pie_flexionado_se_senala():
    # Mitad entre la zona muerta (30°) y el umbral (45°).
    medida = _analizador().analyze(_con_pies(37.5)).measurements[
        TechnicalError.FEET_NOT_EXTENDED
    ]

    assert medida.measured_value == pytest.approx(37.5, abs=0.01)
    assert medida.threshold_value == pytest.approx(45.0)
    assert medida.severity == pytest.approx(30.0)


def test_un_pie_en_flexion_dorsal_satura_la_severidad():
    medida = _analizador().analyze(_con_pies(80.0)).measurements[
        TechnicalError.FEET_NOT_EXTENDED
    ]
    assert medida.severity == pytest.approx(100.0)


def test_la_medida_del_empeine_no_depende_de_la_orientacion_del_cuerpo():
    analizador = _analizador()

    medidas = [
        analizador.analyze(_con_pies(37.5, giro=giro)).measurements[
            TechnicalError.FEET_NOT_EXTENDED
        ]
        for giro in (0.0, 15.0, -25.0, 40.0)
    ]

    for medida in medidas:
        assert medida.measured_value == pytest.approx(37.5, abs=0.01)
        assert medida.severity == pytest.approx(medidas[0].severity)


def test_de_los_dos_pies_manda_el_peor():
    medida = _analizador().analyze(
        _con_pies(32.0, desviacion_derecha=42.0)
    ).measurements[TechnicalError.FEET_NOT_EXTENDED]

    assert medida.measured_value == pytest.approx(42.0, abs=0.01)


def test_los_pies_necesitan_rodilla_tobillo_y_punta():
    informe = _analizador().analyze(_perfil())
    assert TechnicalError.FEET_NOT_EXTENDED not in informe.measurements


def test_las_puntas_solo_se_miden_de_perfil():
    # La flexión plantar ocurre en el plano sagital.
    assert TechnicalError.FEET_NOT_EXTENDED in _analizador(
        ViewMode.LATERAL
    ).analyze(_con_pies(37.5)).measurements

    assert TechnicalError.FEET_NOT_EXTENDED not in _analizador(
        ViewMode.FRONTAL
    ).analyze(_con_pies(37.5)).measurements


def test_los_parametros_comunes_conviven_con_los_de_cada_vista():
    codo = (0.5, 0.80)
    hombro, muneca = _cadena(codo, 180.0, 6.5, 0.1, 0.1)
    _, punta = _cadena(_TOBILLO, 0.0, 37.5, 0.2, 0.05)

    informe = _analizador().analyze(
        _perfil(hombro=hombro, muneca=muneca, codo=codo, punta=punta)
    )

    assert TechnicalError.BACK_ARCH in informe.measurements
    assert TechnicalError.PELVIS_POSITION in informe.measurements
    assert informe.measurements[TechnicalError.ELBOW_NOT_EXTENDED].severity == (
        pytest.approx(30.0)
    )
    assert informe.measurements[TechnicalError.FEET_NOT_EXTENDED].severity == (
        pytest.approx(30.0)
    )


def test_el_analizador_funciona_con_el_archivo_de_umbrales_del_proyecto():
    from core.config.thresholds import DEFAULT_THRESHOLDS_PATH, load_thresholds

    umbrales = load_thresholds(DEFAULT_THRESHOLDS_PATH).alignment

    codo = (0.5, 0.80)
    hombro, muneca = _cadena(codo, 180.0, 6.5, 0.1, 0.1)
    _, punta = _cadena(_TOBILLO, 0.0, 37.5, 0.2, 0.05)

    esperados_de_perfil = {
        TechnicalError.BACK_ARCH,
        TechnicalError.PELVIS_POSITION,
        TechnicalError.HEAD_FORWARD,
        TechnicalError.LEGS_NOT_STRAIGHT,
        TechnicalError.FEET_NOT_EXTENDED,
        TechnicalError.ELBOW_NOT_EXTENDED,
    }

    for vista, cuerpo, esperados in (
        (
            ViewMode.LATERAL,
            _perfil(hombro=hombro, muneca=muneca, codo=codo, punta=punta),
            esperados_de_perfil,
        ),
        (
            ViewMode.FRONTAL,
            _frontal(hombros=6.0, caderas=4.0),
            _ASIMETRIAS | {TechnicalError.NO_SHRUG},
        ),
    ):
        informe = AlignmentAnalyzer(umbrales, vista).analyze(cuerpo)
        assert esperados.issubset(set(informe.measurements)), vista


def test_el_archivo_de_umbrales_declara_todos_los_parametros_que_se_miden():
    # Los nombres que el analizador busca deben ser los que exige el cargador.
    from core.config.thresholds import (
        DEFAULT_THRESHOLDS_PATH,
        PARAMETER_NAMES,
        load_thresholds,
    )

    parametros = load_thresholds(DEFAULT_THRESHOLDS_PATH).alignment.parameters

    assert set(parametros) == set(PARAMETER_NAMES)
