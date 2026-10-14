"""Entry point dell'applicazione.

Ordine di selezione della cartella immagini:
1. argomento da riga di comando (es. `python run_labeling.py /percorso/cartella`)
2. ultima cartella usata (memorizzata automaticamente)
3. selettore di cartelle (solo al primo avvio)"""

import sys
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QApplication, QMessageBox

from labeling_tool.io_utils import leggi_ultima_cartella, salva_ultima_cartella


def scegli_cartella(app: QApplication) -> Optional[Path]:
    """Cartella da aprire: argomento, ultima usata, oppure selettore."""
    if len(sys.argv) > 1 and Path(sys.argv[1]).is_dir():
        return Path(sys.argv[1])
    ultima = leggi_ultima_cartella()
    if ultima is not None:
        return ultima
    from PySide6.QtWidgets import QFileDialog

    scelta = QFileDialog.getExistingDirectory(
        None, "Seleziona la cartella delle immagini", "",
        QFileDialog.Option.DontUseNativeDialog,
    )
    return Path(scelta) if scelta else None


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Label Anything")
    cartella = scegli_cartella(app)
    if cartella is None:
        return 0
    try:
        from labeling_tool.main_window import FinestraPrincipale

        finestra = FinestraPrincipale.apri_progetto(cartella)
    except (FileNotFoundError, NotADirectoryError, RuntimeError) as errore:
        QMessageBox.critical(None, "Errore", str(errore))
        return 1
    finestra.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
