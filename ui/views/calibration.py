"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de la pantalla de calibración corporal.
"""

from __future__ import annotations

import customtkinter as ctk

from core.calibration.neutral_pose import CalibrationCaptureError
from core.models.view_mode import ViewMode
from core.persistence.calibration_repository import DuplicatePendingError
from core.vision.camera_capture import CameraCapture
from core.vision.frame_source import CaptureError
from core.vision.pose_detector import PoseDetector, PoseDetectorError
from ui import frames, theme
from ui.skeleton import overlay
from ui.views.base import BaseView

REFRESH_MS = 33
VIDEO_BOX = (680, 510)

# Las dos capturas, en el orden en que se piden.
STAGES: tuple[tuple[ViewMode, str, str], ...] = (
    (
        ViewMode.LATERAL,
        "Captura lateral",
        "Colócate de perfil a la cámara, de pie y relajado, con los brazos "
        "a lo largo del cuerpo.",
    ),
    (
        ViewMode.FRONTAL,
        "Captura frontal",
        "Colócate de frente a la cámara, de pie y relajado.",
    ),
)


class CalibrationView(BaseView):
    # Calibración corporal. dos capturas de la postura neutra que el entrenador validará después.

    def __init__(self, parent, app) -> None:
        self._stage = 0
        self._source = None
        self._detector = None
        self._timer = None
        self._photo = None
        self._done = False
        super().__init__(parent, app)


    def build(self) -> None:
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=32, pady=(24, 8))
        self.heading(header, "Calibración corporal").pack(side="left")
        ctk.CTkButton(
            header,
            text="Salir",
            width=110,
            fg_color="transparent",
            text_color=theme.COLOR_TEXT_MUTED,
            hover_color=theme.COLOR_SURFACE,
            command=self._abandon,
        ).pack(side="right")

        marco = ctk.CTkFrame(self, fg_color="#000000", corner_radius=12)
        marco.grid(row=1, column=0, sticky="nsew", padx=(32, 16), pady=8)
        self._video = ctk.CTkLabel(marco, text="", fg_color="transparent")
        self._video.pack(fill="both", expand=True, padx=4, pady=4)

        self._build_panel()
        self._build_footer()

        self._start_camera()

    def _build_panel(self) -> None:
        panel = ctk.CTkFrame(self, fg_color=theme.COLOR_SURFACE, corner_radius=12)
        panel.grid(row=1, column=1, sticky="nsew", padx=(0, 32), pady=8)

        interior = ctk.CTkFrame(panel, fg_color="transparent")
        interior.pack(fill="both", expand=True, padx=20, pady=20)

        self._stage_title = ctk.CTkLabel(
            interior,
            text="",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=theme.COLOR_TEXT,
            wraplength=220,
            justify="left",
        )
        self._stage_title.pack(anchor="w")

        self._stage_help = self.muted(interior, "")
        self._stage_help.configure(wraplength=220, justify="left")
        self._stage_help.pack(anchor="w", pady=(6, 20))

        self.muted(interior, "Fotogramas utilizables").pack(anchor="w")
        self._count = ctk.CTkLabel(
            interior,
            text="0",
            font=ctk.CTkFont(size=34, weight="bold"),
            text_color=theme.COLOR_TEXT,
        )
        self._count.pack(anchor="w")

        self._ready = self.muted(interior, "Aún no hay suficientes.")
        self._ready.configure(wraplength=220, justify="left")
        self._ready.pack(anchor="w", pady=(4, 0))

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, columnspan=2, sticky="ew", padx=32, pady=(8, 24))

        self._status = self.muted(footer, "")
        self._status.pack(side="left")

        self._action = ctk.CTkButton(
            footer,
            text="Guardar esta captura",
            width=220,
            height=44,
            state="disabled",
            fg_color=theme.COLOR_ACCENT,
            text_color=theme.COLOR_BACKGROUND,
            hover_color="#D98E18",
            command=self._advance,
        )
        self._action.pack(side="right")

        self._show_stage()


    def _start_camera(self) -> None:
        # La calibración no usa el servicio de sesión.
        # aquí no hay análisis ni feedback, solo la acumulación de fotogramas de la postura neutra.

        if self.context.model_path is None:
            self._fail("Falta el modelo de estimación de pose.")
            return

        try:
            self._source = CameraCapture()
            self._source.open()
            self._detector = PoseDetector(self.context.model_path)
            self._detector.initialize()
        except (CaptureError, PoseDetectorError) as error:
            self._fail(str(error))
            return

        self.context.calibration.reset()
        self._schedule()

    def _schedule(self) -> None:
        self._timer = self.after(REFRESH_MS, self._tick)

    def _tick(self) -> None:
        # Lee un fotograma, lo entrega al servicio y refresca la imagen.

        if self._source is None or self._detector is None or self._done:
            return

        try:
            captured = self._source.read()
            landmarks = self._detector.detect(captured.image, captured.timestamp_ms)
        except (CaptureError, PoseDetectorError) as error:
            self._fail(str(error))
            return

        view, _, _ = STAGES[self._stage]
        self.context.calibration.submit(view, landmarks)

        pintado = overlay(captured.image, landmarks, mirrored=True)
        imagen = frames.to_image(pintado, size=VIDEO_BOX)
        self._photo = ctk.CTkImage(light_image=imagen, size=imagen.size)
        self._video.configure(image=self._photo)

        self._update_progress(view)
        self._schedule()

    def _update_progress(self, view: ViewMode) -> None:
        utilizables, _ = self.context.calibration.captured(view)
        self._count.configure(text=str(utilizables))

        listo = self.context.calibration.is_ready(view)
        self._action.configure(state="normal" if listo else "disabled")
        self._ready.configure(
            text="Captura suficiente." if listo
            else "Aún no hay suficientes fotogramas utilizables."
        )


    def _show_stage(self) -> None:
        _, titulo, ayuda = STAGES[self._stage]
        self._stage_title.configure(text=titulo)
        self._stage_help.configure(text=ayuda)
        self._action.configure(
            text="Guardar esta captura" if self._stage < len(STAGES) - 1
            else "Terminar la calibración"
        )
        self._status.configure(text=f"Paso {self._stage + 1} de {len(STAGES)}")

    def _advance(self) -> None:
        # Pasa a la captura siguiente o cierra la calibración.

        if self._stage < len(STAGES) - 1:
            self._stage += 1
            self._show_stage()
            self._update_progress(STAGES[self._stage][0])
            return

        self._complete()

    def _complete(self) -> None:
        # Mide las dos capturas y las guarda como pendientes de validación.

        self._done = True
        self._cancel_timer()

        try:
            self.context.calibration.complete(self.context.current_user.user_id)
        except DuplicatePendingError:
            self._fail(
                "Ya tienes una calibración pendiente de que tu entrenador la valide."
            )
            return
        except CalibrationCaptureError as error:
            self._fail(str(error))
            return

        self._release()
        self._status.configure(text="")
        self._stage_title.configure(text="Calibración enviada")
        self._stage_help.configure(
            text="Tu entrenador la revisará. Hasta entonces practicarás con "
            "umbrales genéricos."
        )
        self._action.configure(
            text="Volver al inicio", state="normal", command=self.app.show_home
        )

    def _abandon(self) -> None:
        self._cancel_timer()
        self._release()
        self.app.show_home()

    def _fail(self, message: str) -> None:
        self._done = True
        self._cancel_timer()
        self._release()
        self._status.configure(text=message)
        self._action.configure(
            text="Volver", state="normal", command=self.app.show_home
        )


    def _cancel_timer(self) -> None:
        if self._timer is not None:
            self.after_cancel(self._timer)
            self._timer = None

    def _release(self) -> None:
        if self._detector is not None:
            self._detector.close()
            self._detector = None
        if self._source is not None:
            self._source.close()
            self._source = None

    def teardown(self) -> None:
        # Libera la cámara al abandonar la pantalla.

        self._done = True
        self._cancel_timer()
        self._release()