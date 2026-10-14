"""Test della riassegnazione della classe a un box gia' disegnato."""

import pytest

pytest.importorskip("PySide6")

import cv2
import numpy as np

from PySide6.QtWidgets import QApplication

from labeling_tool.config import config_default
from labeling_tool.main_window import FinestraPrincipale
from labeling_tool.model import Progetto, Record


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def finestra(qapp, tmp_path):
    cv2.imwrite(str(tmp_path / "img.png"), np.zeros((32, 32, 3), dtype=np.uint8))
    config = config_default()
    config.workflow = "classificazione+geometrie"
    config.nome_progetto = "test"
    finestra = FinestraPrincipale(tmp_path, Progetto(config))
    yield finestra
    finestra.close()


def test_cambio_classe_riassegna_il_box_selezionato(finestra):
    record = finestra._record_corrente()
    record.geometrie = [{"tipo": "box", "classe": "positivo", "x": 1.0, "y": 1.0, "w": 20.0, "h": 10.0}]
    finestra.viewer.mostra_annotazioni(record)
    assert finestra.combo_classe.count() >= 2

    finestra.viewer._on_box_selezionato(0)  # seleziona il box
    nuova_classe = finestra.combo_classe.itemText(1)
    finestra.combo_classe.setCurrentIndex(1)

    assert finestra._record_corrente().geometrie[0]["classe"] == nuova_classe
    # la classe attiva resta aggiornata per i prossimi disegni
    assert finestra.viewer._classe_attiva == nuova_classe
    # il cambio e' annullabile
    assert len(finestra.storico) >= 1


def test_cambio_classe_senza_selezione_non_tocca_i_box(finestra):
    record = finestra._record_corrente()
    record.geometrie = [{"tipo": "box", "classe": "positivo", "x": 1.0, "y": 1.0, "w": 20.0, "h": 10.0}]
    finestra.viewer.mostra_annotazioni(record)
    assert finestra.viewer.indice_selezionato() < 0

    finestra.combo_classe.setCurrentIndex(1)
    assert finestra._record_corrente().geometrie[0]["classe"] == "positivo"
