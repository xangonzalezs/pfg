import pytest

from core.models.analysis_result import TechnicalError
from core.models.calibration_status import ThresholdsApplied
from core.models.user_role import UserRole
from core.models.view_mode import ViewMode
from core.persistence.database import IN_MEMORY, Database, DatabaseError
from core.persistence.password import MIN_ITERATIONS
from core.persistence.session_repository import ErrorOccurrence, SessionRepository
from core.persistence.user_repository import UserRepository

SESION = {
    "total_duration_s": 180.0,
    "total_hold_time_s": 52.5,
    "hold_attempts": 4,
    "view_mode": ViewMode.LATERAL,
    "thresholds_applied": ThresholdsApplied.PERSONALIZED,
    "mean_alignment_score": 78.5,
}

ERRORES = [
    ErrorOccurrence(TechnicalError.BACK_ARCH, 11.2, 8.0, 4.5),
    ErrorOccurrence(TechnicalError.BACK_ARCH, 12.8, 8.0, 31.0),
    ErrorOccurrence(TechnicalError.INSTABILITY, 0.091, 0.063, 44.2),
]


@pytest.fixture
def entorno():
    db = Database(IN_MEMORY)
    db.open()
    users = UserRepository(db, iterations=MIN_ITERATIONS)
    atleta = users.create("atleta", "c", UserRole.ATHLETE, "Atleta")
    yield SessionRepository(db), atleta.user_id, users
    db.close()


def _guardar(sessions, user_id, errores=None, **cambios):
    datos = dict(SESION)
    datos.update(cambios)
    return sessions.save(user_id, errors=errores, **datos)


def test_una_sesion_guardada_se_recupera(entorno):
    sessions, atleta, _ = entorno

    guardada = _guardar(sessions, atleta)

    assert sessions.get(guardada.session_id) == guardada


def test_la_sesion_conserva_sus_metricas(entorno):
    sessions, atleta, _ = entorno

    guardada = _guardar(sessions, atleta)

    assert guardada.total_duration_s == pytest.approx(180.0)
    assert guardada.total_hold_time_s == pytest.approx(52.5)
    assert guardada.hold_attempts == 4
    assert guardada.mean_alignment_score == pytest.approx(78.5)


def test_la_sesion_conserva_su_contexto(entorno):
    # El modo determina qué errores eran evaluables.
    sessions, atleta, _ = entorno

    guardada = _guardar(sessions, atleta)

    assert guardada.view_mode is ViewMode.LATERAL
    assert guardada.thresholds_applied is ThresholdsApplied.PERSONALIZED


def test_una_sesion_sin_puntuacion_se_admite(entorno):
    # Puede no haberse alcanzado ninguna fase de mantenimiento evaluable.
    sessions, atleta, _ = entorno

    assert _guardar(sessions, atleta, mean_alignment_score=None).mean_alignment_score is None


def test_la_marca_de_tiempo_se_asigna_sola(entorno):
    sessions, atleta, _ = entorno

    assert _guardar(sessions, atleta).timestamp


def test_una_sesion_de_un_atleta_inexistente_se_rechaza(entorno):
    sessions, _, _ = entorno

    with pytest.raises(DatabaseError):
        _guardar(sessions, 9999)


def test_se_registra_una_fila_por_ocurrencia(entorno):
    # no un recuento agregado, que no permitiría el detalle técnico.
    sessions, atleta, _ = entorno

    guardada = _guardar(sessions, atleta, ERRORES)

    assert len(guardada.errors) == 3


def test_cada_ocurrencia_conserva_sus_cuatro_datos(entorno):
    sessions, atleta, _ = entorno

    guardada = _guardar(sessions, atleta, ERRORES)
    primera = guardada.errors[0]

    assert primera.error_type is TechnicalError.BACK_ARCH
    assert primera.measured_value == pytest.approx(11.2)
    assert primera.threshold_value == pytest.approx(8.0)
    assert primera.offset_s == pytest.approx(4.5)


def test_las_ocurrencias_se_devuelven_en_orden_cronologico(entorno):
    sessions, atleta, _ = entorno

    guardada = _guardar(sessions, atleta, list(reversed(ERRORES)))

    desplazamientos = [e.offset_s for e in guardada.errors]
    assert desplazamientos == sorted(desplazamientos)


def test_una_sesion_sin_errores_se_admite(entorno):
    sessions, atleta, _ = entorno

    assert _guardar(sessions, atleta, []).errors == []


def test_un_error_y_su_sesion_se_guardan_juntos_o_no_se_guardan(entorno):
    # Van en una transacción. 
    # una sesión sin sus errores daría un resumen incompleto.
    sessions, atleta, _ = entorno
    invalido = [ErrorOccurrence(TechnicalError.BACK_ARCH, 1.0, 1.0, None)]

    with pytest.raises(DatabaseError):
        _guardar(sessions, atleta, invalido)

    assert sessions.count_for(atleta) == 0



def test_las_sesiones_recientes_van_de_la_ultima_a_la_primera(entorno):
    sessions, atleta, _ = entorno
    antigua = _guardar(sessions, atleta, timestamp="2026-01-01T10:00:00+00:00")
    reciente = _guardar(sessions, atleta, timestamp="2026-03-01T10:00:00+00:00")
    media = _guardar(sessions, atleta, timestamp="2026-02-01T10:00:00+00:00")

    recientes = sessions.recent_for(atleta)

    assert [s.session_id for s in recientes] == [
        reciente.session_id,
        media.session_id,
        antigua.session_id,
    ]


def test_el_limite_acota_las_sesiones_devueltas(entorno):
    sessions, atleta, _ = entorno
    for i in range(5):
        _guardar(sessions, atleta, timestamp=f"2026-01-0{i + 1}T10:00:00+00:00")

    assert len(sessions.recent_for(atleta, limit=2)) == 2


def test_un_limite_invalido_se_rechaza(entorno):
    sessions, atleta, _ = entorno

    with pytest.raises(DatabaseError, match="al menos 1"):
        sessions.recent_for(atleta, limit=0)


def test_solo_se_devuelven_las_sesiones_del_atleta_consultado(entorno):
    sessions, atleta, users = entorno
    otro = users.create("otro", "c", UserRole.ATHLETE, "Otro")
    _guardar(sessions, atleta)
    _guardar(sessions, otro.user_id)

    assert len(sessions.recent_for(atleta)) == 1


def test_se_agregan_las_ocurrencias_de_un_atleta_entre_sesiones(entorno):
    # patrón de error a lo largo del tiempo, no de una sesión.
    sessions, atleta, _ = entorno
    _guardar(sessions, atleta, ERRORES)
    _guardar(sessions, atleta, [ERRORES[0]])

    recuento = sessions.error_counts_for(atleta)

    assert recuento[TechnicalError.BACK_ARCH] == 3
    assert recuento[TechnicalError.INSTABILITY] == 1


def test_el_recuento_no_mezcla_atletas(entorno):
    sessions, atleta, users = entorno
    otro = users.create("otro", "c", UserRole.ATHLETE, "Otro")
    _guardar(sessions, otro.user_id, ERRORES)

    assert sessions.error_counts_for(atleta) == {}


def test_sin_sesiones_el_recuento_esta_vacio(entorno):
    sessions, atleta, _ = entorno

    assert sessions.error_counts_for(atleta) == {}


def test_una_sesion_inexistente_no_se_recupera(entorno):
    sessions, _, _ = entorno

    assert sessions.get(9999) is None



def test_borrar_una_sesion_arrastra_sus_errores(entorno):
    sessions, atleta, _ = entorno
    guardada = _guardar(sessions, atleta, ERRORES)

    sessions.delete(guardada.session_id)

    assert sessions.errors_of(guardada.session_id) == []


def test_borrar_el_atleta_arrastra_sus_sesiones_y_sus_errores(entorno):
    sessions, atleta, users = entorno
    guardada = _guardar(sessions, atleta, ERRORES)

    users.delete(atleta)

    assert sessions.get(guardada.session_id) is None
    assert sessions.errors_of(guardada.session_id) == []