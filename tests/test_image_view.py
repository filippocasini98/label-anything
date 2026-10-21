"""Test del comportamento cursore di ImageViewer."""

import pytest

pytest.importorskip("PySide6")

import numpy as np

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtWidgets import QApplication

from labeling_tool.image_view import ImageViewer


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_set_cursore_applicato_agli_strumenti_di_disegno(qapp):
    viewer = ImageViewer()
    viewer.set_cursore("freccia")
    viewer.set_strumento("box")
    assert viewer.cursor().shape() == Qt.CursorShape.ArrowCursor
    viewer.set_cursore("invisibile")  # cambio a strumento gia' attivo
    assert viewer.cursor().shape() == Qt.CursorShape.BlankCursor


def test_set_cursore_nav_resta_cursore_di_sistema(qapp):
    viewer = ImageViewer()
    viewer.set_cursore("invisibile")
    viewer.set_strumento("nav")
    assert viewer.cursor().shape() == Qt.CursorShape.ArrowCursor
    viewer.set_strumento("box")
    assert viewer.cursor().shape() == Qt.CursorShape.BlankCursor


def test_set_cursore_nome_non_valido_ricade_sul_default(qapp):
    viewer = ImageViewer()
    viewer.set_cursore("pippo")
    viewer.set_strumento("box")
    assert viewer.cursor().shape() == Qt.CursorShape.CrossCursor


def test_croce_schermo_flag_e_mai_attivo_in_nav(qapp):
    viewer = ImageViewer()
    viewer.set_cursore("croce-schermo")
    assert viewer._croce_schermo is True
    viewer.set_strumento("nav")
    assert viewer._croce_schermo is True  # resta impostato ma il tool nav non lo mostra


def test_croce_schermo_traccia_il_mouse_e_sparendo_alluscita(qapp):
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QMouseEvent

    viewer = ImageViewer()
    viewer.set_cursore("croce-schermo")
    viewer.set_strumento("box")
    assert viewer._pos_mouse is None  # nessuna linea finche' il mouse non entra
    ev = QMouseEvent(QEvent.MouseMove, QPointF(10, 10), QPointF(10, 10),
                     Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
    viewer.mouseMoveEvent(ev)
    assert viewer._pos_mouse is not None
    viewer.leaveEvent(QEvent(QEvent.Type.Leave))
    assert viewer._pos_mouse is None


def _viewer_con_immagine() -> ImageViewer:
    viewer = ImageViewer()
    viewer.set_image(np.zeros((64, 64, 3), dtype=np.uint8), "#E74C3C")
    return viewer


def _click(viewer, x, y):
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtCore import QEvent as QE
    ev_p = QMouseEvent(QE.MouseButtonPress, QPointF(x, y), QPointF(x, y),
                       Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    ev_r = QMouseEvent(QE.MouseButtonRelease, QPointF(x, y), QPointF(x, y),
                       Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
    viewer.mousePressEvent(ev_p)
    viewer.mouseReleaseEvent(ev_r)


def test_invio_chiude_il_poligono(qapp):
    viewer = _viewer_con_immagine()
    viewer.set_strumento("poligono")
    aggiunte = []
    viewer.geometriaAggiunta.connect(aggiunte.append)
    for x, y in ((10, 10), (40, 10), (40, 30)):
        _click(viewer, x, y)
    assert not aggiunte
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtCore import QEvent as QE
    viewer.keyPressEvent(QKeyEvent(QE.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier))
    assert len(aggiunte) == 1
    assert aggiunte[0]["tipo"] == "poligono"
    assert len(aggiunte[0]["punti"]) == 3
    assert viewer._punti_correnti == []


def test_doppio_clic_chiude_il_poligono(qapp):
    viewer = _viewer_con_immagine()
    viewer.set_strumento("poligono")
    aggiunte = []
    viewer.geometriaAggiunta.connect(aggiunte.append)
    for x, y in ((10, 10), (40, 10), (40, 30)):
        _click(viewer, x, y)
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtCore import QEvent as QE
    ev = QMouseEvent(QE.MouseButtonDblClick, QPointF(20, 25), QPointF(20, 25),
                     Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    _click(viewer, 20, 25)  # il primo clic del doppio clic: aggiunge l'ultimo vertice
    viewer.mouseDoubleClickEvent(ev)
    assert len(aggiunte) == 1
    assert len(aggiunte[0]["punti"]) == 4
    assert viewer._punti_correnti == []


def test_doppio_clic_fuori_disegno_fa_reset_zoom(qapp):
    viewer = ImageViewer()
    viewer.set_strumento("poligono")
    viewer.zoom_by(2.0)
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtCore import QEvent as QE
    ev = QMouseEvent(QE.MouseButtonDblClick, QPointF(10, 10), QPointF(10, 10),
                     Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    viewer.mouseDoubleClickEvent(ev)
    assert viewer._zoom == 1.0


def test_shortcut_override_reclama_invio_solo_durante_il_disegno(qapp):
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtCore import QEvent as QE

    viewer = _viewer_con_immagine()
    viewer.set_strumento("poligono")
    tasto = QKeyEvent(QE.ShortcutOverride, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    assert viewer.event(tasto) is False  # niente disegno in corso: la scorciatoia globale resta libera
    _click(viewer, 10, 10)
    tasto = QKeyEvent(QE.ShortcutOverride, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    assert viewer.event(tasto) is True   # disegno in corso: Invio va al poligono


def test_clic_sul_primo_punto_chiude_il_poligono(qapp):
    viewer = _viewer_con_immagine()
    viewer.set_strumento("poligono")
    aggiunte = []
    viewer.geometriaAggiunta.connect(aggiunte.append)
    for x, y in ((10, 10), (40, 10), (40, 30)):
        _click(viewer, x, y)
    assert not aggiunte
    _click(viewer, 10, 10)  # clic di nuovo sul primo vertice
    assert len(aggiunte) == 1
    assert len(aggiunte[0]["punti"]) == 3  # il clic di chiusura non aggiunge vertici
    assert viewer._punti_correnti == []


def test_clic_vicino_ma_non_sul_primo_punto_aggiunge(qapp):
    viewer = _viewer_con_immagine()
    viewer.set_strumento("poligono")
    aggiunte = []
    viewer.geometriaAggiunta.connect(aggiunte.append)
    for x, y in ((10, 10), (40, 10), (40, 30)):
        _click(viewer, x, y)
    _click(viewer, 20, 25)  # lontano dal primo vertice: nuovo punto, nessuna chiusura
    assert not aggiunte
    assert len(viewer._punti_correnti) == 4


# ------------------------------------------------------------ strumento seleziona

def _evento(tipo, widget_pos, bottone, bottoni):
    from PySide6.QtGui import QMouseEvent
    return QMouseEvent(tipo, widget_pos, widget_pos, bottone, bottoni,
                       Qt.KeyboardModifier.NoModifier)


def _trascina(viewer, da_scene, a_scene):
    """Drag sinistro tra due punti in coordinate di scena, alla BoxItem."""
    da_w = viewer.mapFromScene(QPointF(*da_scene))
    a_w = viewer.mapFromScene(QPointF(*a_scene))
    viewer.mousePressEvent(_evento(QEvent.MouseButtonPress, da_w,
                                   Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton))
    viewer.mouseMoveEvent(_evento(QEvent.MouseMove, a_w,
                                   Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton))
    viewer.mouseReleaseEvent(_evento(QEvent.MouseButtonRelease, a_w,
                                      Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton))


def _clicca(viewer, punto_scene):
    _trascina(viewer, punto_scene, punto_scene)


def _viewer_con_box() -> ImageViewer:
    from labeling_tool.model import Record
    viewer = _viewer_con_immagine()
    viewer.set_strumento("seleziona")
    record = Record(nome="img")
    record.geometrie = [{"tipo": "box", "classe": "a", "x": 10.0, "y": 10.0, "w": 20.0, "h": 20.0}]
    viewer.mostra_annotazioni(record)
    return viewer


def test_seleziona_primo_clic_dentro_il_box_seleziona_e_sposta(qapp):
    viewer = _viewer_con_box()
    modifiche = []
    viewer.geometriaModificata.connect(lambda i, g: modifiche.append((i, g)))
    _trascina(viewer, (20, 20), (30, 30))  # centro del box
    assert viewer.indice_selezionato() == 0
    assert len(modifiche) == 1
    assert modifiche[0][1]["x"] == pytest.approx(20.0, abs=0.1)
    assert modifiche[0][1]["y"] == pytest.approx(20.0, abs=0.1)


def test_seleziona_box_piccolo_gia_selezionato_il_clic_al_centro_sposta(qapp):
    viewer = _viewer_con_box()
    _clicca(viewer, (20, 20))  # primo clic: seleziona
    assert viewer.indice_selezionato() == 0
    modifiche = []
    viewer.geometriaModificata.connect(lambda i, g: modifiche.append((i, g)))
    _trascina(viewer, (20, 20), (25, 25))  # centro: sposta, non ridimensiona
    assert len(modifiche) == 1
    assert modifiche[0][1]["x"] == pytest.approx(15.0, abs=0.1)
    assert modifiche[0][1]["w"] == pytest.approx(20.0, abs=0.1)


def test_seleziona_maniglia_br_ridimensiona_lato_e_altezza(qapp):
    viewer = _viewer_con_box()
    _clicca(viewer, (20, 20))  # seleziona
    modifiche = []
    viewer.geometriaModificata.connect(lambda i, g: modifiche.append((i, g)))
    _trascina(viewer, (30, 30), (35, 35))  # angolo br
    assert len(modifiche) == 1
    g = modifiche[0][1]
    assert g["w"] > 20.0
    assert g["h"] > 20.0


def test_seleziona_clic_su_spazio_vuoto_deseleziona(qapp):
    viewer = _viewer_con_box()
    _clicca(viewer, (20, 20))
    assert viewer.indice_selezionato() == 0
    _clicca(viewer, (60, 60))
    assert viewer.indice_selezionato() == -1
