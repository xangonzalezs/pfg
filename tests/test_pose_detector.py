import numpy as np
import pytest

from core.vision.pose_detector import PoseDetector, PoseDetectorError

FOTOGRAMA = np.zeros((48, 64, 3), dtype=np.uint8)


class _Punto:
    # Punto tal como lo entrega el estimador. coordenadas normalizadas.

    def __init__(self, x: float, y: float, z: float = 0.0, visibility: float = 0.9):
        self.x, self.y, self.z, self.visibility = x, y, z, visibility


class _EstimadorFalso:
    # Sustituye al estimador real, que exige el modelo y la biblioteca nativa.

    def __init__(self, puntos=None, error: Exception | None = None):
        self.puntos = puntos if puntos is not None else [_Punto(0.5, 0.5)]
        self.error = error
        self.llamadas: list[int] = []
        self.cerrado = False

    def detect(self, frame, timestamp_ms):
        self.llamadas.append(timestamp_ms)
        if self.error is not None:
            raise self.error
        return self.puntos

    def close(self):
        self.cerrado = True


@pytest.fixture
def modelo(tmp_path):
    ruta = tmp_path / "pose_landmarker.task"
    ruta.write_bytes(b"modelo de prueba")
    return ruta


def _detector(modelo, estimador: _EstimadorFalso | None = None):
    estimador = estimador or _EstimadorFalso()
    detector = PoseDetector(modelo, backend_factory=lambda buffer: estimador)
    detector.initialize()
    return detector, estimador



def test_el_detector_no_esta_listo_antes_de_inicializar(modelo):
    assert not PoseDetector(modelo).is_ready


def test_inicializar_deja_el_detector_listo(modelo):
    detector, _ = _detector(modelo)
    assert detector.is_ready


def test_un_modelo_ausente_se_notifica_con_la_forma_de_obtenerlo(tmp_path):
    detector = PoseDetector(tmp_path / "no_esta.task")

    with pytest.raises(PoseDetectorError, match="download_model"):
        detector.initialize()


def test_el_modelo_se_entrega_como_bufer_y_no_como_ruta(modelo):
    recibido: list[bytes] = []

    def fabrica(buffer):
        recibido.append(buffer)
        return _EstimadorFalso()

    PoseDetector(modelo, backend_factory=fabrica).initialize()

    assert recibido == [b"modelo de prueba"]


def test_un_fallo_al_cargar_se_traduce_al_error_del_sistema(modelo):
    def fabrica(buffer):
        raise RuntimeError("biblioteca nativa no disponible")

    detector = PoseDetector(modelo, backend_factory=fabrica)

    with pytest.raises(PoseDetectorError, match="No se pudo cargar"):
        detector.initialize()
    assert not detector.is_ready


def test_inicializar_dos_veces_no_recarga_el_modelo(modelo):
    cargas = []
    detector = PoseDetector(
        modelo, backend_factory=lambda b: cargas.append(b) or _EstimadorFalso()
    )

    detector.initialize()
    detector.initialize()

    assert len(cargas) == 1


def test_no_se_puede_detectar_sin_inicializar(modelo):
    with pytest.raises(PoseDetectorError, match="no está inicializado"):
        PoseDetector(modelo).detect(FOTOGRAMA, 0)



def test_los_puntos_se_traducen_al_modelo_del_sistema(modelo):
    estimador = _EstimadorFalso([_Punto(0.25, 0.75, z=0.1, visibility=0.8)])
    detector, _ = _detector(modelo, estimador)

    resultado = detector.detect(FOTOGRAMA, 0)
    punto = resultado.landmarks[0]

    assert punto.index == 0
    assert punto.x == pytest.approx(0.25)
    assert punto.y == pytest.approx(0.75)
    assert punto.z == pytest.approx(0.1)
    assert punto.visibility == pytest.approx(0.8)


def test_el_indice_de_cada_punto_es_su_posicion_en_la_lista(modelo):
    # Es la convención de MediaPipe, de la que depende todo el análisis.
    estimador = _EstimadorFalso([_Punto(0.1 * i, 0.5) for i in range(5)])
    detector, _ = _detector(modelo, estimador)

    resultado = detector.detect(FOTOGRAMA, 0)

    assert [p.index for p in resultado.landmarks] == [0, 1, 2, 3, 4]


def test_un_fotograma_sin_persona_produce_un_resultado_vacio(modelo):
    # No es un fallo. el atleta puede salir del encuadre.
    detector, _ = _detector(modelo, _EstimadorFalso([]))

    resultado = detector.detect(FOTOGRAMA, 0)

    assert resultado.landmarks == []
    assert not resultado.has_detection


def test_el_resultado_conserva_la_marca_de_tiempo(modelo):
    detector, _ = _detector(modelo)
    assert detector.detect(FOTOGRAMA, 120).timestamp_ms == 120


def test_un_punto_sin_visibilidad_se_traduce_como_no_visible(modelo):
    class SinVisibilidad:
        x, y = 0.5, 0.5

    detector, _ = _detector(modelo, _EstimadorFalso([SinVisibilidad()]))

    assert detector.detect(FOTOGRAMA, 0).landmarks[0].visibility == 0.0


def test_un_fallo_del_estimador_se_traduce_al_error_del_sistema(modelo):
    detector, _ = _detector(
        modelo, _EstimadorFalso(error=RuntimeError("fallo interno"))
    )

    with pytest.raises(PoseDetectorError, match="Fallo al estimar"):
        detector.detect(FOTOGRAMA, 0)



def test_la_marca_se_transmite_al_estimador(modelo):
    # El seguimiento entre fotogramas se apoya en ella.
    detector, estimador = _detector(modelo)

    for marca in (0, 40, 80):
        detector.detect(FOTOGRAMA, marca)

    assert estimador.llamadas == [0, 40, 80]


def test_una_marca_que_no_avanza_se_rechaza(modelo):
    # El modo de vídeo exige marcas estrictamente crecientes.
    detector, _ = _detector(modelo)
    detector.detect(FOTOGRAMA, 100)

    with pytest.raises(PoseDetectorError, match="debe crecer"):
        detector.detect(FOTOGRAMA, 100)


def test_una_marca_hacia_atras_se_rechaza(modelo):
    detector, _ = _detector(modelo)
    detector.detect(FOTOGRAMA, 100)

    with pytest.raises(PoseDetectorError, match="debe crecer"):
        detector.detect(FOTOGRAMA, 40)


def test_una_marca_rechazada_no_altera_la_ultima_valida(modelo):
    detector, _ = _detector(modelo)
    detector.detect(FOTOGRAMA, 100)

    with pytest.raises(PoseDetectorError):
        detector.detect(FOTOGRAMA, 40)

    assert detector.detect(FOTOGRAMA, 140).timestamp_ms == 140


def test_reset_permite_empezar_una_fuente_nueva(modelo):
    # Al analizar un vídeo tras una sesión de cámara las marcas se reinician.
    detector, _ = _detector(modelo)
    detector.detect(FOTOGRAMA, 5000)

    detector.reset()

    assert detector.detect(FOTOGRAMA, 0).timestamp_ms == 0



def test_cerrar_libera_el_estimador(modelo):
    detector, estimador = _detector(modelo)

    detector.close()

    assert estimador.cerrado
    assert not detector.is_ready


def test_cerrar_es_idempotente(modelo):
    detector, _ = _detector(modelo)

    detector.close()
    detector.close()

    assert not detector.is_ready


def test_tras_cerrar_se_puede_volver_a_inicializar(modelo):
    detector, _ = _detector(modelo)
    detector.close()

    detector.initialize()

    assert detector.is_ready