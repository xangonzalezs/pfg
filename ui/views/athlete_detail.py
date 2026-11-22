"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de la pantalla de revisión de las sesiones de un atleta.
"""

from __future__ import annotations

import customtkinter as ctk

from core.services.permissions import Action, PermissionDenied
from ui import charts, formatting, theme
from ui.views.base import BaseView

SESSIONS = 20
BAR_WIDTH = 300


class AthleteDetailView(BaseView):
    # Progreso de un atleta: sus sesiones y el patrón de error que repite a lo largo de ellas.

    def __init__(self, parent, app, *, athlete_id: int) -> None:
        self._athlete_id = athlete_id
        super().__init__(parent, app)

    def build(self) -> None:
        cuerpo = ctk.CTkScrollableFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=32, pady=24)

        try:
            self.context.permissions.require(
                self.context.current_user,
                Action.VIEW_PROGRESS,
                subject_id=self._athlete_id,
            )
        except PermissionDenied:
            self.heading(cuerpo, "No puedes consultar este atleta").pack(anchor="w")
            self._boton_volver(cuerpo)
            return

        atleta = self.context.users.get(self._athlete_id)
        if atleta is None:
            self.heading(cuerpo, "Atleta no encontrado").pack(anchor="w")
            self._boton_volver(cuerpo)
            return

        self.heading(cuerpo, atleta.full_name).pack(anchor="w", pady=(0, 16))

        self._build_calibration(cuerpo)
        self._build_pattern(cuerpo)
        self._build_sessions(cuerpo)
        self._boton_volver(cuerpo)


    def _build_calibration(self, parent) -> None:
        validada = self.context.calibrations.validated_for(self._athlete_id)

        if validada is None:
            texto = "Sin calibración validada: practica con umbrales genéricos."
            color = theme.COLOR_WARNING
        else:
            texto = (
                f"Calibración validada el "
                f"{formatting.day(validada.reviewed_at)}."
            )
            if validada.adjusted_thresholds:
                ajustados = ", ".join(sorted(validada.adjusted_thresholds))
                texto += f" Umbrales ajustados a mano: {ajustados}."
            color = theme.COLOR_TEXT_MUTED

        ctk.CTkLabel(
            parent, text=texto, text_color=color, wraplength=820, justify="left"
        ).pack(anchor="w", pady=(0, 20))

    def _build_pattern(self, parent) -> None:
        # El patrón a lo largo del tiempo, no el de una sesión.

        self.muted(parent, "Desviaciones más repetidas en todas sus sesiones").pack(
            anchor="w"
        )

        recuento = self.context.sessions.error_counts_for(self._athlete_id)
        if not recuento:
            self.muted(parent, "Sin desviaciones registradas.").pack(
                anchor="w", pady=(6, 20)
            )
            return

        ordenado = sorted(recuento.items(), key=lambda item: -item[1])[:5]
        bloque = ctk.CTkFrame(parent, fg_color="transparent")
        bloque.pack(fill="x", pady=(6, 20))

        for error, veces, ancho in charts.bar_widths(ordenado, BAR_WIDTH):
            fila = ctk.CTkFrame(bloque, fg_color="transparent")
            fila.pack(fill="x", pady=3)

            ctk.CTkLabel(
                fila,
                text=self.context.catalog.for_error(error).text,
                text_color=theme.COLOR_TEXT,
                width=260,
                anchor="w",
            ).pack(side="left")

            barra = ctk.CTkFrame(
                fila, fg_color=theme.COLOR_ACCENT, height=14, width=ancho,
                corner_radius=7,
            )
            barra.pack(side="left", padx=12)
            barra.pack_propagate(False)

            self.muted(fila, f"{veces}").pack(side="left")

    def _build_sessions(self, parent) -> None:
        sesiones = self.context.sessions.recent_for(self._athlete_id, limit=SESSIONS)

        self.muted(parent, f"Sesiones ({len(sesiones)})").pack(anchor="w", pady=(0, 6))

        if not sesiones:
            self.muted(parent, "Todavía no ha registrado ninguna sesión.").pack(
                anchor="w", pady=(0, 16)
            )
            return

        for sesion in sesiones:
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

            # El tipo de umbrales condiciona si la puntuación es comparable con la de otras sesiones del atleta.
            detalle = (
                f"{formatting.duration(sesion.total_hold_time_s)} en pino · "
                f"{sesion.hold_attempts} intentos · "
                f"{len(sesion.errors)} desviaciones · "
                f"vista {sesion.view_mode.value} · "
                f"umbrales {sesion.thresholds_applied.value}"
            )
            self.muted(interior, detalle).pack(side="left")

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
        ).pack(anchor="w", pady=(16, 0))