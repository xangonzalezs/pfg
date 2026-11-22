import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Capas del sistema, con el paquete que las materializa.
ANALYSIS = "core.analysis"
CAPTURE = "core.vision"
FEEDBACK = "core.feedback"
PERSISTENCE = "core.persistence"
SERVICES = "core.services"
UI = "ui"


def _modules(package: str) -> list[Path]:
    # Archivos de un paquete, excluido su __init__.

    directory = PROJECT_ROOT / Path(*package.split("."))
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.rglob("*.py") if p.name != "__init__.py")


def _imports(path: Path) -> set[str]:
    # Módulos que importa un archivo.

    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            found.add(node.module)

    return found


def _violations(package: str, forbidden: str) -> list[str]:
    # Archivos del paquete que importan algo del paquete prohibido.

    return [
        f"{path.relative_to(PROJECT_ROOT)} importa {imported}"
        for path in _modules(package)
        for imported in sorted(_imports(path))
        if imported == forbidden or imported.startswith(f"{forbidden}.")
    ]



def test_el_analisis_no_depende_de_la_captura():
    # Es lo que permite alimentarlo desde la cámara o desde un archivo sin que cambie
    # permite probarlo sin MediaPipe.
    assert _violations(ANALYSIS, CAPTURE) == []


def test_el_analisis_no_depende_de_la_interfaz():
    assert _violations(ANALYSIS, UI) == []


def test_el_analisis_no_depende_del_feedback():
    # La dirección es la contraria. el feedback consume el resultado del análisis, no al revés.
    assert _violations(ANALYSIS, FEEDBACK) == []


def test_el_analisis_no_depende_de_la_persistencia():
    assert _violations(ANALYSIS, PERSISTENCE) == []


@pytest.mark.parametrize(
    "package",
    [ANALYSIS, CAPTURE, FEEDBACK, PERSISTENCE, SERVICES, "core.config", "core.models"],
)
def test_ningun_paquete_del_nucleo_depende_de_la_interfaz(package):
    # Lo que hace que el núcleo sea ejecutable sin ventana alguna.
    assert _violations(package, UI) == []


def test_la_captura_no_depende_del_analisis():
    # La captura entrega fotogramas y puntos, y no sabe qué se hace con ellos.
    assert _violations(CAPTURE, ANALYSIS) == []


def test_la_persistencia_no_depende_de_la_captura_ni_del_feedback():
    assert _violations(PERSISTENCE, CAPTURE) == []
    assert _violations(PERSISTENCE, FEEDBACK) == []


@pytest.mark.parametrize("package", [ANALYSIS, CAPTURE, FEEDBACK, PERSISTENCE])
def test_ninguna_capa_inferior_depende_de_los_servicios(package):
    # La dependencia va en un solo sentido.
    # los servicios coordinan las capas, y ninguna de ellas sabe que existen.
    assert _violations(package, SERVICES) == []


def test_la_comprobacion_detecta_una_dependencia_prohibida():
    assert _violations(FEEDBACK, "core.models") != []


def test_se_examina_algun_modulo_de_cada_capa():
    # Un paquete mal escrito daría cero archivos y cero violaciones.
    for package in (ANALYSIS, CAPTURE, FEEDBACK, PERSISTENCE, SERVICES):
        assert _modules(package), f"No se ha encontrado ningún módulo en {package}"