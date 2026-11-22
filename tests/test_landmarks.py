import pytest

from core.analysis.landmarks import (
    DEFAULT_MIN_VISIBILITY,
    IDX_LEFT_HIP,
    IDX_LEFT_SHOULDER,
    IDX_RIGHT_HIP,
    IDX_RIGHT_SHOULDER,
    JOINT_PAIRS,
    as_point,
    joint_point,
    joint_points,
    visible,
    visible_pair,
)
from core.models.landmark_result import Landmark, LandmarkResult

VISIBLE = 0.9
OCULTO = 0.1


def _punto(index: int, x: float, y: float, visibilidad: float = VISIBLE) -> Landmark:
    return Landmark(index=index, x=x, y=y, z=0.0, visibility=visibilidad)


def _fotograma(*puntos: Landmark) -> LandmarkResult:
    return LandmarkResult(landmarks=list(puntos), timestamp_ms=0)


def _caderas(visibilidad_izq: float = VISIBLE, visibilidad_der: float = VISIBLE):
    return _fotograma(
        _punto(IDX_LEFT_HIP, 0.45, 0.5, visibilidad_izq),
        _punto(IDX_RIGHT_HIP, 0.55, 0.5, visibilidad_der),
    )



def test_un_punto_anatomico_se_reduce_a_sus_coordenadas():
    assert as_point(_punto(IDX_LEFT_HIP, 0.3, 0.7)) == (0.3, 0.7)



def test_un_punto_suficientemente_visible_se_devuelve():
    assert visible(_caderas(), IDX_LEFT_HIP) is not None


def test_un_punto_poco_visible_se_descarta():
    assert visible(_caderas(visibilidad_izq=OCULTO), IDX_LEFT_HIP) is None


def test_el_umbral_de_visibilidad_es_inclusivo():
    justo = _fotograma(_punto(IDX_LEFT_HIP, 0.5, 0.5, DEFAULT_MIN_VISIBILITY))
    assert visible(justo, IDX_LEFT_HIP) is not None


def test_el_umbral_de_visibilidad_puede_elevarse():
    assert visible(_caderas(), IDX_LEFT_HIP, 0.95) is None


def test_un_punto_ausente_del_fotograma_se_descarta():
    assert visible(_caderas(), IDX_LEFT_SHOULDER) is None



def test_un_par_completo_se_devuelve_entero():
    par = visible_pair(_caderas(), IDX_LEFT_HIP, IDX_RIGHT_HIP)
    assert par is not None
    assert par[0].index == IDX_LEFT_HIP


def test_un_par_incompleto_no_se_sustituye():
    par = visible_pair(
        _caderas(visibilidad_der=OCULTO), IDX_LEFT_HIP, IDX_RIGHT_HIP
    )
    assert par is None



def test_con_los_dos_lados_visibles_se_toma_el_punto_medio():
    assert joint_point(_caderas(), "hips") == pytest.approx((0.5, 0.5))


def test_con_un_solo_lado_visible_se_toma_ese_lado():
    # vista lateral.
    punto = joint_point(_caderas(visibilidad_der=OCULTO), "hips")
    assert punto == pytest.approx((0.45, 0.5))


def test_sin_ningun_lado_visible_no_hay_punto():
    sin_caderas = _caderas(visibilidad_izq=OCULTO, visibilidad_der=OCULTO)
    assert joint_point(sin_caderas, "hips") is None


def test_una_articulacion_desconocida_es_un_error_de_programacion():
    with pytest.raises(KeyError):
        joint_point(_caderas(), "codos")



def test_solo_se_devuelven_las_articulaciones_disponibles():
    cuerpo = _fotograma(
        _punto(IDX_LEFT_HIP, 0.45, 0.5),
        _punto(IDX_RIGHT_HIP, 0.55, 0.5),
        _punto(IDX_LEFT_SHOULDER, 0.45, 0.7),
        _punto(IDX_RIGHT_SHOULDER, 0.55, 0.7, OCULTO),
    )
    puntos = joint_points(cuerpo)

    assert set(puntos) == {"hips", "shoulders"}
    assert puntos["shoulders"] == pytest.approx((0.45, 0.7))


def test_un_fotograma_vacio_no_produce_articulaciones():
    assert joint_points(_fotograma()) == {}


def test_se_declaran_las_cinco_articulaciones_de_la_cadena():
    assert set(JOINT_PAIRS) == {"wrists", "shoulders", "hips", "knees", "ankles"}