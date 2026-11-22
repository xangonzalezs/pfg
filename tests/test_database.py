import sqlite3

import pytest

from core.models.analysis_result import TechnicalError
from core.models.calibration_status import CalibrationStatus, ThresholdsApplied
from core.models.user_role import UserRole
from core.models.view_mode import ViewMode
from core.persistence import schema
from core.persistence.database import (
    IN_MEMORY,
    Database,
    DatabaseError,
    utc_now,
)


@pytest.fixture
def db():
    base = Database(IN_MEMORY)
    base.open()
    yield base
    base.close()


def _nombres(db, tipo):
    filas = db.connection.execute(
        "SELECT name FROM sqlite_master WHERE type = ? AND name NOT LIKE 'sqlite_%'",
        (tipo,),
    ).fetchall()
    return sorted(fila[0] for fila in filas)


def _usuario(db, username="atleta", role=UserRole.ATHLETE):
    cursor = db.connection.execute(
        "INSERT INTO users (username, password_hash, role, full_name, created_at) "
        "VALUES (?, 'x', ?, 'Nombre', ?)",
        (username, role.value, utc_now()),
    )
    db.connection.commit()
    return int(cursor.lastrowid)



def test_al_abrir_se_crean_las_cinco_tablas(db):
    assert _nombres(db, "table") == sorted(schema.TABLE_NAMES)


def test_al_abrir_se_crean_los_cinco_indices_explicitos(db):
    # Los que el apartado 4.6 justifica uno por uno.
    assert _nombres(db, "index") == sorted(schema.INDEX_NAMES)


def test_el_esquema_registra_su_version(db):
    assert db.schema_version == schema.SCHEMA_VERSION


def test_abrir_una_base_ya_poblada_no_la_altera(tmp_path):
    ruta = tmp_path / "handstand.db"

    with Database(ruta) as primera:
        _usuario(primera)

    with Database(ruta) as segunda:
        total = segunda.connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    assert total == 1


def test_abrir_crea_el_directorio_si_no_existe(tmp_path):
    ruta = tmp_path / "datos" / "handstand.db"

    with Database(ruta):
        pass

    assert ruta.is_file()


def test_abrir_dos_veces_no_reabre(db):
    primera = db.connection
    db.open()

    assert db.connection is primera



def test_la_integridad_referencial_esta_activada(db):
    # SQLite la desactiva por defecto y por conexión.
    # sin esto, todos los ON DELETE del esquema no funcionarían.
    assert db.connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_una_referencia_inexistente_se_rechaza(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.connection.execute(
            "INSERT INTO sessions (user_id, timestamp, total_duration_s, "
            "total_hold_time_s, hold_attempts, view_mode, thresholds_applied) "
            "VALUES (9999, ?, 1.0, 1.0, 1, 'lateral', 'generic')",
            (utc_now(),),
        )


def test_borrar_un_atleta_arrastra_sus_sesiones(db):
    user_id = _usuario(db)
    db.connection.execute(
        "INSERT INTO sessions (user_id, timestamp, total_duration_s, "
        "total_hold_time_s, hold_attempts, view_mode, thresholds_applied) "
        "VALUES (?, ?, 1.0, 1.0, 1, 'lateral', 'generic')",
        (user_id, utc_now()),
    )

    db.connection.execute("DELETE FROM users WHERE user_id = ?", (user_id,))

    assert db.connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0


def test_borrar_un_entrenador_no_arrastra_a_sus_atletas(db):
    # La supervisión es relación entre cuentas, no pertenencia.
    trainer_id = _usuario(db, "entre", UserRole.TRAINER)
    athlete_id = _usuario(db, "atleta")
    db.connection.execute(
        "UPDATE users SET assigned_trainer_id = ? WHERE user_id = ?",
        (trainer_id, athlete_id),
    )

    db.connection.execute("DELETE FROM users WHERE user_id = ?", (trainer_id,))

    fila = db.connection.execute(
        "SELECT assigned_trainer_id FROM users WHERE user_id = ?", (athlete_id,)
    ).fetchone()
    assert fila[0] is None



@pytest.mark.parametrize(
    "columna, tabla, valido",
    [
        ("role", "users", UserRole.ATHLETE.value),
        ("status", "calibration_profiles", CalibrationStatus.PENDING.value),
        ("view_mode", "sessions", ViewMode.LATERAL.value),
        ("thresholds_applied", "sessions", ThresholdsApplied.GENERIC.value),
        ("error_type", "session_errors", TechnicalError.BACK_ARCH.value),
    ],
)
def test_cada_columna_restringida_declara_su_check(db, columna, tabla, valido):
    ddl = db.connection.execute(
        "SELECT sql FROM sqlite_master WHERE name = ?", (tabla,)
    ).fetchone()[0]

    assert f"CHECK ({columna} IN (" in ddl
    assert f"'{valido}'" in ddl


def test_un_rol_no_reconocido_se_rechaza(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.connection.execute(
            "INSERT INTO users (username, password_hash, role, full_name, created_at) "
            "VALUES ('x', 'h', 'superusuario', 'N', ?)",
            (utc_now(),),
        )


def test_un_tipo_de_error_no_reconocido_se_rechaza(db):
    user_id = _usuario(db)
    cursor = db.connection.execute(
        "INSERT INTO sessions (user_id, timestamp, total_duration_s, "
        "total_hold_time_s, hold_attempts, view_mode, thresholds_applied) "
        "VALUES (?, ?, 1.0, 1.0, 1, 'lateral', 'generic')",
        (user_id, utc_now()),
    )

    with pytest.raises(sqlite3.IntegrityError):
        db.connection.execute(
            "INSERT INTO session_errors (session_id, error_type, measured_value, "
            "threshold_value, offset_s) VALUES (?, 'rodilla_torcida', 1.0, 1.0, 1.0)",
            (int(cursor.lastrowid),),
        )


def test_el_vocabulario_de_cada_check_sale_del_enumerado(db):
    # Es lo que impide que la columna y el código se desincronicen.
    ddl = db.connection.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'session_errors'"
    ).fetchone()[0]

    for error in TechnicalError:
        assert f"'{error.value}'" in ddl



def test_una_transaccion_fallida_no_deja_rastro(db):
    with pytest.raises(DatabaseError):
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO users (username, password_hash, role, full_name, "
                "created_at) VALUES ('uno', 'h', 'athlete', 'N', ?)",
                (utc_now(),),
            )
            connection.execute("INSERT INTO users (username) VALUES ('roto')")

    assert db.connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_una_transaccion_correcta_persiste(db):
    with db.transaction() as connection:
        connection.execute(
            "INSERT INTO users (username, password_hash, role, full_name, created_at) "
            "VALUES ('uno', 'h', 'athlete', 'N', ?)",
            (utc_now(),),
        )

    assert db.connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1



def test_no_se_puede_consultar_sin_abrir():
    with pytest.raises(DatabaseError, match="no está abierta"):
        Database(IN_MEMORY).connection


def test_cerrar_es_idempotente(db):
    db.close()
    db.close()

    assert not db.is_open


def test_una_ruta_inaccesible_se_notifica(tmp_path):
    bloqueo = tmp_path / "archivo"
    bloqueo.write_text("no soy un directorio", encoding="utf-8")

    with pytest.raises(DatabaseError):
        Database(bloqueo / "handstand.db").open()



def test_la_marca_de_tiempo_ordena_cronologicamente_como_texto():
    # De ello depende que idx_sessions_user_timestamp sirva para el ORDER BY del panel de progreso.
    from datetime import datetime, timedelta, timezone

    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    marcas = [
        (base + timedelta(days=i)).isoformat(timespec="seconds") for i in range(5)
    ]

    assert marcas == sorted(marcas)


def test_la_marca_de_tiempo_lleva_zona():
    assert utc_now().endswith("+00:00")