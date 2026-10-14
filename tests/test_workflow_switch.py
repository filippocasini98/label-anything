"""Test del ripopolamento degli strumenti al cambio di configurazione a caldo."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialog

from labeling_tool.config import ProgettoConfig, config_default
from labeling_tool.image_view import ImageViewer
from labeling_tool.main_window import FinestraPrincipale
from labeling_tool.model import Progetto


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def finestra(qapp, tmp_path):
    import cv2
    import numpy as np

    cv2.imwrite(str(tmp_path / "img.png"), np.zeros((32, 32, 3), dtype=np.uint8))
    config = ProgettoConfig(nome_progetto="test")
    finestra = FinestraPrincipale(tmp_path, Progetto(config))
    yield finestra
    finestra.close()


def _attiva_workflow_geometrie(monkeypatch, finestra):
    """Simula la conferma dell'editor configurazione col workflow con geometrie."""
    nuova = config_default()
    nuova.workflow = "classificazione+geometrie"

    class DialogoFinto:
        nuova_config = nuova
        Accepted = QDialog.Accepted

        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return QDialog.Accepted

    import labeling_tool.main_window as mw

    monkeypatch.setattr(mw, "EditorConfigurazione", DialogoFinto)
    finestra.modifica_configurazione()


def test_workflow_cambiato_aggiunge_strumenti_geometrici(finestra, monkeypatch):
    # con workflow classificazione: solo naviga e seleziona
    dati = [finestra.combo_strumenti.itemData(i) for i in range(finestra.combo_strumenti.count())]
    assert "box" not in dati and "poligono" not in dati
    _attiva_workflow_geometrie(monkeypatch, finestra)
    dati = [finestra.combo_strumenti.itemData(i) for i in range(finestra.combo_strumenti.count())]
    assert "box" in dati and "poligono" in dati
    assert finestra.viewer._strumento in ImageViewer.STRUMENTI


def test_strumento_non_piu_disponibile_torna_a_nav(monkeypatch, finestra):
    _attiva_workflow_geometrie(monkeypatch, finestra)
    indice_box = next(
        i for i in range(finestra.combo_strumenti.count()) if finestra.combo_strumenti.itemData(i) == "box"
    )
    finestra.combo_strumenti.setCurrentIndex(indice_box)
    assert finestra.viewer._strumento == "box"

    # passa a classificazione: box sparisce, lo strumento torna a naviga
    nuova = config_default()
    nuova.workflow = "classificazione"

    class DialogoFinto:
        nuova_config = nuova
        Accepted = QDialog.Accepted

        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return QDialog.Accepted

    import labeling_tool.main_window as mw

    monkeypatch.setattr(mw, "EditorConfigurazione", DialogoFinto)
    finestra.modifica_configurazione()
    dati = [finestra.combo_strumenti.itemData(i) for i in range(finestra.combo_strumenti.count())]
    assert "box" not in dati
    assert finestra.combo_strumenti.currentData() == "nav"
    assert finestra.viewer._strumento == "nav"


def test_misure_disabilitate_rimuove_strumenti_di_misura(finestra, monkeypatch):
    _attiva_workflow_geometrie(monkeypatch, finestra)
    dati = [finestra.combo_strumenti.itemData(i) for i in range(finestra.combo_strumenti.count())]
    assert "distanza" in dati and "conteggio" in dati

    nuova = config_default()
    nuova.workflow = "classificazione+geometrie"
    nuova.misure_abilitate = False

    class DialogoFinto:
        nuova_config = nuova
        Accepted = QDialog.Accepted

        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return QDialog.Accepted

    import labeling_tool.main_window as mw

    monkeypatch.setattr(mw, "EditorConfigurazione", DialogoFinto)
    finestra.modifica_configurazione()
    dati = [finestra.combo_strumenti.itemData(i) for i in range(finestra.combo_strumenti.count())]
    assert "distanza" not in dati and "conteggio" not in dati
    assert "box" in dati
