"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de derivación y verificación del hash de las contraseñas.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

# Algoritmo, de la biblioteca estándar.
ALGORITHM = "pbkdf2_sha256"
_HASH_NAME = "sha256"

# Iteraciones y longitud de la sal, conforme a las recomendaciones vigentes.
DEFAULT_ITERATIONS = 600_000
MIN_ITERATIONS = 100_000
SALT_BYTES = 16

_SEPARATOR = "$"


class PasswordError(Exception):
    # La contraseña o el hash almacenado no son utilizables.

    pass


def hash_password(
    password: str,
    *,
    iterations: int = DEFAULT_ITERATIONS,
    salt: bytes | None = None,
) -> str:
    # Deriva el hash de una contraseña con una sal aleatoria por usuario.

    if not isinstance(password, str) or not password:
        raise PasswordError("La contraseña no puede estar vacía.")
    if iterations < MIN_ITERATIONS:
        raise PasswordError(
            f"Las iteraciones deben ser al menos {MIN_ITERATIONS}; "
            f"se han recibido {iterations}."
        )

    salt = salt if salt is not None else secrets.token_bytes(SALT_BYTES)
    digest = _derive(password, salt, iterations)

    return _SEPARATOR.join(
        (ALGORITHM, str(iterations), _encode(salt), _encode(digest))
    )


def verify_password(password: str, stored: str) -> bool:
    # Comprueba una contraseña contra su hash almacenado.

    try:
        algorithm, iterations, salt, expected = _split(stored)
    except PasswordError:
        return False

    if algorithm != ALGORITHM:
        return False
    if not isinstance(password, str) or not password:
        return False

    digest = _derive(password, salt, iterations)

    # Comparación en tiempo constante, para no filtrar información por eltiempo que tarda en fallar.
    return hmac.compare_digest(digest, expected)


def needs_rehash(stored: str, *, iterations: int = DEFAULT_ITERATIONS) -> bool:
    # Indica si un hash se derivó con menos iteraciones de las vigentes.
    # Para que pueda rederivarse en el siguiente inicio de sesión válido.

    try:
        algorithm, stored_iterations, _, _ = _split(stored)
    except PasswordError:
        return True

    return algorithm != ALGORITHM or stored_iterations < iterations



def _derive(password: str, salt: bytes, iterations: int) -> bytes:
    # Aplica la función de derivación.

    return hashlib.pbkdf2_hmac(
        _HASH_NAME, password.encode("utf-8"), salt, iterations
    )


def _split(stored: str) -> tuple[str, int, bytes, bytes]:
    # Descompone un hash almacenado en sus cuatro partes.

    if not isinstance(stored, str):
        raise PasswordError("El hash almacenado no es una cadena.")

    parts = stored.split(_SEPARATOR)
    if len(parts) != 4:
        raise PasswordError("El hash almacenado no tiene el formato esperado.")

    algorithm, raw_iterations, raw_salt, raw_digest = parts
    try:
        iterations = int(raw_iterations)
        salt = _decode(raw_salt)
        digest = _decode(raw_digest)
    except (ValueError, TypeError) as error:
        raise PasswordError(f"El hash almacenado no es legible: {error}") from error

    return algorithm, iterations, salt, digest


def _encode(raw: bytes) -> str:
    # Codifica en base64 sin relleno, para que no aparezca el separador.

    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    # Restituye el relleno que _encode suprime.

    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)