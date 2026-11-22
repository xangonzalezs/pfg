"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de la pantalla de registro público.
"""

from __future__ import annotations

import customtkinter as ctk

from core.persistence.user_repository import DuplicateUserError
from core.services.account_service import MIN_PASSWORD_LENGTH, AccountServiceError
from ui import theme
from ui.views.base import BaseView

FIELD_WIDTH = 340


class RegisterView(BaseView):
    # Registro público. Solo crea cuentas de atleta y no ofrece selector de rol.

    def build(self) -> None:
        card = ctk.CTkFrame(self, fg_color=theme.COLOR_SURFACE, corner_radius=16)
        card.place(relx=0.5, rely=0.5, anchor="center")

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=40, pady=36, fill="both")

        self.heading(inner, "Crear una cuenta").pack(pady=(0, 4))
        self.muted(inner, "Se creará una cuenta de atleta").pack(pady=(0, 20))


        self._full_name = self._entry(inner, "Nombre completo")
        self._username = self._entry(inner, "Usuario")
        self._password = self._entry(inner, "Contraseña", show="*")
        self._repeat = self._entry(inner, "Repetir contraseña", show="*")

        self.muted(
            inner, f"Mínimo {MIN_PASSWORD_LENGTH} caracteres", size=12
        ).pack(pady=(2, 0))

        self._message = ctk.CTkLabel(
            inner, text="", text_color=theme.COLOR_ERROR, wraplength=FIELD_WIDTH
        )
        self._message.pack(pady=(10, 0))

        ctk.CTkButton(
            inner,
            text="Crear cuenta",
            width=FIELD_WIDTH,
            height=42,
            fg_color=theme.COLOR_ACCENT,
            text_color=theme.COLOR_BACKGROUND,
            hover_color="#D98E18",
            command=self._create_account,
        ).pack(pady=(14, 8))

        ctk.CTkButton(
            inner,
            text="Volver al acceso",
            width=FIELD_WIDTH,
            height=36,
            fg_color="transparent",
            text_color=theme.COLOR_TEXT_MUTED,
            hover_color=theme.COLOR_BACKGROUND,
            command=self.app.show_login,
        ).pack()

        self._full_name.focus_set()

    def _entry(self, parent, placeholder: str, **kwargs) -> ctk.CTkEntry:
        # Campo del formulario con el mismo tamaño en todos.

        entry = ctk.CTkEntry(
            parent, placeholder_text=placeholder, width=FIELD_WIDTH, height=40, **kwargs
        )
        entry.pack(pady=5)
        return entry

    def _create_account(self) -> None:
        # Crea la cuenta y entra directamente con ella.

        if self._password.get() != self._repeat.get():
            self._message.configure(text="Las contraseñas no coinciden.")
            return

        try:
            created = self.context.accounts.register(
                self._username.get(),
                self._password.get(),
                self._full_name.get(),
            )
        except DuplicateUserError:
            self._message.configure(text="Ese nombre de usuario ya está en uso.")
            return
        except AccountServiceError as error:
            self._message.configure(text=str(error))
            return

        self.context.sign_in(created)
        self.app.show_home()