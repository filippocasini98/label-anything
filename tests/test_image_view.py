"""Test del comportamento cursore di ImageViewer."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
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
