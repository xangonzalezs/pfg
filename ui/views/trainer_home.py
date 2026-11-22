"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo del panel del entrenador.
"""

from __future__ import annotations

import customtkinter as ctk

from ui import formatting, theme
from ui.views.base import BaseView


class TrainerHomeView(BaseView):
    # Cartera de atletas supervisados, con sus calibraciones pendientes de validar destacadas.

    def build(self) -> None:
        user = self.context.current_user

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=32, pady=(28, 0))
        self.heading(header, f"Hola, {user.full_name}").pack(side="left")

        derecha = ctk.CTkFrame(header, fg_color="transparent")
        derecha.pack(side="right")
        ctk.CTkButton(
            derecha,
            text="Mi perfil",
            width=110,
            fg_color="transparent",
            text_color=theme.COLOR_TEXT_MUTED,
            hover_color=theme.COLOR_SURFACE,
            command=self.app.show_profile,
        ).pack(side="left")
        ctk.CTkButton(
            derecha,
            text="Cerrar sesión",
            width=130,
            fg_color="transparent",
            text_color=theme.COLOR_TEXT_MUTED,
            hover_color=theme.COLOR_SURFACE,
            command=self.app.sign_out,
        ).pack(side="left")

        cuerpo = ctk.CTkScrollableFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=32, pady=(12, 24))

        self._build_pending(cuerpo, user)
        self._build_roster(cuerpo, user)


    def _build_pending(self, parent, user) -> None:

        pendientes = self.context.calibrations.pending_for_trainer(user.user_id)
        if not pendientes:
            return

        ctk.CTkLabel(
            parent,
            text=f"Calibraciones pendientes de validar ({len(pendientes)})",
            text_color=theme.COLOR_WARNING,
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", pady=(0, 6))

        for perfil in pendientes:
            atleta = self.context.users.get(perfil.user_id)
            if atleta is None:
                continue

            fila = ctk.CTkFrame(parent, fg_color=theme.COLOR_SURFACE, corner_radius=10)
            fila.pack(fill="x", pady=3)
            interior = ctk.CTkFrame(fila, fg_color="transparent")
            interior.pack(fill="x", padx=16, pady=10)

            ctk.CTkLabel(
                interior, text=atleta.full_name, text_color=theme.COLOR_TEXT,
                width=220, anchor="w",
            ).pack(side="left")
            self.muted(
                interior, f"enviada el {formatting.day(perfil.created_at)}"
            ).pack(side="left")

            ctk.CTkButton(
                interior,
                text="Revisar",
                width=120,
                fg_color=theme.COLOR_ACCENT,
                text_color=theme.COLOR_BACKGROUND,
                hover_color="#D98E18",
                command=lambda p=perfil.profile_id: self.app.show_review(profile_id=p),
            ).pack(side="right")

        ctk.CTkFrame(parent, fg_color="transparent", height=16).pack()

    def _build_roster(self, parent, user) -> None:
        atletas = self.context.users.athletes_of(user.user_id)

        self.muted(parent, f"Atletas supervisados ({len(atletas)})").pack(
            anchor="w", pady=(0, 6)
        )

        if not atletas:
            self.muted(
                parent,
                "Todavía no tienes atletas asignados. La asignación se realiza "
                "con scripts/create_account.py y la gestión de cuentas, que "
                "queda fuera del alcance implementado.",
            ).pack(anchor="w")
            return

        for atleta in atletas:
            self._fila_atleta(parent, atleta)

    def _fila_atleta(self, parent, atleta) -> None:
        fila = ctk.CTkFrame(parent, fg_color=theme.COLOR_SURFACE, corner_radius=10)
        fila.pack(fill="x", pady=3)
        interior = ctk.CTkFrame(fila, fg_color="transparent")
        interior.pack(fill="x", padx=16, pady=10)

        ctk.CTkLabel(
            interior, text=atleta.full_name, text_color=theme.COLOR_TEXT,
            width=220, anchor="w",
        ).pack(side="left")

        validada = self.context.calibrations.validated_for(atleta.user_id)
        estado = "calibrado" if validada is not None else "sin calibrar"
        sesiones = self.context.sessions.count_for(atleta.user_id)
        self.muted(interior, f"{estado} · {sesiones} sesiones").pack(side="left")

        ctk.CTkButton(
            interior,
            text="Ver sesiones",
            width=130,
            fg_color=theme.COLOR_BACKGROUND,
            text_color=theme.COLOR_TEXT,
            hover_color=theme.COLOR_SURFACE,
            command=lambda a=atleta.user_id: self.app.show_athlete(athlete_id=a),
        ).pack(side="right")