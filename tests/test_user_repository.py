import pytest

from core.models.user_role import UserRole
from core.persistence.database import IN_MEMORY, Database, DatabaseError
from core.persistence.password import MIN_ITERATIONS
from core.persistence.user_repository import DuplicateUserError, UserRepository


@pytest.fixture
def users():
    db = Database(IN_MEMORY)
    db.open()
    yield UserRepository(db, iterations=MIN_ITERATIONS)
    db.close()


def _entrenadora(users, username="entre"):
    return users.create(username, "clave", UserRole.TRAINER, "Entrenadora")


def _atleta(users, username="atleta", trainer_id=None):
    return users.create(
        username,
        "secreta",
        UserRole.ATHLETE,
        "Atleta",
        email=f"{username}@ejemplo.es",
        assigned_trainer_id=trainer_id,
    )



def test_una_cuenta_creada_se_recupera(users):
    creada = _atleta(users)

    assert users.get(creada.user_id) == creada


def test_la_cuenta_creada_conserva_su_rol(users):
    assert _atleta(users).role is UserRole.ATHLETE


def test_la_cuenta_creada_registra_su_fecha(users):
    assert _atleta(users).created_at


def test_la_entidad_no_expone_el_hash_de_la_contrasena(users):
    # así no puede acabar en un registro ni en una traza.
    assert not hasattr(_atleta(users), "password_hash")


def test_un_nombre_de_usuario_repetido_se_rechaza(users):
    _atleta(users, "repetido")

    with pytest.raises(DuplicateUserError):
        _atleta(users, "repetido")


def test_un_correo_repetido_se_rechaza(users):
    users.create("uno", "c", UserRole.ATHLETE, "Uno", email="mismo@ejemplo.es")

    with pytest.raises(DuplicateUserError):
        users.create("dos", "c", UserRole.ATHLETE, "Dos", email="mismo@ejemplo.es")


def test_la_contrasena_no_se_guarda_en_claro(users):
    creada = _atleta(users)
    almacenado = users._db.connection.execute(
        "SELECT password_hash FROM users WHERE user_id = ?", (creada.user_id,)
    ).fetchone()[0]

    assert "secreta" not in almacenado


def test_unas_credenciales_correctas_devuelven_la_cuenta(users):
    creada = _atleta(users)

    assert users.authenticate("atleta", "secreta").user_id == creada.user_id


def test_una_contrasena_incorrecta_no_autentica(users):
    _atleta(users)

    assert users.authenticate("atleta", "equivocada") is None


def test_un_usuario_inexistente_no_autentica(users):
    assert users.authenticate("nadie", "secreta") is None


def test_no_se_distingue_el_usuario_inexistente_de_la_clave_incorrecta(users):
    # Devolver lo mismo en ambos casos evita revelar qué cuentas existen.
    _atleta(users)

    assert users.authenticate("atleta", "mal") == users.authenticate("nadie", "mal")


def test_cambiar_la_contrasena_invalida_la_anterior(users):
    creada = _atleta(users)

    users.set_password(creada.user_id, "nueva")

    assert users.authenticate("atleta", "secreta") is None
    assert users.authenticate("atleta", "nueva") is not None


def test_la_cartera_contiene_a_los_atletas_supervisados(users):
    entrenadora = _entrenadora(users)
    _atleta(users, "uno", entrenadora.user_id)
    _atleta(users, "dos", entrenadora.user_id)
    _atleta(users, "ajeno")

    cartera = users.athletes_of(entrenadora.user_id)

    assert [u.username for u in cartera] == ["uno", "dos"]


def test_no_se_puede_asignar_como_entrenador_a_un_atleta(users):
    # El esquema no puede expresarlo: una clave externa no conoce el rol.
    uno = _atleta(users, "uno")
    otro = _atleta(users, "otro")

    with pytest.raises(DatabaseError, match="no tiene rol de entrenador"):
        users.assign_trainer(otro.user_id, uno.user_id)


def test_no_se_puede_asignar_un_entrenador_inexistente(users):
    atleta = _atleta(users)

    with pytest.raises(DatabaseError, match="No existe la cuenta"):
        users.assign_trainer(atleta.user_id, 9999)


def test_una_cuenta_no_puede_supervisarse_a_si_misma(users):
    entrenadora = _entrenadora(users)

    with pytest.raises(DatabaseError, match="sí misma"):
        users.assign_trainer(entrenadora.user_id, entrenadora.user_id)


def test_retirar_el_entrenador_deja_la_cuenta_sin_supervision(users):
    entrenadora = _entrenadora(users)
    atleta = _atleta(users, "atleta", entrenadora.user_id)

    users.assign_trainer(atleta.user_id, None)

    assert users.get(atleta.user_id).assigned_trainer_id is None


def test_crear_con_un_entrenador_invalido_se_rechaza(users):
    uno = _atleta(users, "uno")

    with pytest.raises(DatabaseError):
        _atleta(users, "dos", uno.user_id)



def test_se_encuentra_una_cuenta_por_su_nombre(users):
    _atleta(users)

    assert users.find_by_username("atleta") is not None


def test_un_nombre_inexistente_no_encuentra_nada(users):
    assert users.find_by_username("nadie") is None


def test_se_listan_las_cuentas_por_rol(users):
    _entrenadora(users)
    _atleta(users, "uno")
    _atleta(users, "dos")

    assert len(users.list_by_role(UserRole.ATHLETE)) == 2
    assert len(users.list_by_role(UserRole.TRAINER)) == 1



def test_borrar_una_cuenta_la_elimina(users):
    atleta = _atleta(users)

    assert users.delete(atleta.user_id)
    assert users.get(atleta.user_id) is None


def test_borrar_una_cuenta_inexistente_no_falla(users):
    assert not users.delete(9999)


def test_borrar_un_entrenador_deja_a_sus_atletas_sin_supervision(users):
    entrenadora = _entrenadora(users)
    atleta = _atleta(users, "atleta", entrenadora.user_id)

    users.delete(entrenadora.user_id)

    assert users.get(atleta.user_id).assigned_trainer_id is None



def test_la_fotografia_se_guarda_como_nombre_de_archivo(users):
    # La imagen reside en el sistema de ficheros, no en la base de datos.
    atleta = _atleta(users)

    users.set_profile_photo(atleta.user_id, "atleta.png")

    assert users.get(atleta.user_id).profile_photo_filename == "atleta.png"