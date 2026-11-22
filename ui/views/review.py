"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de la pantalla de validación de una calibración.
"""

from __future__ import annotations

import customtkinter as ctk

from core.config.personalization import PERSONALIZABLE_PARAMETERS
from core.persistence.database import DatabaseError
from core.services.calibration_service import CalibrationServiceError
from core.services.permissions import Action, PermissionDenied
from ui import formatting, theme
from ui.views.base import BaseView

# Rótulos de los parámetros personalizables, para no enseñar sus claves.
PARAMETER_LABELS = {
    "knee_bend": "Extensión de rodilla",
    "back_arch": "Arqueo dorsal",
    "elbow_bend": "Extensión de codo",
}

MEASURE_LABELS = (
    ("neutral_knee_angle_deg", "Ángulo neutro de rodilla", "°"),
    ("neutral_back_arch_angle_deg", "Ángulo neutro dorsal", "°"),
    ("neutral_elbow_angle_deg", "Ángulo neutro de codo", "°"),
    ("legs_trunk_ratio", "Proporción piernas/tronco", ""),
    ("shoulder_width_ratio", "Anchura de hombros", ""),
)


class ReviewCalibrationView(BaseView):
    # Validación de una calibración. 
    # El entrenador ve lo medido, los umbrales que la derivación propone, y puede ajustarlos antes de validar.

    def __init__(self, parent, app, *, profile_id: int) -> None:
        self._profile_id = profile_id
        self._fields: dict[str, ctk.CTkEntry] = {}
        super().__init__(parent, app)

    def build(self) -> None:
        cuerpo = ctk.CTkScrollableFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=32, pady=24)

        perfil = self.context.calibrations.get(self._profile_id)
        if perfil is None:
            self.heading(cuerpo, "Calibración no encontrada").pack(anchor="w")
            self._boton_volver(cuerpo)
            return

        # solo sobre los atletas que supervisa.
        try:
            self.context.permissions.require(
                self.context.current_user,
                Action.REVIEW_CALIBRATION,
                subject_id=perfil.user_id,
            )
        except PermissionDenied:
            self.heading(cuerpo, "No puedes revisar esta calibración").pack(anchor="w")
            self.muted(cuerpo, "Solo los atletas de tu cartera.").pack(anchor="w")
            self._boton_volver(cuerpo)
            return

        self._perfil = perfil
        atleta = self.context.users.get(perfil.user_id)

        self.heading(
            cuerpo, f"Calibración de {atleta.full_name if atleta else 'un atleta'}"
        ).pack(anchor="w")
        self.muted(
            cuerpo, f"Enviada el {formatting.timestamp(perfil.created_at)}"
        ).pack(anchor="w", pady=(0, 20))

        self._build_measures(cuerpo, perfil)
        self._build_thresholds(cuerpo, perfil)
        self._build_decision(cuerpo)


    def _build_measures(self, parent, perfil) -> None:
        self.muted(parent, "Medidas de la postura neutra").pack(anchor="w")

        bloque = ctk.CTkFrame(parent, fg_color=theme.COLOR_SURFACE, corner_radius=12)
        bloque.pack(fill="x", pady=(6, 20))

        for campo, rotulo, unidad in MEASURE_LABELS:
            valor = getattr(perfil, campo, None)
            fila = ctk.CTkFrame(bloque, fg_color="transparent")
            fila.pack(fill="x", padx=16, pady=4)

            ctk.CTkLabel(
                fila, text=rotulo, text_color=theme.COLOR_TEXT_MUTED,
                width=240, anchor="w",
            ).pack(side="left")
            # Una medida ausente no es un cero. no pudo obtenerse.
            texto = (
                f"{valor:.1f}{unidad}" if valor is not None
                else formatting.NOT_AVAILABLE
            )
            ctk.CTkLabel(fila, text=texto, text_color=theme.COLOR_TEXT).pack(
                side="left"
            )

    def _build_thresholds(self, parent, perfil) -> None:
        self.muted(parent, "Umbrales propuestos").pack(anchor="w")
        ctk.CTkLabel(
            parent,
            text="Puedes ajustarlos. Los que dejes en blanco se seguirán "
            "derivando de las medidas en cada sesión.",
            text_color=theme.COLOR_TEXT_MUTED,
            wraplength=780,
            justify="left",
        ).pack(anchor="w", pady=(2, 6))

        propuesta = self.context.calibration.proposed(perfil)
        genericos = self.context.thresholds.alignment.parameters

        bloque = ctk.CTkFrame(parent, fg_color=theme.COLOR_SURFACE, corner_radius=12)
        bloque.pack(fill="x", pady=(0, 20))

        for nombre in PERSONALIZABLE_PARAMETERS:
            fila = ctk.CTkFrame(bloque, fg_color="transparent")
            fila.pack(fill="x", padx=16, pady=6)

            ctk.CTkLabel(
                fila,
                text=PARAMETER_LABELS.get(nombre, nombre),
                text_color=theme.COLOR_TEXT,
                width=200,
                anchor="w",
            ).pack(side="left")

            generico = genericos[nombre].threshold
            derivado = propuesta.thresholds.parameters[nombre].threshold
            self.muted(
                fila, f"genérico {generico:.1f}  →  derivado {derivado:.1f}"
            ).pack(side="left")

            campo = ctk.CTkEntry(fila, width=100, placeholder_text="ajuste")
            campo.pack(side="right")
            self._fields[nombre] = campo

    def _build_decision(self, parent) -> None:
        self.muted(parent, "Nota para el atleta (opcional)").pack(anchor="w")
        self._note = ctk.CTkEntry(parent, width=520, height=38)
        self._note.pack(anchor="w", pady=(4, 16))

        self._message = ctk.CTkLabel(
            parent, text="", text_color=theme.COLOR_ERROR, wraplength=780,
            justify="left",
        )
        self._message.pack(anchor="w", pady=(0, 8))

        fila = ctk.CTkFrame(parent, fg_color="transparent")
        fila.pack(anchor="w")

        ctk.CTkButton(
            fila,
            text="Validar",
            width=160,
            height=42,
            fg_color=theme.COLOR_ACCENT,
            text_color=theme.COLOR_BACKGROUND,
            hover_color="#D98E18",
            command=self._validate,
        ).pack(side="left", padx=(0, 12))

        ctk.CTkButton(
            fila,
            text="Rechazar",
            width=160,
            height=42,
            fg_color="transparent",
            text_color=theme.COLOR_ERROR,
            hover_color=theme.COLOR_SURFACE,
            command=self._reject,
        ).pack(side="left", padx=(0, 12))

        self._boton_volver(fila, inline=True)

    def _boton_volver(self, parent, inline: bool = False) -> None:
        boton = ctk.CTkButton(
            parent,
            text="Volver",
            width=140,
            height=42,
            fg_color="transparent",
            text_color=theme.COLOR_TEXT_MUTED,
            hover_color=theme.COLOR_SURFACE,
            command=self.app.show_home,
        )
        boton.pack(side="left") if inline else boton.pack(anchor="w", pady=(16, 0))


    def _validate(self) -> None:
        try:
            ajustes = self._read_overrides()
        except ValueError as error:
            self._message.configure(text=str(error))
            return

        try:
            self.context.calibration.validate(
                self._profile_id,
                self.context.current_user.user_id,
                overrides=ajustes,
                note=self._note.get().strip() or None,
            )
        except (CalibrationServiceError, DatabaseError) as error:
            self._message.configure(text=str(error))
            return

        self.app.show_home()

    def _reject(self) -> None:
        try:
            self.context.calibration.reject(
                self._profile_id,
                self.context.current_user.user_id,
                note=self._note.get().strip() or None,
            )
        except DatabaseError as error:
            self._message.configure(text=str(error))
            return

        self.app.show_home()

    def _read_overrides(self) -> dict[str, float]:
        # Solo los campos rellenados se almacenan como ajuste.
        # El resto se sigue derivando de las medidas.

        ajustes: dict[str, float] = {}
        for nombre, campo in self._fields.items():
            texto = campo.get().strip().replace(",", ".")
            if not texto:
                continue
            try:
                ajustes[nombre] = float(texto)
            except ValueError:
                rotulo = PARAMETER_LABELS.get(nombre, nombre)
                raise ValueError(f"«{rotulo}»: {texto} no es un número.") from None
        return ajustes