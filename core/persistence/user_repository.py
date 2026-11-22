"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de acceso a las cuentas del sistema.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from core.models.user_role import UserRole
from core.persistence.database import Database, DatabaseError, utc_now
from core.persistence.password import (
    DEFAULT_ITERATIONS,
    hash_password,
    needs_rehash,
    verify_password,
)


@dataclass(frozen=True)
class User:
    # Cuenta del sistema. No incluye el hash de la contraseña.

    user_id: int
    username: str
    role: UserRole
    full_name: str
    email: str | None = None
    profile_photo_filename: str | None = None
    assigned_trainer_id: int | None = None
    created_at: str = ""


class DuplicateUserError(DatabaseError):
    # El nombre de usuario o el correo ya están en uso.

    pass


class UserRepository:
    # Altas, autenticación y consulta de las cuentas.

    _COLUMNS = (
        "user_id, username, role, full_name, email, "
        "profile_photo_filename, assigned_trainer_id, created_at"
    )

    def __init__(
        self, database: Database, *, iterations: int = DEFAULT_ITERATIONS
    ) -> None:
        # iterations se inyecta para que las pruebas no paguen el coste deliberado de la derivación real.

        self._db = database
        self._iterations = iterations

    def create(
        self,
        username: str,
        password: str,
        role: UserRole,
        full_name: str,
        *,
        email: str | None = None,
        assigned_trainer_id: int | None = None,
    ) -> User:
        # Da de alta una cuenta con su contraseña ya derivada.

        if assigned_trainer_id is not None:
            self._require_trainer(assigned_trainer_id)

        try:
            with self._db.transaction() as connection:
                cursor = connection.execute(
                    "INSERT INTO users (username, password_hash, role, full_name, "
                    "email, assigned_trainer_id, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        username,
                        self._hash(password),
                        role.value,
                        full_name,
                        email,
                        assigned_trainer_id,
                        utc_now(),
                    ),
                )
        except DatabaseError as error:
            if "UNIQUE" in str(error):
                raise DuplicateUserError(
                    f"El nombre de usuario o el correo ya están en uso: {username}"
                ) from error
            raise

        created = self.get(int(cursor.lastrowid))
        if created is None:
            raise DatabaseError(f"No se pudo recuperar la cuenta creada: {username}")
        return created

    def authenticate(self, username: str, password: str) -> User | None:
        # Verifica unas credenciales.

        row = self._db.connection.execute(
            f"SELECT {self._COLUMNS}, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()

        if row is None:
            return None
        if not verify_password(password, row["password_hash"]):
            return None

        if needs_rehash(row["password_hash"], iterations=self._iterations):
            # Se rederiva con las iteraciones vigentes aprovechando que la contraseña en claro está disponible por única vez.
            self.set_password(int(row["user_id"]), password)

        return self._to_user(row)

    def get(self, user_id: int) -> User | None:
        # Cuenta por su identificador.

        row = self._db.connection.execute(
            f"SELECT {self._COLUMNS} FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return self._to_user(row) if row is not None else None

    def find_by_username(self, username: str) -> User | None:
        # Cuenta por su nombre de usuario.

        row = self._db.connection.execute(
            f"SELECT {self._COLUMNS} FROM users WHERE username = ?", (username,)
        ).fetchone()
        return self._to_user(row) if row is not None else None

    def athletes_of(self, trainer_id: int) -> list[User]:
        # Cartera de atletas de un entrenador.

        rows = self._db.connection.execute(
            f"SELECT {self._COLUMNS} FROM users "
            "WHERE assigned_trainer_id = ? ORDER BY full_name",
            (trainer_id,),
        ).fetchall()
        return [self._to_user(row) for row in rows]

    def list_by_role(self, role: UserRole) -> list[User]:
        # Cuentas con un rol determinado.

        rows = self._db.connection.execute(
            f"SELECT {self._COLUMNS} FROM users WHERE role = ? ORDER BY full_name",
            (role.value,),
        ).fetchall()
        return [self._to_user(row) for row in rows]

    def assign_trainer(self, user_id: int, trainer_id: int | None) -> None:
        # Asigna o retira el entrenador que supervisa a un atleta.

        if trainer_id is not None:
            self._require_trainer(trainer_id)
            if trainer_id == user_id:
                raise DatabaseError("Una cuenta no puede supervisarse a sí misma.")

        with self._db.transaction() as connection:
            connection.execute(
                "UPDATE users SET assigned_trainer_id = ? WHERE user_id = ?",
                (trainer_id, user_id),
            )

    def set_password(self, user_id: int, password: str) -> None:
        # Sustituye la contraseña de una cuenta.

        with self._db.transaction() as connection:
            connection.execute(
                "UPDATE users SET password_hash = ? WHERE user_id = ?",
                (self._hash(password), user_id),
            )

    def update_profile(
        self,
        user_id: int,
        *,
        full_name: str | None = None,
        email: str | None = None,
    ) -> None:
        # Modifica los datos personales. Un campo a None se deja como estaba, para que se pueda cambiar uno solo.

        if full_name is None and email is None:
            return

        try:
            with self._db.transaction() as connection:
                connection.execute(
                    "UPDATE users SET full_name = COALESCE(?, full_name), "
                    "email = COALESCE(?, email) WHERE user_id = ?",
                    (full_name, email, user_id),
                )
        except DatabaseError as error:
            if "UNIQUE" in str(error):
                raise DuplicateUserError(
                    f"El correo ya está en uso: {email}"
                ) from error
            raise

    def set_profile_photo(self, user_id: int, filename: str | None) -> None:
        # Fija el archivo de la fotografía de perfil, que reside fuera de la base de datos.

        with self._db.transaction() as connection:
            connection.execute(
                "UPDATE users SET profile_photo_filename = ? WHERE user_id = ?",
                (filename, user_id),
            )

    def delete(self, user_id: int) -> bool:
        # Elimina una cuenta. Sus calibraciones y sesiones se borran en cascada.
        # las cuentas que supervisaba quedan sin entrenador asignado.

        with self._db.transaction() as connection:
            cursor = connection.execute(
                "DELETE FROM users WHERE user_id = ?", (user_id,)
            )
        return cursor.rowcount > 0


    def _hash(self, password: str) -> str:
        # Deriva el hash con las iteraciones configuradas.

        return hash_password(password, iterations=self._iterations)

    def _require_trainer(self, trainer_id: int) -> None:
        # El esquema no puede expresar que la referencia apunte a un entrenador
        # una clave externa no conoce el rol de su destino.

        trainer = self.get(trainer_id)
        if trainer is None:
            raise DatabaseError(f"No existe la cuenta {trainer_id}.")
        if trainer.role is not UserRole.TRAINER:
            raise DatabaseError(
                f"La cuenta {trainer_id} no tiene rol de entrenador: "
                f"{trainer.role.value}."
            )

    @staticmethod
    def _to_user(row: sqlite3.Row) -> User:
        # Traduce una fila a la entidad del dominio.

        return User(
            user_id=int(row["user_id"]),
            username=row["username"],
            role=UserRole.from_string(row["role"]),
            full_name=row["full_name"],
            email=row["email"],
            profile_photo_filename=row["profile_photo_filename"],
            assigned_trainer_id=(
                int(row["assigned_trainer_id"])
                if row["assigned_trainer_id"] is not None
                else None
            ),
            created_at=row["created_at"],
        )