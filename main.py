"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Punto de entrada de la aplicación.

Uso: python main.py
"""

from __future__ import annotations

import sys

from core.feedback.audio_player import AudioAssetError
from core.feedback.message_catalog import MessageCatalogError
from core.config.thresholds import ThresholdConfigError
from core.persistence.database import Database, DatabaseError
from ui.app import App
from ui.context import AppContext


def main() -> int:
    # Arranca la aplicación. 
    # Los fallos de configuración y de recursos se notifican aquí, antes de abrir ninguna ventana.

    try:
        database = Database()
        database.open()
    except DatabaseError as error:
        print(f"No se puede abrir la base de datos: {error}")
        return 1

    try:
        context = AppContext(database)
        context.start_audio()
    except (ThresholdConfigError, MessageCatalogError, AudioAssetError) as error:
        print(f"Configuración incompleta: {error}")
        database.close()
        return 1

    App(context).mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())