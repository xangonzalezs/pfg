"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de composición de los servicios que la interfaz utiliza.
"""

from __future__ import annotations

from pathlib import Path

from core.config.thresholds import GenericThresholds, load_thresholds
from core.feedback.audio_player import AudioPlayer
from core.feedback.message_catalog import MessageCatalog, load_catalog
from core.persistence.calibration_repository import CalibrationRepository
from core.persistence.database import Database
from core.persistence.session_repository import SessionRepository
from core.persistence.user_repository import User, UserRepository
from core.services.account_service import AccountService
from core.services.calibration_service import CalibrationService
from core.services.permissions import PermissionChecker

# Modelo de estimación de pose, descargado por scripts/download_model.py.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = _PROJECT_ROOT / "assets" / "models"

# El script admite tres variantes, cada una con su nombre, así que el modelo se busca.
#  El orden va de mayor a menor precisión, por si hay varias.
MODEL_VARIANTS: tuple[str, ...] = ("heavy", "full", "lite")


def find_model(directory: Path | None = None) -> Path | None:
    # Modelo descargado que se usará, o None si no hay ninguno.

    directory = directory if directory is not None else MODELS_DIR
    if not directory.is_dir():
        return None

    for variant in MODEL_VARIANTS:
        candidate = directory / f"pose_landmarker_{variant}.task"
        if candidate.is_file():
            return candidate

    # Cualquier otro nombre, por si se descargó a mano.
    return next(iter(sorted(directory.glob("*.task"))), None)


class AppContext:
    # Reúne en un solo objeto todo lo que las pantallas necesitan para que ninguna construya sus propias dependencias ni abra su propia conexión.

    def __init__(
        self,
        database: Database,
        *,
        thresholds: GenericThresholds | None = None,
        catalog: MessageCatalog | None = None,
        player: AudioPlayer | None = None,
        model_path: Path | None = None,
    ) -> None:
        self.database = database
        self.thresholds = thresholds if thresholds is not None else load_thresholds()
        self.catalog = catalog if catalog is not None else load_catalog()
        self.player = player if player is not None else AudioPlayer()
        self.model_path = model_path if model_path is not None else find_model()

        self.users = UserRepository(database)
        self.calibrations = CalibrationRepository(database)
        self.sessions = SessionRepository(database)

        self.accounts = AccountService(self.users)
        self.calibration = CalibrationService(self.calibrations, self.thresholds)
        self.permissions = PermissionChecker(self.users)

        # Cuenta con la sesión iniciada, o None.
        self.current_user: User | None = None

    def start_audio(self) -> None:
        # Carga las locuciones una sola vez, al arrancar.
        # Si no hay dispositivo de audio la sesión continúa en silencio.

        self.player.initialize(self.catalog.audio_filenames)

    def sign_in(self, user: User) -> None:
        # Fija la cuenta activa.

        self.current_user = user

    def sign_out(self) -> None:
        # Cierra la sesión de la cuenta activa.

        self.current_user = None

    @property
    def is_signed_in(self) -> bool:
        # Indica si hay una cuenta con la sesión iniciada.

        return self.current_user is not None

    @property
    def has_model(self) -> bool:
        # Indica si el modelo de estimación está descargado.
        # Sin él se puede entrar y consultar el histórico, pero no practicar.

        return self.model_path is not None and self.model_path.is_file()

    def close(self) -> None:
        # Libera audio y base de datos al cerrar la aplicación.

        self.player.close()
        self.database.close()