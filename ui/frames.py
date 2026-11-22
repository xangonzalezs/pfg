"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de adaptación de los fotogramas a la superficie de la interfaz.
"""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

# Tamaño mínimo del recuadro de vídeo para no dividir por cero al encajar.
MIN_BOX = 16


def fit_box(
    frame_size: tuple[int, int], box_size: tuple[int, int]
) -> tuple[int, int]:
    # Tamaño al que encaja un fotograma dentro de un recuadro conservando su proporción.

    frame_w, frame_h = frame_size
    box_w, box_h = box_size

    if frame_w <= 0 or frame_h <= 0:
        return MIN_BOX, MIN_BOX

    box_w = max(MIN_BOX, box_w)
    box_h = max(MIN_BOX, box_h)

    scale = min(box_w / frame_w, box_h / frame_h)
    return max(1, int(frame_w * scale)), max(1, int(frame_h * scale))


def to_image(frame: np.ndarray, size: tuple[int, int] | None = None) -> Image.Image:
    # Convierte un fotograma de OpenCV en una imagen que la interfaz puede mostrar. 
    # OpenCV entrega BGR y Tk espera RGB.

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(rgb)

    if size is not None:
        image = image.resize(fit_box(image.size, size), Image.LANCZOS)
    return image


def mirror(frame: np.ndarray) -> np.ndarray:
    # Invierte el fotograma como un espejo que es lo que el atleta espera al verse en directo. 
    # No se aplica a un archivo de video. nadie se está mirando.

    return cv2.flip(frame, 1)