import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from labeling_tool.config import EtichettaDef, config_default


def _app():
    return QApplication.instance() or QApplication([])


def test_dialogo_import_conferma_non_crasha():
    app = _app()
    from labeling_tool.auto_dialog import DialogoMappatura

    config = config_default()
    config.etichette = [EtichettaDef("acino", "#3CB44B", "1")]
    dialogo = DialogoMappatura(config, classi_fonte=["uva", "foglia"], con_modello=False)
    dialogo._conferma()  # mappa vuota: avviso, nessun accept, NESSUN RuntimeError
    assert dialogo.mappa == {}
    dialogo.deleteLater()


def test_dialogo_import_mappa_e_accetta():
    app = _app()
    from labeling_tool.auto_dialog import DialogoMappatura

    config = config_default()
    config.etichette = [EtichettaDef("acino", "#3CB44B", "1")]
    dialogo = DialogoMappatura(config, classi_fonte=["uva"], con_modello=False)
    combo = dialogo.tabella.cellWidget(0, 1)
    combo.setCurrentIndex(1)  # "acino"
    dialogo._conferma()
    assert dialogo.mappa == {"uva": "acino"}
    dialogo.deleteLater()
