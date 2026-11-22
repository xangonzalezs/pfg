"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Script de creación de cuentas de entrenador y de administrador, externo a la
interfaz de la aplicación.

La contraseña se pide por teclado y no se pasa como argumento, para que no
quede registrada en el historial del intérprete de órdenes.

Uso:
    python scripts/create_account.py trainer <usuario> "<nombre completo>"
    python scripts/create_account.py admin   <usuario> "<nombre completo>"

"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT))

from core.models.user_role import UserRole  # noqa: E402
from core.persistence.database import Database, DatabaseError  # noqa: E402
from core.persistence.user_repository import (  # noqa: E402
    DuplicateUserError,
    UserRepository,
)
from core.services.account_service import MIN_PASSWORD_LENGTH  # noqa: E402

# Roles que este script puede crear.
CREATABLE_ROLES = {
    UserRole.TRAINER.value: UserRole.TRAINER,
    UserRole.ADMIN.value: UserRole.ADMIN,
}

_USAGE = (
    'Uso: python scripts/create_account.py {trainer|admin} <usuario> '
    '"<nombre completo>"'
)


def _read_password() -> str | None:
    # Pide la contraseña dos veces y comprueba longitud y coincidencia.

    first = getpass.getpass("Contraseña: ")
    if len(first) < MIN_PASSWORD_LENGTH:
        print(f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres.")
        return None
    if first != getpass.getpass("Repita la contraseña: "):
        print("Las contraseñas no coinciden.")
        return None
    return first


def main(argv: list[str]) -> int:
    # Crea una cuenta de entrenador o de administrador.

    if len(argv) != 4:
        print(_USAGE)
        return 2

    role = CREATABLE_ROLES.get(argv[1].lower())
    if role is None:
        print(f"Rol no reconocido: {argv[1]}")
        print(_USAGE)
        return 2

    username, full_name = argv[2], argv[3]
    password = _read_password()
    if password is None:
        return 1

    try:
        with Database() as database:
            users = UserRepository(database)
            if role is UserRole.ADMIN:
                existing = users.list_by_role(UserRole.ADMIN)
                if existing:
                    # Se avisa, pero no se impide. puede hacer falta otracuenta si se pierde el acceso a la primera.
                    print(f"Aviso: ya hay {len(existing)} administradores.")

            created = users.create(username, password, role, full_name)
    except DuplicateUserError:
        print(f"El nombre de usuario '{username}' ya está en uso.")
        return 1
    except DatabaseError as error:
        print(f"No se pudo crear la cuenta: {error}")
        return 1

    print(
        f"Cuenta creada: {created.username} "
        f"(id {created.user_id}, rol {created.role.value})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))