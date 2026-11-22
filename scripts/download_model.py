"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de 
la técnica en ejercicios posturales. UNED

Descarga el modelo de estimación de pose de MediaPipe.

Uso: python scripts/download_model.py [lite|full|heavy]
"""


from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

BASE_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_{variant}/float16/latest/pose_landmarker_{variant}.task"
)

MODELS_DIR = Path(__file__).resolve().parent.parent / "assets" / "models"


def download(variant: str, force: bool = False) -> Path:
    destination = MODELS_DIR / f"pose_landmarker_{variant}.task"

    if destination.exists() and not force:
        print(f"El modelo ya existe en {destination}. Usa --force para descargarlo de nuevo.")
        return destination

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    url = BASE_URL.format(variant=variant)

    print(f"Descargando {url}")
    urllib.request.urlretrieve(url, destination)
    print(f"Modelo guardado en {destination} ({destination.stat().st_size / 1_048_576:.1f} MB)")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Descarga un modelo PoseLandmarker de MediaPipe.")
    parser.add_argument("variant", nargs="?", default="full", choices=["lite", "full", "heavy"])
    parser.add_argument("--force", action="store_true", help="Sobrescribe el modelo si ya existe.")
    args = parser.parse_args()

    path = download(args.variant, args.force)
    print(f'Para usarlo, ajusta "model_path" en data/config.json a: assets/models/{path.name}')
