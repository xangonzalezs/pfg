"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo del panel del atleta.
"""

from __future__ import annotations

from tkinter import filedialog

import customtkinter as ctk

from core.models.calibration_status import CalibrationStatus
from ui import formatting, theme
from ui.views.base import BaseView

RECENT_SESSIONS = 8
VIDEO_TYPES = [("Vídeo", "*.mp4 *.avi *.mov *.mkv"), ("Todos", "*.*")]


class AthleteHomeView(BaseView):
    # Panel del atleta: calibración, práctica e histórico.

    def build(self) -> None:
        user = self.context.current_user

        self._build_header(user)

        cuerpo = ctk.CTkScrollableFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=32, pady=(8, 24))

        self._build_calibration(cuerpo, user)
        self._build_actions(cuerpo)
        self._build_history(cuerpo, user)


    def _build_header(self, user) -> None:
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

    def _build_calibration(self, parent, user) -> None:
        # El estado de la calibración decide con qué umbrales se practica.

        validada = self.context.calibrations.validated_for(user.user_id)
        pendiente = self.context.calibrations.pending_for(user.user_id)

        if validada is not None:
            texto = "Calibración validada: practicas con umbrales personalizados."
            color = theme.COLOR_TEXT_MUTED
        elif pendiente is not None:
            texto = (
                "Calibración pendiente de que tu entrenador la valide. "
                "Mientras tanto practicas con umbrales genéricos."
            )
            color = theme.COLOR_WARNING
        else:
            texto = "Sin calibrar: practicas con umbrales genéricos."
            color = theme.COLOR_WARNING

        ctk.CTkLabel(
            parent, text=texto, text_color=color, wraplength=820, justify="left"
        ).pack(anchor="w", pady=(0, 16))

        if not self.context.has_model:
            ctk.CTkLabel(
                parent,
                text="Falta el modelo de estimación de pose. Ejecute "
                "scripts/download_model.py para poder calibrar y practicar.",
                text_color=theme.COLOR_ERROR,
                wraplength=820,
                justify="left",
            ).pack(anchor="w", pady=(0, 16))

    def _build_actions(self, parent) -> None:
        fila = ctk.CTkFrame(parent, fg_color="transparent")
        fila.pack(fill="x", pady=(0, 24))

        disponible = "normal" if self.context.has_model else "disabled"

        self._accion(fila, "Practicar", self.app.show_practice, disponible, True)
        self._accion(fila, "Calibración corporal", self.app.show_calibration,
                     disponible, False)
        self._accion(fila, "Analizar un vídeo", self._choose_video,
                     disponible, False)

    def _accion(self, parent, texto, orden, estado, destacado) -> None:
        ctk.CTkButton(
            parent,
            text=texto,
            width=220,
            height=48,
            state=estado,
            command=orden,
            fg_color=theme.COLOR_ACCENT if destacado else theme.COLOR_SURFACE,
            text_color=theme.COLOR_BACKGROUND if destacado else theme.COLOR_TEXT,
            hover_color="#D98E18" if destacado else theme.COLOR_BACKGROUND,
        ).pack(side="left", padx=(0, 12))

    def _build_history(self, parent, user) -> None:
        self.muted(parent, "Últimas sesiones").pack(anchor="w", pady=(0, 6))

        sesiones = self.context.sessions.recent_for(
            user.user_id, limit=RECENT_SESSIONS
        )
        if not sesiones:
            self.muted(parent, "Todavía no has registrado ninguna sesión.").pack(
                anchor="w"
            )
            return

        for sesion in sesiones:
            self._fila_sesion(parent, sesion)

    def _fila_sesion(self, parent, sesion) -> None:
        fila = ctk.CTkFrame(parent, fg_color=theme.COLOR_SURFACE, corner_radius=10)
        fila.pack(fill="x", pady=3)

        interior = ctk.CTkFrame(fila, fg_color="transparent")
        interior.pack(fill="x", padx=16, pady=10)

        ctk.CTkLabel(
            interior,
            text=formatting.timestamp(sesion.timestamp),
            text_color=theme.COLOR_TEXT,
            width=160,
            anchor="w",
        ).pack(side="left")

        ctk.CTkLabel(
            interior,
            text=formatting.score(sesion.mean_alignment_score),
            text_color=theme.color_for_score(sesion.mean_alignment_score),
            width=70,
            anchor="w",
        ).pack(side="left")

        detalle = (
            f"{formatting.duration(sesion.total_hold_time_s)} en pino · "
            f"{sesion.hold_attempts} intentos · "
            f"{len(sesion.errors)} desviaciones · "
            f"vista {sesion.view_mode.value}"
        )
        self.muted(interior, detalle).pack(side="left")


    def _choose_video(self) -> None:
        # Analizar una grabación con el mismo recorrido que la cámara.

        ruta = filedialog.askopenfilename(
            title="Elegir vídeo para analizar", filetypes=VIDEO_TYPES
        )
        if ruta:
            self.app.show_practice(video_path=ruta)