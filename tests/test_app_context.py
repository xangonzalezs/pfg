import pytest

from core.models.user_role import UserRole
from core.persistence.database import IN_MEMORY, Database
from core.persistence.password import MIN_ITERATIONS
from core.persistence.user_repository import UserRepository
from ui.context import MODEL_VARIANTS, AppContext, find_model


class _ReproductorFalso:
    # Sustituye al reproductor. aquí no hay dispositivo de audio.

    def __init__(self):
        self.precargadas: list[str] = []
        self.cerrado = False

    def initialize(self, filenames):
        self.precargadas = list(filenames)

    def close(self):
        self.cerrado = True


@pytest.fixture
def contexto():
    db = Database(IN_MEMORY)
    db.open()
    yield AppContext(db, player=_ReproductorFalso())
    db.close()



def test_el_contexto_reune_los_servicios(contexto):
    assert contexto.accounts is not None
    assert contexto.calibration is not None
    assert contexto.permissions is not None


def test_los_repositorios_comparten_la_base_de_datos(contexto):
    # Una conexión por aplicación. las de SQLite pertenecen a su hilo.
    assert contexto.users._db is contexto.database
    assert contexto.calibrations._db is contexto.database
    assert contexto.sessions._db is contexto.database


def test_los_umbrales_se_cargan_del_archivo(contexto):
    assert contexto.thresholds.alignment.parameters


def test_el_catalogo_se_carga_del_archivo(contexto):
    assert len(contexto.catalog.audio_filenames) == 14



def test_al_arrancar_no_hay_sesion_iniciada(contexto):
    assert not contexto.is_signed_in
    assert contexto.current_user is None


def test_iniciar_sesion_fija_la_cuenta_activa(contexto):
    users = UserRepository(contexto.database, iterations=MIN_ITERATIONS)
    atleta = users.create("atleta", "clave1234", UserRole.ATHLETE, "Atleta")

    contexto.sign_in(atleta)

    assert contexto.is_signed_in
    assert contexto.current_user.username == "atleta"


def test_cerrar_sesion_retira_la_cuenta_activa(contexto):
    users = UserRepository(contexto.database, iterations=MIN_ITERATIONS)
    contexto.sign_in(users.create("a", "clave1234", UserRole.ATHLETE, "A"))

    contexto.sign_out()

    assert not contexto.is_signed_in



def test_las_locuciones_se_precargan_al_arrancar(contexto):
    contexto.start_audio()

    assert len(contexto.player.precargadas) == 14


def test_se_detecta_si_falta_el_modelo(tmp_path):
    db = Database(IN_MEMORY)
    db.open()
    contexto = AppContext(
        db, player=_ReproductorFalso(), model_path=tmp_path / "no_esta.task"
    )

    assert not contexto.has_model

    db.close()


def test_se_detecta_el_modelo_presente(tmp_path):
    # Sin modelo se puede entrar y consultar el histórico pero no practicar.
    modelo = tmp_path / "pose_landmarker_full.task"
    modelo.write_bytes(b"modelo")
    db = Database(IN_MEMORY)
    db.open()
    contexto = AppContext(db, player=_ReproductorFalso(), model_path=modelo)

    assert contexto.has_model

    db.close()



def test_sin_carpeta_de_modelos_no_hay_modelo(tmp_path):
    assert find_model(tmp_path / "no_existe") is None


def test_una_carpeta_vacia_no_tiene_modelo(tmp_path):
    assert find_model(tmp_path) is None


@pytest.mark.parametrize("variante", MODEL_VARIANTS)
def test_se_encuentra_cualquiera_de_las_tres_variantes(tmp_path, variante):
    # El script descarga lite, full o heavy, cada una con su propio nombre.
    modelo = tmp_path / f"pose_landmarker_{variante}.task"
    modelo.write_bytes(b"modelo")

    assert find_model(tmp_path) == modelo


def test_con_varias_descargadas_se_elige_la_mas_precisa(tmp_path):
    for variante in ("lite", "full", "heavy"):
        (tmp_path / f"pose_landmarker_{variante}.task").write_bytes(b"m")

    assert find_model(tmp_path).name == "pose_landmarker_heavy.task"


def test_se_acepta_un_modelo_con_otro_nombre(tmp_path):
    # Por si se descargó a mano desde la página de MediaPipe.
    modelo = tmp_path / "mi_modelo.task"
    modelo.write_bytes(b"modelo")

    assert find_model(tmp_path) == modelo


def test_un_archivo_que_no_es_modelo_se_ignora(tmp_path):
    (tmp_path / "notas.txt").write_text("no soy un modelo", encoding="utf-8")

    assert find_model(tmp_path) is None


def test_cerrar_libera_audio_y_base_de_datos(contexto):
    contexto.close()

    assert contexto.player.cerrado
    assert not contexto.database.is_open