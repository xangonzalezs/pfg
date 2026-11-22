import pytest

from core.config.personalization import (
    CalibrationOutcome,
    NeutralAngles,
    PersonalizationStatus,
    build_calibrated,
)
from core.config.thresholds import (
    DEFAULT_THRESHOLDS_PATH,
    PERSONALIZABLE_PARAMETERS,
    AlignmentThresholds,
    ParameterThreshold,
    PersonalizationLimits,
    load_thresholds,
)

# Umbrales genéricos de los parámetros personalizables.
UMBRAL_RODILLA = 10.0
UMBRAL_ARQUEO = 8.0

BASE = AlignmentThresholds(
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
        "back_arch": ParameterThreshold(threshold=UMBRAL_ARQUEO, noise=3.0),
        "pelvis_shift": ParameterThreshold(threshold=0.07, noise=0.02),
        "head_forward": ParameterThreshold(threshold=0.10, noise=0.03),
        "knee_bend": ParameterThreshold(threshold=UMBRAL_RODILLA, noise=3.0),
        "leg_tilt": ParameterThreshold(threshold=8.0, noise=2.5),
        "shoulder_tilt": ParameterThreshold(threshold=8.6, noise=1.7),
        "hip_tilt": ParameterThreshold(threshold=8.6, noise=1.7),
        "shrug": ParameterThreshold(threshold=0.30, noise=0.22),
        "elbow_bend": ParameterThreshold(threshold=10.0, noise=3.0),
        "foot_extension": ParameterThreshold(threshold=45.0, noise=30.0),
    },
)

LIMITES = {
    "knee_bend": PersonalizationLimits(
        min_plausible_deg=160.0, max_plausible_deg=185.0, max_threshold_deg=30.0
    ),
    "back_arch": PersonalizationLimits(
        min_plausible_deg=165.0, max_plausible_deg=185.0, max_threshold_deg=20.0
    ),
    "elbow_bend": PersonalizationLimits(
        min_plausible_deg=165.0, max_plausible_deg=185.0, max_threshold_deg=20.0
    ),
}


def _derivar(**angulos) -> CalibrationOutcome:
    return build_calibrated(BASE, NeutralAngles(**angulos), LIMITES)


def _umbral(resultado: CalibrationOutcome, parametro: str) -> float:
    return resultado.thresholds.parameters[parametro].threshold



def test_un_neutro_recto_deja_los_umbrales_genericos():
    resultado = _derivar(knee_deg=180.0, back_arch_deg=180.0)

    assert _umbral(resultado, "knee_bend") == pytest.approx(UMBRAL_RODILLA)
    assert _umbral(resultado, "back_arch") == pytest.approx(UMBRAL_ARQUEO)
    assert not resultado.is_personalized


def test_una_rodilla_que_no_extiende_del_todo_recibe_mas_tolerancia():
    # Neutro de 170°: 10° de flexión residual que el atleta no puede corregir
    # el umbral pasa de 10° a 20°.
    resultado = _derivar(knee_deg=170.0)

    assert _umbral(resultado, "knee_bend") == pytest.approx(20.0)
    assert resultado.outcomes["knee_bend"].status is (
        PersonalizationStatus.PERSONALIZED
    )


def test_una_espalda_con_curvatura_natural_recibe_mas_tolerancia():
    resultado = _derivar(back_arch_deg=174.0)

    assert _umbral(resultado, "back_arch") == pytest.approx(14.0)
    assert resultado.outcomes["back_arch"].status is (
        PersonalizationStatus.PERSONALIZED
    )


def test_la_tolerancia_crece_con_la_desviacion_del_neutro():
    umbrales = [
        _umbral(_derivar(knee_deg=angulo), "knee_bend")
        for angulo in (180.0, 176.0, 172.0, 168.0, 164.0)
    ]
    assert umbrales == sorted(umbrales)


def test_la_personalizacion_nunca_endurece_el_umbral():
    resultado = _derivar(knee_deg=185.0, back_arch_deg=185.0)

    assert _umbral(resultado, "knee_bend") == pytest.approx(UMBRAL_RODILLA)
    assert _umbral(resultado, "back_arch") == pytest.approx(UMBRAL_ARQUEO)
    assert resultado.outcomes["knee_bend"].status is PersonalizationStatus.UNCHANGED


def test_cada_parametro_se_deriva_de_su_propio_angulo():
    resultado = _derivar(knee_deg=170.0, back_arch_deg=174.0)

    assert _umbral(resultado, "knee_bend") == pytest.approx(20.0)
    assert _umbral(resultado, "back_arch") == pytest.approx(14.0)


def test_el_arqueo_no_rebasa_su_limite_de_seguridad():
    # Por elevada que sea la curvatura natural, no se tolera un arqueo superior a 20°.
    resultado = _derivar(back_arch_deg=165.0)

    assert _umbral(resultado, "back_arch") == pytest.approx(20.0)
    assert resultado.outcomes["back_arch"].status is PersonalizationStatus.CAPPED


def test_el_limite_de_seguridad_se_distingue_de_la_personalizacion_normal():
    # El entrenador debe poder ver que la propuesta quedó recortada.
    recortado = _derivar(back_arch_deg=165.0).outcomes["back_arch"]
    normal = _derivar(back_arch_deg=174.0).outcomes["back_arch"]

    assert recortado.status is PersonalizationStatus.CAPPED
    assert normal.status is PersonalizationStatus.PERSONALIZED
    assert recortado.is_personalized and normal.is_personalized


def test_la_rodilla_queda_acotada_por_su_rango_de_plausibilidad():
    # Con el neutro más desviado que se admite (160°) el umbral llega a 30°.
    resultado = _derivar(knee_deg=160.0)
    assert _umbral(resultado, "knee_bend") == pytest.approx(30.0)



def test_un_angulo_fisiologicamente_improbable_se_descarta():
    # Más probable un error de detección que una anatomía real.
    resultado = _derivar(knee_deg=120.0)

    assert _umbral(resultado, "knee_bend") == pytest.approx(UMBRAL_RODILLA)
    assert resultado.outcomes["knee_bend"].status is (
        PersonalizationStatus.IMPLAUSIBLE
    )


def test_los_extremos_del_rango_si_se_admiten():
    assert _derivar(knee_deg=160.0).outcomes["knee_bend"].is_personalized
    assert (
        _derivar(knee_deg=185.0).outcomes["knee_bend"].status
        is PersonalizationStatus.UNCHANGED
    )


def test_cada_parametro_tiene_su_propio_rango():
    # 162° es verosímil para la rodilla y no para el arqueo dorsal.
    resultado = _derivar(knee_deg=162.0, back_arch_deg=162.0)

    assert resultado.outcomes["knee_bend"].is_personalized
    assert resultado.outcomes["back_arch"].status is (
        PersonalizationStatus.IMPLAUSIBLE
    )


def test_un_angulo_descartado_no_impide_personalizar_el_otro():
    resultado = _derivar(knee_deg=120.0, back_arch_deg=174.0)

    assert _umbral(resultado, "knee_bend") == pytest.approx(UMBRAL_RODILLA)
    assert _umbral(resultado, "back_arch") == pytest.approx(14.0)



def test_un_angulo_no_medido_conserva_el_umbral_generico():
    resultado = _derivar(knee_deg=170.0)

    assert _umbral(resultado, "back_arch") == pytest.approx(UMBRAL_ARQUEO)
    assert resultado.outcomes["back_arch"].status is (
        PersonalizationStatus.NOT_MEASURED
    )


def test_una_calibracion_sin_angulos_no_personaliza_nada():
    resultado = _derivar()

    assert resultado.thresholds.parameters == BASE.parameters
    assert not resultado.is_personalized
    assert resultado.personalized_parameters == ()


def test_no_medido_e_improbable_son_estados_distintos():
    # El entrenador necesita distinguir una captura incompleta de una medida que el sistema ha rechazado.
    sin_medir = _derivar().outcomes["knee_bend"]
    rechazado = _derivar(knee_deg=120.0).outcomes["knee_bend"]

    assert sin_medir.neutral_angle_deg is None
    assert rechazado.neutral_angle_deg == pytest.approx(120.0)
    assert sin_medir.status is not rechazado.status


def test_solo_cambian_los_parametros_personalizables():
    resultado = _derivar(knee_deg=165.0, back_arch_deg=170.0)
    derivados = resultado.thresholds.parameters

    for nombre, umbral in BASE.parameters.items():
        if nombre in ("knee_bend", "back_arch"):
            continue
        assert derivados[nombre] == umbral, nombre


def test_los_pesos_y_el_resto_de_la_configuracion_se_conservan():
    resultado = _derivar(knee_deg=170.0).thresholds

    assert resultado.segment_weights == BASE.segment_weights
    assert resultado.noise_threshold_deg == BASE.noise_threshold_deg
    assert resultado.max_segment_deviation_deg == BASE.max_segment_deviation_deg
    assert resultado.score_exponent == BASE.score_exponent
    assert resultado.min_trunk_length == BASE.min_trunk_length
    assert resultado.min_pair_width == BASE.min_pair_width


def test_la_zona_muerta_del_parametro_no_se_altera():
    # Solo se relaja el umbral; el ruido del estimador no depende del atleta.
    resultado = _derivar(knee_deg=170.0).thresholds

    assert resultado.parameters["knee_bend"].noise == (
        pytest.approx(BASE.parameters["knee_bend"].noise)
    )


def test_los_umbrales_de_partida_no_se_modifican():
    antes = dict(BASE.parameters)
    _derivar(knee_deg=165.0, back_arch_deg=170.0)
    assert BASE.parameters == antes


def test_el_umbral_derivado_sigue_superando_su_zona_muerta():
    # Condición que exige la curva de severidad para estar bien formada.
    for angulo in (160.0, 170.0, 180.0, 185.0):
        derivados = _derivar(knee_deg=angulo, back_arch_deg=max(165.0, angulo))
        for nombre in ("knee_bend", "back_arch"):
            umbral = derivados.thresholds.parameters[nombre]
            assert umbral.threshold > umbral.noise



def test_la_derivacion_funciona_con_la_configuracion_del_proyecto():
    umbrales = load_thresholds(DEFAULT_THRESHOLDS_PATH)

    resultado = build_calibrated(
        umbrales.alignment,
        NeutralAngles(knee_deg=170.0, back_arch_deg=172.0),
        umbrales.personalization,
    )

    assert resultado.is_personalized
    assert set(resultado.outcomes) == set(PERSONALIZABLE_PARAMETERS)



def test_un_codo_que_no_extiende_del_todo_recibe_mas_tolerancia():
    resultado = _derivar(elbow_deg=174.0)

    assert _umbral(resultado, "elbow_bend") == pytest.approx(16.0)
    assert resultado.outcomes["elbow_bend"].status is (
        PersonalizationStatus.PERSONALIZED
    )


def test_el_codo_tambien_tiene_limite_de_seguridad():
    # La flexión del codo desestabiliza la posición con independencia de la anatomía.
    resultado = _derivar(elbow_deg=165.0)

    assert _umbral(resultado, "elbow_bend") == pytest.approx(20.0)
    assert resultado.outcomes["elbow_bend"].status is PersonalizationStatus.CAPPED


def test_un_codo_que_hiperextiende_conserva_el_umbral_generico():
    resultado = _derivar(elbow_deg=185.0)

    assert _umbral(resultado, "elbow_bend") == pytest.approx(10.0)
    assert resultado.outcomes["elbow_bend"].status is (
        PersonalizationStatus.UNCHANGED
    )


def test_los_tres_angulos_se_derivan_de_forma_independiente():
    resultado = _derivar(knee_deg=170.0, back_arch_deg=174.0, elbow_deg=120.0)

    assert _umbral(resultado, "knee_bend") == pytest.approx(20.0)
    assert _umbral(resultado, "back_arch") == pytest.approx(14.0)
    assert _umbral(resultado, "elbow_bend") == pytest.approx(10.0)
    assert resultado.outcomes["elbow_bend"].status is (
        PersonalizationStatus.IMPLAUSIBLE
    )
