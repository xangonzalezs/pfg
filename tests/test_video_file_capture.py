from pathlib import Path

import cv2
import numpy as np
import pytest

from core.vision.frame_source import (
    CaptureError,
    CapturedFrame,
    EndOfVideoError,
    FrameSource,
)
from core.vision import video_file_capture
from core.vision.video_file_capture import DEFAULT_FPS, VideoFileCapture

ANCHO, ALTO = 64, 48
FPS = 20.0
FOTOGRAMAS = 8


def _grabar(ruta, n: int = FOTOGRAMAS, fps: float = FPS) -> str:
    # Genera un vídeo real, para no simular la biblioteca de vídeo.

    escritor = cv2.VideoWriter(
        str(ruta), cv2.VideoWriter_fourcc(*"MJPG"), fps, (ANCHO, ALTO)
    )
    assert escritor.isOpened()
    for i in range(n):
        escritor.write(np.full((ALTO, ANCHO, 3), (i * 30) % 255, dtype=np.uint8))
    escritor.release()
    return str(ruta)


@pytest.fixture
def video(tmp_path):
    return _grabar(tmp_path / "pino.avi")


def _fuente(ruta, **kwargs) -> VideoFileCapture:
    opciones = {"realtime": False}
    opciones.update(kwargs)
    fuente = VideoFileCapture(ruta, **opciones)
    fuente.open()
    return fuente



def test_se_leen_todos_los_fotogramas_del_archivo(video):
    fuente = _fuente(video)
    leidos = 0
    while True:
        try:
            fuente.read()
        except EndOfVideoError:
            break
        leidos += 1

    assert leidos == FOTOGRAMAS


def test_cada_fotograma_llega_con_su_imagen(video):
    fotograma = _fuente(video).read()

    assert isinstance(fotograma, CapturedFrame)
    assert fotograma.image.shape == (ALTO, ANCHO, 3)


def test_el_final_del_video_no_es_un_fallo_sino_un_final(video):
    # EndOfVideoError hereda de CaptureError, de modo que quien no distinga entre ambos sigue capturando el final.
    assert issubclass(EndOfVideoError, CaptureError)


def test_la_fuente_cumple_el_contrato_comun(video):
    # Lo que permite analizar un archivo con el mismo recorrido que la cámara.
    assert isinstance(_fuente(video), FrameSource)



def test_las_marcas_se_derivan_de_la_cadencia_del_archivo(video):
    fuente = _fuente(video)
    marcas = [fuente.read().timestamp_ms for _ in range(FOTOGRAMAS)]

    assert marcas == [0, 50, 100, 150, 200, 250, 300, 350]


def test_las_marcas_crecen_estrictamente(video):
    # El seguimiento temporal del estimador de pose lo exige.
    fuente = _fuente(video)
    marcas = [fuente.read().timestamp_ms for _ in range(FOTOGRAMAS)]

    assert all(b > a for a, b in zip(marcas, marcas[1:]))


def test_las_marcas_son_deterministas(video):
    # El mismo archivo produce las mismas marcas en cualquier equipo.
    primera = [_fuente(video).read().timestamp_ms for _ in range(1)]
    segunda = [_fuente(video).read().timestamp_ms for _ in range(1)]

    assert primera == segunda


def test_las_marcas_no_dependen_de_la_velocidad_de_proceso(video):
    # analizar deprisa o despacio no altera las marcas del vídeo.
    rapido = _fuente(video)
    lento = _fuente(video)

    assert [rapido.read().timestamp_ms for _ in range(4)] == [
        lento.read().timestamp_ms for _ in range(4)
    ]



def test_se_adopta_la_cadencia_declarada_por_el_archivo(video):
    assert _fuente(video).fps == pytest.approx(FPS)


def test_una_cadencia_implausible_se_sustituye_por_la_de_respaldo(video):
    class CadenciaRota:
        def __init__(self, real):
            self._real = real

        def get(self, prop):
            if prop == cv2.CAP_PROP_FPS:
                return 0.0
            return self._real.get(prop)

        def __getattr__(self, nombre):
            return getattr(self._real, nombre)

    fuente = _fuente(
        video, capture_factory=lambda ruta: CadenciaRota(cv2.VideoCapture(ruta))
    )

    assert fuente.fps == pytest.approx(DEFAULT_FPS)


def test_en_tiempo_real_se_espera_entre_fotogramas(video):
    # El canal visual se observa, así que el vídeo se reproduce a su ritmo.
    esperas: list[float] = []
    instante = [0.0]

    def reloj() -> float:
        return instante[0]

    def dormir(segundos: float) -> None:
        esperas.append(segundos)
        instante[0] += segundos

    fuente = VideoFileCapture(
        video, realtime=True, clock=reloj, sleep=dormir
    )
    fuente.open()
    for _ in range(3):
        fuente.read()

    assert len(esperas) == 2
    assert all(espera == pytest.approx(1.0 / FPS) for espera in esperas)


def test_sin_tiempo_real_no_se_espera(video):
    # Las pruebas y el procesamiento por lotes no deben pagar la espera.
    esperas: list[float] = []
    fuente = VideoFileCapture(
        video, realtime=False, sleep=lambda s: esperas.append(s)
    )
    fuente.open()
    for _ in range(FOTOGRAMAS):
        fuente.read()

    assert esperas == []



def test_un_archivo_inexistente_se_rechaza_al_abrir(tmp_path):
    with pytest.raises(CaptureError, match="no existe"):
        VideoFileCapture(tmp_path / "no_esta.avi").open()


def test_un_archivo_ilegible_se_rechaza_al_abrir(tmp_path):
    roto = tmp_path / "roto.avi"
    roto.write_bytes(b"esto no es un video")

    with pytest.raises(CaptureError):
        VideoFileCapture(roto).open()


def test_la_extension_no_basta_para_aceptar_un_archivo(tmp_path):
    # se valida el contenido, no el nombre.
    disfrazado = tmp_path / "parece_un_video.mp4"
    disfrazado.write_bytes(b"%PDF-1.4 esto es otra cosa")

    with pytest.raises(CaptureError):
        VideoFileCapture(disfrazado).open()


def test_un_archivo_demasiado_grande_se_rechaza_al_abrir(tmp_path, monkeypatch):
    # el tope son 200 MB. Se baja el límite para no escribir tanto.
    monkeypatch.setattr(video_file_capture, "MAX_VIDEO_BYTES", 1024)
    grande = tmp_path / "grande.avi"
    grande.write_bytes(b"\0" * 2048)

    with pytest.raises(CaptureError, match="supera el máximo"):
        VideoFileCapture(grande).open()


def test_el_tamano_se_comprueba_antes_de_abrir(tmp_path, monkeypatch):
    # Un archivo que excede el tope no llega al decodificador.
    monkeypatch.setattr(video_file_capture, "MAX_VIDEO_BYTES", 1024)
    grande = tmp_path / "grande.avi"
    grande.write_bytes(b"\0" * 2048)

    def no_debe_llamarse(_ruta):
        raise AssertionError("no debería abrirse el archivo")

    with pytest.raises(CaptureError, match="supera el máximo"):
        VideoFileCapture(grande, capture_factory=no_debe_llamarse).open()


def test_un_archivo_en_el_limite_se_acepta(video, monkeypatch):
    # El tope es un máximo inclusivo, no un límite estricto.
    monkeypatch.setattr(
        video_file_capture, "MAX_VIDEO_BYTES", Path(video).stat().st_size
    )

    fuente = VideoFileCapture(video, realtime=False)
    fuente.open()
    fuente.close()


def test_no_se_puede_leer_sin_abrir(video):
    with pytest.raises(CaptureError, match="no está abierto"):
        VideoFileCapture(video).read()


def test_abrir_dos_veces_no_reinicia_la_lectura(video):
    fuente = _fuente(video)
    fuente.read()
    fuente.open()

    assert fuente.read().timestamp_ms == 50


def test_cerrar_es_idempotente(video):
    fuente = _fuente(video)

    fuente.close()
    fuente.close()

    assert not fuente.is_open


def test_tras_cerrar_no_se_puede_leer(video):
    fuente = _fuente(video)
    fuente.close()

    with pytest.raises(CaptureError):
        fuente.read()


def test_la_fuente_conoce_el_archivo_que_lee(video):
    assert _fuente(video).path.name == "pino.avi"