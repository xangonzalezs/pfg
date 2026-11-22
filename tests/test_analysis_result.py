from core.models.analysis_result import (
    AnalysisResult,
    DetectedError,
    ErrorMeasurement,
    TechnicalError,
)


def test_un_resultado_sin_errores_no_los_declara_activos():
    resultado = AnalysisResult(alignment_score=95.0, in_handstand=True)
    assert not resultado.has_errors


def test_un_resultado_con_errores_los_declara_activos():
    resultado = AnalysisResult(
        alignment_score=60.0,
        active_errors=[
            DetectedError(
                error_type=TechnicalError.BACK_ARCH,
                measured_value=19.4,
                threshold_value=12.0,
            )
        ],
        in_handstand=True,
    )
    assert resultado.has_errors


def test_un_error_detectado_conserva_su_evidencia_numerica():
    error = DetectedError(
        error_type=TechnicalError.LEGS_NOT_STRAIGHT,
        measured_value=162.0,
        threshold_value=170.0,
    )
    assert error.error_type is TechnicalError.LEGS_NOT_STRAIGHT
    assert error.measured_value == 162.0
    assert error.threshold_value == 170.0


def test_los_tipos_de_error_se_devuelven_en_el_mismo_orden():
    resultado = AnalysisResult(
        alignment_score=55.0,
        active_errors=[
            DetectedError(TechnicalError.BACK_ARCH, 19.4, 12.0),
            DetectedError(TechnicalError.HEAD_FORWARD, 14.1, 10.0),
        ],
        in_handstand=True,
    )
    assert resultado.error_types == [
        TechnicalError.BACK_ARCH,
        TechnicalError.HEAD_FORWARD,
    ]


def test_un_resultado_sin_errores_no_tiene_tipos_de_error():
    resultado = AnalysisResult(alignment_score=95.0, in_handstand=True)
    assert resultado.error_types == []


def test_dos_medidas_distintas_del_mismo_error_dan_el_mismo_tipo():
    # Dos fotogramas seguidos miden ángulos ligeramente distintos para el mismo error y deben seguir considerándose el mismo.
    primero = AnalysisResult(
        alignment_score=60.0,
        active_errors=[DetectedError(TechnicalError.BACK_ARCH, 19.4, 12.0)],
        in_handstand=True,
    )
    segundo = AnalysisResult(
        alignment_score=59.0,
        active_errors=[DetectedError(TechnicalError.BACK_ARCH, 19.9, 12.0)],
        in_handstand=True,
    )
    assert primero.active_errors != segundo.active_errors
    assert primero.error_types == segundo.error_types


def test_un_resultado_sin_puntuacion_no_es_valido():
    resultado = AnalysisResult()
    assert not resultado.is_valid


def test_una_puntuacion_de_cero_sigue_siendo_valida():
    # Una puntuación de 0.0 es un valor calculado, no la ausencia de valor.
    resultado = AnalysisResult(alignment_score=0.0)
    assert resultado.is_valid

def test_una_medicion_separa_la_severidad_de_la_evidencia():
    medicion = ErrorMeasurement(
        error_type=TechnicalError.BACK_ARCH,
        measured_value=12.5,
        threshold_value=8.0,
        severity=96.0,
    )

    assert medicion.severity == 96.0
    assert medicion.measured_value == 12.5
    assert medicion.threshold_value == 8.0


def test_una_medicion_se_convierte_en_el_error_detectado_que_se_registra():
    medicion = ErrorMeasurement(
        error_type=TechnicalError.PELVIS_POSITION,
        measured_value=0.09,
        threshold_value=0.07,
        severity=72.0,
    )

    detectado = medicion.to_detected_error()

    assert isinstance(detectado, DetectedError)
    assert detectado.error_type is TechnicalError.PELVIS_POSITION
    assert detectado.measured_value == 0.09
    assert detectado.threshold_value == 0.07
