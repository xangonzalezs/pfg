import numpy as np
import pytest

from core.analysis import landmarks as lm
from core.models.landmark_result import Landmark, LandmarkResult
from ui import formatting, theme
from ui.skeleton import CONNECTIONS, draw_skeleton

ANCHO, ALTO = 128, 96


def _punto(indice, x=0.5, y=0.5, visibilidad=0.9):
    return Landmark(index=indice, x=x, y=y, z=0.0, visibility=visibilidad)


def _esqueleto(visibilidad=0.9):
    # Los catorce puntos que intervienen en los segmentos dibujados.

    indices = sorted({i for par in CONNECTIONS for i in par})
    return LandmarkResult(
        landmarks=[
            _punto(indice, x=0.3 + 0.02 * n, y=0.2 + 0.04 * n, visibilidad=visibilidad)
            for n, indice in enumerate(indices)
        ],
        timestamp_ms=0,
    )


def _fotograma():
    return np.zeros((ALTO, ANCHO, 3), dtype=np.uint8)


def _pintados(imagen):
    return int(np.count_nonzero(imagen.any(axis=2)))



@pytest.mark.parametrize(
    "puntuacion, etiqueta",
    [
        (100.0, "Correcta"),
        (80.0, "Correcta"),
        (79.9, "Aceptable"),
        (60.0, "Aceptable"),
        (45.0, "Mejorable"),
        (40.0, "Mejorable"),
        (39.9, "Deficiente"),
        (0.0, "Deficiente"),
    ],
)
def test_cada_puntuacion_cae_en_su_banda(puntuacion, etiqueta):
    assert theme.label_for_score(puntuacion) == etiqueta


def test_hay_exactamente_cuatro_bandas():
    assert len(theme.SCORE_BANDS) == 4


def test_las_bandas_van_de_mayor_a_menor_y_cubren_el_rango():
    minimos = [banda.minimum for banda in theme.SCORE_BANDS]

    assert minimos == sorted(minimos, reverse=True)
    assert minimos[-1] == 0.0


def test_una_puntuacion_fuera_de_rango_se_acota():
    assert theme.band_for_score(150.0) is theme.SCORE_BANDS[0]
    assert theme.band_for_score(-20.0) is theme.SCORE_BANDS[-1]


def test_sin_puntuacion_no_hay_banda():
    # La ausencia no es una banda. un cero significaría postura pésima.
    assert theme.band_for_score(None) is None
    assert theme.label_for_score(None) == "Sin evaluar"
    assert theme.color_for_score(None) == theme.COLOR_NO_SCORE_HEX


def test_cada_banda_tiene_su_etiqueta_y_su_color():
    # El color no puede ser el único portador de la información.
    etiquetas = {banda.label for banda in theme.SCORE_BANDS}
    colores = {banda.hex_color for banda in theme.SCORE_BANDS}

    assert len(etiquetas) == 4
    assert len(colores) == 4


def test_el_color_bgr_corresponde_al_hexadecimal():
    # OpenCV dibuja en BGR. los widgets usan hexadecimal. 
    # Deben ser el mismo color o el esqueleto y el número dirían cosas distintas.
    for banda in theme.SCORE_BANDS:
        rojo = int(banda.hex_color[1:3], 16)
        verde = int(banda.hex_color[3:5], 16)
        azul = int(banda.hex_color[5:7], 16)

        assert banda.bgr == (azul, verde, rojo)




def test_se_dibuja_el_esqueleto_detectado():
    pintado = draw_skeleton(_fotograma(), _esqueleto(), 75.0)

    assert _pintados(pintado) > 0


def test_no_se_altera_el_fotograma_recibido():
    # La capa de captura puede estar reutilizando el búfer.
    original = _fotograma()

    draw_skeleton(original, _esqueleto(), 75.0)

    assert _pintados(original) == 0


def test_sin_puntos_no_se_dibuja_nada():
    pintado = draw_skeleton(_fotograma(), LandmarkResult(landmarks=[]), 75.0)

    assert _pintados(pintado) == 0


def test_un_punto_poco_visible_no_se_dibuja():
    # Pintar una estimación poco fiable induciría a confiar en ella.
    pintado = draw_skeleton(_fotograma(), _esqueleto(visibilidad=0.1), 75.0)

    assert _pintados(pintado) == 0


def test_un_punto_fuera_del_encuadre_no_se_dibuja():
    # MediaPipe estima puntos fuera de [0, 1] cuando salen de la imagen.
    fuera = LandmarkResult(
        landmarks=[_punto(lm.IDX_LEFT_HIP, x=1.4, y=-0.3)], timestamp_ms=0
    )

    assert _pintados(draw_skeleton(_fotograma(), fuera, 75.0)) == 0


def test_el_color_del_esqueleto_sigue_a_la_puntuacion():
    buena = draw_skeleton(_fotograma(), _esqueleto(), 95.0)
    mala = draw_skeleton(_fotograma(), _esqueleto(), 20.0)

    assert not np.array_equal(buena, mala)


def test_el_color_dibujado_es_el_de_la_banda():
    pintado = draw_skeleton(_fotograma(), _esqueleto(), 95.0)
    presentes = {tuple(p) for p in pintado.reshape(-1, 3) if p.any()}

    assert theme.bgr_for_score(95.0) in presentes


def test_sin_puntuacion_se_dibuja_igualmente():
    # En preparación aún no hay puntuación y el encuadre debe verse.
    pintado = draw_skeleton(_fotograma(), _esqueleto(), None)

    assert _pintados(pintado) > 0


def test_se_dibujan_los_segmentos_que_el_sistema_mide():
    # Lo que se pinta debe ser lo que se analiza, no la topología completa.
    indices = {i for par in CONNECTIONS for i in par}

    assert lm.IDX_LEFT_WRIST in indices
    assert lm.IDX_RIGHT_FOOT_INDEX in indices
    assert len(CONNECTIONS) == 14




@pytest.mark.parametrize(
    "segundos, esperado",
    [
        (0.0, "0 s"),
        (1.4, "1 s"),
        (59.0, "59 s"),
        (60.0, "1 min"),
        (83.0, "1 min 23 s"),
        (120.0, "2 min"),
        (599.6, "10 min"),
    ],
)
def test_la_duracion_se_expresa_en_minutos_y_segundos(segundos, esperado):
    assert formatting.duration(segundos) == esperado


def test_una_duracion_ausente_se_marca_como_no_disponible():
    assert formatting.duration(None) == formatting.NOT_AVAILABLE
    assert formatting.duration(-3.0) == formatting.NOT_AVAILABLE


def test_la_puntuacion_lleva_un_decimal():
    assert formatting.score(78.456) == "78.5"


def test_una_sesion_sin_puntuacion_no_muestra_un_cero():
    assert formatting.score(None) == formatting.NOT_AVAILABLE


def test_el_porcentaje_no_lleva_decimales():
    assert formatting.percentage(52.5, 180.0) == "29 %"


def test_un_porcentaje_sobre_cero_no_se_calcula():
    assert formatting.percentage(1.0, 0.0) == formatting.NOT_AVAILABLE


def test_la_marca_se_muestra_en_hora_local():
    # Se persiste en UTC.
    from datetime import datetime, timedelta, timezone

    utc = datetime(2026, 3, 1, 10, 30, tzinfo=timezone.utc)
    mostrado = formatting.timestamp(utc.isoformat(timespec="seconds"))
    esperado = utc.astimezone().strftime("%d/%m/%Y %H:%M")

    assert mostrado == esperado


def test_la_fecha_sola_se_formatea_para_el_historico():
    assert formatting.day("2026-03-01T10:30:00+00:00").endswith("/2026")


@pytest.mark.parametrize("valor", [None, "", "no es una fecha", 42])
def test_una_marca_ilegible_no_rompe_la_pantalla(valor):
    assert formatting.timestamp(valor) == formatting.NOT_AVAILABLE
    assert formatting.day(valor) == formatting.NOT_AVAILABLE