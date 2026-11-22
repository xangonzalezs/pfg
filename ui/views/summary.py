"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de la pantalla de resumen de una sesión.
"""

from __future__ import annotations

import customtkinter as ctk

from ui import charts, formatting, theme
from ui.views.base import BaseView

CHART_WIDTH = 620
CHART_HEIGHT = 160
BAR_WIDTH = 320


class SummaryView(BaseView):
    # Resumen al terminar: métricas, evolución y errores más frecuentes. Es donde el canal visual recupera su utilidad plena.

    def __init__(self, parent, app, *, session_id=None, metrics=None) -> None:
        self._session_id = session_id
        self._metrics = metrics
        super().__init__(parent, app)

    def build(self) -> None:
        cuerpo = ctk.CTkScrollableFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=32, pady=24)

        self.heading(cuerpo, "Resumen de la sesión").pack(anchor="w", pady=(0, 16))

        if self._metrics is None:
            self.muted(cuerpo, "No se registró ninguna sesión.").pack(anchor="w")
            self._boton_volver(cuerpo)
            return

        self._build_metrics(cuerpo)
        self._build_evolution(cuerpo)
        self._build_errors(cuerpo)
        self._boton_volver(cuerpo)


    def _build_metrics(self, parent) -> None:
        fila = ctk.CTkFrame(parent, fg_color="transparent")
        fila.pack(fill="x", pady=(0, 24))

        media = self._metrics.mean_score
        self._metric(fila, "Alineación media", formatting.score(media),
                     theme.color_for_score(media))
        self._metric(fila, "Tiempo en pino",
                     formatting.duration(self._metrics.total_hold_ms / 1000.0))
        self._metric(fila, "Intentos", str(self._metrics.hold_attempts))
        self._metric(fila, "Desviaciones", str(len(self._metrics.occurrences)))

    def _metric(self, parent, titulo: str, valor: str, color: str | None = None):
        # Una métrica, con su rótulo encima.

        tarjeta = ctk.CTkFrame(parent, fg_color=theme.COLOR_SURFACE, corner_radius=12)
        tarjeta.pack(side="left", fill="x", expand=True, padx=(0, 12))

        self.muted(tarjeta, titulo, size=12).pack(anchor="w", padx=16, pady=(14, 0))
        ctk.CTkLabel(
            tarjeta,
            text=valor,
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=color or theme.COLOR_TEXT,
        ).pack(anchor="w", padx=16, pady=(0, 14))

    def _build_evolution(self, parent) -> None:
        # La evolución solo existe al terminar la sesión. 
        # las puntuaciones por fotograma no se persisten. el esquema guarda únicamente la media.

        self.muted(parent, "Evolución de la alineación").pack(anchor="w")

        lienzo = ctk.CTkCanvas(
            parent,
            width=CHART_WIDTH,
            height=CHART_HEIGHT,
            highlightthickness=0,
            bg=theme.COLOR_SURFACE,
        )
        lienzo.pack(anchor="w", pady=(6, 24))

        puntos = charts.score_polyline(
            self._metrics.scores, CHART_WIDTH, CHART_HEIGHT
        )
        if len(puntos) < 2:
            lienzo.create_text(
                CHART_WIDTH // 2,
                CHART_HEIGHT // 2,
                text="Sin posturas evaluadas",
                fill=theme.COLOR_TEXT_MUTED,
            )
            return

        # Referencia del umbral de refuerzo, para situar la línea.
        referencia = charts.score_polyline(
            [self.context.thresholds.feedback.positive_score_threshold],
            CHART_WIDTH,
            CHART_HEIGHT,
        )
        lienzo.create_line(
            *referencia[0], *referencia[1], fill=theme.COLOR_TEXT_MUTED, dash=(4, 4)
        )

        planos = [coordenada for punto in puntos for coordenada in punto]
        lienzo.create_line(
            *planos,
            fill=theme.color_for_score(self._metrics.mean_score),
            width=2,
            smooth=True,
        )

    def _build_errors(self, parent) -> None:
        self.muted(parent, "Desviaciones más frecuentes").pack(anchor="w")

        recuento = charts.top_errors(self._metrics.occurrences, limit=5)
        if not recuento:
            self.muted(parent, "Ninguna desviación registrada.").pack(
                anchor="w", pady=(6, 24)
            )
            return

        bloque = ctk.CTkFrame(parent, fg_color="transparent")
        bloque.pack(fill="x", pady=(6, 24))

        for error, veces, ancho in charts.bar_widths(recuento, BAR_WIDTH):
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

    def _boton_volver(self, parent) -> None:
        ctk.CTkButton(
            parent,
            text="Volver al inicio",
            width=200,
            height=42,
            fg_color=theme.COLOR_ACCENT,
            text_color=theme.COLOR_BACKGROUND,
            hover_color="#D98E18",
            command=self.app.show_home,
        ).pack(anchor="w", pady=(8, 0))