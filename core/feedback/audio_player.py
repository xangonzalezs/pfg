"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de reproducción de las locuciones del feedback.

"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Protocol

# Ubicación de las locuciones dentro del proyecto.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUDIO_DIR = _PROJECT_ROOT / "assets" / "audio"


class AudioAssetError(Exception):
    # Falta una locución declarada en el catálogo. Es un defecto del paquete.

    pass


class MixerBackend(Protocol):
    # Envoltura del mezclador real, para poder sustituirlo en las pruebas.

    def load(self, path: Path) -> Any:
        ...

    def play(self, sound: Any) -> None:
        ...

    def is_busy(self) -> bool:
        ...

    def close(self) -> None:
        ...


class AudioPlayer:
    # Reproduce las locuciones ya sintetizadas, precargadas en memoria.

    def __init__(
        self,
        audio_dir: Path | str = DEFAULT_AUDIO_DIR,
        *,
        backend_factory: Callable[[], MixerBackend] | None = None,
    ) -> None:
        # backend_factory permite construir el reproductor sin pygame.
        # hace comprobable esta clase sin dispositivo de audio.

        self._audio_dir = Path(audio_dir)
        self._backend_factory = backend_factory or _create_pygame_backend
        self._backend: MixerBackend | None = None
        self._sounds: dict[str, Any] = {}

    @property
    def is_available(self) -> bool:
        # Indica si el canal auditivo está operativo.

        return self._backend is not None

    @property
    def is_playing(self) -> bool:
        # Indica si hay una locución en curso, consultando al mezclador.

        if self._backend is None:
            return False
        return self._backend.is_busy()

    def initialize(self, filenames: Sequence[str]) -> None:
        # Comprueba las locuciones y las carga en memoria.

        missing = [name for name in filenames if not (self._audio_dir / name).is_file()]
        if missing:
            raise AudioAssetError(
                f"Faltan locuciones en {self._audio_dir}: {', '.join(sorted(missing))}. "
                "Ejecute scripts/generate_audio.py para generarlas."
            )

        if self._backend is not None:
            return

        try:
            backend = self._backend_factory()
        except Exception:
            self._backend = None
            self._sounds.clear()
            return

        # La carga ocurre aquí y no al emitir.
        try:
            sounds = {
                name: backend.load(self._audio_dir / name) for name in filenames
            }
        except Exception:
            backend.close()
            self._backend = None
            self._sounds.clear()
            return

        self._backend = backend
        self._sounds = sounds

    def play(self, filename: str) -> None:
        # Reproduce una locución precargada. Sin audio no hace nada.

        if self._backend is None:
            return

        sound = self._sounds.get(filename)
        if sound is None:
            raise AudioAssetError(
                f"La locución '{filename}' no se precargó. Debe declararse en el "
                "catálogo de mensajes antes de inicializar el reproductor."
            )

        self._backend.play(sound)

    def close(self) -> None:
        # Libera el mezclador. Puede invocarse más de una vez.

        if self._backend is not None:
            self._backend.close()
            self._backend = None
        self._sounds.clear()


class _PygameBackend:
    # Mezclador real, apoyado en pygame.mixer.

    def __init__(self) -> None:
        import pygame

        self._pygame = pygame
        pygame.mixer.init()

    def load(self, path: Path) -> Any:
        return self._pygame.mixer.Sound(str(path))

    def play(self, sound: Any) -> None:
        sound.play()

    def is_busy(self) -> bool:
        # Estado real del mezclador.

        return bool(self._pygame.mixer.get_busy())

    def close(self) -> None:
        self._pygame.mixer.quit()


def _create_pygame_backend() -> MixerBackend:
    # Construye el mezclador real.
    # pygame se importa aquí y no al cargar el módulo.

    return _PygameBackend()