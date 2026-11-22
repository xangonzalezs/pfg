"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo del servicio de acceso al sistema y de gestión del perfil.
"""

from __future__ import annotations

from core.models.user_role import UserRole
from core.persistence.user_repository import User, UserRepository

# Longitud mínima de contraseña.
MIN_PASSWORD_LENGTH = 8


class AccountServiceError(Exception):
    # Los datos de la cuenta o del perfil no son válidos.

    pass


class AccountService:
    # Registro público, autenticación y perfil (CU-01, CU-02).

    def __init__(self, users: UserRepository) -> None:
        self._users = users

    def register(
        self,
        username: str,
        password: str,
        full_name: str,
        *,
        email: str | None = None,
    ) -> User:
        # Crea una cuenta desde el registro público.

        username = self._clean(username, "nombre de usuario")
        full_name = self._clean(full_name, "nombre completo")
        self._check_password(password)

        return self._users.create(
            username,
            password,
            UserRole.ATHLETE,
            full_name,
            email=self._clean_optional(email),
        )

    def authenticate(self, username: str, password: str) -> User | None:
        # Verifica unas credenciales y devuelve la cuenta, o None.

        if not isinstance(username, str) or not isinstance(password, str):
            return None
        return self._users.authenticate(username.strip(), password)

    def update_profile(
        self,
        actor: User,
        *,
        full_name: str | None = None,
        email: str | None = None,
    ) -> User:
        # Modifica los datos personales de la propia cuenta.

        if full_name is not None:
            full_name = self._clean(full_name, "nombre completo")
        self._users.update_profile(
            actor.user_id, full_name=full_name, email=self._clean_optional(email)
        )
        return self._require(actor.user_id)

    def set_profile_photo(self, actor: User, filename: str | None) -> User:
        # Fija la fotografía de perfil, que reside en el sistema de ficheros.

        self._users.set_profile_photo(actor.user_id, self._clean_optional(filename))
        return self._require(actor.user_id)

    def change_password(
        self, actor: User, current_password: str, new_password: str
    ) -> None:
        # Cambia la contraseña de la propia cuenta, exigiendo la anterior.

        if self._users.authenticate(actor.username, current_password) is None:
            raise AccountServiceError("La contraseña actual no es correcta.")

        self._check_password(new_password)
        self._users.set_password(actor.user_id, new_password)


    @staticmethod
    def _clean(value: str, field: str) -> str:
        # Exige un valor no vacío y le quita los espacios de los extremos.

        if not isinstance(value, str) or not value.strip():
            raise AccountServiceError(f"El {field} no puede estar vacío.")
        return value.strip()

    @staticmethod
    def _clean_optional(value: str | None) -> str | None:
        # Un campo opcional en blanco equivale a no haberlo indicado.

        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @staticmethod
    def _check_password(password: str) -> None:
        # Comprueba la longitud mínima sin reproducir la contraseña (NFR-03).

        if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
            raise AccountServiceError(
                f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} "
                f"caracteres."
            )

    def _require(self, user_id: int) -> User:
        # Cuenta existente, o AccountServiceError.

        user = self._users.get(user_id)
        if user is None:
            raise AccountServiceError(f"No existe la cuenta {user_id}.")
        return user