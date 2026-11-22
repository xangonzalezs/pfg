import numpy as np
import pytest

from core.vision.camera_capture import CameraCapture
from core.vision.frame_source import CaptureError, FrameSource

ANCHO, ALTO = 64, 48


class _CamaraFalsa:
    # Sustituye al dispositivo, que no existe en un entorno de pruebas.

    def __init__(self, *, abierta: bool = True, fotogramas: int | None = None):
        self._abierta = abierta
        self._restantes = fotogramas
        self.liberada = False

    def isOpened(self):
        return self._abierta

    def read(self):
        if self._restantes is not None:
            if self._restantes <= 0:
                return False, None
            self._restantes -= 1
        return True, np.zeros((ALTO, ANCHO, 3), dtype=np.uint8)

    def release(self):
        self.liberada = True
        self._abierta = False


class _Reloj:
    # Reloj controlado, para comprobar las marcas sin depender del tiempo real.

    def __init__(self):
        self.ahora = 10.0

    def __call__(self) -> float:
        return self.ahora

    def avanzar(self, segundos: float) -> None:
        self.ahora += segundos


class _Dispositivos:
    # La fábrica entrega una cámara nueva en cada apertura.

    def __init__(self, **opciones):
        self.opciones = opciones
        self.creadas: list[_CamaraFalsa] = []

    def __call__(self, indice: int) -> _CamaraFalsa:
        self.creadas.append(_CamaraFalsa(**self.opciones))
        return self.creadas[-1]

    @property
    def ultima(self) -> _CamaraFalsa:
        return self.creadas[-1]


def _camara(reloj: _Reloj | None = None, **opciones):
    reloj = reloj or _Reloj()
    dispositivos = _Dispositivos(**opciones)
    fuente = CameraCapture(0, capture_factory=dispositivos, clock=reloj)
    fuente.open()
    return fuente, dispositivos, reloj


def test_una_camara_disponible_se_abre():
    fuente, _, _ = _camara()
    assert fuente.is_open


def test_una_camara_no_disponible_se_rechaza():
    fuente = CameraCapture(2, capture_factory=_Dispositivos(abierta=False))

    with pytest.raises(CaptureError, match="cámara 2"):
        fuente.open()


def test_una_camara_no_disponible_se_libera_igualmente():
    dispositivos = _Dispositivos(abierta=False)
    fuente = CameraCapture(0, capture_factory=dispositivos)

    with pytest.raises(CaptureError):
        fuente.open()

    assert dispositivos.ultima.liberada


def test_abrir_dos_veces_no_reabre_el_dispositivo():
    fuente, dispositivos, _ = _camara()

    fuente.open()

    assert len(dispositivos.creadas) == 1


def test_la_fuente_cumple_el_contrato_comun():
    fuente, _, _ = _camara()
    assert isinstance(fuente, FrameSource)



def test_se_entrega_el_fotograma_de_la_camara():
    fuente, _, _ = _camara()
    assert fuente.read().image.shape == (ALTO, ANCHO, 3)


def test_no_se_puede_leer_sin_abrir():
    fuente = CameraCapture(0, capture_factory=_Dispositivos())

    with pytest.raises(CaptureError, match="no está abierta"):
        fuente.read()


def test_una_camara_que_deja_de_responder_se_notifica():
    fuente, _, _ = _camara(fotogramas=1)
    fuente.read()

    with pytest.raises(CaptureError, match="dejó de entregar"):
        fuente.read()



def test_la_marca_es_el_tiempo_transcurrido_desde_la_apertura():
    # En directo los fotogramas llegan a medida que ocurren.
    fuente, _, reloj = _camara()

    reloj.avanzar(0.040)
    primera = fuente.read().timestamp_ms
    reloj.avanzar(0.040)
    segunda = fuente.read().timestamp_ms

    assert primera == 40
    assert segunda == 80


def test_la_primera_marca_parte_de_cero():
    fuente, _, _ = _camara()
    assert fuente.read().timestamp_ms == 0


def test_las_marcas_crecen_con_el_tiempo():
    fuente, _, reloj = _camara()
    marcas = []
    for _ in range(4):
        reloj.avanzar(0.033)
        marcas.append(fuente.read().timestamp_ms)

    assert all(b > a for a, b in zip(marcas, marcas[1:]))



def test_cerrar_libera_el_dispositivo():
    fuente, dispositivos, _ = _camara()

    fuente.close()

    assert dispositivos.ultima.liberada
    assert not fuente.is_open


def test_cerrar_es_idempotente():
    fuente, _, _ = _camara()

    fuente.close()
    fuente.close()

    assert not fuente.is_open


def test_reabrir_reinicia_el_origen_de_tiempos():
    fuente, _, reloj = _camara()
    reloj.avanzar(5.0)
    fuente.read()

    fuente.close()
    fuente.open()

    assert fuente.read().timestamp_ms == 0