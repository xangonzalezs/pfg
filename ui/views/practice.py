"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de la pantalla de práctica, con su fase previa de preparación.
"""

from __future__ import annotations

import customtkinter as ctk

from core.models.calibration_status import ThresholdsApplied
from core.models.view_mode import ViewMode
from core.vision.frame_source import CaptureError
from core.vision.pose_detector import PoseDetectorError
from ui import formatting, frames, theme
from ui.pipeline import (
    PipelineError,
    build_session,
    open_pipeline,
    rebuild_for_view,
)
from ui.skeleton import overlay
from ui.views.base import BaseView

# Cadencia de refresco de la imagen. No fija la del análisis, que corre en supropio hilo.
REFRESH_MS = 33

VIDEO_BOX = (720, 540)


class PracticeView(BaseView):
    # Práctica con feedback correctivo  y análisis de un vídeo grabado, que recorren la misma pantalla.

    def __init__(self, parent, app, *, video_path=None) -> None:
        self._video_path = video_path
        self._pipeline = None
        self._timer = None
        self._photo = None
        self._phase = "preparing"
        super().__init__(parent, app)


    def build(self) -> None:
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_video()
        self._build_panel()
        self._build_footer()

        self._start_preparation()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=32, pady=(24, 8))

        titulo = "Analizar vídeo" if self._video_path else "Sesión de práctica"
        self.heading(header, titulo).pack(side="left")

        ctk.CTkButton(
            header,
            text="Salir",
            width=110,
            fg_color="transparent",
            text_color=theme.COLOR_TEXT_MUTED,
            hover_color=theme.COLOR_SURFACE,
            command=self._abandon,
        ).pack(side="right")

    def _build_video(self) -> None:
        marco = ctk.CTkFrame(self, fg_color="#000000", corner_radius=12)
        marco.grid(row=1, column=0, sticky="nsew", padx=(32, 16), pady=8)

        self._video = ctk.CTkLabel(marco, text="", fg_color="transparent")
        self._video.pack(fill="both", expand=True, padx=4, pady=4)

    def _build_panel(self) -> None:
        panel = ctk.CTkFrame(self, fg_color=theme.COLOR_SURFACE, corner_radius=12)
        panel.grid(row=1, column=1, sticky="nsew", padx=(0, 32), pady=8)

        interior = ctk.CTkFrame(panel, fg_color="transparent")
        interior.pack(fill="both", expand=True, padx=20, pady=20)

        # Selección de la vista, solo durante la preparación.
        self._view_label = self.muted(interior, "Vista de la cámara")
        self._view_label.pack(anchor="w")
        self._view_choice = ctk.CTkSegmentedButton(
            interior, values=["Lateral", "Frontal"]
        )
        self._view_choice.set("Lateral")
        self._view_choice.pack(fill="x", pady=(4, 20))

        # La puntuación, en número además de en color.
        self.muted(interior, "Alineación").pack(anchor="w")
        self._score = ctk.CTkLabel(
            interior,
            text=formatting.NOT_AVAILABLE,
            font=ctk.CTkFont(size=44, weight="bold"),
            text_color=theme.COLOR_TEXT,
        )
        self._score.pack(anchor="w")
        self._band = self.muted(interior, "Sin evaluar")
        self._band.pack(anchor="w", pady=(0, 20))

        self.muted(interior, "Tiempo en pino").pack(anchor="w")
        self._hold = ctk.CTkLabel(
            interior,
            text="0 s",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=theme.COLOR_TEXT,
        )
        self._hold.pack(anchor="w", pady=(0, 20))


        self._generic_warning = ctk.CTkLabel(
            interior,
            text="",
            text_color=theme.COLOR_WARNING,
            wraplength=200,
            justify="left",
        )
        self._generic_warning.pack(anchor="w", pady=(0, 8))

        self._framing_warning = ctk.CTkLabel(
            interior,
            text="",
            text_color=theme.COLOR_ERROR,
            wraplength=200,
            justify="left",
        )
        self._framing_warning.pack(anchor="w")

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, columnspan=2, sticky="ew", padx=32, pady=(8, 24))

        self._action = ctk.CTkButton(
            footer,
            text="Empezar",
            width=200,
            height=44,
            fg_color=theme.COLOR_ACCENT,
            text_color=theme.COLOR_BACKGROUND,
            hover_color="#D98E18",
            command=self._begin,
        )
        self._action.pack(side="right")

        self._status = self.muted(footer, "Colócate en el encuadre.")
        self._status.pack(side="left")


    def _start_preparation(self) -> None:
        # Abre la cámara y comprueba el encuadre, sin registrar todavía.

        try:
            self._pipeline = build_session(
                self.context,
                self.context.current_user,
                self._selected_view(),
                video_path=self._video_path,
            )
            open_pipeline(self._pipeline)
        except (PipelineError, CaptureError, PoseDetectorError) as error:
            self._fail(str(error))
            return

        self._announce_thresholds()
        self._pipeline.service.prepare()
        self._pipeline.runner.start()
        self._schedule()

    def _announce_thresholds(self) -> None:
        # que el atleta no atribuya a su técnica lo que puede deberse a no haberse calibrado.

        if self._pipeline is None:
            return
        generico = self._pipeline.thresholds_applied is ThresholdsApplied.GENERIC
        self._generic_warning.configure(
            text="Umbrales genéricos: aún no tienes una calibración validada."
            if generico else ""
        )

    def _begin(self) -> None:
        # Pasa de la preparación a la sesión registrada.

        if self._pipeline is None or self._phase != "preparing":
            return

        # La vista se fija aquí y ya no cambia. 
        self._cancel_timer()
        self._pipeline = rebuild_for_view(
            self._pipeline,
            self.context,
            self.context.current_user,
            self._selected_view(),
        )
        self._announce_thresholds()

        self._view_choice.configure(state="disabled")
        self._phase = "active"
        self._pipeline.service.start()
        self._pipeline.runner.start()
        self._schedule()
        self._action.configure(text="Terminar", command=self._finish)
        self._status.configure(text="Sesión en curso.")

    def _finish(self) -> None:
        # Cierra la sesión, la registra y pasa al resumen.

        if self._pipeline is None or self._phase != "active":
            return

        self._phase = "finished"
        self._cancel_timer()
        self._pipeline.runner.stop()

        # El registro corre en este hilo y no en el del bucle.
        # la conexión de SQLite pertenece al hilo que la abrió.
        metrics = self._pipeline.service.metrics
        failed = self._pipeline.runner.failure is not None
        session_id = self._pipeline.service.finish(failed=failed)

        self._release()
        self.app.show_summary(session_id=session_id, metrics=metrics)

    def _abandon(self) -> None:
        # Sale sin registrar si aún no había empezado; si ya había empezado, conserva lo hecho.

        if self._phase == "active":
            self._finish()
            return

        self._cancel_timer()
        self._release()
        self.app.show_home()

    def _fail(self, message: str) -> None:
        # Deja la pantalla en un estado honesto cuando la cámara no abre.

        self._phase = "finished"
        self._cancel_timer()
        self._release()
        self._status.configure(text=message)
        self._action.configure(text="Volver", command=self.app.show_home)


    def _schedule(self) -> None:
        self._timer = self.after(REFRESH_MS, self._tick)

    def _tick(self) -> None:
        # Recoge el último resultado publicado por el hilo de análisis.

        if self._pipeline is None:
            return

        runner = self._pipeline.runner
        if runner.failure is not None:
            # si ya había empezado, lo registrado se conserva; si no, no hay sesión que guardar.
            if self._phase == "active":
                self._finish()
            else:
                self._fail(runner.failure)
            return

        if runner.source_exhausted and self._phase == "active":
            # el archivo se acabó, la sesión se cierra sola.
            self._finish()
            return

        publicado = runner.latest()
        if publicado is not None:
            self._render(publicado)

        self._schedule()

    def _render(self, publicado) -> None:
        # Pinta el fotograma y actualiza los indicadores.

        outcome = publicado.outcome
        score = outcome.analysis.alignment_score if outcome.analysis else None
        self._paint(publicado.image, outcome, score)

        self._score.configure(text=formatting.score(score))
        self._score.configure(text_color=theme.color_for_score(score))
        self._band.configure(text=theme.label_for_score(score))
        self._hold.configure(text=formatting.duration(outcome.hold_time_s))

        # el silencio no debe confundirse con una ejecución correcta.
        self._framing_warning.configure(
            text="" if outcome.is_framed or score is not None
            else "No se te ve bien. Colócate en el encuadre."
        )

    def _paint(self, frame, outcome, score) -> None:
        # Superpone el esqueleto y lleva el fotograma al widget.

        espejo = self._pipeline is not None and self._pipeline.mirrored
        pintado = overlay(frame, outcome.landmark_result, score, mirrored=espejo)
        imagen = frames.to_image(pintado, size=VIDEO_BOX)
        self._photo = ctk.CTkImage(light_image=imagen, size=imagen.size)
        self._video.configure(image=self._photo)


    def _selected_view(self) -> ViewMode:
        # Vista elegida en la preparación.

        return (
            ViewMode.FRONTAL
            if self._view_choice.get() == "Frontal"
            else ViewMode.LATERAL
        )

    def _cancel_timer(self) -> None:
        if self._timer is not None:
            self.after_cancel(self._timer)
            self._timer = None

    def _release(self) -> None:
        if self._pipeline is not None:
            self._pipeline.close()
            self._pipeline = None

    def teardown(self) -> None:
        # Detiene el hilo y libera la cámara al abandonar la pantalla.

        self._cancel_timer()
        self._release()