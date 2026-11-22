"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Script de asignación de un atleta a un entrenador, externo a la interfaz de la
aplicación.

Uso: python scripts/assign_trainer.py <atleta> <entrenador>
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT))

from core.models.user_role import UserRole  
from core.persistence.database import Database, DatabaseError  
from core.persistence.user_repository import User, UserRepository  
# Valor que retira al atleta de la cartera en la que esté.
_NONE_FLAG = "--ninguno"

_USAGE = (
    "Uso: python scripts/assign_trainer.py <atleta> <entrenador>\n"
    f"     python scripts/assign_trainer.py <atleta> {_NONE_FLAG}"
)


def _find(users: UserRepository, username: str, expected: UserRole) -> User | None:
    # Localiza una cuenta por su nombre de usuario y comprueba su rol.

    user = users.find_by_username(username)
    if user is None:
        print(f"No existe la cuenta '{username}'.")
        return None
    if user.role is not expected:
        print(
            f"La cuenta '{username}' tiene rol {user.role.value}, "
            f"y se esperaba {expected.value}."
        )
        return None
    return user


def main(argv: list[str]) -> int:
    # Asigna un atleta a un entrenador, o lo deja sin entrenador.

    if len(argv) != 3:
        print(_USAGE)
        return 2

    athlete_name, trainer_name = argv[1], argv[2]

    try:
        with Database() as database:
            users = UserRepository(database)

            athlete = _find(users, athlete_name, UserRole.ATHLETE)
            if athlete is None:
                return 1

            if trainer_name == _NONE_FLAG:
                users.assign_trainer(athlete.user_id, None)
                print(f"{athlete.username} queda sin entrenador asignado.")
                return 0

            trainer = _find(users, trainer_name, UserRole.TRAINER)
            if trainer is None:
                return 1

            users.assign_trainer(athlete.user_id, trainer.user_id)
    except DatabaseError as error:
        print(f"No se pudo asignar: {error}")
        return 1

    print(
        f"{athlete.username} ({athlete.full_name}) asignado a "
        f"{trainer.username} ({trainer.full_name})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))