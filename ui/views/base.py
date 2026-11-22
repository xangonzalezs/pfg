"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo base de las pantallas de la aplicación.
"""

from __future__ import annotations

import customtkinter as ctk

from ui import theme


class BaseView(ctk.CTkFrame):
    # Pantalla de la aplicación. Guarda la referencia a la ventana para poder pedirle que navegue, y al contexto para alcanzar los servicios.

    def __init__(self, parent, app, **kwargs) -> None:
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.app = app
        self.context = app.context
        self.build()

    def build(self) -> None:
        # Construye los widgets. Cada pantalla la sobrescribe.

        raise NotImplementedError

    def teardown(self) -> None:
        # Libera lo que la pantalla tenga vivo (cámara, hilos, temporizadores) antes de destruirla.
        pass

    def heading(self, parent, text: str) -> ctk.CTkLabel:
        # Título de pantalla, con el mismo tratamiento en todas.

        return ctk.CTkLabel(
            parent,
            text=text,
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=theme.COLOR_TEXT,
        )

    def muted(self, parent, text: str, size: int = 13) -> ctk.CTkLabel:
        # Texto secundario.

        return ctk.CTkLabel(
            parent,
            text=text,
            font=ctk.CTkFont(size=size),
            text_color=theme.COLOR_TEXT_MUTED,
        )