import json

import pytest

from core.feedback.message_catalog import (
    DEFAULT_CATALOG_PATH,
    NOT_ANALYZING_KEY,
    POSITIVE_KEY,
    MessageCatalogError,
    load_catalog,
    required_keys,
)
from core.models.analysis_result import TechnicalError

VALIDO = {clave: f"Texto de {clave}." for clave in required_keys()}


def _escribir(tmp_path, datos):
    ruta = tmp_path / "feedback_messages.json"
    ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    return ruta


def _sin(clave):
    datos = dict(VALIDO)
    del datos[clave]
    return datos



def test_un_catalogo_completo_se_acepta(tmp_path):
    catalogo = load_catalog(_escribir(tmp_path, VALIDO))
    assert catalogo.for_error(TechnicalError.BACK_ARCH).text == "Texto de back_arch."


def test_cada_error_tecnico_exige_su_mensaje():
    # El catálogo debe cubrir el enumerado completo.
    exigidas = set(required_keys())
    assert {error.value for error in TechnicalError} <= exigidas


def test_el_catalogo_exige_los_dos_mensajes_sin_error():
    exigidas = set(required_keys())
    assert POSITIVE_KEY in exigidas
    assert NOT_ANALYZING_KEY in exigidas


@pytest.mark.parametrize("clave", [error.value for error in TechnicalError])
def test_un_mensaje_de_error_ausente_se_rechaza(tmp_path, clave):
    with pytest.raises(MessageCatalogError, match=clave):
        load_catalog(_escribir(tmp_path, _sin(clave)))


def test_el_mensaje_positivo_ausente_se_rechaza(tmp_path):
    with pytest.raises(MessageCatalogError, match=POSITIVE_KEY):
        load_catalog(_escribir(tmp_path, _sin(POSITIVE_KEY)))


def test_el_aviso_de_no_evaluacion_ausente_se_rechaza(tmp_path):
    with pytest.raises(MessageCatalogError, match=NOT_ANALYZING_KEY):
        load_catalog(_escribir(tmp_path, _sin(NOT_ANALYZING_KEY)))


def test_un_mensaje_sobrante_se_rechaza(tmp_path):
    # Suele ser un error que ya no se emite, con su locución huérfana.
    datos = dict(VALIDO, shoulders_hips_misaligned="Alinea hombros y caderas.")

    with pytest.raises(MessageCatalogError, match="shoulders_hips_misaligned"):
        load_catalog(_escribir(tmp_path, datos))



def test_un_mensaje_vacio_se_rechaza(tmp_path):
    datos = dict(VALIDO, back_arch="   ")

    with pytest.raises(MessageCatalogError, match="vacío"):
        load_catalog(_escribir(tmp_path, datos))


def test_un_mensaje_que_no_es_texto_se_rechaza(tmp_path):
    datos = dict(VALIDO, back_arch=42)

    with pytest.raises(MessageCatalogError, match="cadena"):
        load_catalog(_escribir(tmp_path, datos))


def test_un_archivo_ausente_se_rechaza(tmp_path):
    with pytest.raises(MessageCatalogError, match="No se encuentra"):
        load_catalog(tmp_path / "no_esta.json")


def test_un_archivo_que_no_es_json_se_rechaza(tmp_path):
    ruta = tmp_path / "roto.json"
    ruta.write_text("{esto no es json", encoding="utf-8")

    with pytest.raises(MessageCatalogError, match="JSON"):
        load_catalog(ruta)


def test_una_raiz_que_no_es_objeto_se_rechaza(tmp_path):
    ruta = tmp_path / "lista.json"
    ruta.write_text('["uno"]', encoding="utf-8")

    with pytest.raises(MessageCatalogError, match="objeto"):
        load_catalog(ruta)



def test_el_audio_se_deriva_del_identificador_del_error(tmp_path):
    catalogo = load_catalog(_escribir(tmp_path, VALIDO))

    mensaje = catalogo.for_error(TechnicalError.LEFT_HIP_LOW)

    assert mensaje.audio_filename == "left_hip_low.mp3"


def test_se_declara_una_locucion_por_mensaje(tmp_path):
    catalogo = load_catalog(_escribir(tmp_path, VALIDO))

    assert len(catalogo.audio_filenames) == len(required_keys())
    assert len(set(catalogo.audio_filenames)) == len(catalogo.audio_filenames)



def test_el_catalogo_del_proyecto_es_valido():
    # Verifica el archivo que se despliega, y no solo uno de prueba.
    catalogo = load_catalog(DEFAULT_CATALOG_PATH)

    for error in TechnicalError:
        assert catalogo.for_error(error).text.strip()


def test_el_catalogo_del_proyecto_nombra_el_segmento_corporal():
    # Los mensajes identifican la parte del cuerpo y el sentido de la corrección.
    catalogo = load_catalog(DEFAULT_CATALOG_PATH)

    for error in TechnicalError:
        texto = catalogo.for_error(error).text
        assert len(texto.split()) >= 3