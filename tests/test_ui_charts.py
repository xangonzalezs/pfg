import numpy as np
import pytest

from core.models.analysis_result import TechnicalError
from core.persistence.session_repository import ErrorOccurrence
from ui import charts, frames

ANCHO, ALTO = 320, 240


def _ocurrencia(tipo, offset=0.0):
    return ErrorOccurrence(
        error_type=tipo, measured_value=11.0, threshold_value=8.0, offset_s=offset
    )


def _fotograma(ancho=ANCHO, alto=ALTO):
    return np.zeros((alto, ancho, 3), dtype=np.uint8)



def test_un_fotograma_mas_ancho_se_ajusta_por_el_ancho():
    assert frames.fit_box((640, 480), (320, 480)) == (320, 240)


def test_un_fotograma_mas_alto_se_ajusta_por_el_alto():
    assert frames.fit_box((640, 480), (640, 240)) == (320, 240)


def test_se_conserva_la_proporcion():
    # Deformar la imagen falsearía los ángulos que el atleta ve.
    ancho, alto = frames.fit_box((1280, 720), (500, 500))

    assert ancho / alto == pytest.approx(1280 / 720, abs=0.01)


def test_un_recuadro_mayor_que_el_fotograma_lo_amplia():
    assert frames.fit_box((320, 240), (640, 480)) == (640, 480)


@pytest.mark.parametrize("tamano", [(0, 480), (640, 0), (-10, 10)])
def test_un_fotograma_sin_tamano_no_rompe_el_calculo(tamano):
    assert frames.fit_box(tamano, (320, 240)) == (frames.MIN_BOX, frames.MIN_BOX)


def test_un_recuadro_diminuto_se_acota():
    ancho, alto = frames.fit_box((640, 480), (1, 1))

    assert ancho >= 1 and alto >= 1



def test_el_fotograma_se_convierte_a_imagen():
    imagen = frames.to_image(_fotograma())

    assert imagen.size == (ANCHO, ALTO)


def test_la_conversion_pasa_de_bgr_a_rgb():
    # OpenCV entrega BGR y Tk espera RGB. sin la conversión el esqueleto verde se vería rojo.
    fotograma = _fotograma(2, 2)
    fotograma[:, :] = (255, 0, 0)          # azul en BGR

    assert frames.to_image(fotograma).getpixel((0, 0)) == (0, 0, 255)


def test_la_conversion_puede_redimensionar():
    imagen = frames.to_image(_fotograma(640, 480), size=(320, 320))

    assert imagen.size == (320, 240)


def test_el_espejo_invierte_el_fotograma():
    # En directo el atleta espera verse como en un espejo.
    fotograma = _fotograma(4, 2)
    fotograma[:, 0] = (255, 255, 255)

    reflejado = frames.mirror(fotograma)

    assert reflejado[0, 3].tolist() == [255, 255, 255]
    assert reflejado[0, 0].tolist() == [0, 0, 0]



def test_la_linea_tiene_un_punto_por_puntuacion():
    puntos = charts.score_polyline([50.0, 60.0, 70.0, 80.0], ANCHO, ALTO)

    assert len(puntos) == 4


def test_la_linea_recorre_el_ancho_disponible():
    puntos = charts.score_polyline([10.0, 90.0], ANCHO, ALTO, padding=8)

    assert puntos[0][0] == pytest.approx(8)
    assert puntos[-1][0] == pytest.approx(ANCHO - 8)


def test_una_puntuacion_alta_queda_arriba():
    # El cero abajo y el cien arriba, como se lee un gráfico.
    alta = charts.score_polyline([90.0], ANCHO, ALTO)[0]
    baja = charts.score_polyline([10.0], ANCHO, ALTO)[0]

    assert alta[1] < baja[1]


def test_la_escala_es_fija_de_cero_a_cien():
    # Usar el rango observado exageraría variaciones mínimas y haría incomparables dos sesiones.
    estrecha = charts.score_polyline([70.0, 72.0], ANCHO, ALTO)
    amplia = charts.score_polyline([10.0, 95.0], ANCHO, ALTO)

    recorrido_estrecho = abs(estrecha[0][1] - estrecha[1][1])
    recorrido_amplio = abs(amplia[0][1] - amplia[1][1])

    assert recorrido_estrecho < recorrido_amplio / 10


def test_una_sola_puntuacion_da_una_linea_horizontal():
    puntos = charts.score_polyline([65.0], ANCHO, ALTO)

    assert len(puntos) == 2
    assert puntos[0][1] == pytest.approx(puntos[1][1])


def test_sin_puntuaciones_no_hay_linea():
    assert charts.score_polyline([], ANCHO, ALTO) == []


def test_un_recuadro_demasiado_pequeno_no_dibuja():
    assert charts.score_polyline([50.0], 10, 10, padding=8) == []


def test_una_puntuacion_fuera_de_rango_se_acota():
    dentro = charts.score_polyline([100.0], ANCHO, ALTO)[0]
    fuera = charts.score_polyline([150.0], ANCHO, ALTO)[0]

    assert dentro[1] == pytest.approx(fuera[1])




def test_los_errores_se_ordenan_por_frecuencia():
    ocurrencias = [
        _ocurrencia(TechnicalError.BACK_ARCH),
        _ocurrencia(TechnicalError.INSTABILITY),
        _ocurrencia(TechnicalError.BACK_ARCH),
        _ocurrencia(TechnicalError.BACK_ARCH),
        _ocurrencia(TechnicalError.INSTABILITY),
        _ocurrencia(TechnicalError.HEAD_FORWARD),
    ]

    assert charts.error_counts(ocurrencias) == [
        (TechnicalError.BACK_ARCH, 3),
        (TechnicalError.INSTABILITY, 2),
        (TechnicalError.HEAD_FORWARD, 1),
    ]


def test_a_igual_frecuencia_el_orden_es_estable():
    # Dos sesiones iguales deben presentarse siempre igual.
    ocurrencias = [
        _ocurrencia(TechnicalError.INSTABILITY),
        _ocurrencia(TechnicalError.BACK_ARCH),
    ]

    primera = charts.error_counts(ocurrencias)
    segunda = charts.error_counts(list(reversed(ocurrencias)))

    assert primera == segunda


def test_se_limitan_a_los_mas_frecuentes():
    ocurrencias = [
        _ocurrencia(error)
        for error in (
            TechnicalError.BACK_ARCH,
            TechnicalError.INSTABILITY,
            TechnicalError.HEAD_FORWARD,
            TechnicalError.NO_SHRUG,
        )
    ]

    assert len(charts.top_errors(ocurrencias, limit=3)) == 3


def test_sin_errores_no_hay_recuento():
    assert charts.error_counts([]) == []
    assert charts.top_errors([]) == []


def test_un_limite_invalido_no_devuelve_nada():
    assert charts.top_errors([_ocurrencia(TechnicalError.BACK_ARCH)], limit=0) == []



def test_el_error_mas_frecuente_ocupa_todo_el_ancho():
    barras = charts.bar_widths(
        [(TechnicalError.BACK_ARCH, 6), (TechnicalError.INSTABILITY, 3)], 200
    )

    assert barras[0][2] == 200


def test_las_barras_son_proporcionales_al_maximo():
    # Comparar un error con otro, no su peso sobre el total.
    barras = charts.bar_widths(
        [(TechnicalError.BACK_ARCH, 6), (TechnicalError.INSTABILITY, 3)], 200
    )

    assert barras[1][2] == 100


def test_una_barra_nunca_desaparece():
    barras = charts.bar_widths(
        [(TechnicalError.BACK_ARCH, 500), (TechnicalError.INSTABILITY, 1)], 200
    )

    assert barras[1][2] >= 1


def test_sin_recuento_no_hay_barras():
    assert charts.bar_widths([], 200) == []