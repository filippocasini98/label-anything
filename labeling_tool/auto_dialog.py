"""Annotazione assistita: dialogo di mappatura classi e worker di predizione."""

from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from labeling_tool.annotazioni_auto import (
    annota_immagine,
    applica_mappa,
    carica_modello,
    pre_mappa,
)
from labeling_tool.config import ProgettoConfig
from labeling_tool.io_utils import leggi_cv

IGNORA = "— ignora —"


class WorkerCaricamento(QThread):
    """Carica i pesi di un modello in background ed estrae i nomi delle classi."""

    classiPronte = Signal(list)
    errore = Signal(str)

    def __init__(self, percorso: str, parent=None):
        super().__init__(parent)
        self.percorso = percorso

    def run(self) -> None:
        try:
            modello = carica_modello(self.percorso)
            nomi = modello.names
            if isinstance(nomi, dict):
                chiavi = sorted(nomi.keys(), key=lambda k: int(k))
                classi = [str(nomi[k]) for k in chiavi]
            else:
                classi = [str(n) for n in nomi]
            self.classiPronte.emit(classi)
        except Exception as errore:  # modello mancante o illeggibile
            self.errore.emit(str(errore))


class WorkerAnnotazione(QThread):
    """Predizione in background immagine per immagine, annullabile."""

    progresso = Signal(int, int)          # elaborate, totali
    immagineAnnotata = Signal(str, list)  # nome immagine, geometrie
    finito = Signal(int, int, int)        # annotate, saltate, errori
    erroreCaricamento = Signal(str)

    def __init__(self, percorso_modello: str, percorsi, soglia: float,
                 mappa: Dict[str, str], salta_gia_annotate: bool,
                 geometrie_esistenti: set, parent=None):
        super().__init__(parent)
        self.percorso_modello = percorso_modello
        self.percorsi = list(percorsi)
        self.soglia = soglia
        self.mappa = dict(mappa)
        self.salta_gia_annotate = salta_gia_annotate
        self.geometrie_esistenti = set(geometrie_esistenti)
        self._annulla = False

    def annulla(self) -> None:
        self._annulla = True

    def run(self) -> None:
        try:
            modello = carica_modello(self.percorso_modello)
        except Exception as errore:
            self.erroreCaricamento.emit(str(errore))
            return
        annotate = saltate = errori = 0
        totale = len(self.percorsi)
        nome_modello = Path(self.percorso_modello).name
        for i, percorso in enumerate(self.percorsi):
            if self._annulla:
                break
            self.progresso.emit(i, totale)
            nome = percorso.name
            if self.salta_gia_annotate and nome in self.geometrie_esistenti:
                saltate += 1
                continue
            immagine = leggi_cv(percorso)
            if immagine is None:
                errori += 1
                continue
            try:
                grezze = annota_immagine(modello, immagine, self.soglia, nome_modello)
            except Exception:
                errori += 1
                continue
            geometrie = applica_mappa(grezze, self.mappa, self.soglia)
            if geometrie:
                self.immagineAnnotata.emit(nome, geometrie)
                annotate += 1
            else:
                saltate += 1
        self.progresso.emit(totale, totale)
        self.finito.emit(annotate, saltate, errori)


class DialogoMappatura(QDialog):
    """Configura l'annotazione automatica: modello, soglia, salto e mappa classi.

    Import: passare classi_fonte e con_modello=False (nessun file modello).
    Inferenza: con_modello=True; le classi vengono caricate dal modello in thread.
    """

    def __init__(self, config: ProgettoConfig, classi_fonte: Optional[List[str]] = None,
                 con_modello: bool = True, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Annotazione assistita")
        self.setMinimumWidth(560)
        self.config = config
        self.mappa: Dict[str, str] = {}
        self.modello_percorso = config.modello_percorso
        self._worker: Optional[WorkerCaricamento] = None

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.edit_modello: Optional[QLineEdit] = None
        if con_modello:
            self.edit_modello = QLineEdit(config.modello_percorso)
            bottone_sfoglia = QPushButton("Sfoglia...")
            bottone_sfoglia.clicked.connect(self._scegli_modello)
            riga_modello = QWidget()
            layout_riga = QHBoxLayout(riga_modello)
            layout_riga.setContentsMargins(0, 0, 0, 0)
            layout_riga.addWidget(self.edit_modello, 1)
            layout_riga.addWidget(bottone_sfoglia)
            form.addRow("Modello (.pt/.onnx)", riga_modello)

        self.spin_soglia = QDoubleSpinBox()
        self.spin_soglia.setRange(0.01, 0.99)
        self.spin_soglia.setSingleStep(0.05)
        self.spin_soglia.setValue(config.modello_soglia)
        if con_modello:
            form.addRow("Soglia di confidenza", self.spin_soglia)

        self.check_salta = QCheckBox("Salta le immagini che hanno gia' geometrie")
        self.check_salta.setChecked(config.salta_gia_annotate)
        form.addRow("", self.check_salta)

        self.avviso_classi = QLabel()
        self.avviso_classi.setStyleSheet("color:#F39C12;")
        form.addRow("", self.avviso_classi)
        layout.addLayout(form)

        layout.addWidget(QLabel("Mappatura classi (lascia '— ignora —' per escludere):"))
        self.tabella = QTableWidget(0, 2)
        self.tabella.setHorizontalHeaderLabels(["Classe fonte", "Etichetta progetto"])
        self.tabella.horizontalHeader().setStretchLastSection(True)
        self.tabella.setColumnWidth(0, 220)
        layout.addWidget(self.tabella, 1)

        bottoni = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bottoni.button(QDialogButtonBox.Ok).setText("Avvia")
        bottoni.accepted.connect(self._conferma)
        bottoni.rejected.connect(self.reject)
        layout.addWidget(bottoni)

        if classi_fonte:
            self._popola_mappa(classi_fonte)
        elif con_modello and config.modello_percorso:
            self._carica_classi(config.modello_percorso)

    def reject(self) -> None:
        """Alla chiusura aspetta un eventuale caricamento in corso.

        Il worker e' figlio del dialogo: senza attesa Qt lo distruggerebbe
        mentre il thread gira (crash fatale)."""
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait()
        super().reject()

    def _scegli_modello(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self.avviso_classi.setText("Attendi il caricamento del modello in corso...")
            return
        percorso, _ = QFileDialog.getOpenFileName(
            self, "Scegli il modello", self.edit_modello.text() or str(Path.home()),
            "Modelli (*.pt *.onnx);;Tutti i file (*)")
        if percorso:
            self.edit_modello.setText(percorso)
            self._carica_classi(percorso)

    def _carica_classi(self, percorso: str) -> None:
        if self._worker is not None and self._worker.isRunning():
            self.avviso_classi.setText("Attendi il caricamento del modello in corso...")
            return
        self.avviso_classi.setText("Caricamento del modello in corso...")
        self._worker = WorkerCaricamento(percorso, self)
        self._worker.classiPronte.connect(self._on_classi_pronte)
        self._worker.errore.connect(self._on_errore_caricamento)
        self._worker.start()

    def _on_classi_pronte(self, classi: list) -> None:
        self.avviso_classi.setText("")
        self._popola_mappa(classi)

    def _on_errore_caricamento(self, messaggio: str) -> None:
        self.avviso_classi.setText(f"Modello non caricabile: {messaggio}")

    def _popola_mappa(self, classi_fonte: List[str]) -> None:
        etichette = [e.nome for e in self.config.etichette]
        iniziale = pre_mappa(classi_fonte, etichette, self.config.mappa_classi)
        self.tabella.setRowCount(0)
        for classe in classi_fonte:
            riga = self.tabella.rowCount()
            self.tabella.insertRow(riga)
            self.tabella.setItem(riga, 0, QTableWidgetItem(classe))
            combo = QComboBox()
            combo.addItem(IGNORA, "")
            for nome in etichette:
                combo.addItem(nome, nome)
            indice = combo.findData(iniziale.get(classe, ""))
            combo.setCurrentIndex(max(0, indice))
            self.tabella.setCellWidget(riga, 1, combo)

    def _conferma(self) -> None:
        if self.edit_modello is not None:
            self.modello_percorso = self.edit_modello.text().strip()
        self.mappa = {}
        for riga in range(self.tabella.rowCount()):
            item = self.tabella.item(riga, 0)
            combo = self.tabella.cellWidget(riga, 1)
            if item is None or combo is None:
                continue
            classe = item.text().strip()
            destinazione = str(combo.currentData() or "")
            if classe and destinazione:
                self.mappa[classe] = destinazione
        if not self.mappa:
            self.avviso_classi.setText("Mappa almeno una classe su un'etichetta del progetto.")
            return
        self.accept()

    @property
    def soglia(self) -> float:
        return self.spin_soglia.value()

    @property
    def salta(self) -> bool:
        return self.check_salta.isChecked()
