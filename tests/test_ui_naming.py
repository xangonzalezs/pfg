import ast
from pathlib import Path

import pytest

UI_ROOT = Path(__file__).resolve().parents[1] / "ui"

# Nombres que tkinter.Misc y sus descendientes ya definen. 
RESERVED = frozenset(
    {
        # Internos de Misc
        "_bind", "_configure", "_displayof", "_do", "_getboolean",
        "_getconfigure", "_getdoubles", "_getints", "_grid_configure",
        "_nametowidget", "_options", "_register", "_report_exception",
        "_root", "_substitute", "_w",
        # Públicos de Misc y de los gestores de geometría
        "after", "after_cancel", "after_idle", "bbox", "bell", "bind",
        "bind_all", "bind_class", "bindtags", "cget", "columnconfigure",
        "config", "configure", "deletecommand", "destroy", "event_add",
        "event_delete", "event_generate", "focus", "focus_force",
        "focus_get", "focus_set", "forget", "grid", "grid_configure",
        "grid_forget", "grid_info", "grid_propagate", "grid_remove",
        "grid_slaves", "info", "keys", "lift", "lower", "mainloop",
        "nametowidget", "pack", "pack_configure", "pack_forget",
        "pack_info", "pack_propagate", "pack_slaves", "place",
        "place_configure", "place_forget", "place_info", "propagate",
        "quit", "register", "rowconfigure", "selection_clear",
        "selection_get", "send", "setvar", "size", "slaves", "tkraise",
        "unbind", "unbind_all", "update", "update_idletasks",
        "wait_variable", "wait_visibility", "wait_window", "winfo_children",
        "winfo_exists", "winfo_height", "winfo_width", "winfo_x", "winfo_y",
    }
)


def _clases_de_widget(path: Path):
    # Clases del archivo que descienden de un widget, por su base declarada.

    arbol = ast.parse(path.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.ClassDef):
            continue
        bases = [ast.unparse(b) for b in nodo.bases]
        if any("ctk." in b or "CTk" in b or "View" in b for b in bases):
            yield nodo


def _miembros(clase: ast.ClassDef):
    # Métodos y atributos de instancia que la clase declara.

    for nodo in clase.body:
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield nodo.name, nodo.lineno

    for nodo in ast.walk(clase):
        if not isinstance(nodo, ast.Assign):
            continue
        for destino in nodo.targets:
            if (
                isinstance(destino, ast.Attribute)
                and isinstance(destino.value, ast.Name)
                and destino.value.id == "self"
            ):
                yield destino.attr, destino.lineno


def _archivos():
    return sorted(UI_ROOT.rglob("*.py"))



@pytest.mark.parametrize("path", _archivos(), ids=lambda p: p.name)
def test_ninguna_pantalla_tapa_un_nombre_de_tkinter(path):
    colisiones = [
        f"{clase.name}.{nombre} (línea {linea})"
        for clase in _clases_de_widget(path)
        for nombre, linea in _miembros(clase)
        if nombre in RESERVED
    ]

    assert colisiones == [], (
        f"{path.name} tapa nombres de tkinter: {', '.join(colisiones)}"
    )


def test_se_examina_alguna_clase_de_widget():
    # Si el reconocimiento de las bases fallara, la prueba anterior pasaría sin haber mirado nada.
    total = sum(len(list(_clases_de_widget(p))) for p in _archivos())

    assert total >= 5


def test_la_comprobacion_detecta_una_colision(tmp_path):
    # Sin esto, los asertos pasarían también si _miembros no devolviera nada.
    sospechoso = tmp_path / "falsa.py"
    sospechoso.write_text(
        "class FalsaView(BaseView):\n"
        "    def _register(self):\n"
        "        pass\n",
        encoding="utf-8",
    )

    clase = next(_clases_de_widget(sospechoso))
    nombres = {nombre for nombre, _ in _miembros(clase)}

    assert "_register" in nombres & RESERVED