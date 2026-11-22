import pytest

from core.calibration.neutral_pose import CalibrationCaptureError
from core.config.thresholds import load_thresholds
from core.models.calibration_status import CalibrationStatus, ThresholdsApplied
from core.models.landmark_result import Landmark, LandmarkResult
from core.models.user_role import UserRole
from core.models.view_mode import ViewMode
from core.persistence.calibration_repository import CalibrationRepository
from core.persistence.database import IN_MEMORY, Database
from core.persistence.password import MIN_ITERATIONS
from core.persistence.user_repository import UserRepository
from core.services.calibration_service import (
    CalibrationService,
    CalibrationServiceError,
)

UMBRALES = load_thresholds()


@pytest.fixture
def entorno():
    db = Database(IN_MEMORY)
    db.open()
    users = UserRepository(db, iterations=MIN_ITERATIONS)
    entrenadora = users.create("entre", "c", UserRole.TRAINER, "Entrenadora")
    atleta = users.create(
        "atleta",
        "c",
        UserRole.ATHLETE,
        "Atleta",
        assigned_trainer_id=entrenadora.user_id,
    )
    repositorio = CalibrationRepository(db)
    yield (
        CalibrationService(repositorio, UMBRALES),
        repositorio,
        atleta.user_id,
        entrenadora.user_id,
    )
    db.close()


def _vacio(marca=0):
    # Fotograma sin puntos: nunca es utilizable.

    return LandmarkResult(landmarks=[], timestamp_ms=marca)


def _completo(marca=0, visibilidad=0.9):
    # Fotograma con los 33 puntos visibles, utilizable en ambas vistas.

    return LandmarkResult(
        landmarks=[
            Landmark(index=i, x=0.5, y=0.1 + i * 0.02, z=0.0, visibility=visibilidad)
            for i in range(33)
        ],
        timestamp_ms=marca,
    )




def test_un_fotograma_utilizable_se_acepta(entorno):
    servicio, _, _, _ = entorno

    assert servicio.submit(ViewMode.FRONTAL, _completo())


def test_un_fotograma_sin_puntos_no_es_utilizable(entorno):
    servicio, _, _, _ = entorno

    assert not servicio.submit(ViewMode.FRONTAL, _vacio())


def test_se_conservan_tambien_los_no_utilizables(entorno):
    # La proporción de válidos sobre el total es criterio de aceptación.
    servicio, _, _, _ = entorno

    servicio.submit(ViewMode.FRONTAL, _completo())
    servicio.submit(ViewMode.FRONTAL, _vacio())

    assert servicio.captured(ViewMode.FRONTAL) == (1, 2)


def test_las_dos_capturas_se_cuentan_por_separado(entorno):
    servicio, _, _, _ = entorno

    servicio.submit(ViewMode.FRONTAL, _completo())
    servicio.submit(ViewMode.LATERAL, _completo())
    servicio.submit(ViewMode.LATERAL, _completo())

    assert servicio.captured(ViewMode.FRONTAL)[1] == 1
    assert servicio.captured(ViewMode.LATERAL)[1] == 2


def test_reiniciar_descarta_lo_capturado(entorno):
    servicio, _, _, _ = entorno
    servicio.submit(ViewMode.FRONTAL, _completo())

    servicio.reset()

    assert servicio.captured(ViewMode.FRONTAL) == (0, 0)




def test_una_captura_corta_no_esta_lista(entorno):
    servicio, _, _, _ = entorno

    for i in range(UMBRALES.calibration.min_frames - 1):
        servicio.submit(ViewMode.FRONTAL, _completo(i))

    assert not servicio.is_ready(ViewMode.FRONTAL)


def test_una_captura_suficiente_esta_lista(entorno):
    servicio, _, _, _ = entorno

    for i in range(UMBRALES.calibration.min_frames):
        servicio.submit(ViewMode.FRONTAL, _completo(i))

    assert servicio.is_ready(ViewMode.FRONTAL)


def test_demasiados_fotogramas_malos_invalidan_la_captura(entorno):
    # Aunque haya suficientes válidos, la proporción cuenta.
    servicio, _, _, _ = entorno
    validos = UMBRALES.calibration.min_frames

    for i in range(validos):
        servicio.submit(ViewMode.FRONTAL, _completo(i))
    for i in range(validos * 3):
        servicio.submit(ViewMode.FRONTAL, _vacio(i))

    assert not servicio.is_ready(ViewMode.FRONTAL)


def test_una_captura_vacia_no_esta_lista(entorno):
    servicio, _, _, _ = entorno

    assert not servicio.is_ready(ViewMode.LATERAL)



def test_una_captura_insuficiente_no_se_puede_cerrar(entorno):
    servicio, _, atleta, _ = entorno
    servicio.submit(ViewMode.FRONTAL, _completo())

    with pytest.raises(CalibrationCaptureError):
        servicio.complete(atleta)


def test_al_cerrar_se_guarda_como_pendiente(entorno):
    servicio, _, atleta, _ = entorno
    _capturar(servicio)

    perfil = servicio.complete(atleta)

    assert perfil.status is CalibrationStatus.PENDING


def test_al_cerrar_se_guardan_las_rutas_de_las_imagenes(entorno):
    servicio, _, atleta, _ = entorno
    _capturar(servicio)

    perfil = servicio.complete(
        atleta, frontal_image="f.png", lateral_image="l.png"
    )

    assert (perfil.frontal_image, perfil.lateral_image) == ("f.png", "l.png")


def test_al_cerrar_se_descarta_lo_capturado(entorno):
    # Para que una calibración nueva no arrastre fotogramas de la anterior.
    servicio, _, atleta, _ = entorno
    _capturar(servicio)

    servicio.complete(atleta)

    assert servicio.captured(ViewMode.FRONTAL) == (0, 0)


def _capturar(servicio, n=None):
    # Llena las dos capturas con fotogramas utilizables.

    n = n or UMBRALES.calibration.min_frames
    for view in (ViewMode.FRONTAL, ViewMode.LATERAL):
        for i in range(n):
            servicio.submit(view, _completo(i))



def test_una_rodilla_neutra_limitada_relaja_su_umbral(entorno):
    servicio, repositorio, atleta, _ = entorno
    perfil = repositorio.create_pending(atleta, knee_deg=170.0)

    propuesto = servicio.proposed(perfil)

    generico = UMBRALES.alignment.parameters["knee_bend"].threshold
    assert propuesto.thresholds.parameters["knee_bend"].threshold > generico


def test_sin_medida_el_umbral_se_queda_en_el_generico(entorno):
    servicio, repositorio, atleta, _ = entorno
    perfil = repositorio.create_pending(atleta)

    propuesto = servicio.proposed(perfil)

    assert propuesto.thresholds.parameters["knee_bend"].threshold == pytest.approx(
        UMBRALES.alignment.parameters["knee_bend"].threshold
    )


def test_la_propuesta_explica_que_parametros_personaliza(entorno):
    servicio, repositorio, atleta, _ = entorno
    perfil = repositorio.create_pending(atleta, knee_deg=170.0)

    assert "knee_bend" in servicio.proposed(perfil).personalized_parameters



def test_validar_sin_ajustes_deja_la_derivacion_intacta(entorno):
    servicio, repositorio, atleta, entrenadora = entorno
    perfil = repositorio.create_pending(atleta, knee_deg=170.0)
    derivado = servicio.proposed(perfil).thresholds.parameters["knee_bend"].threshold

    servicio.validate(perfil.profile_id, entrenadora)
    umbrales, _ = servicio.thresholds_for(atleta)

    assert umbrales.parameters["knee_bend"].threshold == pytest.approx(derivado)


def test_solo_se_almacenan_los_parametros_que_el_entrenador_ajusta(entorno):
    #el resto se sigue derivando.
    servicio, repositorio, atleta, entrenadora = entorno
    perfil = repositorio.create_pending(atleta, knee_deg=170.0, back_arch_deg=175.0)

    validada = servicio.validate(
        perfil.profile_id, entrenadora, overrides={"knee_bend": 25.0}
    )

    assert validada.adjusted_thresholds == {"knee_bend": 25.0}


def test_el_ajuste_del_entrenador_prevalece_sobre_lo_derivado(entorno):
    servicio, repositorio, atleta, entrenadora = entorno
    perfil = repositorio.create_pending(atleta, knee_deg=170.0, back_arch_deg=175.0)
    derivado_arqueo = (
        servicio.proposed(perfil).thresholds.parameters["back_arch"].threshold
    )

    servicio.validate(perfil.profile_id, entrenadora, overrides={"knee_bend": 25.0})
    umbrales, _ = servicio.thresholds_for(atleta)

    assert umbrales.parameters["knee_bend"].threshold == pytest.approx(25.0)
    assert umbrales.parameters["back_arch"].threshold == pytest.approx(
        derivado_arqueo
    )


def test_el_ajuste_no_altera_la_zona_muerta(entorno):
    # El ruido del detector no es cosa del entrenador.
    servicio, repositorio, atleta, entrenadora = entorno
    perfil = repositorio.create_pending(atleta, knee_deg=170.0)
    ruido = UMBRALES.alignment.parameters["knee_bend"].noise

    servicio.validate(perfil.profile_id, entrenadora, overrides={"knee_bend": 25.0})
    umbrales, _ = servicio.thresholds_for(atleta)

    assert umbrales.parameters["knee_bend"].noise == pytest.approx(ruido)


def test_un_ajuste_sobre_un_parametro_no_personalizable_se_rechaza(entorno):
    # Quedaría almacenado sin que nada lo leyera nunca.
    servicio, repositorio, atleta, entrenadora = entorno
    perfil = repositorio.create_pending(atleta)

    with pytest.raises(CalibrationServiceError, match="no personalizables"):
        servicio.validate(
            perfil.profile_id, entrenadora, overrides={"instability": 1.0}
        )


@pytest.mark.parametrize("valor", [0.0, -5.0])
def test_un_ajuste_no_positivo_se_rechaza(entorno, valor):
    servicio, repositorio, atleta, entrenadora = entorno
    perfil = repositorio.create_pending(atleta)

    with pytest.raises(CalibrationServiceError, match="positivo"):
        servicio.validate(
            perfil.profile_id, entrenadora, overrides={"knee_bend": valor}
        )


def test_un_ajuste_rechazado_no_valida_la_calibracion(entorno):
    servicio, repositorio, atleta, entrenadora = entorno
    perfil = repositorio.create_pending(atleta)

    with pytest.raises(CalibrationServiceError):
        servicio.validate(
            perfil.profile_id, entrenadora, overrides={"knee_bend": -1.0}
        )

    assert repositorio.get(perfil.profile_id).status is CalibrationStatus.PENDING


def test_rechazar_una_calibracion_la_marca_como_rechazada(entorno):
    servicio, repositorio, atleta, entrenadora = entorno
    perfil = repositorio.create_pending(atleta)

    rechazada = servicio.reject(perfil.profile_id, entrenadora, note="mal encuadre")

    assert rechazada.status is CalibrationStatus.REJECTED
    assert rechazada.review_note == "mal encuadre"




def test_sin_calibracion_validada_se_practica_con_los_genericos(entorno):
    servicio, _, atleta, _ = entorno

    umbrales, clase = servicio.thresholds_for(atleta)

    assert clase is ThresholdsApplied.GENERIC
    assert umbrales is UMBRALES.alignment


def test_una_calibracion_pendiente_no_personaliza_todavia(entorno):
    #hasta que el entrenador valide, se practica en modo básico.
    servicio, repositorio, atleta, _ = entorno
    repositorio.create_pending(atleta, knee_deg=170.0)

    _, clase = servicio.thresholds_for(atleta)

    assert clase is ThresholdsApplied.GENERIC


def test_una_calibracion_validada_personaliza(entorno):
    servicio, repositorio, atleta, entrenadora = entorno
    perfil = repositorio.create_pending(atleta, knee_deg=170.0)
    servicio.validate(perfil.profile_id, entrenadora)

    _, clase = servicio.thresholds_for(atleta)

    assert clase is ThresholdsApplied.PERSONALIZED


def test_una_calibracion_rechazada_no_personaliza(entorno):
    servicio, repositorio, atleta, entrenadora = entorno
    perfil = repositorio.create_pending(atleta, knee_deg=170.0)
    servicio.reject(perfil.profile_id, entrenadora)

    _, clase = servicio.thresholds_for(atleta)

    assert clase is ThresholdsApplied.GENERIC


def test_al_sustituirse_una_calibracion_rigen_los_umbrales_nuevos(entorno):
    servicio, repositorio, atleta, entrenadora = entorno
    primera = repositorio.create_pending(atleta, knee_deg=170.0)
    servicio.validate(primera.profile_id, entrenadora, overrides={"knee_bend": 25.0})
    segunda = repositorio.create_pending(atleta, knee_deg=178.0)

    servicio.validate(segunda.profile_id, entrenadora)
    umbrales, _ = servicio.thresholds_for(atleta)

    assert umbrales.parameters["knee_bend"].threshold != pytest.approx(25.0)