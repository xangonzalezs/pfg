import pytest

from core.feedback.audio_player import AudioAssetError, AudioPlayer

LOCUCIONES = ("back_arch.mp3", "positive.mp3")


class _MezcladorFalso:
    # Sustituye a pygame, que exige un dispositivo de audio.

    def __init__(self, *, ocupado: bool = False, falla_al_cargar: bool = False):
        self.ocupado = ocupado
        self._falla_al_cargar = falla_al_cargar
        self.cargadas: list[str] = []
        self.reproducidas: list[str] = []
        self.cerrado = False

    def load(self, path):
        if self._falla_al_cargar:
            raise RuntimeError("formato no soportado")
        self.cargadas.append(path.name)
        return path.name

    def play(self, sound):
        self.reproducidas.append(sound)

    def is_busy(self):
        return self.ocupado

    def close(self):
        self.cerrado = True


@pytest.fixture
def audio_dir(tmp_path):
    for nombre in LOCUCIONES:
        (tmp_path / nombre).write_bytes(b"audio de prueba")
    return tmp_path


def _reproductor(audio_dir, mezclador=None, locuciones=LOCUCIONES):
    mezclador = mezclador or _MezcladorFalso()
    player = AudioPlayer(audio_dir, backend_factory=lambda: mezclador)
    player.initialize(locuciones)
    return player, mezclador



def test_las_locuciones_se_cargan_al_inicializar(audio_dir):
    # emitir un mensaje no debe implicar ninguna lectura en disco.
    _, mezclador = _reproductor(audio_dir)

    assert sorted(mezclador.cargadas) == sorted(LOCUCIONES)


def test_reproducir_no_vuelve_a_cargar(audio_dir):
    player, mezclador = _reproductor(audio_dir)

    player.play("back_arch.mp3")
    player.play("back_arch.mp3")

    assert len(mezclador.cargadas) == len(LOCUCIONES)


def test_inicializar_dos_veces_no_recarga(audio_dir):
    player, mezclador = _reproductor(audio_dir)

    player.initialize(LOCUCIONES)

    assert len(mezclador.cargadas) == len(LOCUCIONES)


def test_una_locucion_ausente_se_rechaza(audio_dir):
    player = AudioPlayer(audio_dir, backend_factory=_MezcladorFalso)

    with pytest.raises(AudioAssetError, match="elbow_not_extended.mp3"):
        player.initialize(("back_arch.mp3", "elbow_not_extended.mp3"))


def test_una_locucion_ausente_se_rechaza_tambien_sin_audio(audio_dir):
    # Es un defecto del paquete, no una circunstancia del equipo.
    def sin_mezclador():
        raise RuntimeError("no hay dispositivo de audio")

    player = AudioPlayer(audio_dir, backend_factory=sin_mezclador)

    with pytest.raises(AudioAssetError):
        player.initialize(("no_existe.mp3",))


def test_una_locucion_no_precargada_no_se_reproduce(audio_dir):
    player, _ = _reproductor(audio_dir, locuciones=("back_arch.mp3",))

    with pytest.raises(AudioAssetError, match="no se precargó"):
        player.play("positive.mp3")



def test_sin_dispositivo_de_audio_el_reproductor_queda_inoperativo(audio_dir):
    # la sesión continúa con el canal visual como único medio.
    def sin_mezclador():
        raise RuntimeError("no hay dispositivo de audio")

    player = AudioPlayer(audio_dir, backend_factory=sin_mezclador)
    player.initialize(LOCUCIONES)

    assert not player.is_available


def test_sin_dispositivo_de_audio_reproducir_no_falla(audio_dir):
    player = AudioPlayer(
        audio_dir, backend_factory=lambda: (_ for _ in ()).throw(RuntimeError())
    )
    player.initialize(LOCUCIONES)

    player.play("back_arch.mp3")


def test_un_fallo_al_cargar_deja_el_reproductor_inoperativo(audio_dir):
    mezclador = _MezcladorFalso(falla_al_cargar=True)
    player = AudioPlayer(audio_dir, backend_factory=lambda: mezclador)

    player.initialize(LOCUCIONES)

    assert not player.is_available
    assert mezclador.cerrado


def test_sin_dispositivo_de_audio_nada_suena_nunca(audio_dir):
    # is_playing debe ser falso, o bloquearía el motor de feedback.
    player = AudioPlayer(
        audio_dir, backend_factory=lambda: (_ for _ in ()).throw(RuntimeError())
    )
    player.initialize(LOCUCIONES)

    assert not player.is_playing



def test_se_reproduce_la_locucion_pedida(audio_dir):
    player, mezclador = _reproductor(audio_dir)

    player.play("positive.mp3")

    assert mezclador.reproducidas == ["positive.mp3"]


def test_el_estado_de_reproduccion_lo_informa_el_mezclador(audio_dir):
    player, mezclador = _reproductor(audio_dir, _MezcladorFalso(ocupado=True))

    assert player.is_playing

    mezclador.ocupado = False

    assert not player.is_playing



def test_cerrar_libera_el_mezclador(audio_dir):
    player, mezclador = _reproductor(audio_dir)

    player.close()

    assert mezclador.cerrado
    assert not player.is_available


def test_cerrar_es_idempotente(audio_dir):
    player, _ = _reproductor(audio_dir)

    player.close()
    player.close()

    assert not player.is_available


def test_tras_cerrar_se_puede_volver_a_inicializar(audio_dir):
    player, _ = _reproductor(audio_dir)
    player.close()

    player.initialize(LOCUCIONES)

    assert player.is_available