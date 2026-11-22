import math

import pytest

from core.analysis.landmarks import (
    IDX_LEFT_ANKLE,
    IDX_LEFT_ELBOW,
    IDX_LEFT_HIP,
    IDX_LEFT_KNEE,
    IDX_LEFT_SHOULDER,
    IDX_LEFT_WRIST,
    IDX_RIGHT_ANKLE,
    IDX_RIGHT_ELBOW,
    IDX_RIGHT_HIP,
    IDX_RIGHT_KNEE,
    IDX_RIGHT_SHOULDER,
    IDX_RIGHT_WRIST,
)
from core.calibration.neutral_pose import (
    CalibrationCaptureError,
    CaptureSummary,
    is_frame_valid,
    measure_neutral_pose,
)
from core.config.personalization import build_calibrated
from core.config.thresholds import (
    DEFAULT_THRESHOLDS_PATH,
    CalibrationThresholds,
    load_thresholds,
)
from core.models.landmark_result import Landmark, LandmarkResult
from core.models.view_mode import ViewMode

UMBRALES = CalibrationThresholds(
    min_visibility=0.5, min_frames=10, min_validity_rate=0.5
)

VISIBLE = 0.9
OCULTO = 0.1

MINIMO = UMBRALES.min_frames

# Alturas de una persona de pie, de la cabeza a los pies.
_HOMBRO_Y = 0.30
_CADERA_Y = 0.50
_RODILLA_Y = 0.70
_TOBILLO_Y = 0.90


def _punto(index: int, x: float, y: float, visibilidad: float = VISIBLE) -> Landmark:
    return Landmark(index=index, x=x, y=y, z=0.0, visibility=visibilidad)


def _perfil(
    *,
    rodilla_deg: float = 180.0,
    arqueo_deg: float = 180.0,
    codo_deg: float | None = 180.0,
    lado: str = "izq",
    visibilidad: float = VISIBLE,
) -> LandmarkResult:
    # Persona de perfil. Los déficits de extensión se producen en el plano sagital.

    hombro_idx, cadera_idx, rodilla_idx, tobillo_idx, codo_idx, muneca_idx = (
        (IDX_LEFT_SHOULDER, IDX_LEFT_HIP, IDX_LEFT_KNEE, IDX_LEFT_ANKLE,
         IDX_LEFT_ELBOW, IDX_LEFT_WRIST)
        if lado == "izq"
        else (IDX_RIGHT_SHOULDER, IDX_RIGHT_HIP, IDX_RIGHT_KNEE, IDX_RIGHT_ANKLE,
              IDX_RIGHT_ELBOW, IDX_RIGHT_WRIST)
    )

    cadera = (0.5, _CADERA_Y)
    rodilla = (0.5, _RODILLA_Y)
    # El gemelo se separa de la prolongación del muslo.
    flexion = math.radians(180.0 - rodilla_deg)
    tobillo = (
        rodilla[0] + 0.2 * math.sin(flexion),
        rodilla[1] + 0.2 * math.cos(flexion),
    )


    dx, dy = tobillo[0] - cadera[0], tobillo[1] - cadera[1]
    largo = math.hypot(dx, dy)
    ux, uy = dx / largo, dy / largo
    giro = math.radians(arqueo_deg)
    hombro = (
        cadera[0] + 0.2 * (ux * math.cos(giro) - uy * math.sin(giro)),
        cadera[1] + 0.2 * (ux * math.sin(giro) + uy * math.cos(giro)),
    )

    landmarks = [
        _punto(hombro_idx, hombro[0], hombro[1], visibilidad),
        _punto(cadera_idx, cadera[0], cadera[1], visibilidad),
        _punto(rodilla_idx, rodilla[0], rodilla[1], visibilidad),
        _punto(tobillo_idx, tobillo[0], tobillo[1], visibilidad),
    ]

    if codo_deg is not None:
        codo = (hombro[0], hombro[1] + 0.15)
        apertura = math.radians(180.0 - codo_deg)
        muneca = (
            codo[0] + 0.15 * math.sin(apertura),
            codo[1] + 0.15 * math.cos(apertura),
        )
        landmarks.append(_punto(codo_idx, codo[0], codo[1], visibilidad))
        landmarks.append(_punto(muneca_idx, muneca[0], muneca[1], visibilidad))

    return LandmarkResult(landmarks=landmarks, timestamp_ms=0)


def _frontal(
    *,
    largo_pierna: float = 0.20,
    anchura_hombros: float = 0.16,
    visibilidad: float = VISIBLE,
    ocultos: tuple[int, ...] = (),
) -> LandmarkResult:
    # Persona de frente. El tronco mide 0.20 en vertical.

    def par(izq, der, y, media_anchura):
        for indice, lado in ((izq, -1.0), (der, 1.0)):
            vis = OCULTO if indice in ocultos else visibilidad
            landmarks.append(_punto(indice, 0.5 + lado * media_anchura, y, vis))

    landmarks: list[Landmark] = []
    par(IDX_LEFT_SHOULDER, IDX_RIGHT_SHOULDER, _HOMBRO_Y, anchura_hombros / 2.0)
    par(IDX_LEFT_HIP, IDX_RIGHT_HIP, _CADERA_Y, 0.07)
    par(IDX_LEFT_KNEE, IDX_RIGHT_KNEE, _CADERA_Y + largo_pierna / 2.0, 0.07)
    par(IDX_LEFT_ANKLE, IDX_RIGHT_ANKLE, _CADERA_Y + largo_pierna, 0.07)

    return LandmarkResult(landmarks=landmarks, timestamp_ms=0)


def _medir(laterales=None, frontales=None, n: int = MINIMO):
    laterales = [_perfil()] * n if laterales is None else laterales
    frontales = [_frontal()] * n if frontales is None else frontales
    return measure_neutral_pose(laterales, frontales, UMBRALES)



def test_un_perfil_completo_es_valido_para_la_captura_lateral():
    assert is_frame_valid(_perfil(), ViewMode.LATERAL, UMBRALES)


def test_un_frontal_completo_es_valido_para_la_captura_frontal():
    assert is_frame_valid(_frontal(), ViewMode.FRONTAL, UMBRALES)


def test_de_frente_se_exigen_los_dos_lados():
    # Las medidas frontales son longitudes entre lados opuestos.
    cuerpo = _frontal(ocultos=(IDX_RIGHT_KNEE,))
    assert not is_frame_valid(cuerpo, ViewMode.FRONTAL, UMBRALES)


def test_de_perfil_basta_un_lado_completo():
    # El lado más alejado queda ocluido por el propio cuerpo.
    assert is_frame_valid(_perfil(lado="der"), ViewMode.LATERAL, UMBRALES)


def test_de_perfil_el_brazo_no_es_obligatorio():
    # Su ausencia deja el codo sin medir, no invalida la captura.
    assert is_frame_valid(_perfil(codo_deg=None), ViewMode.LATERAL, UMBRALES)


def test_un_fotograma_poco_visible_no_es_valido():
    assert not is_frame_valid(
        _perfil(visibilidad=OCULTO), ViewMode.LATERAL, UMBRALES
    )


def test_un_fotograma_sin_puntos_no_es_valido():
    vacio = LandmarkResult(landmarks=[], timestamp_ms=0)
    for vista in (ViewMode.LATERAL, ViewMode.FRONTAL):
        assert not is_frame_valid(vacio, vista, UMBRALES)



def test_una_captura_con_pocos_fotogramas_se_rechaza():
    with pytest.raises(CalibrationCaptureError) as exc:
        _medir(n=MINIMO - 1)
    assert exc.value.view is ViewMode.LATERAL


def test_una_captura_con_demasiados_fotogramas_invalidos_se_rechaza():
    # Más de la mitad inservibles. la postura no se sostuvo.
    laterales = [_perfil()] * MINIMO + [_perfil(visibilidad=OCULTO)] * (MINIMO + 2)
    with pytest.raises(CalibrationCaptureError):
        _medir(laterales=laterales)


def test_el_rechazo_indica_que_captura_fallo_y_con_que_calidad():
    # El atleta debe saber cuál repetir y el entrenador, por qué se rechazó.
    with pytest.raises(CalibrationCaptureError) as exc:
        _medir(frontales=[_frontal(visibilidad=OCULTO)] * MINIMO)

    assert exc.value.view is ViewMode.FRONTAL
    assert exc.value.summary.valid_frames == 0
    assert exc.value.summary.total_frames == MINIMO


def test_una_captura_con_fotogramas_sueltos_invalidos_se_acepta():
    laterales = [_perfil()] * MINIMO + [_perfil(visibilidad=OCULTO)]
    medida = _medir(laterales=laterales)

    assert medida.lateral.valid_frames == MINIMO
    assert medida.lateral.total_frames == MINIMO + 1


def test_la_calidad_de_cada_captura_viaja_en_la_medida():
    medida = _medir()
    assert medida.lateral.validity_rate == pytest.approx(1.0)
    assert medida.frontal.validity_rate == pytest.approx(1.0)


def test_una_captura_vacia_no_divide_por_cero():
    assert CaptureSummary(0, 0).validity_rate == 0.0



def test_una_postura_recta_mide_los_angulos_de_extension_completa():
    medida = _medir()

    assert medida.knee_deg == pytest.approx(180.0, abs=0.1)
    assert medida.back_arch_deg == pytest.approx(180.0, abs=0.1)
    assert medida.elbow_deg == pytest.approx(180.0, abs=0.1)


def test_la_rodilla_se_mide_en_la_captura_lateral():
    medida = _medir(laterales=[_perfil(rodilla_deg=170.0)] * MINIMO)
    assert medida.knee_deg == pytest.approx(170.0, abs=0.1)


def test_el_arqueo_neutro_se_mide_en_la_captura_lateral():
    medida = _medir(laterales=[_perfil(arqueo_deg=172.0)] * MINIMO)
    assert medida.back_arch_deg == pytest.approx(172.0, abs=0.1)


def test_el_codo_neutro_se_mide_en_la_captura_lateral():
    medida = _medir(laterales=[_perfil(codo_deg=174.0)] * MINIMO)
    assert medida.elbow_deg == pytest.approx(174.0, abs=0.1)


def test_sin_brazo_visible_el_codo_queda_sin_medir():
    medida = _medir(laterales=[_perfil(codo_deg=None)] * MINIMO)

    assert medida.elbow_deg is None
    assert medida.knee_deg is not None


def test_las_tres_medidas_sagitales_son_independientes():
    medida = _medir(
        laterales=[_perfil(rodilla_deg=168.0, arqueo_deg=174.0, codo_deg=176.0)]
        * MINIMO
    )

    assert medida.knee_deg == pytest.approx(168.0, abs=0.1)
    assert medida.back_arch_deg == pytest.approx(174.0, abs=0.1)
    assert medida.elbow_deg == pytest.approx(176.0, abs=0.1)


def test_se_mide_igual_desde_cualquiera_de_los_dos_lados():
    izquierdo = _medir(laterales=[_perfil(rodilla_deg=170.0, lado="izq")] * MINIMO)
    derecho = _medir(laterales=[_perfil(rodilla_deg=170.0, lado="der")] * MINIMO)

    assert izquierdo.knee_deg == pytest.approx(derecho.knee_deg, abs=0.1)


def test_cada_magnitud_se_resume_con_la_mediana():
    # Un fotograma mal estimado no debe arrastrar la medida.
    laterales = [_perfil(rodilla_deg=170.0)] * MINIMO + [_perfil(rodilla_deg=90.0)]
    medida = _medir(laterales=laterales)

    assert medida.knee_deg == pytest.approx(170.0, abs=0.1)




def test_la_proporcion_piernas_tronco_se_mide_de_frente():
    # Piernas de 0.20 sobre un tronco de 0.20.
    medida = _medir(frontales=[_frontal(largo_pierna=0.20)] * MINIMO)
    assert medida.legs_trunk_ratio == pytest.approx(1.0, abs=0.01)


def test_la_proporcion_crece_con_la_longitud_de_las_piernas():
    corto = _medir(frontales=[_frontal(largo_pierna=0.20)] * MINIMO)
    largo = _medir(frontales=[_frontal(largo_pierna=0.30)] * MINIMO)

    assert largo.legs_trunk_ratio > corto.legs_trunk_ratio


def test_la_anchura_de_hombros_se_normaliza_por_el_tronco():
    medida = _medir(frontales=[_frontal(anchura_hombros=0.16)] * MINIMO)
    assert medida.shoulder_width_ratio == pytest.approx(0.8, abs=0.01)


def test_las_proporciones_no_dependen_de_la_captura_lateral():
    medida = _medir(laterales=[_perfil(rodilla_deg=160.0)] * MINIMO)
    assert medida.legs_trunk_ratio is not None



def test_la_medida_se_entrega_en_la_forma_que_espera_la_derivacion():
    medida = _medir(
        laterales=[_perfil(rodilla_deg=170.0, arqueo_deg=174.0, codo_deg=176.0)]
        * MINIMO
    )
    angulos = medida.neutral_angles

    assert angulos.knee_deg == pytest.approx(170.0, abs=0.1)
    assert angulos.back_arch_deg == pytest.approx(174.0, abs=0.1)
    assert angulos.elbow_deg == pytest.approx(176.0, abs=0.1)


def test_una_calibracion_completa_produce_umbrales_personalizados():
    umbrales = load_thresholds(DEFAULT_THRESHOLDS_PATH)
    medida = measure_neutral_pose(
        [_perfil(rodilla_deg=170.0, arqueo_deg=174.0)] * MINIMO,
        [_frontal()] * MINIMO,
        umbrales.calibration,
    )

    resultado = build_calibrated(
        umbrales.alignment, medida.neutral_angles, umbrales.personalization
    )

    assert resultado.is_personalized
    assert resultado.thresholds.parameters["knee_bend"].threshold == pytest.approx(20.0)
    assert resultado.thresholds.parameters["back_arch"].threshold == pytest.approx(14.0)


def test_una_postura_neutra_recta_no_altera_los_umbrales():
    umbrales = load_thresholds(DEFAULT_THRESHOLDS_PATH)
    medida = measure_neutral_pose(
        [_perfil()] * MINIMO, [_frontal()] * MINIMO, umbrales.calibration
    )

    resultado = build_calibrated(
        umbrales.alignment, medida.neutral_angles, umbrales.personalization
    )

    assert not resultado.is_personalized


def test_la_medicion_funciona_con_la_configuracion_del_proyecto():
    umbrales = load_thresholds(DEFAULT_THRESHOLDS_PATH).calibration
    medida = measure_neutral_pose(
        [_perfil()] * umbrales.min_frames,
        [_frontal()] * umbrales.min_frames,
        umbrales,
    )

    assert medida.knee_deg is not None
    assert medida.legs_trunk_ratio is not None