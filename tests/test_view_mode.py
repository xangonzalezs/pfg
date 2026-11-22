from core.models.view_mode import ViewMode


def test_las_cadenas_conocidas_se_convierten_a_su_modo():
    assert ViewMode.from_string("lateral") is ViewMode.LATERAL
    assert ViewMode.from_string("frontal") is ViewMode.FRONTAL


def test_las_mayusculas_y_los_espacios_no_impiden_la_conversion():
    assert ViewMode.from_string("  FRONTAL  ") is ViewMode.FRONTAL


def test_el_modo_posterior_heredado_se_traduce_a_frontal():
    # BR-05: el modo frontal cubre cualquier orientación distinta de la
    # lateral. Una sesión guardada por una versión anterior con el valor
    # "posterior" debe releerse como frontal y no caer en el modo por
    # defecto, que cambiaría los errores evaluables de esa sesión.
    assert ViewMode.from_string("posterior") is ViewMode.FRONTAL


def test_la_ausencia_de_valor_se_resuelve_como_lateral():
    assert ViewMode.from_string(None) is ViewMode.LATERAL


def test_un_valor_desconocido_se_resuelve_como_lateral():
    assert ViewMode.from_string("cualquier_cosa") is ViewMode.LATERAL


def test_una_cadena_vacia_se_resuelve_como_lateral():
    assert ViewMode.from_string("") is ViewMode.LATERAL


def test_ya_no_existe_un_modo_posterior_en_la_enumeracion():
    assert not hasattr(ViewMode, "POSTERIOR")
    assert [modo.value for modo in ViewMode] == ["lateral", "frontal"]
