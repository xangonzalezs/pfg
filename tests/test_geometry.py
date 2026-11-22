import math

import pytest

from core.analysis.geometry import (
    angle_at,
    centroid,
    deviation_from_horizontal,
    deviation_from_vertical,
    distance,
    distance_to_line,
    midpoint,
)


def test_el_punto_medio_equidista_de_los_extremos():
    medio = midpoint((0.0, 0.0), (1.0, 1.0))
    assert medio == pytest.approx((0.5, 0.5))


def test_el_punto_medio_de_dos_puntos_coincidentes_es_ese_punto():
    assert midpoint((0.3, 0.7), (0.3, 0.7)) == pytest.approx((0.3, 0.7))


def test_el_centroide_de_un_solo_punto_es_el_propio_punto():
    # Es el caso de la vista lateral, donde solo un lado resulta visible.
    assert centroid([(0.4, 0.6)]) == pytest.approx((0.4, 0.6))


def test_el_centroide_de_dos_puntos_coincide_con_su_punto_medio():
    puntos = [(0.2, 0.1), (0.6, 0.9)]
    assert centroid(puntos) == pytest.approx(midpoint(*puntos))


def test_el_centroide_promedia_las_dos_coordenadas():
    assert centroid([(0.0, 0.0), (0.3, 0.6), (0.6, 0.0)]) == pytest.approx((0.3, 0.2))


def test_un_conjunto_vacio_no_tiene_centroide():
    with pytest.raises(ValueError):
        centroid([])



def test_la_distancia_es_la_hipotenusa():
    assert distance((0.0, 0.0), (0.3, 0.4)) == pytest.approx(0.5)


def test_la_distancia_de_un_punto_a_si_mismo_es_nula():
    assert distance((0.5, 0.5), (0.5, 0.5)) == 0.0


def test_la_distancia_no_depende_del_orden():
    a, b = (0.1, 0.2), (0.8, 0.4)
    assert distance(a, b) == pytest.approx(distance(b, a))



def test_dos_segmentos_perpendiculares_forman_noventa_grados():
    assert angle_at((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)) == pytest.approx(90.0)


def test_tres_puntos_alineados_forman_ciento_ochenta_grados():
    # Es la referencia de la extensión completa. una articulación recta.
    assert angle_at((0.5, 0.5), (0.5, 0.3), (0.5, 0.7)) == pytest.approx(180.0)


def test_dos_segmentos_superpuestos_forman_cero_grados():
    assert angle_at((0.0, 0.0), (1.0, 0.0), (0.5, 0.0)) == pytest.approx(0.0)


def test_el_angulo_no_depende_del_orden_de_los_extremos():
    vertice, a, b = (0.5, 0.5), (0.7, 0.9), (0.2, 0.4)
    assert angle_at(vertice, a, b) == pytest.approx(angle_at(vertice, b, a))


def test_un_segmento_de_longitud_nula_deja_el_angulo_sin_definir():
    assert angle_at((0.5, 0.5), (0.5, 0.5), (0.2, 0.3)) is None
    assert angle_at((0.5, 0.5), (0.2, 0.3), (0.5, 0.5)) is None


def test_el_angulo_se_mantiene_en_su_intervalo():
    for grados in range(0, 181, 15):
        radianes = math.radians(grados)
        angulo = angle_at(
            (0.0, 0.0), (1.0, 0.0), (math.cos(radianes), math.sin(radianes))
        )
        assert angulo == pytest.approx(float(grados))



def test_un_segmento_vertical_no_se_desvia():
    assert deviation_from_vertical((0.5, 0.2), (0.5, 0.8)) == pytest.approx(0.0)


def test_un_segmento_horizontal_se_desvia_noventa_grados():
    assert deviation_from_vertical((0.2, 0.5), (0.8, 0.5)) == pytest.approx(90.0)


def test_la_desviacion_se_mide_en_grados_conocidos():
    # Cateto opuesto 1, adyacente 1: cuarenta y cinco grados.
    assert deviation_from_vertical((0.0, 0.0), (0.1, 0.1)) == pytest.approx(45.0)


def test_la_desviacion_es_siempre_positiva():
    # La medida dice cuánto se inclina el segmento, no hacia qué lado.
    izquierda = deviation_from_vertical((0.5, 0.3), (0.4, 0.7))
    derecha = deviation_from_vertical((0.5, 0.3), (0.6, 0.7))
    assert izquierda == pytest.approx(derecha)
    assert izquierda > 0.0


def test_un_segmento_de_longitud_nula_no_se_considera_inclinado():
    assert deviation_from_vertical((0.5, 0.5), (0.5, 0.5)) == 0.0



def test_un_segmento_horizontal_no_se_desvia_de_la_horizontal():
    assert deviation_from_horizontal((0.2, 0.5), (0.8, 0.5)) == pytest.approx(0.0)


def test_un_segmento_vertical_se_desvia_noventa_grados_de_la_horizontal():
    assert deviation_from_horizontal((0.5, 0.2), (0.5, 0.8)) == pytest.approx(90.0)


def test_una_diagonal_se_desvia_cuarenta_y_cinco_grados():
    assert deviation_from_horizontal((0.0, 0.0), (0.1, 0.1)) == pytest.approx(45.0)


def test_la_desviacion_horizontal_no_distingue_que_extremo_esta_mas_bajo():
    arriba = deviation_from_horizontal((0.3, 0.5), (0.7, 0.4))
    abajo = deviation_from_horizontal((0.3, 0.5), (0.7, 0.6))
    assert arriba == pytest.approx(abajo)
    assert arriba > 0.0


def test_las_dos_desviaciones_son_complementarias():
    # Un mismo segmento se desvía de la vertical y de la horizontal en ángulos que suman un recto.
    a, b = (0.2, 0.3), (0.7, 0.9)
    assert deviation_from_vertical(a, b) + deviation_from_horizontal(a, b) == (
        pytest.approx(90.0)
    )


def test_un_segmento_de_longitud_nula_tampoco_se_desvia_de_la_horizontal():
    assert deviation_from_horizontal((0.5, 0.5), (0.5, 0.5)) == 0.0



def test_un_punto_sobre_la_recta_esta_a_distancia_nula():
    assert distance_to_line((0.5, 0.5), (0.5, 0.2), (0.5, 0.8)) == pytest.approx(0.0)


def test_la_distancia_a_una_recta_vertical_es_la_separacion_horizontal():
    assert distance_to_line((0.6, 0.5), (0.5, 0.2), (0.5, 0.8)) == pytest.approx(0.1)


def test_la_distancia_se_mide_perpendicularmente_y_no_a_los_extremos():
    # El punto está más lejos de cada extremo que de la recta.
    recta_inicio, recta_fin = (0.0, 0.0), (1.0, 1.0)
    punto = (1.0, 0.0)
    assert distance_to_line(punto, recta_inicio, recta_fin) == pytest.approx(
        1.0 / math.sqrt(2.0)
    )


def test_la_distancia_a_la_recta_no_depende_del_lado():
    recta_inicio, recta_fin = (0.5, 0.2), (0.5, 0.8)
    izquierda = distance_to_line((0.4, 0.5), recta_inicio, recta_fin)
    derecha = distance_to_line((0.6, 0.5), recta_inicio, recta_fin)
    assert izquierda == pytest.approx(derecha)


def test_la_distancia_no_depende_de_como_se_oriente_la_recta():
    inicio, fin = (0.5, 0.2), (0.5, 0.8)
    punto = (0.65, 0.4)
    assert distance_to_line(punto, inicio, fin) == pytest.approx(
        distance_to_line(punto, fin, inicio)
    )


def test_una_recta_degenerada_se_trata_como_un_punto():
    assert distance_to_line((0.3, 0.4), (0.0, 0.0), (0.0, 0.0)) == pytest.approx(0.5)


def test_tres_puntos_casi_colineales_no_rompen_el_arcocoseno():
    # Con el segmento casi extendido, el coseno sale de [-1, 1] por redondeo.
    angulo = angle_at((0.5, 0.5), (0.500001, 0.500001), (0.500002, 0.500002))

    assert angulo == pytest.approx(0.0)


def test_el_angulo_nunca_se_sale_del_rango_valido():
    # Barrido sobre segmentos casi extendidos, en ambos sentidos.
    for k in range(1, 200):
        d = k * 1e-7
        mismo = angle_at((0.5, 0.5), (0.5 + d, 0.5 + d), (0.5 + 2 * d, 0.5 + 2 * d))
        opuesto = angle_at((0.5, 0.5), (0.5 + d, 0.5 + d), (0.5 - 2 * d, 0.5 - 2 * d))

        assert mismo is not None and 0.0 <= mismo <= 180.0
        assert opuesto is not None and 0.0 <= opuesto <= 180.0