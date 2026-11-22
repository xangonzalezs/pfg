"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de composición de la cadena de una sesión de práctica.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path

from core.analysis.handstand_analyzer import HandstandAnalyzer
from core.feedback.feedback_engine import FeedbackEngine
from core.models.calibration_status import ThresholdsApplied
from core.models.view_mode import ViewMode
from core.persistence.user_repository import User
from core.services.session_runner import SessionRunner
from core.services.session_service import SessionService
from core.vision.camera_capture import CameraCapture
from core.vision.frame_source import FrameSource
from core.vision.pose_detector import PoseDetector
from core.vision.video_file_capture import VideoFileCapture


class PipelineError(Exception):
    # La cadena de análisis no puede montarse.

    pass


@dataclass
class SessionPipeline:
    # Cadena completa de una sesión: fuente, estimador, análisis y feedback.

    source: FrameSource
    detector: PoseDetector
    service: SessionService
    runner: SessionRunner
    thresholds_applied: ThresholdsApplied
    # Un archivo no se refleja como un espejo: no hay nadie mirándose.
    mirrored: bool

    def close(self) -> None:
        # Libera la fuente y el estimador. Puede invocarse más de una vez.

        self.runner.stop()
        self.detector.close()
        self.source.close()


def build_session(
    context,
    user: User,
    view_mode: ViewMode,
    *,
    video_path: Path | str | None = None,
    camera_index: int = 0,
    source_factory=None,
    detector_factory=None,
) -> SessionPipeline:
    # Monta la cadena de una sesión y la deja lista para arrancar.

    if context.model_path is None and detector_factory is None:
        raise PipelineError(
            "Falta el modelo de estimación de pose. Ejecute "
            "scripts/download_model.py."
        )

    alignment, applied = context.calibration.thresholds_for(user.user_id)
    thresholds = dataclasses.replace(context.thresholds, alignment=alignment)

    analyzer = HandstandAnalyzer.from_thresholds(thresholds, view_mode)
    feedback = FeedbackEngine(context.catalog, context.player, thresholds.feedback)
    service = SessionService(
        analyzer,
        feedback,
        context.sessions,
        view_mode=view_mode,
        thresholds_applied=applied,
        user_id=user.user_id,
    )

    if source_factory is not None:
        source = source_factory()
    elif video_path is not None:
        source = VideoFileCapture(video_path)
    else:
        source = CameraCapture(camera_index)

    detector = (
        detector_factory()
        if detector_factory is not None
        else PoseDetector(context.model_path)
    )

    return SessionPipeline(
        source=source,
        detector=detector,
        service=service,
        runner=SessionRunner(source, detector, service),
        thresholds_applied=applied,
        mirrored=video_path is None,
    )


def rebuild_for_view(
    pipeline: SessionPipeline, context, user: User, view_mode: ViewMode
) -> SessionPipeline:
    # Rehace análisis, feedback y servicio para la vista elegida, conservando la fuente y el estimador abiertos. 
    pipeline.runner.stop()

    alignment, applied = context.calibration.thresholds_for(user.user_id)
    thresholds = dataclasses.replace(context.thresholds, alignment=alignment)

    analyzer = HandstandAnalyzer.from_thresholds(thresholds, view_mode)
    feedback = FeedbackEngine(context.catalog, context.player, thresholds.feedback)
    service = SessionService(
        analyzer,
        feedback,
        context.sessions,
        view_mode=view_mode,
        thresholds_applied=applied,
        user_id=user.user_id,
    )

    return dataclasses.replace(
        pipeline,
        service=service,
        runner=SessionRunner(pipeline.source, pipeline.detector, service),
        thresholds_applied=applied,
    )


def open_pipeline(pipeline: SessionPipeline) -> None:
    # Abre la fuente y carga el modelo.

    pipeline.source.open()
    pipeline.detector.initialize()