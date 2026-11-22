import pytest

from core.models.calibration_status import CalibrationStatus
from core.models.user_role import UserRole
from core.persistence.calibration_repository import (
    CalibrationRepository,
    DuplicatePendingError,
)
from core.persistence.database import IN_MEMORY, Database, DatabaseError
from core.persistence.password import MIN_ITERATIONS
from core.persistence.user_repository import UserRepository

MEDIDAS = {
    "knee_deg": 178.0,
    "back_arch_deg": 172.5,
    "elbow_deg": 179.0,
    "legs_trunk_ratio": 1.12,
    "shoulder_width_ratio": 0.24,
}


@pytest.fixture
def entorno():
    db = Database(IN_MEMORY)
    db.open()
    users = UserRepository(db, iterations=MIN_ITERATIONS)
    entrenadora = users.create("entre", "c", UserRole.TRAINER, "Entrenadora")
    atleta = users.create(
        "atleta", "c", UserRole.ATHLETE, "Atleta", assigned_trainer_id=entrenadora.user_id
    )
    yield CalibrationRepository(db), atleta.user_id, entrenadora.user_id, users
    db.close()



def test_una_calibracion_nueva_queda_pendiente(entorno):
    cal, atleta, _, _ = entorno

    assert cal.create_pending(atleta).status is CalibrationStatus.PENDING


def test_la_calibracion_conserva_las_medidas(entorno):
    cal, atleta, _, _ = entorno

    perfil = cal.create_pending(atleta, **MEDIDAS)

    assert perfil.neutral_knee_angle_deg == pytest.approx(178.0)
    assert perfil.neutral_back_arch_angle_deg == pytest.approx(172.5)
    assert perfil.neutral_elbow_angle_deg == pytest.approx(179.0)
    assert perfil.legs_trunk_ratio == pytest.approx(1.12)
    assert perfil.shoulder_width_ratio == pytest.approx(0.24)


def test_una_medida_no_obtenida_se_guarda_como_ausente(entorno):
    # Un valor a None significa que no pudo medirse, no que sea cero.
    cal, atleta, _, _ = entorno

    perfil = cal.create_pending(atleta, knee_deg=178.0)

    assert perfil.neutral_elbow_angle_deg is None


def test_las_imagenes_se_guardan_como_rutas(entorno):
    # los archivos residen en el sistema de ficheros.
    cal, atleta, _, _ = entorno

    perfil = cal.create_pending(
        atleta, frontal_image="f.png", lateral_image="l.png"
    )

    assert (perfil.frontal_image, perfil.lateral_image) == ("f.png", "l.png")


def test_una_segunda_calibracion_pendiente_se_rechaza(entorno):
    # Lo impone el índice único parcial sobre status = 'pending'.
    cal, atleta, _, _ = entorno
    cal.create_pending(atleta)

    with pytest.raises(DuplicatePendingError):
        cal.create_pending(atleta)


def test_dos_atletas_pueden_tener_su_pendiente_a_la_vez(entorno):
    cal, atleta, entrenadora, users = entorno
    otro = users.create("otro", "c", UserRole.ATHLETE, "Otro")
    cal.create_pending(atleta)

    assert cal.create_pending(otro.user_id).status is CalibrationStatus.PENDING



def test_validar_cambia_el_estado_y_registra_la_decision(entorno):
    cal, atleta, entrenadora, _ = entorno
    perfil = cal.create_pending(atleta, **MEDIDAS)

    validada = cal.validate(perfil.profile_id, entrenadora, note="correcta")

    assert validada.status is CalibrationStatus.VALIDATED
    assert validada.reviewed_by == entrenadora
    assert validada.reviewed_at
    assert validada.review_note == "correcta"


def test_los_umbrales_ajustados_se_conservan(entorno):
    # no son derivables de los ángulos neutros, son una corrección sobre lo derivado.
    cal, atleta, entrenadora, _ = entorno
    perfil = cal.create_pending(atleta, **MEDIDAS)

    validada = cal.validate(
        perfil.profile_id, entrenadora, thresholds={"knee_bend": 7.0, "back_arch": 9.5}
    )

    assert validada.adjusted_thresholds == {"knee_bend": 7.0, "back_arch": 9.5}


def test_validar_sin_ajustes_no_guarda_umbrales(entorno):
    cal, atleta, entrenadora, _ = entorno
    perfil = cal.create_pending(atleta)

    validada = cal.validate(perfil.profile_id, entrenadora)

    assert validada.adjusted_thresholds == {}


def test_la_calibracion_validada_es_la_vigente(entorno):
    cal, atleta, entrenadora, _ = entorno
    perfil = cal.create_pending(atleta)
    cal.validate(perfil.profile_id, entrenadora)

    assert cal.validated_for(atleta).profile_id == perfil.profile_id


def test_validar_una_nueva_sustituye_a_la_anterior(entorno):
    # solo puede haber una calibración vigente. la anterior no fue rechazada.
    cal, atleta, entrenadora, _ = entorno
    primera = cal.create_pending(atleta)
    cal.validate(primera.profile_id, entrenadora)
    segunda = cal.create_pending(atleta)

    cal.validate(segunda.profile_id, entrenadora)

    assert cal.validated_for(atleta).profile_id == segunda.profile_id
    assert cal.get(primera.profile_id).status is CalibrationStatus.SUPERSEDED


def test_validar_una_calibracion_inexistente_se_rechaza(entorno):
    cal, _, entrenadora, _ = entorno

    with pytest.raises(DatabaseError, match="No existe la calibración"):
        cal.validate(9999, entrenadora)



def test_rechazar_cambia_el_estado(entorno):
    cal, atleta, entrenadora, _ = entorno
    perfil = cal.create_pending(atleta)

    rechazada = cal.reject(perfil.profile_id, entrenadora, note="mal encuadre")

    assert rechazada.status is CalibrationStatus.REJECTED
    assert rechazada.review_note == "mal encuadre"


def test_rechazar_no_altera_la_vigente(entorno):
    # la última calibración validada permanece mientras la nueva se decide.
    cal, atleta, entrenadora, _ = entorno
    vigente = cal.create_pending(atleta)
    cal.validate(vigente.profile_id, entrenadora)
    nueva = cal.create_pending(atleta)

    cal.reject(nueva.profile_id, entrenadora)

    assert cal.validated_for(atleta).profile_id == vigente.profile_id


def test_tras_rechazar_se_puede_volver_a_calibrar(entorno):
    cal, atleta, entrenadora, _ = entorno
    primera = cal.create_pending(atleta)
    cal.reject(primera.profile_id, entrenadora)

    assert cal.create_pending(atleta).status is CalibrationStatus.PENDING



def test_sin_calibraciones_no_hay_vigente_ni_pendiente(entorno):
    cal, atleta, _, _ = entorno

    assert cal.validated_for(atleta) is None
    assert cal.pending_for(atleta) is None


def test_la_pendiente_se_recupera_por_atleta(entorno):
    cal, atleta, _, _ = entorno
    perfil = cal.create_pending(atleta)

    assert cal.pending_for(atleta).profile_id == perfil.profile_id


def test_el_historico_va_de_la_mas_reciente_a_la_mas_antigua(entorno):
    cal, atleta, entrenadora, _ = entorno
    primera = cal.create_pending(atleta)
    cal.validate(primera.profile_id, entrenadora)
    segunda = cal.create_pending(atleta)

    historico = cal.history_for(atleta)

    assert [p.profile_id for p in historico] == [
        segunda.profile_id,
        primera.profile_id,
    ]


def test_el_entrenador_ve_las_pendientes_de_su_cartera(entorno):
    # Se restringe la validación a los atletas que supervisa.
    cal, atleta, entrenadora, users = entorno
    ajeno = users.create("ajeno", "c", UserRole.ATHLETE, "Ajeno")
    cal.create_pending(atleta)
    cal.create_pending(ajeno.user_id)

    pendientes = cal.pending_for_trainer(entrenadora)

    assert [p.user_id for p in pendientes] == [atleta]


def test_borrar_una_calibracion_arrastra_sus_umbrales(entorno):
    cal, atleta, entrenadora, _ = entorno
    perfil = cal.create_pending(atleta)
    cal.validate(perfil.profile_id, entrenadora, thresholds={"knee_bend": 7.0})

    cal.delete(perfil.profile_id)

    assert cal.thresholds_of(perfil.profile_id) == {}


def test_borrar_el_atleta_arrastra_sus_calibraciones(entorno):
    cal, atleta, _, users = entorno
    cal.create_pending(atleta)

    users.delete(atleta)

    assert cal.history_for(atleta) == []