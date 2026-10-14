"""Test dell'overlay delle dimensioni su box e poligoni."""

import pytest

pytest.importorskip("PySide6")

import cv2
import numpy as np

from PySide6.QtWidgets import QApplication, QGraphicsTextItem

from labeling_tool.config import ProgettoConfig
from labeling_tool.image_view import ImageViewer
from labeling_tool.main_window import FinestraPrincipale
from labeling_tool.model import Progetto, Record


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def finestra(qapp, tmp_path):
    cv2.imwrite(str(tmp_path / "img.png"), np.zeros((32, 32, 3), dtype=np.uint8))
    finestra = FinestraPrincipale(tmp_path, Progetto(ProgettoConfig(nome_progetto="test")))
    yield finestra
    finestra.close()


def _testi_overlay(viewer):
    return [i.toPlainText() for i in viewer._altri_items if isinstance(i, QGraphicsTextItem)]


def test_box_mostra_solo_dimensioni_in_px(qapp):
    viewer = ImageViewer()
    record = Record("img.png")
    record.geometrie = [{"tipo": "box", "classe": "positivo", "x": 10.0, "y": 10.0, "w": 22.0, "h": 11.0}]
    viewer.mostra_annotazioni(record)
    assert _testi_overlay(viewer) == ["22x11"]


def test_poligono_mostra_solo_dimensioni_in_px(qapp):
    viewer = ImageViewer()
    record = Record("img.png")
    record.geometrie = [{
        "tipo": "poligono", "classe": "positivo",
        "punti": [[0.0, 0.0], [50.0, 0.0], [50.0, 25.0], [0.0, 25.0]],
    }]
    viewer.mostra_annotazioni(record)
    assert _testi_overlay(viewer) == ["50x25"]


def test_disabilitazione_nasconde_le_dimensioni(qapp):
    viewer = ImageViewer()
    record = Record("img.png")
    record.geometrie = [{"tipo": "box", "classe": "positivo", "x": 10.0, "y": 10.0, "w": 22.0, "h": 11.0}]
    viewer.set_mostra_dimensioni(False)
    viewer.mostra_annotazioni(record)
    assert _testi_overlay(viewer) == []


def test_checkbox_dimensioni_aggiorna_il_viewer_della_finestra(finestra):
    record = finestra._record_corrente()
    record.geometrie = [{"tipo": "box", "classe": "positivo", "x": 1.0, "y": 1.0, "w": 22.0, "h": 11.0}]
    finestra.viewer.mostra_annotazioni(record)
    assert _testi_overlay(finestra.viewer) == ["22x11"]

    finestra.check_dimensioni.setChecked(False)
    assert finestra.viewer._mostra_dimensioni is False
    assert _testi_overlay(finestra.viewer) == []

    finestra.check_dimensioni.setChecked(True)
    assert _testi_overlay(finestra.viewer) == ["22x11"]
