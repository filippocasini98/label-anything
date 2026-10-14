"""Test del comportamento cursore di ImageViewer."""

import pytest

pytest.importorskip("PySide6")

import numpy as np

from PySide6.QtCore import QPointF, Qt
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
