"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de la pantalla de gestión del perfil propio.
"""

from __future__ import annotations

import customtkinter as ctk

from core.persistence.user_repository import DuplicateUserError
from core.services.account_service import MIN_PASSWORD_LENGTH, AccountServiceError
from ui import formatting, theme
from ui.views.base import BaseView

FIELD_WIDTH = 340


class ProfileView(BaseView):
    # Gestión del perfil propio, común a los tres roles.

    def build(self) -> None:
        cuerpo = ctk.CTkScrollableFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=32, pady=24)

        user = self.context.current_user
        self.heading(cuerpo, "Mi perfil").pack(anchor="w")
        self.muted(
            cuerpo,
            f"{user.username} · {user.role.value} · "
            f"cuenta creada el {formatting.day(user.created_at)}",
        ).pack(anchor="w", pady=(0, 20))

        self._build_data(cuerpo, user)
        self._build_password(cuerpo)
        self._boton_volver(cuerpo)


    def _build_data(self, parent, user) -> None:
        bloque = self._tarjeta(parent, "Datos personales")

        self._full_name = self._campo(bloque, "Nombre completo", user.full_name)
        self._email = self._campo(bloque, "Correo electrónico", user.email or "")

        self._data_message = ctk.CTkLabel(
            bloque, text="", text_color=theme.COLOR_ERROR, wraplength=FIELD_WIDTH
        )
        self._data_message.pack(anchor="w", pady=(6, 0))

        ctk.CTkButton(
            bloque,
            text="Guardar",
            width=160,
            height=38,
            fg_color=theme.COLOR_ACCENT,
            text_color=theme.COLOR_BACKGROUND,
            hover_color="#D98E18",
            command=self._save_data,
        ).pack(anchor="w", pady=(12, 0))

    def _build_password(self, parent) -> None:
        bloque = self._tarjeta(parent, "Cambiar la contraseña")

        self._current = self._campo(bloque, "Contraseña actual", "", show="*")
        self._new = self._campo(bloque, "Contraseña nueva", "", show="*")
        self._repeat = self._campo(bloque, "Repetir la nueva", "", show="*")

        self.muted(bloque, f"Mínimo {MIN_PASSWORD_LENGTH} caracteres", size=12).pack(
            anchor="w"
        )

        self._password_message = ctk.CTkLabel(
            bloque, text="", text_color=theme.COLOR_ERROR, wraplength=FIELD_WIDTH
        )
        self._password_message.pack(anchor="w", pady=(6, 0))

        ctk.CTkButton(
            bloque,
            text="Cambiar",
            width=160,
            height=38,
            fg_color=theme.COLOR_SURFACE,
            text_color=theme.COLOR_TEXT,
            hover_color=theme.COLOR_BACKGROUND,
            command=self._change_password,
        ).pack(anchor="w", pady=(12, 0))


    def _save_data(self) -> None:
        try:
            actualizada = self.context.accounts.update_profile(
                self.context.current_user,
                full_name=self._full_name.get(),
                email=self._email.get(),
            )
        except DuplicateUserError:
            self._data_message.configure(text="Ese correo ya está en uso.")
            return
        except AccountServiceError as error:
            self._data_message.configure(text=str(error))
            return

        # La cuenta activa lleva los datos.
        self.context.sign_in(actualizada)
        self._data_message.configure(
            text="Datos guardados.", text_color=theme.COLOR_TEXT_MUTED
        )

    def _change_password(self) -> None:
        if self._new.get() != self._repeat.get():
            self._password_message.configure(
                text="Las contraseñas no coinciden.", text_color=theme.COLOR_ERROR
            )
            return

        try:
            self.context.accounts.change_password(
                self.context.current_user, self._current.get(), self._new.get()
            )
        except AccountServiceError as error:
            self._password_message.configure(
                text=str(error), text_color=theme.COLOR_ERROR
            )
            return

        for campo in (self._current, self._new, self._repeat):
            campo.delete(0, "end")
        self._password_message.configure(
            text="Contraseña cambiada.", text_color=theme.COLOR_TEXT_MUTED
        )


    def _tarjeta(self, parent, titulo: str) -> ctk.CTkFrame:
        tarjeta = ctk.CTkFrame(parent, fg_color=theme.COLOR_SURFACE, corner_radius=12)
        tarjeta.pack(anchor="w", fill="x", pady=(0, 20))

        interior = ctk.CTkFrame(tarjeta, fg_color="transparent")
        interior.pack(anchor="w", padx=24, pady=20)

        ctk.CTkLabel(
            interior,
            text=titulo,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=theme.COLOR_TEXT,
        ).pack(anchor="w", pady=(0, 12))

        return interior

    def _campo(self, parent, rotulo: str, valor: str, **kwargs) -> ctk.CTkEntry:
        self.muted(parent, rotulo, size=12).pack(anchor="w")
        campo = ctk.CTkEntry(parent, width=FIELD_WIDTH, height=38, **kwargs)
        if valor:
            campo.insert(0, valor)
        campo.pack(anchor="w", pady=(2, 10))
        return campo

    def _boton_volver(self, parent) -> None:
        ctk.CTkButton(
            parent,
            text="Volver",
            width=160,
            height=42,
            fg_color="transparent",
            text_color=theme.COLOR_TEXT_MUTED,
            hover_color=theme.COLOR_SURFACE,
            command=self.app.show_home,
        ).pack(anchor="w")