"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo del catálogo único de mensajes del feedback.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.models.analysis_result import TechnicalError

# Ubicación del catálogo dentro del proyecto.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG_PATH = _PROJECT_ROOT / "assets" / "messages" / "feedback_messages.json"

# Mensajes que no corresponden a un error técnico.
POSITIVE_KEY = "positive"
NOT_ANALYZING_KEY = "not_analyzing"

# Extensión de las locuciones generadas por scripts/generate_audio.py.
AUDIO_EXTENSION = ".mp3"


class MessageCatalogError(Exception):
    # El catálogo falta, es ilegible o no cubre todos los mensajes exigidos.

    pass


@dataclass(frozen=True)
class FeedbackMessage:
    # Un mensaje del catálogo con la locución que le corresponde.

    key: str
    text: str
    audio_filename: str


class MessageCatalog:
    # Única fuente de los textos y de las locuciones del feedback.

    def __init__(self, messages: dict[str, FeedbackMessage]) -> None:
        self._messages = dict(messages)

    def for_error(self, error: TechnicalError) -> FeedbackMessage:
        # Mensaje de un error técnico.

        return self._messages[error.value]

    @property
    def positive(self) -> FeedbackMessage:
        # Mensaje de refuerzo al concluir una fase de mantenimiento.

        return self._messages[POSITIVE_KEY]

    @property
    def not_analyzing(self) -> FeedbackMessage:
        # Aviso de que el sistema no está evaluando la postura.

        return self._messages[NOT_ANALYZING_KEY]

    @property
    def audio_filenames(self) -> tuple[str, ...]:
        # Locuciones que el reproductor debe precargar.

        return tuple(
            self._messages[key].audio_filename for key in sorted(self._messages)
        )


def required_keys() -> tuple[str, ...]:
    # Claves que el catálogo debe declarar.

    return tuple(error.value for error in TechnicalError) + (
        POSITIVE_KEY,
        NOT_ANALYZING_KEY,
    )


def load_catalog(path: Path | str | None = None) -> MessageCatalog:
    # Lee y valida el catálogo completo.

    file_path = Path(path) if path is not None else DEFAULT_CATALOG_PATH
    data = _read_json(file_path)

    expected = required_keys()
    _reject_unknown_keys(data, set(expected), file_path)

    messages: dict[str, FeedbackMessage] = {}
    for key in expected:
        messages[key] = FeedbackMessage(
            key=key,
            text=_read_text(data, key, file_path),
            audio_filename=f"{key}{AUDIO_EXTENSION}",
        )

    return MessageCatalog(messages)


def _read_json(file_path: Path) -> dict[str, Any]:
    # Lee el archivo y comprueba que contiene un objeto en su raíz.

    try:
        raw_text = file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise MessageCatalogError(
            f"No se encuentra el catálogo de mensajes: {file_path}"
        ) from None
    except OSError as error:
        raise MessageCatalogError(
            f"No se puede leer el catálogo de mensajes {file_path}: {error}"
        ) from error

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as error:
        raise MessageCatalogError(
            f"El catálogo de mensajes {file_path} no contiene JSON válido: {error}"
        ) from error

    if not isinstance(data, dict):
        raise MessageCatalogError(
            f"El catálogo de mensajes {file_path} debe contener un objeto en su raíz."
        )

    return data


def _read_text(data: dict[str, Any], key: str, file_path: Path) -> str:
    # Lee el texto de un mensaje.

    if key not in data:
        raise MessageCatalogError(
            f"Falta el mensaje '{key}' en el catálogo {file_path}. "
            f"Todo error técnico debe tener su texto declarado."
        )

    text = data[key]
    if not isinstance(text, str):
        raise MessageCatalogError(
            f"El mensaje '{key}' debe ser una cadena en el catálogo {file_path}; "
            f"se ha leído {text!r}."
        )
    if not text.strip():
        raise MessageCatalogError(
            f"El mensaje '{key}' está vacío en el catálogo {file_path}."
        )

    return text


def _reject_unknown_keys(
    data: dict[str, Any], expected: set[str], file_path: Path
) -> None:

    unknown = sorted(set(data) - expected)
    if unknown:
        raise MessageCatalogError(
            f"Mensajes no reconocidos en el catálogo {file_path}: "
            f"{', '.join(unknown)}."
        )