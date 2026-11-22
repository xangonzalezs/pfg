"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de la pantalla de inicio de sesión.
"""

from __future__ import annotations

import customtkinter as ctk

from ui import theme
from ui.views.base import BaseView

FIELD_WIDTH = 340


class LoginView(BaseView):
    # Acceso al sistema.

    def build(self) -> None:
        # El ancho lo fija el contenido.
        card = ctk.CTkFrame(self, fg_color=theme.COLOR_SURFACE, corner_radius=16)
        card.place(relx=0.5, rely=0.5, anchor="center")

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=40, pady=40, fill="both")

        self.heading(inner, theme.APP_NAME).pack(pady=(0, 4))
        self.muted(inner, "Entrenamiento del pino con feedback auditivo").pack(
            pady=(0, 24)
        )

        self._username = ctk.CTkEntry(
            inner, placeholder_text="Usuario", width=340, height=40
        )
        self._username.pack(pady=6)

        self._password = ctk.CTkEntry(
            inner, placeholder_text="Contraseña", show="*", width=340, height=40
        )
        self._password.pack(pady=6)

        self._message = ctk.CTkLabel(
            inner, text="", text_color=theme.COLOR_ERROR, wraplength=340
        )
        self._message.pack(pady=(10, 0))

        ctk.CTkButton(
            inner,
            text="Entrar",
            width=340,
            height=42,
            fg_color=theme.COLOR_ACCENT,
            text_color=theme.COLOR_BACKGROUND,
            hover_color="#D98E18",
            command=self._sign_in,
        ).pack(pady=(14, 8))

        ctk.CTkButton(
            inner,
            text="Crear una cuenta",
            width=340,
            height=36,
            fg_color="transparent",
            text_color=theme.COLOR_TEXT_MUTED,
            hover_color=theme.COLOR_BACKGROUND,
            command=self.app.show_register,
        ).pack()

        self._username.focus_set()
        # Entrar con la tecla intro desde cualquiera de los dos campos.
        for entry in (self._username, self._password):
            entry.bind("<Return>", lambda _event: self._sign_in())

    def _sign_in(self) -> None:
        # Verifica las credenciales y entra al panel que toque.

        user = self.context.accounts.authenticate(
            self._username.get(), self._password.get()
        )
        if user is None:
            # Un mensaje único para ambos casos.
            self._message.configure(text="Usuario o contraseña incorrectos.")
            self._password.delete(0, "end")
            return

        self.context.sign_in(user)
        self.app.show_home()