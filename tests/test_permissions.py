import pytest

from core.models.user_role import UserRole
from core.persistence.database import IN_MEMORY, Database
from core.persistence.password import MIN_ITERATIONS
from core.persistence.user_repository import UserRepository
from core.services.permissions import Action, PermissionChecker, PermissionDenied

# Acciones que se ejercen sobre un atleta concreto.
CON_SUJETO = (Action.REVIEW_CALIBRATION, Action.VIEW_PROGRESS)


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
    ajeno = users.create("ajeno", "c", UserRole.ATHLETE, "Ajeno")
    otra = users.create("otra", "c", UserRole.TRAINER, "Otra entrenadora")
    admin = users.create("admin", "c", UserRole.ADMIN, "Administrador")
    yield PermissionChecker(users), atleta, entrenadora, ajeno, otra, admin
    db.close()



@pytest.mark.parametrize(
    "accion, permitida",
    [
        (Action.PRACTICE, True),
        (Action.CALIBRATE, True),
        (Action.REVIEW_CALIBRATION, False),
        (Action.LIST_PENDING_CALIBRATIONS, False),
        (Action.VIEW_PROGRESS, True),
    ],
)
def test_lo_que_puede_un_atleta(entorno, accion, permitida):
    checker, atleta, _, _, _, _ = entorno
    sujeto = atleta.user_id if accion in CON_SUJETO else None

    assert checker.may(atleta, accion, subject_id=sujeto) is permitida


@pytest.mark.parametrize(
    "accion, permitida",
    [
        (Action.PRACTICE, False),
        (Action.CALIBRATE, False),
        (Action.REVIEW_CALIBRATION, True),
        (Action.LIST_PENDING_CALIBRATIONS, True),
        (Action.VIEW_PROGRESS, True),
    ],
)
def test_lo_que_puede_un_entrenador(entorno, accion, permitida):
    checker, atleta, entrenadora, _, _, _ = entorno
    sujeto = atleta.user_id if accion in CON_SUJETO else None

    assert checker.may(entrenadora, accion, subject_id=sujeto) is permitida


@pytest.mark.parametrize("accion", list(Action))
def test_el_administrador_no_participa_en_el_nucleo(entorno, accion):
    checker, atleta, _, _, _, admin = entorno
    sujeto = atleta.user_id if accion in CON_SUJETO else None

    assert not checker.may(admin, accion, subject_id=sujeto)



def test_un_entrenador_valida_las_calibraciones_de_su_cartera(entorno):
    checker, atleta, entrenadora, _, _, _ = entorno

    assert checker.may(
        entrenadora, Action.REVIEW_CALIBRATION, subject_id=atleta.user_id
    )


def test_un_entrenador_no_valida_calibraciones_ajenas(entorno):
    checker, _, entrenadora, ajeno, _, _ = entorno

    assert not checker.may(
        entrenadora, Action.REVIEW_CALIBRATION, subject_id=ajeno.user_id
    )


def test_otro_entrenador_no_entra_en_una_cartera_que_no_es_suya(entorno):
    checker, atleta, _, _, otra, _ = entorno

    assert not checker.may(
        otra, Action.REVIEW_CALIBRATION, subject_id=atleta.user_id
    )


def test_un_entrenador_consulta_el_progreso_de_su_cartera(entorno):
    checker, atleta, entrenadora, _, _, _ = entorno

    assert checker.may(entrenadora, Action.VIEW_PROGRESS, subject_id=atleta.user_id)


def test_un_entrenador_no_consulta_el_progreso_de_un_ajeno(entorno):
    checker, _, entrenadora, ajeno, _, _ = entorno

    assert not checker.may(
        entrenadora, Action.VIEW_PROGRESS, subject_id=ajeno.user_id
    )


def test_un_atleta_solo_consulta_su_propio_progreso(entorno):
    checker, atleta, _, ajeno, _, _ = entorno

    assert checker.may(atleta, Action.VIEW_PROGRESS, subject_id=atleta.user_id)
    assert not checker.may(atleta, Action.VIEW_PROGRESS, subject_id=ajeno.user_id)


def test_un_atleta_no_valida_su_propia_calibracion(entorno):
    # la validación es del entrenador, no del atleta.
    checker, atleta, _, _, _, _ = entorno

    assert not checker.may(
        atleta, Action.REVIEW_CALIBRATION, subject_id=atleta.user_id
    )



@pytest.mark.parametrize("accion", CON_SUJETO)
def test_una_accion_sobre_un_atleta_exige_decir_sobre_cual(entorno, accion):
    # Sin sujeto no se concede: sería un permiso sobre todos.
    checker, _, entrenadora, _, _, _ = entorno

    assert not checker.may(entrenadora, accion, subject_id=None)


def test_una_cuenta_inexistente_no_se_supervisa(entorno):
    checker, _, entrenadora, _, _, _ = entorno

    assert not checker.may(
        entrenadora, Action.REVIEW_CALIBRATION, subject_id=9999
    )


def test_retirar_el_entrenador_le_retira_el_acceso(entorno):
    checker, atleta, entrenadora, _, _, _ = entorno
    checker._users.assign_trainer(atleta.user_id, None)

    assert not checker.may(
        entrenadora, Action.VIEW_PROGRESS, subject_id=atleta.user_id
    )



def test_require_deja_pasar_lo_permitido(entorno):
    checker, atleta, _, _, _, _ = entorno

    checker.require(atleta, Action.PRACTICE)


def test_require_rechaza_lo_no_permitido(entorno):
    checker, _, entrenadora, _, _, _ = entorno

    with pytest.raises(PermissionDenied, match="trainer"):
        checker.require(entrenadora, Action.PRACTICE)


def test_el_rechazo_nombra_la_cuenta_cuando_hay_sujeto(entorno):
    checker, _, entrenadora, ajeno, _, _ = entorno

    with pytest.raises(PermissionDenied, match=str(ajeno.user_id)):
        checker.require(
            entrenadora, Action.REVIEW_CALIBRATION, subject_id=ajeno.user_id
        )


def test_toda_accion_declara_sus_roles(entorno):
    # Una acción nueva sin entrada en la tabla daría KeyError en ejecución.
    checker, atleta, _, _, _, _ = entorno

    for accion in Action:
        checker.may(atleta, accion, subject_id=atleta.user_id)