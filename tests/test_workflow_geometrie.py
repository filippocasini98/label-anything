"""Test del workflow 'Solo geometrie' (box e poligoni senza classificazione)."""

import pytest

pytest.importorskip("PySide6")

import cv2
import numpy as np

from PySide6.QtWidgets import QApplication

from labeling_tool.config import EtichettaDef, ProgettoConfig
from labeling_tool.main_window import FinestraPrincipale
from labeling_tool.model import Progetto, Record


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _config_geometrie() -> ProgettoConfig:
    return ProgettoConfig(
        nome_progetto="test",
        workflow="geometrie",
        etichette=[
            EtichettaDef("cella", "#3CB44B", "1"),
            EtichettaDef("sfondo", "#D83A3A", "2"),
        ],
    )


@pytest.fixture()
def finestra(qapp, tmp_path):
    cv2.imwrite(str(tmp_path / "img.png"), np.zeros((32, 32, 3), dtype=np.uint8))
    finestra = FinestraPrincipale(tmp_path, Progetto(_config_geometrie()))
    yield finestra
    finestra.close()


def test_config_geometrie_valida():
    assert _config_geometrie().valida() == []
    senza_etichette = ProgettoConfig(nome_progetto="test", workflow="geometrie", etichette=[])
    assert senza_etichette.valida() != []


def test_strumenti_box_e_poligono_disponibili(finestra):
    dati = [finestra.combo_strumenti.itemData(i) for i in range(finestra.combo_strumenti.count())]
    assert "box" in dati and "poligono" in dati


def test_sezione_etichette_nascosta_senza_classificazione(finestra):
    assert finestra.sezione_etichette.isVisible() is False
    assert finestra.contenitore_etichette.isVisible() is False
    # il combo delle classi resta: definisce la classe degli oggetti disegnati
    assert finestra.combo_classe.count() == 2


def test_record_completato_con_le_geometrie(finestra):
    record = finestra._record_corrente()
    record.geometrie = [{"tipo": "box", "classe": "cella", "x": 1.0, "y": 1.0, "w": 5.0, "h": 5.0}]
    assert finestra._record_completato(record) is True
    record2 = Record("img.png")
    record2.etichette = ["cella"]
    assert finestra._record_completato(record2) is False


def test_colore_record_dal_primo_oggetto(finestra):
    record = finestra._record_corrente()
    record.geometrie = [{"tipo": "box", "classe": "cella", "x": 1.0, "y": 1.0, "w": 5.0, "h": 5.0}]
    assert finestra._colore_record(record) == "#3CB44B"
    vuoto = Record("img.png")
    assert finestra._colore_record(vuoto) == "#E74C3C"


def test_filtro_non_etichettate_usa_le_geometrie(finestra, monkeypatch):
    record = finestra._record_corrente()
    record.geometrie = [{"tipo": "box", "classe": "cella", "x": 1.0, "y": 1.0, "w": 5.0, "h": 5.0}]
    indice = finestra.indice
    finestra.combo_filtro.setCurrentText("Non etichettate")
    assert indice not in finestra.indici_visibili
    finestra.combo_filtro.setCurrentText("Tutte")
    assert indice in finestra.indici_visibili
