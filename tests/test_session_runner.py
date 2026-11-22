import threading

import numpy as np
import pytest

from core.models.landmark_result import LandmarkResult
from core.services.session_runner import SessionRunner
from core.services.session_service import FrameOutcome
from core.vision.frame_source import CaptureError, CapturedFrame, EndOfVideoError
from core.vision.pose_detector import PoseDetectorError

IMAGEN = np.zeros((48, 64, 3), dtype=np.uint8)


class _FuenteFalsa:
    # Entrega un número fijo de fotogramas y luego lo que se le indique.

    def __init__(self, fotogramas: int = 3, al_agotarse=EndOfVideoError):
        self._restantes = fotogramas
        self._al_agotarse = al_agotarse
        self._i = 0
        self.leidos = 0

    def read(self) -> CapturedFrame:
        if self._restantes <= 0:
            raise self._al_agotarse("fuente agotada")
        self._restantes -= 1
        self.leidos += 1
        marca = self._i * 33
        self._i += 1
        return CapturedFrame(image=IMAGEN, timestamp_ms=marca)

    def close(self) -> None:
        pass

    @property
    def is_open(self) -> bool:
        return True


class _FuenteInagotable(_FuenteFalsa):
    # Nunca se agota, para comprobar la parada cooperativa.

    def read(self) -> CapturedFrame:
        marca = self._i * 33
        self._i += 1
        self.leidos += 1
        return CapturedFrame(image=IMAGEN, timestamp_ms=marca)


class _DetectorFalso:
    def __init__(self, fallos: int = 0):
        self._fallos = fallos
        self.marcas: list[int] = []

    def detect(self, image, timestamp_ms: int) -> LandmarkResult:
        if self._fallos > 0:
            self._fallos -= 1
            raise PoseDetectorError("fallo simulado")
        self.marcas.append(timestamp_ms)
        return LandmarkResult(landmarks=[], timestamp_ms=timestamp_ms)


class _ServicioFalso:
    # Sustituye al servicio. registra qué fotogramas recibe.

    def __init__(self, tope_fallos: int = 3):
        self.recibidos: list[int] = []
        self.fallos = 0
        self._tope = tope_fallos

    def process(self, landmark_result) -> FrameOutcome:
        self.recibidos.append(landmark_result.timestamp_ms)
        return FrameOutcome(
            landmark_result=landmark_result, analysis=None, is_framed=True
        )

    def note_failure(self) -> bool:
        self.fallos += 1
        return self.fallos < self._tope


def _runner(fuente=None, detector=None, servicio=None):
    fuente = fuente or _FuenteFalsa()
    detector = detector or _DetectorFalso()
    servicio = servicio or _ServicioFalso()
    return SessionRunner(fuente, detector, servicio), fuente, detector, servicio


def _correr_hasta_el_final(runner):
    # La fuente se agota sola. basta esperar al hilo sin dormir.

    runner.start()
    runner.stop()



def test_se_entregan_todos_los_fotogramas_al_servicio():
    runner, _, _, servicio = _runner(_FuenteFalsa(fotogramas=5))

    _correr_hasta_el_final(runner)

    assert len(servicio.recibidos) == 5


def test_la_marca_de_la_fuente_llega_hasta_el_servicio():
    # la fuente sabe qué reloj aplica.
    runner, _, detector, servicio = _runner(_FuenteFalsa(fotogramas=3))

    _correr_hasta_el_final(runner)

    assert detector.marcas == [0, 33, 66]
    assert servicio.recibidos == [0, 33, 66]


def test_la_imagen_se_publica_junto_a_su_resultado():
    # La interfaz pinta la imagen y el esqueleto de un mismo fotograma.
    runner, _, _, _ = _runner(_FuenteFalsa(fotogramas=3))

    _correr_hasta_el_final(runner)
    publicado = runner.latest()

    assert publicado.image is IMAGEN
    assert publicado.outcome.landmark_result.timestamp_ms == 66


def test_el_ultimo_resultado_queda_publicado():
    runner, _, _, _ = _runner(_FuenteFalsa(fotogramas=3))

    _correr_hasta_el_final(runner)

    assert runner.latest().outcome.landmark_result.timestamp_ms == 66


def test_antes_de_arrancar_no_hay_nada_publicado():
    runner, _, _, _ = _runner()

    assert runner.latest() is None




def test_el_fin_del_video_no_es_un_fallo():
    # el archivo se acaba y la interfaz pasa al resumen.
    runner, _, _, _ = _runner(_FuenteFalsa(fotogramas=2))

    _correr_hasta_el_final(runner)

    assert runner.source_exhausted
    assert runner.failure is None


def test_un_fallo_de_la_fuente_se_distingue_del_fin_del_video():
    # la interfaz tiene que poder avisar.
    runner, _, _, _ = _runner(_FuenteFalsa(fotogramas=2, al_agotarse=CaptureError))

    _correr_hasta_el_final(runner)

    assert not runner.source_exhausted
    assert "fuente agotada" in runner.failure


def test_tras_agotarse_la_fuente_el_hilo_termina_solo():
    runner, _, _, _ = _runner(_FuenteFalsa(fotogramas=1))

    runner.start()
    runner.stop()

    assert not runner.is_running




def test_un_fallo_puntual_del_estimador_no_corta_el_bucle():
    detector = _DetectorFalso(fallos=1)
    runner, _, _, servicio = _runner(_FuenteFalsa(fotogramas=3), detector)

    _correr_hasta_el_final(runner)

    assert servicio.fallos == 1
    assert len(servicio.recibidos) == 2


def test_si_el_servicio_da_la_sesion_por_perdida_el_bucle_termina():
    detector = _DetectorFalso(fallos=10)
    servicio = _ServicioFalso(tope_fallos=3)
    runner, _, _, _ = _runner(_FuenteInagotable(), detector, servicio)

    _correr_hasta_el_final(runner)

    assert servicio.fallos == 3
    assert runner.failure is not None




def test_se_puede_parar_una_fuente_inagotable():
    runner, _, _, _ = _runner(_FuenteInagotable())

    runner.start()
    runner.stop()

    assert not runner.is_running


def test_arrancar_dos_veces_no_crea_un_segundo_hilo():
    antes = threading.active_count()
    runner, _, _, _ = _runner(_FuenteInagotable())

    runner.start()
    runner.start()
    activos = threading.active_count()
    runner.stop()

    assert activos == antes + 1


def test_parar_sin_haber_arrancado_no_falla():
    runner, _, _, _ = _runner()

    runner.stop()

    assert not runner.is_running


def test_el_hilo_es_demonio():
    # Para que un cierre de la aplicación no quede colgado esperándolo.
    runner, _, _, _ = _runner(_FuenteInagotable())

    runner.start()
    es_demonio = runner._thread.daemon
    runner.stop()

    assert es_demonio


def test_rearrancar_limpia_el_motivo_anterior():
    runner, _, _, _ = _runner(_FuenteFalsa(fotogramas=1, al_agotarse=CaptureError))
    _correr_hasta_el_final(runner)
    assert runner.failure is not None

    runner._source = _FuenteInagotable()
    runner.start()
    motivo = runner.failure
    runner.stop()

    assert motivo is None



def test_el_runner_no_llama_a_finish():
    # Las conexiones de SQLite pertenecen al hilo que las abrió.
    # el registro corresponde a quien llama, tras stop().
    llamadas = []

    class ServicioQueVigila(_ServicioFalso):
        def finish(self, **kwargs):
            llamadas.append(kwargs)

    runner, _, _, _ = _runner(_FuenteFalsa(fotogramas=2), None, ServicioQueVigila())

    _correr_hasta_el_final(runner)

    assert llamadas == []