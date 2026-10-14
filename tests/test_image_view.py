"""Test del comportamento cursore di ImageViewer."""

import pytest

pytest.importorskip("PySide6")

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
