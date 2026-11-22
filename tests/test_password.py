import pytest

from core.persistence.password import (
    ALGORITHM,
    DEFAULT_ITERATIONS,
    MIN_ITERATIONS,
    SALT_BYTES,
    PasswordError,
    hash_password,
    needs_rehash,
    verify_password,
)

CLAVE = "una contraseña con espacios y ñ"
# Las pruebas usan el mínimo legal: la derivación real es lenta a propósito.
ITER = MIN_ITERATIONS


def _hash(password=CLAVE, iterations=ITER):
    return hash_password(password, iterations=iterations)



def test_una_contrasena_se_verifica_contra_su_hash():
    assert verify_password(CLAVE, _hash())


def test_una_contrasena_incorrecta_no_se_verifica():
    assert not verify_password("otra cosa", _hash())


def test_el_hash_no_contiene_la_contrasena():
    # la contraseña no se almacena en claro en ningún sitio.
    almacenado = _hash()

    assert CLAVE not in almacenado


def test_dos_hashes_de_la_misma_contrasena_difieren():
    #  efecto de la sal. dos cuentas con igual contraseña no comparten hash.
    assert _hash() != _hash()


def test_la_sal_se_almacena_con_el_hash():
    partes = _hash().split("$")

    assert len(partes) == 4
    assert partes[0] == ALGORITHM
    assert int(partes[1]) == ITER
    assert len(partes[2]) >= SALT_BYTES


def test_la_misma_sal_produce_el_mismo_hash():
    sal = b"0123456789abcdef"

    assert hash_password(CLAVE, iterations=ITER, salt=sal) == hash_password(
        CLAVE, iterations=ITER, salt=sal
    )


def test_el_algoritmo_vigente_usa_iteraciones_suficientes():
    # No se deriva nada aquí. se comprueba la constante configurada.
    assert DEFAULT_ITERATIONS >= MIN_ITERATIONS



def test_una_contrasena_vacia_se_rechaza():
    with pytest.raises(PasswordError, match="vacía"):
        hash_password("")


def test_unas_iteraciones_insuficientes_se_rechazan():
    # Evita que una configuración descuidada debilite la derivación.
    with pytest.raises(PasswordError, match="al menos"):
        hash_password(CLAVE, iterations=MIN_ITERATIONS - 1)


def test_el_mensaje_de_error_no_revela_la_contrasena():
    try:
        hash_password(CLAVE, iterations=1)
    except PasswordError as error:
        assert CLAVE not in str(error)



def test_un_hash_manipulado_no_se_verifica():
    almacenado = _hash()
    partes = almacenado.split("$")
    partes[3] = "A" * len(partes[3])

    assert not verify_password(CLAVE, "$".join(partes))


def test_una_sal_cambiada_no_se_verifica():
    partes = _hash().split("$")
    partes[2] = "B" * len(partes[2])

    assert not verify_password(CLAVE, "$".join(partes))


@pytest.mark.parametrize(
    "almacenado", ["", "sin separadores", "a$b$c", "a$b$c$d$e", "pbkdf2_sha256$x$y$z"]
)
def test_un_hash_ilegible_deniega_el_acceso(almacenado):
    # Un registro corrupto debe denegar la autenticación, no interrumpirla.
    assert verify_password(CLAVE, almacenado) is False


def test_otro_algoritmo_no_se_verifica():
    partes = _hash().split("$")
    partes[0] = "md5"

    assert not verify_password(CLAVE, "$".join(partes))


def test_una_contrasena_vacia_no_se_verifica_nunca():
    assert not verify_password("", _hash())



def test_un_hash_con_las_iteraciones_vigentes_no_necesita_rederivarse():
    assert not needs_rehash(_hash(), iterations=ITER)


def test_un_hash_debil_necesita_rederivarse():
    # Permite subir las iteraciones sin invalidar las cuentas existentes.
    assert needs_rehash(_hash(iterations=ITER), iterations=ITER * 2)


def test_un_hash_ilegible_necesita_rederivarse():
    assert needs_rehash("basura")


def test_un_hash_de_otro_algoritmo_necesita_rederivarse():
    partes = _hash().split("$")
    partes[0] = "md5"

    assert needs_rehash("$".join(partes), iterations=ITER)