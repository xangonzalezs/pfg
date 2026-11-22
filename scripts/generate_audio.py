"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Script de generación de las locuciones del feedback a partir del catálogo.

Uso: python scripts/generate_audio.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT))

from core.feedback.audio_player import DEFAULT_AUDIO_DIR  # noqa: E402
from core.feedback.message_catalog import (  # noqa: E402
    MessageCatalogError,
    load_catalog,
)

# Voz neuronal en español de Microsoft Edge.
VOICE = "es-ES-ElviraNeural"


async def _generate(text: str, output_path: Path, voice: str) -> None:
    # Sintetiza un mensaje y lo escribe como MP3.

    import edge_tts

    await edge_tts.Communicate(text=text, voice=voice).save(str(output_path))


async def _generate_all(voice: str) -> int:
    # Genera una locución por cada mensaje del catálogo.

    try:
        catalog = load_catalog()
    except MessageCatalogError as error:
        # Se valida con el mismo cargador que usa la aplicación.
        print(f"Catálogo no válido: {error}")
        return 1

    DEFAULT_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    messages = [catalog.positive, catalog.not_analyzing] + [
        catalog.for_error(error) for error in _every_error()
    ]
    print(f"Generando {len(messages)} locuciones en {DEFAULT_AUDIO_DIR}\n")

    for message in messages:
        output_path = DEFAULT_AUDIO_DIR / message.audio_filename
        try:
            await _generate(message.text, output_path, voice)
        except Exception as error:
            print(f"ERROR {message.audio_filename}: {error}")
            return 1
        print(f"  {message.audio_filename}: {message.text}")

    _report_orphans(catalog.audio_filenames)
    print("\nLocuciones generadas.")
    return 0


def _every_error():
    # Importación local para no exigir el enumerado al leer el script.

    from core.models.analysis_result import TechnicalError

    return list(TechnicalError)


def _report_orphans(expected: tuple[str, ...]) -> None:

    orphans = sorted(
        path.name
        for path in DEFAULT_AUDIO_DIR.glob("*.mp3")
        if path.name not in set(expected)
    )
    if orphans:
        print(
            f"\nLocuciones sobrantes, ya no declaradas en el catálogo: "
            f"{', '.join(orphans)}"
        )


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_generate_all(VOICE)))