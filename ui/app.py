"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de la ventana principal y del encaminamiento entre pantallas.
"""

from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

from core.models.user_role import UserRole
from ui import theme
from ui.context import AppContext

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
ICON_ICO = _PROJECT_ROOT / "assets" / "icons" / "handstandapp.ico"
ICON_PNG = _PROJECT_ROOT / "assets" / "icons" / "logo_64.png"

WINDOW_SIZE = "1100x720"
MIN_SIZE = (900, 620)


class App(ctk.CTk):
    # Ventana única de la aplicación. Las pantallas se sustituyen dentro de ella en lugar de abrir ventanas nuevas.

    def __init__(self, context: AppContext) -> None:
        super().__init__()

        self.context = context

        ctk.set_appearance_mode("dark")
        self.title(theme.APP_NAME)
        self.geometry(WINDOW_SIZE)
        self.minsize(*MIN_SIZE)
        self.configure(fg_color=theme.COLOR_BACKGROUND)
        self._set_icon()

        self._container = ctk.CTkFrame(self, fg_color="transparent")
        self._container.pack(fill="both", expand=True)
        self._current = None

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.show_login()


    def show(self, view_factory, **kwargs) -> None:
        # Sustituye la pantalla actual por otra.

        if self._current is not None:
            self._current.teardown()
            self._current.destroy()
        self._current = view_factory(self._container, self, **kwargs)
        self._current.pack(fill="both", expand=True)

    def show_login(self) -> None:
        # Pantalla de acceso.

        from ui.views.login import LoginView

        self.context.sign_out()
        self.show(LoginView)

    def show_register(self) -> None:
        # Registro público, que solo crea cuentas de atletas.

        from ui.views.register import RegisterView

        self.show(RegisterView)

    def show_home(self) -> None:
        # Panel que corresponde al rol de la cuenta activa.

        from ui.views.athlete_home import AthleteHomeView
        from ui.views.trainer_home import TrainerHomeView

        user = self.context.current_user
        if user is None:
            self.show_login()
            return

        if user.role is UserRole.TRAINER:
            self.show(TrainerHomeView)
        elif user.role is UserRole.ATHLETE:
            self.show(AthleteHomeView)
        else:
            # El panel del administrador queda fuera del alcance implementado.
            self.show_login()

    def show_practice(self, *, video_path=None) -> None:
        # Práctica con la cámara, o análisis de una grabación.

        from ui.views.practice import PracticeView

        self.show(PracticeView, video_path=video_path)

    def show_calibration(self) -> None:
        # Calibración corporal.

        from ui.views.calibration import CalibrationView

        self.show(CalibrationView)

    def show_summary(self, *, session_id=None, metrics=None) -> None:
        # Resumen de la sesión recién terminada.

        from ui.views.summary import SummaryView

        self.show(SummaryView, session_id=session_id, metrics=metrics)

    def show_profile(self) -> None:
        # Gestión del perfil propio, común a los tres roles.

        from ui.views.profile import ProfileView

        self.show(ProfileView)

    def show_review(self, *, profile_id: int) -> None:
        # Validación de una calibración por su entrenador.

        from ui.views.review import ReviewCalibrationView

        self.show(ReviewCalibrationView, profile_id=profile_id)

    def show_athlete(self, *, athlete_id: int) -> None:
        # Progreso de un atleta de la cartera.

        from ui.views.athlete_detail import AthleteDetailView

        self.show(AthleteDetailView, athlete_id=athlete_id)

    def sign_out(self) -> None:
        # Cierra la sesión y vuelve al acceso.

        self.show_login()


    def _set_icon(self) -> None:
        # El icono de ventana se fija de distinta forma según el sistema. 

        try:
            if ICON_ICO.is_file():
                self.iconbitmap(str(ICON_ICO))
        except Exception:
            pass

        try:
            if ICON_PNG.is_file():
                import tkinter as tk

                self._icon = tk.PhotoImage(file=str(ICON_PNG))
                self.iconphoto(True, self._icon)
        except Exception:
            pass

    def _on_close(self) -> None:
        # Libera la pantalla actual antes de cerrar para que un hilo de captura en curso se detenga de forma ordenada.

        if self._current is not None:
            self._current.teardown()
            self._current.destroy()
            self._current = None
        self.context.close()
        self.destroy()