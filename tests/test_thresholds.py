import json
from pathlib import Path

import pytest

from core.config.thresholds import (
    DEFAULT_THRESHOLDS_PATH,
    PARAMETER_NAMES,
    PERSONALIZABLE_PARAMETERS,
    GenericThresholds,
    ThresholdConfigError,
    load_thresholds,
)

VALIDO = {
    "stability": {
        "window_size": 10,
        "instability_threshold": 0.063,
        "noise": 0.02,
    },
    "alignment": {
        "segment_weights": {
            "wrists_shoulders": 0.40,
            "shoulders_hips": 0.30,
            "hips_knees": 0.20,
            "knees_ankles": 0.10,
        },
        "noise_threshold_deg": 2.0,
        "max_segment_deviation_deg": 12.0,
        "score_exponent": 1.5,
        "min_trunk_length": 0.02,
        "min_pair_width": 0.02,
        "parameters": {
            "back_arch": {"threshold": 8.0, "noise": 3.0},
            "pelvis_shift": {"threshold": 0.07, "noise": 0.02},
            "head_forward": {"threshold": 0.10, "noise": 0.03},
            "knee_bend": {"threshold": 10.0, "noise": 3.0},
            "leg_tilt": {"threshold": 8.0, "noise": 2.5},
            "shoulder_tilt": {"threshold": 8.6, "noise": 1.7},
            "hip_tilt": {"threshold": 8.6, "noise": 1.7},
            "shrug": {"threshold": 0.30, "noise": 0.22},
            "elbow_bend": {"threshold": 10.0, "noise": 3.0},
            "foot_extension": {"threshold": 45.0, "noise": 30.0},
        },
    },
    "handstand": {
        "order_margin": 0.03,
        "min_body_length": 0.10,
        "max_tilt_deg": 20.0,
        "confirmation_frames": 9,
        "grace_frames": 5,
    },
    "calibration": {
        "min_visibility": 0.5,
        "min_frames": 10,
        "min_validity_rate": 0.5,
    },
    "error_selection": {
        "min_severity_to_report": 15.0,
        "hysteresis_factor": 0.7,
    },
    "feedback": {
        "confirmation_frames": 3,
        "grace_frames": 5,
        "repeat_cooldown_ms": 8000,
        "not_analyzing_cooldown_ms": 10000,
        "positive_score_threshold": 80.0,
    },
    "personalization": {
        "knee_bend": {
            "min_plausible_deg": 160.0,
            "max_plausible_deg": 185.0,
            "max_threshold_deg": 30.0,
        },
        "back_arch": {
            "min_plausible_deg": 165.0,
            "max_plausible_deg": 185.0,
            "max_threshold_deg": 20.0,
        },
        "elbow_bend": {
            "min_plausible_deg": 165.0,
            "max_plausible_deg": 185.0,
            "max_threshold_deg": 20.0,
        },
    },
}


def _escribir(tmp_path: Path, contenido, nombre: str = "umbrales.json") -> Path:
    ruta = tmp_path / nombre
    if isinstance(contenido, str):
        ruta.write_text(contenido, encoding="utf-8")
    else:
        ruta.write_text(json.dumps(contenido), encoding="utf-8")
    return ruta


def _sin(seccion: str, clave: str) -> dict:
    datos = json.loads(json.dumps(VALIDO))
    del datos[seccion][clave]
    return datos


def _con(seccion: str, clave: str, valor) -> dict:
    datos = json.loads(json.dumps(VALIDO))
    datos[seccion][clave] = valor
    return datos


def _pesos_con(**cambios) -> dict:
    datos = json.loads(json.dumps(VALIDO))
    datos["alignment"]["segment_weights"].update(cambios)
    return datos


def _parametro(nombre: str, **cambios) -> dict:
    datos = json.loads(json.dumps(VALIDO))
    datos["alignment"]["parameters"][nombre].update(cambios)
    return datos


def test_un_archivo_valido_produce_los_umbrales(tmp_path):
    umbrales = load_thresholds(_escribir(tmp_path, VALIDO))

    assert isinstance(umbrales, GenericThresholds)
    assert umbrales.stability.window_size == 10
    assert umbrales.stability.instability_threshold == pytest.approx(0.063)
    assert umbrales.alignment.noise_threshold_deg == pytest.approx(2.0)
    assert umbrales.alignment.max_segment_deviation_deg == pytest.approx(12.0)
    assert umbrales.alignment.score_exponent == pytest.approx(1.5)
    assert umbrales.alignment.min_trunk_length == pytest.approx(0.02)
    assert umbrales.alignment.segment_weights == {
        "wrists_shoulders": pytest.approx(0.40),
        "shoulders_hips": pytest.approx(0.30),
        "hips_knees": pytest.approx(0.20),
        "knees_ankles": pytest.approx(0.10),
    }


def test_se_leen_los_umbrales_de_cada_parametro_postural(tmp_path):
    umbrales = load_thresholds(_escribir(tmp_path, VALIDO))

    assert set(umbrales.alignment.parameters) == set(PARAMETER_NAMES)
    arqueo = umbrales.alignment.parameters["back_arch"]
    assert arqueo.threshold == pytest.approx(8.0)
    assert arqueo.noise == pytest.approx(3.0)


def test_los_umbrales_son_inmutables(tmp_path):
    # Una vez cargados, no se debe poder alterarlos.
    umbrales = load_thresholds(_escribir(tmp_path, VALIDO))

    with pytest.raises(Exception):
        umbrales.stability.window_size = 20


def test_el_archivo_del_proyecto_es_valido():
    umbrales = load_thresholds(DEFAULT_THRESHOLDS_PATH)
    assert umbrales.stability.window_size >= 2
    assert umbrales.stability.instability_threshold > 0.0
    assert len(umbrales.alignment.segment_weights) == 4
    assert umbrales.alignment.max_segment_deviation_deg > umbrales.alignment.noise_threshold_deg
    assert 0.0 < umbrales.error_selection.hysteresis_factor <= 1.0
    assert umbrales.error_selection.min_severity_to_report > 0.0


def test_un_factor_de_histeresis_mayor_que_uno_se_rechaza(tmp_path):
    ruta = _escribir(tmp_path, _con("error_selection", "hysteresis_factor", 1.5))
    with pytest.raises(ThresholdConfigError):
        load_thresholds(ruta)


def test_un_factor_de_histeresis_no_positivo_se_rechaza(tmp_path):
    ruta = _escribir(tmp_path, _con("error_selection", "hysteresis_factor", 0.0))
    with pytest.raises(ThresholdConfigError):
        load_thresholds(ruta)


def test_una_severidad_minima_fuera_de_rango_se_rechaza(tmp_path):
    for valor in (0.0, 101.0):
        ruta = _escribir(tmp_path, _con("error_selection", "min_severity_to_report", valor))
        with pytest.raises(ThresholdConfigError):
            load_thresholds(ruta)



def test_unos_pesos_que_no_suman_uno_se_rechazan(tmp_path):
    ruta = _escribir(tmp_path, _pesos_con(wrists_shoulders=0.50))
    with pytest.raises(ThresholdConfigError) as error:
        load_thresholds(ruta)
    assert "1.0" in str(error.value)


def test_un_peso_de_linea_ausente_se_rechaza(tmp_path):
    datos = json.loads(json.dumps(VALIDO))
    del datos["alignment"]["segment_weights"]["knees_ankles"]
    with pytest.raises(ThresholdConfigError) as error:
        load_thresholds(_escribir(tmp_path, datos))
    assert "knees_ankles" in str(error.value)


def test_una_linea_corporal_inventada_se_rechaza(tmp_path):
    ruta = _escribir(tmp_path, _pesos_con(hombros_codos=0.0))
    with pytest.raises(ThresholdConfigError) as error:
        load_thresholds(ruta)
    assert "hombros_codos" in str(error.value)


def test_un_peso_no_positivo_se_rechaza(tmp_path):
    ruta = _escribir(tmp_path, _pesos_con(knees_ankles=0.0, hips_knees=0.30))
    with pytest.raises(ThresholdConfigError):
        load_thresholds(ruta)


def test_un_maximo_que_no_supera_la_zona_muerta_se_rechaza(tmp_path):
    # Sin intervalo entre ruido y máximo no habría nada que graduar.
    ruta = _escribir(tmp_path, _con("alignment", "max_segment_deviation_deg", 2.0))
    with pytest.raises(ThresholdConfigError):
        load_thresholds(ruta)


def test_una_zona_muerta_negativa_se_rechaza(tmp_path):
    ruta = _escribir(tmp_path, _con("alignment", "noise_threshold_deg", -1.0))
    with pytest.raises(ThresholdConfigError):
        load_thresholds(ruta)


def test_un_exponente_no_positivo_se_rechaza(tmp_path):
    ruta = _escribir(tmp_path, _con("alignment", "score_exponent", 0.0))
    with pytest.raises(ThresholdConfigError):
        load_thresholds(ruta)


def test_una_anchura_minima_de_par_no_positiva_se_rechaza(tmp_path):
    ruta = _escribir(tmp_path, _con("alignment", "min_pair_width", 0.0))
    with pytest.raises(ThresholdConfigError):
        load_thresholds(ruta)


def test_una_longitud_de_tronco_no_positiva_se_rechaza(tmp_path):
    ruta = _escribir(tmp_path, _con("alignment", "min_trunk_length", 0.0))
    with pytest.raises(ThresholdConfigError):
        load_thresholds(ruta)


def test_un_archivo_inexistente_se_rechaza(tmp_path):
    with pytest.raises(ThresholdConfigError) as error:
        load_thresholds(tmp_path / "no_existe.json")
    assert "no_existe.json" in str(error.value)


def test_un_json_malformado_se_rechaza(tmp_path):
    ruta = _escribir(tmp_path, "{ esto no es json")
    with pytest.raises(ThresholdConfigError):
        load_thresholds(ruta)


def test_una_raiz_que_no_es_objeto_se_rechaza(tmp_path):
    ruta = _escribir(tmp_path, [1, 2, 3])
    with pytest.raises(ThresholdConfigError):
        load_thresholds(ruta)


def test_una_seccion_ausente_se_rechaza(tmp_path):
    ruta = _escribir(tmp_path, {})
    with pytest.raises(ThresholdConfigError) as error:
        load_thresholds(ruta)
    assert "stability" in str(error.value)


def test_una_seccion_que_no_es_objeto_se_rechaza(tmp_path):
    ruta = _escribir(tmp_path, {"stability": 10})
    with pytest.raises(ThresholdConfigError):
        load_thresholds(ruta)


def test_una_clave_ausente_se_rechaza_nombrandola(tmp_path):
    ruta = _escribir(tmp_path, _sin("stability", "instability_threshold"))
    with pytest.raises(ThresholdConfigError) as error:
        load_thresholds(ruta)
    assert "instability_threshold" in str(error.value)


def test_una_clave_desconocida_se_rechaza_nombrandola(tmp_path):
    ruta = _escribir(tmp_path, _con("stability", "window_sizee", 10))
    with pytest.raises(ThresholdConfigError) as error:
        load_thresholds(ruta)
    assert "window_sizee" in str(error.value)


def test_un_umbral_de_texto_se_rechaza(tmp_path):
    ruta = _escribir(tmp_path, _con("stability", "instability_threshold", "0.063"))
    with pytest.raises(ThresholdConfigError):
        load_thresholds(ruta)


def test_una_ventana_decimal_se_rechaza(tmp_path):
    ruta = _escribir(tmp_path, _con("stability", "window_size", 10.5))
    with pytest.raises(ThresholdConfigError):
        load_thresholds(ruta)


def test_un_booleano_no_se_acepta_como_numero(tmp_path):
    # En Python True es un entero.
    ruta = _escribir(tmp_path, _con("stability", "window_size", True))
    with pytest.raises(ThresholdConfigError):
        load_thresholds(ruta)


def test_una_ventana_demasiado_corta_se_rechaza(tmp_path):
    ruta = _escribir(tmp_path, _con("stability", "window_size", 1))
    with pytest.raises(ThresholdConfigError):
        load_thresholds(ruta)


def test_un_umbral_no_positivo_se_rechaza(tmp_path):
    ruta = _escribir(tmp_path, _con("stability", "instability_threshold", 0.0))
    with pytest.raises(ThresholdConfigError):
        load_thresholds(ruta)

    ruta = _escribir(tmp_path, _con("stability", "instability_threshold", -0.1))
    with pytest.raises(ThresholdConfigError):
        load_thresholds(ruta)


def test_un_umbral_entero_se_acepta_como_real(tmp_path):
    # JSON no distingue 1 de 1.0; escribir un entero no debe ser un error.
    ruta = _escribir(tmp_path, _con("stability", "instability_threshold", 1))
    umbrales = load_thresholds(ruta)
    assert umbrales.stability.instability_threshold == pytest.approx(1.0)


def test_la_seccion_de_parametros_es_obligatoria(tmp_path):
    ruta = _escribir(tmp_path, _sin("alignment", "parameters"))
    with pytest.raises(ThresholdConfigError):
        load_thresholds(ruta)


def test_un_parametro_ausente_se_rechaza_nombrandolo(tmp_path):
    datos = json.loads(json.dumps(VALIDO))
    del datos["alignment"]["parameters"]["pelvis_shift"]

    with pytest.raises(ThresholdConfigError, match="pelvis_shift"):
        load_thresholds(_escribir(tmp_path, datos))


def test_un_parametro_inventado_se_rechaza(tmp_path):
    datos = json.loads(json.dumps(VALIDO))
    datos["alignment"]["parameters"]["arqueo_dorsal"] = {
        "threshold": 8.0,
        "noise": 3.0,
    }

    with pytest.raises(ThresholdConfigError, match="arqueo_dorsal"):
        load_thresholds(_escribir(tmp_path, datos))


def test_un_umbral_que_no_supera_su_zona_muerta_se_rechaza(tmp_path):
    # Sin intervalo entre la zona muerta y el umbral no hay severidad que graduar: la medida pasaría de 0 a 100 de golpe.
    ruta = _escribir(tmp_path, _parametro("back_arch", threshold=3.0))
    with pytest.raises(ThresholdConfigError):
        load_thresholds(ruta)


def test_una_zona_muerta_negativa_en_un_parametro_se_rechaza(tmp_path):
    ruta = _escribir(tmp_path, _parametro("knee_bend", noise=-1.0))
    with pytest.raises(ThresholdConfigError):
        load_thresholds(ruta)


def test_una_clave_desconocida_en_un_parametro_se_rechaza(tmp_path):
    datos = json.loads(json.dumps(VALIDO))
    datos["alignment"]["parameters"]["leg_tilt"]["margen"] = 1.0

    with pytest.raises(ThresholdConfigError, match="margen"):
        load_thresholds(_escribir(tmp_path, datos))


def test_un_parametro_que_no_es_un_objeto_se_rechaza(tmp_path):
    datos = json.loads(json.dumps(VALIDO))
    datos["alignment"]["parameters"]["head_forward"] = 0.10

    with pytest.raises(ThresholdConfigError):
        load_thresholds(_escribir(tmp_path, datos))


def test_los_parametros_del_plano_frontal_se_leen_con_los_demas(tmp_path):
    umbrales = load_thresholds(_escribir(tmp_path, VALIDO)).alignment

    assert umbrales.parameters["shoulder_tilt"].threshold == pytest.approx(8.6)
    assert umbrales.parameters["hip_tilt"].noise == pytest.approx(1.7)
    assert umbrales.parameters["shrug"].threshold == pytest.approx(0.30)
    assert umbrales.min_pair_width == pytest.approx(0.02)


def test_la_zona_muerta_del_shrug_puede_estar_lejos_de_cero(tmp_path):
    # la razón oreja-hombro tiene un valor de referencia positivo. las orejas nunca llegan a coincidir con los hombros.
    umbrales = load_thresholds(_escribir(tmp_path, VALIDO)).alignment
    shrug = umbrales.parameters["shrug"]

    assert shrug.noise > 0.5 * shrug.threshold


def test_los_parametros_comunes_a_las_dos_vistas_se_leen_con_los_demas(tmp_path):
    parametros = load_thresholds(_escribir(tmp_path, VALIDO)).alignment.parameters

    assert parametros["elbow_bend"].threshold == pytest.approx(10.0)
    assert parametros["foot_extension"].threshold == pytest.approx(45.0)


def test_la_zona_muerta_del_empeine_tampoco_esta_cerca_de_cero(tmp_path):
    # El pie no llega a prolongar la pierna ni en flexión plantar completa. queda un ángulo anatómico irreducible.
    parametros = load_thresholds(_escribir(tmp_path, VALIDO)).alignment.parameters
    empeine = parametros["foot_extension"]

    assert empeine.noise > 0.5 * empeine.threshold


def test_el_archivo_del_proyecto_declara_todos_los_parametros():
    umbrales = load_thresholds(DEFAULT_THRESHOLDS_PATH)
    assert set(umbrales.alignment.parameters) == set(PARAMETER_NAMES)
    for limites in umbrales.alignment.parameters.values():
        assert limites.threshold > limites.noise >= 0.0



def test_se_leen_los_limites_de_personalizacion(tmp_path):
    limites = load_thresholds(_escribir(tmp_path, VALIDO)).personalization

    assert set(limites) == set(PERSONALIZABLE_PARAMETERS)
    assert limites["back_arch"].max_threshold_deg == pytest.approx(20.0)
    assert limites["knee_bend"].min_plausible_deg == pytest.approx(160.0)


def test_la_seccion_de_personalizacion_es_obligatoria(tmp_path):
    datos = json.loads(json.dumps(VALIDO))
    del datos["personalization"]

    with pytest.raises(ThresholdConfigError, match="personalization"):
        load_thresholds(_escribir(tmp_path, datos))


def test_un_parametro_no_personalizable_se_rechaza(tmp_path):
    datos = json.loads(json.dumps(VALIDO))
    datos["personalization"]["shrug"] = {
        "min_plausible_deg": 1.0,
        "max_plausible_deg": 2.0,
        "max_threshold_deg": 3.0,
    }

    with pytest.raises(ThresholdConfigError, match="shrug"):
        load_thresholds(_escribir(tmp_path, datos))


def test_un_rango_de_plausibilidad_invertido_se_rechaza(tmp_path):
    datos = json.loads(json.dumps(VALIDO))
    datos["personalization"]["knee_bend"]["min_plausible_deg"] = 190.0

    with pytest.raises(ThresholdConfigError):
        load_thresholds(_escribir(tmp_path, datos))


def test_un_techo_no_positivo_se_rechaza(tmp_path):
    datos = json.loads(json.dumps(VALIDO))
    datos["personalization"]["back_arch"]["max_threshold_deg"] = 0.0

    with pytest.raises(ThresholdConfigError):
        load_thresholds(_escribir(tmp_path, datos))


def test_un_techo_por_debajo_del_umbral_generico_se_rechaza(tmp_path):
    datos = json.loads(json.dumps(VALIDO))
    datos["personalization"]["back_arch"]["max_threshold_deg"] = 5.0

    with pytest.raises(ThresholdConfigError, match="genérico"):
        load_thresholds(_escribir(tmp_path, datos))


def test_una_clave_desconocida_en_los_limites_se_rechaza(tmp_path):
    datos = json.loads(json.dumps(VALIDO))
    datos["personalization"]["knee_bend"]["margen"] = 1.0

    with pytest.raises(ThresholdConfigError, match="margen"):
        load_thresholds(_escribir(tmp_path, datos))


def test_unos_limites_que_no_son_objeto_se_rechazan(tmp_path):
    datos = json.loads(json.dumps(VALIDO))
    datos["personalization"]["knee_bend"] = 170.0

    with pytest.raises(ThresholdConfigError):
        load_thresholds(_escribir(tmp_path, datos))


def test_el_archivo_del_proyecto_declara_los_limites_de_personalizacion():
    limites = load_thresholds(DEFAULT_THRESHOLDS_PATH).personalization
    parametros = load_thresholds(DEFAULT_THRESHOLDS_PATH).alignment.parameters

    assert set(limites) == set(PERSONALIZABLE_PARAMETERS)
    for nombre, limite in limites.items():
        assert limite.min_plausible_deg < limite.max_plausible_deg
        assert limite.max_threshold_deg >= parametros[nombre].threshold


def _con_ruta(ruta_clave: str, valor) -> dict:
    # Copia de VALIDO con una sola clave alterada. La ruta usa puntos.

    datos = json.loads(json.dumps(VALIDO))
    partes = ruta_clave.split(".")
    nodo = datos
    for parte in partes[:-1]:
        nodo = nodo[parte]
    nodo[partes[-1]] = valor
    return datos


# Cada guarda de validación con el valor que debe rechazar y parte del mensaje.
GUARDAS = [
    ("feedback.confirmation_frames", 0, "confirmation_frames"),
    ("feedback.grace_frames", -1, "grace_frames"),
    ("feedback.repeat_cooldown_ms", 0, "repeat_cooldown_ms"),
    ("feedback.not_analyzing_cooldown_ms", 0, "not_analyzing_cooldown_ms"),
    ("feedback.positive_score_threshold", 150.0, "positive_score_threshold"),
    ("handstand.order_margin", 0.0, "order_margin"),
    ("handstand.min_body_length", 0.0, "min_body_length"),
    ("handstand.max_tilt_deg", 95.0, "max_tilt_deg"),
    ("handstand.confirmation_frames", 0, "confirmation_frames"),
    ("handstand.grace_frames", -1, "grace_frames"),
    ("calibration.min_visibility", 1.5, "min_visibility"),
    ("calibration.min_frames", 0, "min_frames"),
    ("calibration.min_validity_rate", 2.0, "min_validity_rate"),
    ("stability.instability_threshold", 0.0, "instability_threshold"),
    ("stability.noise", -0.1, "noise"),
    ("alignment.parameters", "esto no es un objeto", "parameters"),
    ("alignment.segment_weights", "esto no es un objeto", "segment_weights"),
    ("personalization.knee_bend.max_plausible_deg", 300.0, "hiperextensión"),
    ("personalization.knee_bend.max_threshold_deg", 0.0, "max_threshold_deg"),
]


@pytest.mark.parametrize("clave, valor, mensaje", GUARDAS)
def test_un_valor_invalido_se_rechaza_al_cargar(tmp_path, clave, valor, mensaje):
    # una configuración mal formada no debe llegar al análisis.

    ruta = _escribir(tmp_path, _con_ruta(clave, valor))

    with pytest.raises(ThresholdConfigError, match=mensaje):
        load_thresholds(ruta)


def test_la_zona_muerta_de_estabilidad_no_puede_alcanzar_su_umbral(tmp_path):
    # Sin intervalo entre ambas no hay severidad que graduar.

    datos = _con_ruta("stability.noise", VALIDO["stability"]["instability_threshold"])
    ruta = _escribir(tmp_path, datos)

    with pytest.raises(ThresholdConfigError, match="debe ser menor que"):
        load_thresholds(ruta)


def test_un_rango_de_personalizacion_invertido_se_rechaza(tmp_path):
    # El mínimo debe quedar por debajo del máximo.

    datos = _con_ruta("personalization.knee_bend.min_plausible_deg", 190.0)
    ruta = _escribir(tmp_path, datos)

    with pytest.raises(ThresholdConfigError, match="debe ser menor que"):
        load_thresholds(ruta)


def test_un_archivo_que_no_existe_se_informa_como_tal(tmp_path):
    with pytest.raises(ThresholdConfigError, match="No se encuentra"):
        load_thresholds(tmp_path / "no_existe.json")


def test_un_directorio_en_lugar_de_archivo_se_informa_como_ilegible(tmp_path):
    # Cubre la rama de OSError distinta de archivo inexistente.

    carpeta = tmp_path / "umbrales.json"
    carpeta.mkdir()

    with pytest.raises(ThresholdConfigError, match="No se puede leer"):
        load_thresholds(carpeta)


def test_la_ausencia_de_los_pesos_de_segmento_se_informa(tmp_path):
    ruta = _escribir(tmp_path, _sin("alignment", "segment_weights"))

    with pytest.raises(ThresholdConfigError, match="segment_weights"):
        load_thresholds(ruta)