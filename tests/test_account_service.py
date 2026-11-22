import inspect

import pytest

from core.models.user_role import UserRole
from core.persistence.database import IN_MEMORY, Database
from core.persistence.password import MIN_ITERATIONS
from core.persistence.user_repository import DuplicateUserError, UserRepository
from core.services.account_service import (
    MIN_PASSWORD_LENGTH,
    AccountService,
    AccountServiceError,
)

CLAVE = "unaClaveLarga"


@pytest.fixture
def servicio():
    db = Database(IN_MEMORY)
    db.open()
    yield AccountService(UserRepository(db, iterations=MIN_ITERATIONS))
    db.close()


def _registrar(servicio, username="atleta", **cambios):
    datos = {"full_name": "Atleta de prueba", "email": f"{username}@ejemplo.es"}
    datos.update(cambios)
    return servicio.register(username, CLAVE, datos.pop("full_name"), **datos)



def test_el_registro_publico_crea_una_cuenta(servicio):
    creada = _registrar(servicio)

    assert creada.username == "atleta"


def test_el_registro_publico_crea_siempre_un_atleta(servicio):
    assert _registrar(servicio).role is UserRole.ATHLETE


def test_el_registro_no_admite_elegir_rol(servicio):
    # por esta vía no puede nacer un entrenador ni un administrador.
    parametros = inspect.signature(servicio.register).parameters

    assert "role" not in parametros
    assert "rol" not in parametros


def test_el_correo_es_opcional(servicio):
    creada = servicio.register("sincorreo", CLAVE, "Sin Correo")

    assert creada.email is None


def test_un_correo_en_blanco_equivale_a_no_indicarlo(servicio):
    creada = servicio.register("blanco", CLAVE, "Blanco", email="   ")

    assert creada.email is None


def test_un_usuario_repetido_se_rechaza(servicio):
    _registrar(servicio, "repetido")

    with pytest.raises(DuplicateUserError):
        _registrar(servicio, "repetido", email="otro@ejemplo.es")


@pytest.mark.parametrize("username", ["", "   "])
def test_un_usuario_vacio_se_rechaza(servicio, username):
    with pytest.raises(AccountServiceError, match="nombre de usuario"):
        servicio.register(username, CLAVE, "Nombre")


def test_un_nombre_completo_vacio_se_rechaza(servicio):
    with pytest.raises(AccountServiceError, match="nombre completo"):
        servicio.register("usuario", CLAVE, "   ")


def test_se_recortan_los_espacios_de_los_extremos(servicio):
    creada = servicio.register("  atleta  ", CLAVE, "  Atleta  ")

    assert creada.username == "atleta"
    assert creada.full_name == "Atleta"



def test_una_contrasena_corta_se_rechaza(servicio):
    with pytest.raises(AccountServiceError, match="al menos"):
        servicio.register("usuario", "a" * (MIN_PASSWORD_LENGTH - 1), "Nombre")


def test_una_contrasena_de_la_longitud_minima_se_acepta(servicio):
    creada = servicio.register("usuario", "a" * MIN_PASSWORD_LENGTH, "Nombre")

    assert creada.user_id


def test_el_rechazo_no_reproduce_la_contrasena(servicio):
    # no aparece en claro en ningún sitio, mensajes incluidos.
    corta = "secreta"

    try:
        servicio.register("usuario", corta, "Nombre")
    except AccountServiceError as error:
        assert corta not in str(error)



def test_unas_credenciales_correctas_autentican(servicio):
    creada = _registrar(servicio)

    assert servicio.authenticate("atleta", CLAVE).user_id == creada.user_id


def test_una_contrasena_incorrecta_no_autentica(servicio):
    _registrar(servicio)

    assert servicio.authenticate("atleta", "otraClaveLarga") is None


def test_un_usuario_inexistente_no_autentica(servicio):
    assert servicio.authenticate("nadie", CLAVE) is None


def test_los_espacios_del_usuario_no_impiden_entrar(servicio):
    _registrar(servicio)

    assert servicio.authenticate("  atleta  ", CLAVE) is not None


def test_la_contrasena_no_se_recorta(servicio):
    # Un espacio puede formar parte de la contraseña.
    servicio.register("usuario", " claveConEspacio ", "Nombre")

    assert servicio.authenticate("usuario", " claveConEspacio ") is not None
    assert servicio.authenticate("usuario", "claveConEspacio") is None


def test_una_entrada_que_no_es_texto_no_autentica(servicio):
    assert servicio.authenticate(None, CLAVE) is None
    assert servicio.authenticate("atleta", None) is None



def test_se_modifica_el_nombre_completo(servicio):
    cuenta = _registrar(servicio)

    actualizada = servicio.update_profile(cuenta, full_name="Nombre Nuevo")

    assert actualizada.full_name == "Nombre Nuevo"


def test_se_modifica_el_correo(servicio):
    cuenta = _registrar(servicio)

    actualizada = servicio.update_profile(cuenta, email="nuevo@ejemplo.es")

    assert actualizada.email == "nuevo@ejemplo.es"


def test_modificar_un_campo_no_borra_el_otro(servicio):
    cuenta = _registrar(servicio)

    actualizada = servicio.update_profile(cuenta, full_name="Solo El Nombre")

    assert actualizada.email == "atleta@ejemplo.es"


def test_un_nombre_vacio_no_sustituye_al_anterior(servicio):
    cuenta = _registrar(servicio)

    with pytest.raises(AccountServiceError):
        servicio.update_profile(cuenta, full_name="  ")


def test_un_correo_ya_usado_se_rechaza(servicio):
    _registrar(servicio, "uno")
    cuenta = _registrar(servicio, "dos")

    with pytest.raises(DuplicateUserError):
        servicio.update_profile(cuenta, email="uno@ejemplo.es")


def test_la_fotografia_se_guarda_como_nombre_de_archivo(servicio):
    # La imagen reside en el sistema de ficheros, no en la base de datos.
    cuenta = _registrar(servicio)

    actualizada = servicio.set_profile_photo(cuenta, "atleta.png")

    assert actualizada.profile_photo_filename == "atleta.png"


def test_se_puede_retirar_la_fotografia(servicio):
    cuenta = _registrar(servicio)
    servicio.set_profile_photo(cuenta, "atleta.png")

    actualizada = servicio.set_profile_photo(cuenta, None)

    assert actualizada.profile_photo_filename is None



def test_cambiar_la_contrasena_exige_la_anterior(servicio):
    cuenta = _registrar(servicio)

    with pytest.raises(AccountServiceError, match="actual"):
        servicio.change_password(cuenta, "equivocada", "otraClaveLarga")


def test_la_contrasena_nueva_sustituye_a_la_anterior(servicio):
    cuenta = _registrar(servicio)

    servicio.change_password(cuenta, CLAVE, "otraClaveLarga")

    assert servicio.authenticate("atleta", CLAVE) is None
    assert servicio.authenticate("atleta", "otraClaveLarga") is not None


def test_una_contrasena_nueva_corta_se_rechaza(servicio):
    cuenta = _registrar(servicio)

    with pytest.raises(AccountServiceError, match="al menos"):
        servicio.change_password(cuenta, CLAVE, "corta")


def test_un_cambio_rechazado_deja_la_anterior_en_vigor(servicio):
    cuenta = _registrar(servicio)

    with pytest.raises(AccountServiceError):
        servicio.change_password(cuenta, CLAVE, "corta")

    assert servicio.authenticate("atleta", CLAVE) is not None