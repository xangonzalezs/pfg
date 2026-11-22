import pytest

from core.analysis.error_selection import ErrorSelector, severity_from_metric
from core.config.thresholds import ErrorSelectionThresholds
from core.models.analysis_result import TechnicalError
from core.models.view_mode import ViewMode

UMBRALES = ErrorSelectionThresholds(
    min_severity_to_report=15.0,
    hysteresis_factor=0.7,
)

# Severidad por debajo de la cual un error activo se desactiva: 15 * 0.7.
DESACTIVACION = 10.5


def _selector(vista: ViewMode = ViewMode.LATERAL) -> ErrorSelector:
    return ErrorSelector(vista, UMBRALES)


def test_por_debajo_de_la_zona_muerta_la_severidad_es_nula():
    assert severity_from_metric(1.0, threshold=8.0, noise=3.0) == 0.0
    assert severity_from_metric(3.0, threshold=8.0, noise=3.0) == 0.0


def test_en_el_tramo_suave_la_severidad_crece_hasta_sesenta():
    # Mitad entre la zona muerta y el umbral, la mitad de 60.
    assert severity_from_metric(5.5, threshold=8.0, noise=3.0) == pytest.approx(30.0)
    assert severity_from_metric(8.0, threshold=8.0, noise=3.0) == pytest.approx(60.0)


def test_superado_el_umbral_la_severidad_crece_mas_deprisa():
    # la saturación se alcanza con 2.5° de exceso.
    assert severity_from_metric(9.25, threshold=8.0, noise=3.0) == pytest.approx(80.0)
    assert severity_from_metric(10.5, threshold=8.0, noise=3.0) == pytest.approx(100.0)


def test_la_severidad_no_pasa_de_cien():
    assert severity_from_metric(90.0, threshold=8.0, noise=3.0) == pytest.approx(100.0)


def test_la_severidad_es_monotona():
    valores = [
        severity_from_metric(v / 10.0, threshold=8.0, noise=3.0) for v in range(0, 200)
    ]
    assert valores == sorted(valores)


def test_una_configuracion_degenerada_no_divide_por_cero():
    # Umbral igual a la zona muerta. no hay intervalo que graduar.
    assert severity_from_metric(3.0, threshold=3.0, noise=3.0) == 0.0
    assert severity_from_metric(3.1, threshold=3.0, noise=3.0) == 100.0


def test_una_severidad_por_debajo_del_minimo_no_activa_el_error():
    selector = _selector()
    assert selector.select({TechnicalError.BACK_ARCH: 14.9}) == []
    assert not selector.is_active(TechnicalError.BACK_ARCH)


def test_alcanzado_el_minimo_el_error_se_activa():
    selector = _selector()
    assert selector.select({TechnicalError.BACK_ARCH: 15.0}) == [
        TechnicalError.BACK_ARCH
    ]
    assert selector.is_active(TechnicalError.BACK_ARCH)


def test_un_error_activo_sigue_activo_por_encima_de_la_desactivacion():
    # Entre 10.5 y 15 el error no se habría activado, pero una vez activo se mantiene. histéresis.
    selector = _selector()
    selector.select({TechnicalError.BACK_ARCH: 20.0})

    activos = selector.select({TechnicalError.BACK_ARCH: 12.0})

    assert activos == [TechnicalError.BACK_ARCH]
    assert selector.is_active(TechnicalError.BACK_ARCH)


def test_un_error_activo_se_desactiva_al_caer_por_debajo_del_limite():
    selector = _selector()
    selector.select({TechnicalError.BACK_ARCH: 20.0})

    activos = selector.select({TechnicalError.BACK_ARCH: DESACTIVACION - 0.1})

    assert activos == []
    assert not selector.is_active(TechnicalError.BACK_ARCH)


def test_la_histeresis_evita_el_parpadeo_del_aviso():

    selector = _selector()
    salidas = [
        selector.select({TechnicalError.BACK_ARCH: severidad})
        for severidad in (16.0, 14.0, 16.0, 13.0, 15.5, 12.0)
    ]
    assert all(salida == [TechnicalError.BACK_ARCH] for salida in salidas)


def test_un_error_sin_medida_conserva_su_estado():
    selector = _selector()
    selector.select({TechnicalError.BACK_ARCH: 20.0})

    assert selector.select({}) == []
    assert selector.is_active(TechnicalError.BACK_ARCH)
    assert selector.select({TechnicalError.BACK_ARCH: 20.0}) == [
        TechnicalError.BACK_ARCH
    ]


def test_reset_olvida_los_errores_activos():
    selector = _selector()
    selector.select({TechnicalError.BACK_ARCH: 20.0})

    selector.reset()

    assert not selector.is_active(TechnicalError.BACK_ARCH)
    assert selector.select({TechnicalError.BACK_ARCH: 12.0}) == []


def test_se_devuelven_todos_los_errores_activos():
    # Es el motor de feedback quien decide cuál se verbaliza.
    selector = _selector()
    activos = selector.select(
        {
            TechnicalError.HEAD_FORWARD: 80.0,
            TechnicalError.BACK_ARCH: 50.0,
            TechnicalError.LEGS_NOT_STRAIGHT: 30.0,
            TechnicalError.FEET_NOT_EXTENDED: 18.0,
        }
    )
    assert len(activos) == 4


def test_los_errores_por_debajo_del_minimo_quedan_fuera():
    selector = _selector()
    activos = selector.select(
        {TechnicalError.BACK_ARCH: 50.0, TechnicalError.FEET_NOT_EXTENDED: 5.0}
    )
    assert activos == [TechnicalError.BACK_ARCH]


def test_el_orden_de_salida_es_estable_y_no_depende_de_la_severidad():
    # El orden es el de declaración del enumerado, no una prioridad.
    selector = _selector()
    primero = selector.select(
        {TechnicalError.BACK_ARCH: 90.0, TechnicalError.HEAD_FORWARD: 20.0}
    )
    selector.reset()
    segundo = selector.select(
        {TechnicalError.BACK_ARCH: 20.0, TechnicalError.HEAD_FORWARD: 90.0}
    )
    assert primero == segundo


def test_sin_errores_no_se_devuelve_nada():
    assert _selector().select({}) == []



def test_el_arqueo_se_suprime_si_la_pelvis_esta_adelantada():
    selector = _selector()
    activos = selector.select(
        {TechnicalError.PELVIS_POSITION: 50.0, TechnicalError.BACK_ARCH: 45.0}
    )
    assert activos == [TechnicalError.PELVIS_POSITION]


def test_la_supresion_no_depende_de_cual_sea_mas_severo():
    selector = _selector()
    activos = selector.select(
        {TechnicalError.PELVIS_POSITION: 30.0, TechnicalError.BACK_ARCH: 90.0}
    )
    assert activos == [TechnicalError.PELVIS_POSITION]


def test_el_arqueo_sin_desplazamiento_pelvico_si_se_comunica():
    selector = _selector()
    activos = selector.select({TechnicalError.BACK_ARCH: 50.0})
    assert activos == [TechnicalError.BACK_ARCH]


def test_de_dos_asimetrias_opuestas_sobrevive_la_mas_severa():
    selector = _selector(ViewMode.FRONTAL)
    activos = selector.select(
        {
            TechnicalError.LEFT_SHOULDER_LOW: 40.0,
            TechnicalError.RIGHT_SHOULDER_LOW: 60.0,
        }
    )
    assert activos == [TechnicalError.RIGHT_SHOULDER_LOW]


def test_ante_asimetrias_empatadas_el_resultado_es_determinista():
    activos = [
        _selector(ViewMode.FRONTAL).select(
            {
                TechnicalError.LEFT_HIP_LOW: 50.0,
                TechnicalError.RIGHT_HIP_LOW: 50.0,
            }
        )
        for _ in range(5)
    ]
    assert all(salida == activos[0] for salida in activos)
    assert len(activos[0]) == 1


def test_las_asimetrias_de_pares_distintos_coexisten():
    # Un hombro bajo y una cadera baja son errores independientes.
    selector = _selector(ViewMode.FRONTAL)
    activos = selector.select(
        {TechnicalError.LEFT_SHOULDER_LOW: 50.0, TechnicalError.RIGHT_HIP_LOW: 40.0}
    )
    assert len(activos) == 2


def test_en_lateral_se_descartan_los_errores_del_plano_frontal():
    selector = _selector(ViewMode.LATERAL)
    assert selector.select({TechnicalError.LEFT_SHOULDER_LOW: 90.0}) == []
    assert TechnicalError.LEFT_SHOULDER_LOW not in selector.relevant_errors


def test_en_frontal_se_descartan_los_errores_del_plano_sagital():
    selector = _selector(ViewMode.FRONTAL)
    assert selector.select({TechnicalError.BACK_ARCH: 90.0}) == []
    assert TechnicalError.BACK_ARCH not in selector.relevant_errors


def test_los_errores_comunes_son_evaluables_en_las_dos_vistas():
    # El codo y la inestabilidad son los únicos errores evaluables desde las dos vistas. 
    for vista in (ViewMode.LATERAL, ViewMode.FRONTAL):
        relevantes = _selector(vista).relevant_errors
        assert TechnicalError.ELBOW_NOT_EXTENDED in relevantes
        assert TechnicalError.INSTABILITY in relevantes


def test_las_puntas_no_son_evaluables_de_frente():
    # La flexión plantar ocurre en el plano sagital.
    assert TechnicalError.FEET_NOT_EXTENDED in _selector(
        ViewMode.LATERAL
    ).relevant_errors
    assert TechnicalError.FEET_NOT_EXTENDED not in _selector(
        ViewMode.FRONTAL
    ).relevant_errors


def test_de_frente_se_descartan_las_puntas_aunque_lleguen_con_severidad():
    assert _selector(ViewMode.FRONTAL).select(
        {TechnicalError.FEET_NOT_EXTENDED: 90.0}
    ) == []


def test_un_error_irrelevante_no_estorba_a_uno_relevante():
    selector = _selector(ViewMode.LATERAL)
    activos = selector.select(
        {TechnicalError.LEFT_HIP_LOW: 99.0, TechnicalError.BACK_ARCH: 30.0}
    )
    assert activos == [TechnicalError.BACK_ARCH]


def test_el_selector_recuerda_su_vista():
    assert _selector(ViewMode.FRONTAL).view_mode is ViewMode.FRONTAL


def test_un_intervalo_util_estrecho_sigue_graduando():
    # Intervalo de medio grado: pequeño, pero no degenerado. Debe graduarse.
    assert severity_from_metric(8.25, threshold=8.5, noise=8.0) == pytest.approx(30.0)
    assert severity_from_metric(8.5, threshold=8.5, noise=8.0) == pytest.approx(60.0)


def test_una_configuracion_sin_intervalo_no_gradua():
    # Umbral igual o menor que la zona muerta. no hay nada que graduar.
    # la severidad solo puede ser nula o máxima.
    assert severity_from_metric(4.0, threshold=5.0, noise=5.0) == 0.0
    assert severity_from_metric(6.0, threshold=5.0, noise=5.0) == 100.0
    assert severity_from_metric(6.0, threshold=3.0, noise=5.0) == 100.0


def test_en_el_punto_exacto_de_desactivacion_el_error_sigue_activo():
    # La desactivación exige caer POR DEBAJO del umbral reducido, no alcanzarlo.
    selector = _selector()
    selector.select({TechnicalError.BACK_ARCH: 40.0})
    assert selector.is_active(TechnicalError.BACK_ARCH)

    selector.select({TechnicalError.BACK_ARCH: DESACTIVACION})

    assert selector.is_active(TechnicalError.BACK_ARCH)


def test_por_debajo_del_punto_de_desactivacion_el_error_se_apaga():
    selector = _selector()
    selector.select({TechnicalError.BACK_ARCH: 40.0})

    selector.select({TechnicalError.BACK_ARCH: DESACTIVACION - 0.1})

    assert not selector.is_active(TechnicalError.BACK_ARCH)


def test_ante_severidades_iguales_se_conserva_el_primero_del_par():
    # Dos asimetrías opuestas no pueden darse a la vez. 
    # con severidades idénticas el desempate debe ser determinista y no depender del orden.
    selector = _selector(ViewMode.FRONTAL)

    activos = selector.select(
        {
            TechnicalError.LEFT_SHOULDER_LOW: 50.0,
            TechnicalError.RIGHT_SHOULDER_LOW: 50.0,
        }
    )

    assert activos == [TechnicalError.LEFT_SHOULDER_LOW]