import pytest

from core.analysis.stability_analyzer import (
    ReferencePoint,
    StabilityAnalyzer,
    StabilityResult,
)
from core.models.analysis_result import TechnicalError
from core.models.landmark_result import Landmark, LandmarkResult

UMBRAL = 0.063
ZONA_MUERTA = 0.02
VENTANA = 10

_IDX_LEFT_SHOULDER = 11
_IDX_RIGHT_SHOULDER = 12
_IDX_LEFT_HIP = 23
_IDX_RIGHT_HIP = 24

VISIBLE = 0.9
OCULTO = 0.1


def _analizador(**kwargs) -> StabilityAnalyzer:
    opciones = {
        "window_size": VENTANA,
        "instability_threshold": UMBRAL,
        "instability_noise": ZONA_MUERTA,
    }
    opciones.update(kwargs)
    return StabilityAnalyzer(**opciones)


def _punto(index: int, x: float, y: float, visibilidad: float = VISIBLE) -> Landmark:
    return Landmark(index=index, x=x, y=y, z=0.0, visibility=visibilidad)


def _frame(*puntos: Landmark) -> LandmarkResult:
    return LandmarkResult(landmarks=list(puntos), timestamp_ms=0)


def _fotograma(
    x: float,
    y: float,
    *,
    referencia: ReferencePoint = ReferencePoint.HIPS,
    visibilidad: float = VISIBLE,
) -> LandmarkResult:
    if referencia is ReferencePoint.HIPS:
        izquierdo, derecho = _IDX_LEFT_HIP, _IDX_RIGHT_HIP
    else:
        izquierdo, derecho = _IDX_LEFT_SHOULDER, _IDX_RIGHT_SHOULDER

    return _frame(
        _punto(izquierdo, x - 0.05, y, visibilidad),
        _punto(derecho, x + 0.05, y, visibilidad),
    )


def _fotograma_lateral(x: float, y: float, *, cadera_lejana: float = OCULTO) -> LandmarkResult:
    return _frame(
        _punto(_IDX_LEFT_HIP, x, y, VISIBLE),
        _punto(_IDX_RIGHT_HIP, x, y, cadera_lejana),
    )


def _alimentar(analizador: StabilityAnalyzer, posiciones) -> StabilityResult:
    resultado = None
    for x, y in posiciones:
        resultado = analizador.update(_fotograma(x, y))
    return resultado


def _oscilacion(amplitud: float, n: int = VENTANA):
    return [(0.5 + amplitud if i % 2 else 0.5 - amplitud, 0.5) for i in range(n)]


def test_un_centroide_inmovil_no_produce_inestabilidad():
    resultado = _alimentar(_analizador(), [(0.5, 0.5)] * VENTANA)
    assert resultado.dispersion == pytest.approx(0.0)
    assert not resultado.is_unstable


def test_una_oscilacion_por_debajo_del_umbral_no_es_inestabilidad():
    resultado = _alimentar(_analizador(), _oscilacion(0.05))
    assert resultado.dispersion == pytest.approx(0.05, abs=1e-6)
    assert not resultado.is_unstable


def test_una_oscilacion_por_encima_del_umbral_si_lo_es():
    resultado = _alimentar(_analizador(), _oscilacion(0.07))
    assert resultado.dispersion == pytest.approx(0.07, abs=1e-6)
    assert resultado.is_unstable


def test_el_resultado_expone_el_umbral_aplicado():
    resultado = _alimentar(_analizador(), _oscilacion(0.07))
    assert resultado.threshold == UMBRAL


def test_el_primer_fotograma_no_es_evaluable():
    resultado = _analizador().update(_fotograma(0.5, 0.5))
    assert resultado.dispersion is None
    assert not resultado.is_evaluable
    assert not resultado.is_unstable
    assert resultado.history_size == 1


def test_con_las_dos_caderas_visibles_se_prefiere_el_par():
    resultado = _analizador().update(_fotograma(0.5, 0.5))
    assert resultado.reference is ReferencePoint.HIPS


def test_en_vista_lateral_basta_una_cadera():
    analizador = _analizador()
    for _ in range(VENTANA):
        resultado = analizador.update(_fotograma_lateral(0.5, 0.5))
    assert resultado.reference is ReferencePoint.LEFT_HIP
    assert resultado.is_evaluable
    assert resultado.dispersion == pytest.approx(0.0)


def test_en_vista_lateral_se_detecta_la_oscilacion():
    analizador = _analizador()
    for i in range(VENTANA):
        x = 0.5 + 0.07 if i % 2 else 0.5 - 0.07
        resultado = analizador.update(_fotograma_lateral(x, 0.5))
    assert resultado.dispersion == pytest.approx(0.07, abs=1e-6)
    assert resultado.is_unstable


def test_el_parpadeo_de_la_cadera_lejana_no_reinicia_la_ventana():
    analizador = _analizador()
    for i in range(VENTANA):
        lejana = VISIBLE if i % 2 else OCULTO
        resultado = analizador.update(_fotograma_lateral(0.5, 0.5, cadera_lejana=lejana))

    assert resultado.reference is ReferencePoint.LEFT_HIP
    assert resultado.history_size == VENTANA
    assert not resultado.is_unstable


def test_sin_caderas_visibles_se_recurre_a_los_hombros():
    analizador = _analizador()
    sin_caderas = _frame(
        _punto(_IDX_LEFT_HIP, 0.45, 0.5, OCULTO),
        _punto(_IDX_RIGHT_HIP, 0.55, 0.5, OCULTO),
        _punto(_IDX_LEFT_SHOULDER, 0.45, 0.3),
        _punto(_IDX_RIGHT_SHOULDER, 0.55, 0.3),
    )
    resultado = analizador.update(sin_caderas)
    assert resultado.reference is ReferencePoint.SHOULDERS
    assert resultado.history_size == 1


def test_sin_ningun_punto_visible_el_fotograma_no_se_acumula():
    analizador = _analizador()
    analizador.update(_fotograma(0.5, 0.5))

    resultado = analizador.update(_fotograma(0.5, 0.5, visibilidad=OCULTO))

    assert resultado.dispersion is None
    assert not resultado.is_evaluable
    assert resultado.history_size == 1


def test_cambiar_de_referencia_vacia_la_ventana():
    analizador = _analizador()
    _alimentar(analizador, [(0.5, 0.6)] * 5)
    assert analizador.reference is ReferencePoint.HIPS

    resultado = analizador.update(
        _fotograma(0.5, 0.3, referencia=ReferencePoint.SHOULDERS)
    )

    assert resultado.reference is ReferencePoint.SHOULDERS
    assert resultado.history_size == 1
    assert not resultado.is_unstable


def test_la_referencia_en_uso_se_conserva_aunque_reaparezca_otra_mejor():
    analizador = _analizador()
    for _ in range(3):
        analizador.update(_fotograma_lateral(0.5, 0.5))
    assert analizador.reference is ReferencePoint.LEFT_HIP

    for _ in range(3):
        resultado = analizador.update(_fotograma_lateral(0.5, 0.5, cadera_lejana=VISIBLE))

    assert resultado.reference is ReferencePoint.LEFT_HIP
    assert resultado.history_size == 6


def test_una_interrupcion_breve_conserva_la_ventana():
    analizador = _analizador(max_missing_frames=5)
    _alimentar(analizador, [(0.5, 0.5)] * 6)

    for _ in range(3):
        analizador.update(_fotograma(0.5, 0.5, visibilidad=OCULTO))

    assert analizador.history_size == 6


def test_una_interrupcion_prolongada_vacia_la_ventana():
    analizador = _analizador(max_missing_frames=5)
    _alimentar(analizador, [(0.5, 0.5)] * 6)

    for _ in range(6):
        analizador.update(_fotograma(0.5, 0.5, visibilidad=OCULTO))

    assert analizador.history_size == 0
    assert analizador.reference is None


def test_la_ventana_no_crece_por_encima_de_su_tamano():
    analizador = _analizador()
    _alimentar(analizador, [(0.5, 0.5)] * (VENTANA + 4))
    assert analizador.history_size == VENTANA


def test_reset_vacia_la_ventana_y_olvida_la_referencia():
    analizador = _analizador()
    _alimentar(analizador, [(0.5, 0.5)] * 4)

    analizador.reset()

    assert analizador.history_size == 0
    assert analizador.reference is None


def test_la_ventana_deslizante_olvida_las_posiciones_antiguas():
    analizador = _analizador()
    _alimentar(analizador, _oscilacion(0.07))
    resultado = _alimentar(analizador, [(0.5, 0.5)] * VENTANA)
    assert resultado.dispersion == pytest.approx(0.0)
    assert not resultado.is_unstable


def test_no_se_admite_una_configuracion_invalida():
    with pytest.raises(ValueError):
        StabilityAnalyzer(
            window_size=1, instability_threshold=UMBRAL, instability_noise=ZONA_MUERTA
        )
    with pytest.raises(ValueError):
        StabilityAnalyzer(
            window_size=VENTANA, instability_threshold=0.0, instability_noise=ZONA_MUERTA
        )


def test_una_zona_muerta_que_alcanza_el_umbral_se_rechaza():
    # Sin intervalo entre la zona muerta y el umbral no hay severidad que graduar: la medida pasaría de 0 a 100 de golpe.
    with pytest.raises(ValueError):
        StabilityAnalyzer(
            window_size=VENTANA, instability_threshold=UMBRAL, instability_noise=UMBRAL
        )
    with pytest.raises(ValueError):
        StabilityAnalyzer(
            window_size=VENTANA, instability_threshold=UMBRAL, instability_noise=-0.01
        )


def test_los_umbrales_no_tienen_valor_por_defecto():
    with pytest.raises(TypeError):
        StabilityAnalyzer()



def test_el_resultado_expresa_la_inestabilidad_como_una_medicion():
    # La inestabilidad recorre el mismo camino que los demás errores
    resultado = _alimentar(_analizador(), _oscilacion(0.07))
    medicion = resultado.measurement

    assert medicion is not None
    assert medicion.error_type is TechnicalError.INSTABILITY
    assert medicion.measured_value == pytest.approx(0.07, abs=1e-6)
    assert medicion.threshold_value == UMBRAL


def test_una_dispersion_dentro_de_la_zona_muerta_no_produce_severidad():
    resultado = _alimentar(_analizador(), _oscilacion(0.015))
    assert resultado.measurement.severity == 0.0
    assert not resultado.is_unstable


def test_la_severidad_crece_entre_la_zona_muerta_y_el_umbral():
    # A mitad de camino entre 0.02 y 0.063, la mitad de 60.
    medio = (ZONA_MUERTA + UMBRAL) / 2.0
    resultado = _alimentar(_analizador(), _oscilacion(medio))
    assert resultado.measurement.severity == pytest.approx(30.0, abs=0.1)


def test_alcanzado_el_umbral_la_severidad_es_sesenta():
    resultado = _alimentar(_analizador(), _oscilacion(UMBRAL))
    assert resultado.measurement.severity == pytest.approx(60.0, abs=0.1)


def test_una_oscilacion_muy_amplia_satura_la_severidad():
    resultado = _alimentar(_analizador(), _oscilacion(0.3))
    assert resultado.measurement.severity == pytest.approx(100.0)


def test_un_fotograma_no_evaluable_no_produce_medicion():
    #una severidad nula desactivaría por histéresis un aviso en curso ante una pérdida momentánea de visibilidad.
    resultado = _analizador().update(_fotograma(0.5, 0.5))

    assert not resultado.is_evaluable
    assert resultado.measurement is None


def test_la_medicion_se_convierte_en_el_error_detectado():
    resultado = _alimentar(_analizador(), _oscilacion(0.07))
    detectado = resultado.measurement.to_detected_error()

    assert detectado.error_type is TechnicalError.INSTABILITY
    assert detectado.measured_value == pytest.approx(0.07, abs=1e-6)
    assert detectado.threshold_value == UMBRAL


def test_el_booleano_y_la_severidad_coinciden_en_el_umbral():
    analizador = _analizador()
    por_debajo = _alimentar(analizador, _oscilacion(UMBRAL - 0.01))
    assert not por_debajo.is_unstable
    assert por_debajo.measurement.severity < 60.0

    analizador.reset()
    por_encima = _alimentar(analizador, _oscilacion(UMBRAL + 0.01))
    assert por_encima.is_unstable
    assert por_encima.measurement.severity > 60.0


def test_la_inestabilidad_recibe_la_histeresis_como_los_demas_errores():
    from core.analysis.error_selection import ErrorSelector
    from core.config.thresholds import ErrorSelectionThresholds
    from core.models.view_mode import ViewMode

    analizador = _analizador()
    selector = ErrorSelector(
        ViewMode.LATERAL,
        ErrorSelectionThresholds(min_severity_to_report=15.0, hysteresis_factor=0.7),
    )

    def activos(amplitud: float) -> list[TechnicalError]:
        resultado = _alimentar(analizador, _oscilacion(amplitud))
        medicion = resultado.measurement
        severidades = {} if medicion is None else {
            TechnicalError.INSTABILITY: medicion.severity
        }
        return selector.select(severidades)

    assert activos(0.010) == []
    assert activos(0.040) == [TechnicalError.INSTABILITY]
    # Por debajo del mínimo de activación pero por encima del de desactivación
    assert activos(0.030) == [TechnicalError.INSTABILITY]
    assert activos(0.015) == []
