import numpy as np
import pytest

from core.models.calibration_status import ThresholdsApplied
from core.models.landmark_result import LandmarkResult
from core.models.user_role import UserRole
from core.models.view_mode import ViewMode
from core.persistence.database import IN_MEMORY, Database
from core.persistence.password import MIN_ITERATIONS
from core.persistence.user_repository import UserRepository
from core.vision.frame_source import CapturedFrame
from ui.context import AppContext
from ui.pipeline import PipelineError, build_session

IMAGEN = np.zeros((48, 64, 3), dtype=np.uint8)


class _ReproductorFalso:
    is_playing = False

    def initialize(self, filenames):
        pass

    def play(self, filename):
        pass

    def close(self):
        pass


class _FuenteFalsa:
    def __init__(self):
        self.abierta = False
        self.cerrada = False

    def open(self):
        self.abierta = True

    def read(self):
        return CapturedFrame(image=IMAGEN, timestamp_ms=0)

    def close(self):
        self.cerrada = True

    @property
    def is_open(self):
        return self.abierta


class _DetectorFalso:
    def __init__(self):
        self.inicializado = False
        self.cerrado = False

    def initialize(self):
        self.inicializado = True

    def detect(self, image, timestamp_ms):
        return LandmarkResult(landmarks=[], timestamp_ms=timestamp_ms)

    def close(self):
        self.cerrado = True


@pytest.fixture
def entorno():
    db = Database(IN_MEMORY)
    db.open()
    contexto = AppContext(db, player=_ReproductorFalso())
    users = UserRepository(db, iterations=MIN_ITERATIONS)
    entrenadora = users.create("entre", "clave1234", UserRole.TRAINER, "E")
    atleta = users.create(
        "atleta",
        "clave1234",
        UserRole.ATHLETE,
        "Atleta",
        assigned_trainer_id=entrenadora.user_id,
    )
    yield contexto, atleta, entrenadora.user_id
    db.close()


def _montar(contexto, atleta, **cambios):
    opciones = {
        "source_factory": _FuenteFalsa,
        "detector_factory": _DetectorFalso,
    }
    opciones.update(cambios)
    return build_session(contexto, atleta, ViewMode.LATERAL, **opciones)



def test_la_cadena_queda_completa(entorno):
    contexto, atleta, _ = entorno

    cadena = _montar(contexto, atleta)

    assert cadena.source is not None
    assert cadena.detector is not None
    assert cadena.service is not None
    assert cadena.runner is not None


def test_la_vista_elegida_rige_la_sesion(entorno):
    # se fija antes de empezar y no cambia.
    contexto, atleta, _ = entorno

    cadena = build_session(
        contexto,
        atleta,
        ViewMode.FRONTAL,
        source_factory=_FuenteFalsa,
        detector_factory=_DetectorFalso,
    )

    assert cadena.service.view_mode is ViewMode.FRONTAL


def test_sin_modelo_descargado_no_se_monta(entorno):
    # Es lo que impide entrar a practicar sin haberlo descargado.
    contexto, atleta, _ = entorno
    contexto.model_path = None

    with pytest.raises(PipelineError, match="download_model"):
        build_session(contexto, atleta, ViewMode.LATERAL, source_factory=_FuenteFalsa)



def test_sin_calibracion_validada_se_practica_con_los_genericos(entorno):
    contexto, atleta, _ = entorno

    assert _montar(contexto, atleta).thresholds_applied is ThresholdsApplied.GENERIC


def test_con_calibracion_validada_se_practica_personalizado(entorno):
    contexto, atleta, entrenadora = entorno
    perfil = contexto.calibrations.create_pending(atleta.user_id, knee_deg=170.0)
    contexto.calibration.validate(perfil.profile_id, entrenadora)

    cadena = _montar(contexto, atleta)

    assert cadena.thresholds_applied is ThresholdsApplied.PERSONALIZED


def test_los_umbrales_personalizados_llegan_al_analisis(entorno):
    # No basta con etiquetar la sesión. el analizador tiene que usarlos.
    contexto, atleta, entrenadora = entorno
    perfil = contexto.calibrations.create_pending(atleta.user_id, knee_deg=165.0)
    contexto.calibration.validate(
        perfil.profile_id, entrenadora, overrides={"knee_bend": 27.0}
    )

    cadena = _montar(contexto, atleta)
    umbral = cadena.service._analyzer._alignment.thresholds.parameters["knee_bend"]

    assert umbral.threshold == pytest.approx(27.0)


def test_en_directo_la_imagen_se_refleja(entorno):
    # El atleta se mira. debe verse como en un espejo.
    contexto, atleta, _ = entorno

    assert _montar(contexto, atleta).mirrored


def test_al_analizar_un_archivo_no_se_refleja(entorno):
    contexto, atleta, _ = entorno

    cadena = _montar(contexto, atleta, video_path="pino.avi")

    assert not cadena.mirrored



def test_abrir_prepara_fuente_y_estimador(entorno):
    from ui.pipeline import open_pipeline

    contexto, atleta, _ = entorno
    cadena = _montar(contexto, atleta)

    open_pipeline(cadena)

    assert cadena.source.abierta
    assert cadena.detector.inicializado


def test_cerrar_libera_fuente_y_estimador(entorno):
    contexto, atleta, _ = entorno
    cadena = _montar(contexto, atleta)

    cadena.close()

    assert cadena.source.cerrada
    assert cadena.detector.cerrado


def test_cerrar_es_idempotente(entorno):
    contexto, atleta, _ = entorno
    cadena = _montar(contexto, atleta)

    cadena.close()
    cadena.close()

    assert cadena.source.cerrada



def test_rehacer_para_una_vista_cambia_el_analisis(entorno):
    # La vista no se conoce hasta que el usuario la elige al terminar la preparación.
    from ui.pipeline import rebuild_for_view

    contexto, atleta, _ = entorno
    cadena = _montar(contexto, atleta)
    assert cadena.service.view_mode is ViewMode.LATERAL

    rehecha = rebuild_for_view(cadena, contexto, atleta, ViewMode.FRONTAL)

    assert rehecha.service.view_mode is ViewMode.FRONTAL


def test_rehacer_conserva_la_fuente_y_el_estimador(entorno):
    # Volver a abrir la cámara tardaría y parpadearía sin motivo.
    from ui.pipeline import rebuild_for_view

    contexto, atleta, _ = entorno
    cadena = _montar(contexto, atleta)
    fuente, detector = cadena.source, cadena.detector

    rehecha = rebuild_for_view(cadena, contexto, atleta, ViewMode.FRONTAL)

    assert rehecha.source is fuente
    assert rehecha.detector is detector
    assert not fuente.cerrada


def test_rehacer_da_un_hilo_nuevo_sobre_el_servicio_nuevo(entorno):
    from ui.pipeline import rebuild_for_view

    contexto, atleta, _ = entorno
    cadena = _montar(contexto, atleta)

    rehecha = rebuild_for_view(cadena, contexto, atleta, ViewMode.FRONTAL)

    assert rehecha.runner is not cadena.runner
    assert rehecha.runner._service is rehecha.service


def test_rehacer_conserva_el_tipo_de_umbrales(entorno):
    from ui.pipeline import rebuild_for_view

    contexto, atleta, entrenadora = entorno
    perfil = contexto.calibrations.create_pending(atleta.user_id, knee_deg=170.0)
    contexto.calibration.validate(perfil.profile_id, entrenadora)
    cadena = _montar(contexto, atleta)

    rehecha = rebuild_for_view(cadena, contexto, atleta, ViewMode.FRONTAL)

    assert rehecha.thresholds_applied is ThresholdsApplied.PERSONALIZED