"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de carga de los umbrales genéricos del sistema desde configuración externa.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Ubicación del archivo de umbrales dentro del proyecto.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_THRESHOLDS_PATH = _PROJECT_ROOT / "assets" / "config" / "umbrales.json"


class ThresholdConfigError(Exception):
    # Error en el archivo de umbrales: falta, ilegible o inconsistente.

    pass


@dataclass(frozen=True)
class StabilityThresholds:
    # Umbrales del análisis de estabilidad.

    window_size: int
    instability_threshold: float
    noise: float


@dataclass(frozen=True)
class ParameterThreshold:
    # Umbral de un parámetro postural concreto, con su zona muerta.

    threshold: float
    noise: float


@dataclass(frozen=True)
class AlignmentThresholds:
    # Umbrales y pesos de la alineación de las líneas corporales.

    segment_weights: dict[str, float]
    noise_threshold_deg: float
    max_segment_deviation_deg: float
    score_exponent: float
    min_trunk_length: float
    min_pair_width: float
    parameters: dict[str, ParameterThreshold]


@dataclass(frozen=True)
class HandstandThresholds:
    # Umbrales de la detección de la posición invertida.
    # Las dos ventanas van en fotogramas, para que no dependan de la cadencia de la fuente.

    order_margin: float
    min_body_length: float
    max_tilt_deg: float
    confirmation_frames: int
    grace_frames: int


@dataclass(frozen=True)
class CalibrationThresholds:
    # Criterios de aceptación de una captura de calibración.

    min_visibility: float
    min_frames: int
    min_validity_rate: float


@dataclass(frozen=True)
class PersonalizationLimits:
    # Límites que acotan la personalización de un parámetro.

    min_plausible_deg: float
    max_plausible_deg: float
    max_threshold_deg: float

    def is_plausible(self, angle_deg: float) -> bool:
        # Indica si el ángulo neutro medido es fisiológicamente verosímil.

        return self.min_plausible_deg <= angle_deg <= self.max_plausible_deg


@dataclass(frozen=True)
class ErrorSelectionThresholds:
    # Umbrales que determinan las desviaciones que se comunican al atleta.

    min_severity_to_report: float
    hysteresis_factor: float


@dataclass(frozen=True)
class FeedbackThresholds:
    # Umbrales del motor de feedback. 
    # Las ventanas van en fotogramas, las esperas en milisegundos.

    confirmation_frames: int
    grace_frames: int
    repeat_cooldown_ms: int
    not_analyzing_cooldown_ms: int
    positive_score_threshold: float


@dataclass(frozen=True)
class GenericThresholds:
    # Conjunto completo de umbrales genéricos del sistema.

    stability: StabilityThresholds
    alignment: AlignmentThresholds
    handstand: HandstandThresholds
    calibration: CalibrationThresholds
    error_selection: ErrorSelectionThresholds
    feedback: FeedbackThresholds
    personalization: dict[str, PersonalizationLimits]


def load_thresholds(path: Path | str | None = None) -> GenericThresholds:
    # Lee y valida el archivo de umbrales.

    file_path = Path(path) if path is not None else DEFAULT_THRESHOLDS_PATH

    try:
        raw_text = file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ThresholdConfigError(
            f"No se encuentra el archivo de umbrales: {file_path}"
        ) from None
    except OSError as error:
        raise ThresholdConfigError(
            f"No se puede leer el archivo de umbrales {file_path}: {error}"
        ) from error

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as error:
        raise ThresholdConfigError(
            f"El archivo de umbrales {file_path} no contiene JSON válido: {error}"
        ) from error

    if not isinstance(data, dict):
        raise ThresholdConfigError(
            f"El archivo de umbrales {file_path} debe contener un objeto en su raíz."
        )

    _reject_unknown_keys(
        data,
        {
            "stability",
            "alignment",
            "handstand",
            "calibration",
            "error_selection",
            "feedback",
            "personalization",
        },
        file_path,
        context="raíz",
    )

    # Las secciones se validan en el orden en que aparecen en el archivo.
    stability = _read_stability(_read_section(data, "stability", file_path), file_path)
    alignment = _read_alignment(_read_section(data, "alignment", file_path), file_path)
    handstand = _read_handstand(_read_section(data, "handstand", file_path), file_path)
    calibration = _read_calibration(
        _read_section(data, "calibration", file_path), file_path
    )
    error_selection = _read_error_selection(
        _read_section(data, "error_selection", file_path), file_path
    )
    feedback = _read_feedback(_read_section(data, "feedback", file_path), file_path)
    personalization = _read_personalization(
        _read_section(data, "personalization", file_path), file_path
    )

    _check_personalization_consistency(alignment, personalization, file_path)

    return GenericThresholds(
        stability=stability,
        alignment=alignment,
        handstand=handstand,
        calibration=calibration,
        error_selection=error_selection,
        feedback=feedback,
        personalization=personalization,
    )


def _read_feedback(section: dict[str, Any], file_path: Path) -> FeedbackThresholds:
    # Valida y construye los umbrales del motor de feedback.

    _reject_unknown_keys(
        section,
        {
            "confirmation_frames",
            "grace_frames",
            "repeat_cooldown_ms",
            "not_analyzing_cooldown_ms",
            "positive_score_threshold",
        },
        file_path,
        context="feedback",
    )

    confirmation = _read_int(
        section, "confirmation_frames", file_path, context="feedback"
    )
    grace = _read_int(section, "grace_frames", file_path, context="feedback")
    cooldown = _read_int(section, "repeat_cooldown_ms", file_path, context="feedback")
    not_analyzing = _read_int(
        section, "not_analyzing_cooldown_ms", file_path, context="feedback"
    )
    positive = _read_float(
        section, "positive_score_threshold", file_path, context="feedback"
    )

    if confirmation < 1:
        raise ThresholdConfigError(
            f"'feedback.confirmation_frames' debe ser al menos 1 en {file_path}; "
            f"se ha leído {confirmation}."
        )
    if grace < 0:
        raise ThresholdConfigError(
            f"'feedback.grace_frames' no puede ser negativo en {file_path}; "
            f"se ha leído {grace}."
        )
    if cooldown <= 0:
        raise ThresholdConfigError(
            f"'feedback.repeat_cooldown_ms' debe ser positivo en {file_path}; "
            f"se ha leído {cooldown}. Un valor nulo repetiría la corrección en "
            f"cada fotograma."
        )
    if not_analyzing <= 0:
        raise ThresholdConfigError(
            f"'feedback.not_analyzing_cooldown_ms' debe ser positivo en {file_path}; "
            f"se ha leído {not_analyzing}."
        )
    if not 0.0 < positive <= 100.0:
        raise ThresholdConfigError(
            f"'feedback.positive_score_threshold' debe estar entre 0 y 100 en "
            f"{file_path}; se ha leído {positive}."
        )

    return FeedbackThresholds(
        confirmation_frames=confirmation,
        grace_frames=grace,
        repeat_cooldown_ms=cooldown,
        not_analyzing_cooldown_ms=not_analyzing,
        positive_score_threshold=positive,
    )


def _read_handstand(section: dict[str, Any], file_path: Path) -> HandstandThresholds:
    # Valida y construye los umbrales de la detección de pino.

    _reject_unknown_keys(
        section,
        {
            "order_margin",
            "min_body_length",
            "max_tilt_deg",
            "confirmation_frames",
            "grace_frames",
        },
        file_path,
        context="handstand",
    )

    margin = _read_float(section, "order_margin", file_path, context="handstand")
    body_length = _read_float(section, "min_body_length", file_path, context="handstand")
    tilt = _read_float(section, "max_tilt_deg", file_path, context="handstand")
    confirmation = _read_int(
        section, "confirmation_frames", file_path, context="handstand"
    )
    grace = _read_int(section, "grace_frames", file_path, context="handstand")

    if margin <= 0.0:
        raise ThresholdConfigError(
            f"'handstand.order_margin' debe ser positivo en {file_path}; "
            f"se ha leído {margin}."
        )
    if body_length <= 0.0:
        raise ThresholdConfigError(
            f"'handstand.min_body_length' debe ser positivo en {file_path}; "
            f"se ha leído {body_length}."
        )
    if not 0.0 < tilt < 90.0:
        raise ThresholdConfigError(
            f"'handstand.max_tilt_deg' debe estar entre 0 y 90 en {file_path}; "
            f"se ha leído {tilt}."
        )
    if confirmation < 1:
        raise ThresholdConfigError(
            f"'handstand.confirmation_frames' debe ser al menos 1 en {file_path}; "
            f"se ha leído {confirmation}."
        )
    if grace < 0:
        raise ThresholdConfigError(
            f"'handstand.grace_frames' no puede ser negativo en {file_path}; "
            f"se ha leído {grace}."
        )

    return HandstandThresholds(
        order_margin=margin,
        min_body_length=body_length,
        max_tilt_deg=tilt,
        confirmation_frames=confirmation,
        grace_frames=grace,
    )


def _read_calibration(
    section: dict[str, Any], file_path: Path
) -> CalibrationThresholds:
    # Valida y construye los criterios de aceptación de una captura.

    _reject_unknown_keys(
        section,
        {"min_visibility", "min_frames", "min_validity_rate"},
        file_path,
        context="calibration",
    )

    visibility = _read_float(section, "min_visibility", file_path, context="calibration")
    frames = _read_int(section, "min_frames", file_path, context="calibration")
    rate = _read_float(section, "min_validity_rate", file_path, context="calibration")

    if not 0.0 < visibility <= 1.0:
        raise ThresholdConfigError(
            f"'calibration.min_visibility' debe estar entre 0 y 1 en {file_path}; "
            f"se ha leído {visibility}."
        )
    if frames < 1:
        raise ThresholdConfigError(
            f"'calibration.min_frames' debe ser al menos 1 en {file_path}; "
            f"se ha leído {frames}."
        )
    if not 0.0 < rate <= 1.0:
        raise ThresholdConfigError(
            f"'calibration.min_validity_rate' debe estar entre 0 y 1 en {file_path}; "
            f"se ha leído {rate}."
        )

    return CalibrationThresholds(
        min_visibility=visibility,
        min_frames=frames,
        min_validity_rate=rate,
    )


def _read_personalization(
    section: dict[str, Any], file_path: Path
) -> dict[str, PersonalizationLimits]:
    # Valida y construye los límites de personalización de cada parámetro.

    _reject_unknown_keys(
        section, set(PERSONALIZABLE_PARAMETERS), file_path, context="personalization"
    )

    limits: dict[str, PersonalizationLimits] = {}

    for name in PERSONALIZABLE_PARAMETERS:
        entry = _read_present(section, name, file_path, context="personalization")
        context = f"personalization.{name}"
        if not isinstance(entry, dict):
            raise ThresholdConfigError(
                f"'{context}' debe ser un objeto en {file_path}."
            )
        _reject_unknown_keys(
            entry,
            {"min_plausible_deg", "max_plausible_deg", "max_threshold_deg"},
            file_path,
            context=context,
        )

        minimum = _read_float(entry, "min_plausible_deg", file_path, context=context)
        maximum = _read_float(entry, "max_plausible_deg", file_path, context=context)
        cap = _read_float(entry, "max_threshold_deg", file_path, context=context)

        if minimum >= maximum:
            raise ThresholdConfigError(
                f"'{context}.min_plausible_deg' ({minimum}) debe ser menor que "
                f"'max_plausible_deg' ({maximum}) en {file_path}."
            )
        if maximum > STRAIGHT_ANGLE_DEG + 15.0:
            raise ThresholdConfigError(
                f"'{context}.max_plausible_deg' ({maximum}) excede la "
                f"hiperextensión admitida en {file_path}."
            )
        if cap <= 0.0:
            raise ThresholdConfigError(
                f"'{context}.max_threshold_deg' debe ser positivo en {file_path}; "
                f"se ha leído {cap}."
            )

        limits[name] = PersonalizationLimits(
            min_plausible_deg=minimum,
            max_plausible_deg=maximum,
            max_threshold_deg=cap,
        )

    return limits


def _check_personalization_consistency(
    alignment: AlignmentThresholds,
    personalization: dict[str, PersonalizationLimits],
    file_path: Path,
) -> None:
    # Un techo por debajo del umbral genérico haría que la personalización resultase más estricta que no personalizar.
    for name, limits in personalization.items():
        generic = alignment.parameters[name].threshold
        if limits.max_threshold_deg < generic:
            raise ThresholdConfigError(
                f"'personalization.{name}.max_threshold_deg' "
                f"({limits.max_threshold_deg}) no puede ser menor que el umbral "
                f"genérico del parámetro ({generic}) en {file_path}."
            )


def _read_error_selection(
    section: dict[str, Any], file_path: Path
) -> ErrorSelectionThresholds:
    # Valida y construye los umbrales de selección de errores.

    _reject_unknown_keys(
        section,
        {"min_severity_to_report", "hysteresis_factor"},
        file_path,
        context="error_selection",
    )

    minimum = _read_float(
        section, "min_severity_to_report", file_path, context="error_selection"
    )
    hysteresis = _read_float(
        section, "hysteresis_factor", file_path, context="error_selection"
    )
    if not 0.0 < minimum <= 100.0:
        raise ThresholdConfigError(
            f"'error_selection.min_severity_to_report' debe estar entre 0 y 100 en "
            f"{file_path}; se ha leído {minimum}."
        )
    if not 0.0 < hysteresis <= 1.0:
        raise ThresholdConfigError(
            f"'error_selection.hysteresis_factor' debe ser mayor que 0 y no mayor que 1 "
            f"en {file_path}; se ha leído {hysteresis}. Un valor de 1 eliminaría la "
            f"histéresis y un valor mayor invertiría su sentido."
        )
    return ErrorSelectionThresholds(
        min_severity_to_report=minimum,
        hysteresis_factor=hysteresis,
    )


def _read_section(data: dict[str, Any], name: str, file_path: Path) -> dict[str, Any]:
    # Devuelve una sección del archivo, comprobando que existe y es un objeto.

    if name not in data:
        raise ThresholdConfigError(
            f"Falta la sección '{name}' en el archivo de umbrales {file_path}."
        )

    section = data[name]
    if not isinstance(section, dict):
        raise ThresholdConfigError(
            f"La sección '{name}' del archivo de umbrales {file_path} debe ser un objeto."
        )

    return section


def _read_stability(section: dict[str, Any], file_path: Path) -> StabilityThresholds:
    # Valida y construye los umbrales de estabilidad.

    _reject_unknown_keys(
        section,
        {"window_size", "instability_threshold", "noise"},
        file_path,
        context="stability",
    )

    window_size = _read_int(section, "window_size", file_path, context="stability")
    instability_threshold = _read_float(
        section, "instability_threshold", file_path, context="stability"
    )
    noise = _read_float(section, "noise", file_path, context="stability")

    if window_size < 2:
        raise ThresholdConfigError(
            f"'stability.window_size' debe ser al menos 2 en {file_path}; se ha leído {window_size}."
        )
    if instability_threshold <= 0.0:
        raise ThresholdConfigError(
            f"'stability.instability_threshold' debe ser positivo en {file_path}; "
            f"se ha leído {instability_threshold}."
        )

    if noise < 0.0:
        raise ThresholdConfigError(
            f"'stability.noise' no puede ser negativo en {file_path}; "
            f"se ha leído {noise}."
        )
    if noise >= instability_threshold:
        raise ThresholdConfigError(
            f"'stability.noise' ({noise}) debe ser menor que "
            f"'stability.instability_threshold' ({instability_threshold}) en "
            f"{file_path}; de otro modo no existiría un intervalo en el que "
            f"graduar la severidad."
        )

    return StabilityThresholds(
        window_size=window_size,
        instability_threshold=instability_threshold,
        noise=noise,
    )


# Nombres de las cuatro líneas corporales, en orden descendente desde las manos. 
# claves que debe declarar 'alignment.segment_weights'.
SEGMENT_NAMES: tuple[str, ...] = (
    "wrists_shoulders",
    "shoulders_hips",
    "hips_knees",
    "knees_ankles",
)

# Nombres de los parámetros posturales. 
# claves que debe declarar 'alignment.parameters'. 
PARAMETER_NAMES: tuple[str, ...] = (
    "back_arch",
    "pelvis_shift",
    "head_forward",
    "knee_bend",
    "leg_tilt",
    "shoulder_tilt",
    "hip_tilt",
    "shrug",
    "elbow_bend",
    "foot_extension",
)

# Parámetros cuyo umbral puede derivarse de la calibración del atleta.
PERSONALIZABLE_PARAMETERS: tuple[str, ...] = ("knee_bend", "back_arch", "elbow_bend")

# Ángulo de la articulación completamente extendida, en grados.
STRAIGHT_ANGLE_DEG: float = 180.0

# Tolerancia admitida al comprobar que los pesos suman la unidad.
_WEIGHT_SUM_TOLERANCE = 1e-6


def _read_alignment(section: dict[str, Any], file_path: Path) -> AlignmentThresholds:
    # Valida y construye los umbrales de alineación.

    _reject_unknown_keys(
        section,
        {
            "segment_weights",
            "noise_threshold_deg",
            "max_segment_deviation_deg",
            "score_exponent",
            "min_trunk_length",
            "min_pair_width",
            "parameters",
        },
        file_path,
        context="alignment",
    )

    weights = _read_segment_weights(section, file_path)

    noise = _read_float(section, "noise_threshold_deg", file_path, context="alignment")
    maximum = _read_float(
        section, "max_segment_deviation_deg", file_path, context="alignment"
    )
    exponent = _read_float(section, "score_exponent", file_path, context="alignment")
    trunk = _read_float(section, "min_trunk_length", file_path, context="alignment")
    pair_width = _read_float(section, "min_pair_width", file_path, context="alignment")

    if noise < 0.0:
        raise ThresholdConfigError(
            f"'alignment.noise_threshold_deg' no puede ser negativo en {file_path}; "
            f"se ha leído {noise}."
        )
    if maximum <= noise:
        raise ThresholdConfigError(
            f"'alignment.max_segment_deviation_deg' ({maximum}) debe ser mayor que "
            f"'alignment.noise_threshold_deg' ({noise}) en {file_path}; de otro modo no "
            f"existiría un intervalo en el que graduar la penalización."
        )
    if exponent <= 0.0:
        raise ThresholdConfigError(
            f"'alignment.score_exponent' debe ser positivo en {file_path}; "
            f"se ha leído {exponent}."
        )
    if trunk <= 0.0:
        raise ThresholdConfigError(
            f"'alignment.min_trunk_length' debe ser positivo en {file_path}; "
            f"se ha leído {trunk}."
        )
    if pair_width <= 0.0:
        raise ThresholdConfigError(
            f"'alignment.min_pair_width' debe ser positivo en {file_path}; "
            f"se ha leído {pair_width}."
        )

    return AlignmentThresholds(
        parameters=_read_parameters(section, file_path),
        segment_weights=weights,
        noise_threshold_deg=noise,
        max_segment_deviation_deg=maximum,
        score_exponent=exponent,
        min_trunk_length=trunk,
        min_pair_width=pair_width,
    )


def _read_parameters(
    section: dict[str, Any], file_path: Path
) -> dict[str, ParameterThreshold]:
    # Valida los umbrales de cada parámetro postural.

    parameters = section.get("parameters")
    if parameters is None:
        raise ThresholdConfigError(
            f"Falta la clave 'alignment.parameters' en el archivo de umbrales {file_path}."
        )
    if not isinstance(parameters, dict):
        raise ThresholdConfigError(
            f"'alignment.parameters' debe ser un objeto en {file_path}."
        )

    _reject_unknown_keys(
        parameters, set(PARAMETER_NAMES), file_path, context="alignment.parameters"
    )

    result: dict[str, ParameterThreshold] = {}
    for name in PARAMETER_NAMES:
        if name not in parameters:
            raise ThresholdConfigError(
                f"Falta el parámetro 'alignment.parameters.{name}' en el archivo de "
                f"umbrales {file_path}."
            )

        entry = parameters[name]
        context = f"alignment.parameters.{name}"
        if not isinstance(entry, dict):
            raise ThresholdConfigError(
                f"'{context}' debe ser un objeto con las claves 'threshold' y 'noise' "
                f"en {file_path}."
            )

        _reject_unknown_keys(entry, {"threshold", "noise"}, file_path, context=context)

        threshold = _read_float(entry, "threshold", file_path, context=context)
        noise = _read_float(entry, "noise", file_path, context=context)

        if noise < 0.0:
            raise ThresholdConfigError(
                f"'{context}.noise' no puede ser negativo en {file_path}; "
                f"se ha leído {noise}."
            )
        if threshold <= noise:
            raise ThresholdConfigError(
                f"'{context}.threshold' ({threshold}) debe ser mayor que "
                f"'{context}.noise' ({noise}) en {file_path}; de otro modo no "
                f"existiría un intervalo en el que graduar la severidad."
            )

        result[name] = ParameterThreshold(threshold=threshold, noise=noise)

    return result


def _read_segment_weights(section: dict[str, Any], file_path: Path) -> dict[str, float]:
    # Valida los pesos de las cuatro líneas corporales.

    weights = section.get("segment_weights")
    if weights is None:
        raise ThresholdConfigError(
            f"Falta la clave 'alignment.segment_weights' en el archivo de umbrales {file_path}."
        )
    if not isinstance(weights, dict):
        raise ThresholdConfigError(
            f"'alignment.segment_weights' debe ser un objeto en {file_path}."
        )

    _reject_unknown_keys(
        weights, set(SEGMENT_NAMES), file_path, context="alignment.segment_weights"
    )

    result: dict[str, float] = {}
    for name in SEGMENT_NAMES:
        weight = _read_float(
            weights, name, file_path, context="alignment.segment_weights"
        )
        if weight <= 0.0:
            raise ThresholdConfigError(
                f"'alignment.segment_weights.{name}' debe ser positivo en {file_path}; "
                f"se ha leído {weight}."
            )
        result[name] = weight

    total = sum(result.values())
    if abs(total - 1.0) > _WEIGHT_SUM_TOLERANCE:
        raise ThresholdConfigError(
            f"Los pesos de 'alignment.segment_weights' deben sumar 1.0 en {file_path}; "
            f"suman {total}."
        )

    return result


def _read_int(section: dict[str, Any], key: str, file_path: Path, *, context: str) -> int:
    # Lee un entero, rechazando los booleanos, que en Python son enteros.

    value = _read_present(section, key, file_path, context=context)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ThresholdConfigError(
            f"'{context}.{key}' debe ser un número entero en {file_path}; "
            f"se ha leído {value!r}."
        )
    return value


def _read_float(section: dict[str, Any], key: str, file_path: Path, *, context: str) -> float:
    # Lee un número real. Se acepta un entero, que JSON no distingue del real.

    value = _read_present(section, key, file_path, context=context)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ThresholdConfigError(
            f"'{context}.{key}' debe ser un número en {file_path}; se ha leído {value!r}."
        )
    return float(value)


def _read_present(section: dict[str, Any], key: str, file_path: Path, *, context: str) -> Any:
    # Comprueba que la clave está presente antes de validar su tipo.

    if key not in section:
        raise ThresholdConfigError(
            f"Falta la clave '{context}.{key}' en el archivo de umbrales {file_path}."
        )
    return section[key]


def _reject_unknown_keys(section: dict[str, Any], expected: set[str], file_path: Path, *, context: str) -> None:
    # Rechaza las claves no reconocidas.

    unknown = sorted(set(section) - expected)
    if unknown:
        raise ThresholdConfigError(
            f"Claves no reconocidas en '{context}' del archivo de umbrales {file_path}: "
            f"{', '.join(unknown)}."
        )