"""Wizard di primo avvio ed editor della configurazione (solo GUI, nessun file da editare)."""

from typing import Optional

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from labeling_tool.config import ESTENSIONI_DEFAULT, ProgettoConfig, EtichettaDef

WORKFLOW_VOCI = {
    "classificazione": "Solo classificazione (etichette per immagine)",
    "classificazione+geometrie": "Classificazione + geometrie (box e poligoni)",
}


class BottoneColore(QPushButton):
    """Pulsante che mostra e sceglie un colore."""

    def __init__(self, colore: str = "#BDBDBD"):
        super().__init__()
        self.colore = QColor(colore)
        self.setFixedWidth(60)
        self.aggiorna()
        self.clicked.connect(self._scegli)

    def _scegli(self):
        scelto = QColorDialog.getColor(self.colore, self, "Scegli il colore")
        if scelto.isValid():
            self.colore = scelto
            self.aggiorna()

    def aggiorna(self):
        self.setStyleSheet(f"background:{self.colore.name()}; border:1px solid #4B515C;")

    def hex(self) -> str:
        return self.colore.name()


class ModuloEtichette(QWidget):
    """Tabella etichette: nome, colore, tasto. Aggiungi/rimuovi righe."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabella = QTableWidget(0, 3)
        self.tabella.setHorizontalHeaderLabels(["Nome", "Colore", "Tasto"])
        self.tabella.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.tabella)
        bottoni = QHBoxLayout()
        aggiungi = QPushButton("+ Aggiungi etichetta")
        rimuovi = QPushButton("- Rimuovi selezionata")
        aggiungi.clicked.connect(self.aggiungi_riga)
        rimuovi.clicked.connect(self.rimuovi_riga)
        bottoni.addWidget(aggiungi)
        bottoni.addWidget(rimuovi)
        bottoni.addStretch()
        layout.addLayout(bottoni)

    def aggiungi_riga(self, nome: str = "", colore: str = "#BDBDBD", tasto: str = ""):
        riga = self.tabella.rowCount()
        self.tabella.insertRow(riga)
        self.tabella.setItem(riga, 0, QTableWidgetItem(nome))
        bottone_colore = BottoneColore(colore)
        self.tabella.setCellWidget(riga, 1, bottone_colore)
        tasto_item = QTableWidgetItem(tasto)
        self.tabella.setItem(riga, 2, tasto_item)

    def rimuovi_riga(self):
        riga = self.tabella.currentRow()
        if riga >= 0:
            self.tabella.removeRow(riga)

    def etichette(self):
        risultato = []
        for riga in range(self.tabella.rowCount()):
            nome_item = self.tabella.item(riga, 0)
            bottone = self.tabella.cellWidget(riga, 1)
            tasto_item = self.tabella.item(riga, 2)
            nome = (nome_item.text() if nome_item else "").strip()
            if not nome:
                continue
            risultato.append(EtichettaDef(
                nome=nome,
                colore=bottone.hex() if bottone else "#BDBDBD",
                tasto=(tasto_item.text() if tasto_item else "").strip(),
            ))
        return risultato

    def carica(self, etichette):
        self.tabella.setRowCount(0)
        for e in etichette:
            self.aggiungi_riga(e.nome, e.colore, e.tasto)


class ModuloConfig(QWidget):
    """Modulo riutilizzabile per editare una ProgettoConfig."""

    def __init__(self, parent=None):
        super().__init__(parent)
        form = QFormLayout(self)
        self.nome_progetto = QLineEdit()
        self.etichettatore = QLineEdit()
        self.workflow = QComboBox()
        for chiave, etichetta in WORKFLOW_VOCI.items():
            self.workflow.addItem(etichetta, chiave)
        self.multi_label = QCheckBox("Più etichette per immagine (multi-label)")
        form.addRow("Nome progetto", self.nome_progetto)
        form.addRow("Etichettatore", self.etichettatore)
        form.addRow("Workflow", self.workflow)
        form.addRow("", self.multi_label)
        self.modulo_etichette = ModuloEtichette()
        form.addRow("Etichette", self.modulo_etichette)
        self.ricorsivo = QCheckBox("Includi le sottocartelle")
        form.addRow("Scansione", self.ricorsivo)
        estensioni_widget = QWidget()
        est_layout = QHBoxLayout(estensioni_widget)
        est_layout.setContentsMargins(0, 0, 0, 0)
        self.checkbox_estensioni = {}
        for est in ESTENSIONI_DEFAULT:
            check = QCheckBox(est)
            check.setChecked(True)
            est_layout.addWidget(check)
            self.checkbox_estensioni[est] = check
        self.altre_estensioni = QLineEdit()
        self.altre_estensioni.setPlaceholderText("altre, separate da spazio")
        est_layout.addWidget(self.altre_estensioni)
        form.addRow("Estensioni", estensioni_widget)
        unita_widget = QWidget()
        unita_layout = QHBoxLayout(unita_widget)
        unita_layout.setContentsMargins(0, 0, 0, 0)
        self.unita = QLineEdit("px")
        self.unita.setMaximumWidth(80)
        self.scala = QDoubleSpinBox()
        self.scala.setRange(0.000001, 1000000.0)
        self.scala.setDecimals(6)
        self.scala.setValue(1.0)
        self.scala.setMaximumWidth(140)
        unita_layout.addWidget(QLabel("Unità"))
        unita_layout.addWidget(self.unita)
        unita_layout.addWidget(QLabel("Scala px per unità"))
        unita_layout.addWidget(self.scala)
        unita_layout.addStretch()
        form.addRow("Misure", unita_widget)
        opzioni = QWidget()
        op_layout = QHBoxLayout(opzioni)
        op_layout.setContentsMargins(0, 0, 0, 0)
        self.misure_abilitate = QCheckBox("Strumenti di misura")
        self.misure_abilitate.setChecked(True)
        self.filtri_abilitati = QCheckBox("Filtri di visualizzazione")
        self.filtri_abilitati.setChecked(True)
        op_layout.addWidget(self.misure_abilitate)
        op_layout.addWidget(self.filtri_abilitati)
        op_layout.addStretch()
        form.addRow("Strumenti", opzioni)

    def get_config(self) -> ProgettoConfig:
        estensioni = [est for est, check in self.checkbox_estensioni.items() if check.isChecked()]
        for token in self.altre_estensioni.text().replace(",", " ").split():
            if not token.startswith("."):
                token = "." + token
            if token.lower() not in estensioni:
                estensioni.append(token.lower())
        return ProgettoConfig(
            nome_progetto=self.nome_progetto.text().strip() or "progetto",
            etichettatore=self.etichettatore.text().strip(),
            multi_label=self.multi_label.isChecked(),
            workflow=self.workflow.currentData(),
            etichette=self.modulo_etichette.etichette(),
            estensioni=estensioni or list(ESTENSIONI_DEFAULT),
            ricorsivo=self.ricorsivo.isChecked(),
            unita_misura=self.unita.text().strip() or "px",
            scala_px_per_unita=self.scala.value(),
            misure_abilitate=self.misure_abilitate.isChecked(),
            filtri_abilitati=self.filtri_abilitati.isChecked(),
        )

    def set_config(self, c: ProgettoConfig) -> None:
        self.nome_progetto.setText(c.nome_progetto)
        self.etichettatore.setText(c.etichettatore)
        indice = self.workflow.findData(c.workflow)
        if indice >= 0:
            self.workflow.setCurrentIndex(indice)
        self.multi_label.setChecked(c.multi_label)
        self.modulo_etichette.carica(c.etichette)
        self.ricorsivo.setChecked(c.ricorsivo)
        for est, check in self.checkbox_estensioni.items():
            check.setChecked(est in c.estensioni)
        extra = [e for e in c.estensioni if e not in ESTENSIONI_DEFAULT]
        self.altre_estensioni.setText(" ".join(extra))
        self.unita.setText(c.unita_misura)
        self.scala.setValue(c.scala_px_per_unita)
        self.misure_abilitate.setChecked(c.misure_abilitate)
        self.filtri_abilitati.setChecked(c.filtri_abilitati)


class WizardProgetto(QDialog):
    """Wizard al primo avvio: cartella + configurazione iniziale."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nuovo progetto")
        self.setMinimumWidth(640)
        layout = QVBoxLayout(self)
        form_cartella = QFormLayout()
        self.cartella_edit = QLineEdit()
        bottone_sfoglia = QPushButton("Sfoglia...")
        bottone_sfoglia.clicked.connect(self._scegli_cartella)
        riga_cartella = QWidget()
        riga = QHBoxLayout(riga_cartella)
        riga.setContentsMargins(0, 0, 0, 0)
        riga.addWidget(self.cartella_edit, 1)
        riga.addWidget(bottone_sfoglia)
        form_cartella.addRow("Cartella immagini", riga_cartella)
        layout.addLayout(form_cartella)
        self.modulo = ModuloConfig()
        layout.addWidget(self.modulo)
        self.avviso = QLabel()
        self.avviso.setStyleSheet("color:#F39C12;")
        layout.addWidget(self.avviso)
        bottoni = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bottoni.button(QDialogButtonBox.Ok).setText("Crea progetto")
        bottoni.accepted.connect(self._conferma)
        bottoni.rejected.connect(self.reject)
        layout.addWidget(bottoni)

    def _scegli_cartella(self):
        cartella = QFileDialog.getExistingDirectory(self, "Seleziona la cartella delle immagini")
        if cartella:
            self.cartella_edit.setText(cartella)

    def _conferma(self):
        cartella = self.cartella_edit.text().strip()
        if not cartella:
            self.avviso.setText("Seleziona la cartella delle immagini.")
            return
        config = self.modulo.get_config()
        errori = config.valida()
        if errori:
            self.avviso.setText("  •  " + "  •  ".join(errori))
            return
        self.avviso.setText("")
        self.accept()

    def risultati(self):
        from pathlib import Path

        return Path(self.cartella_edit.text().strip()), self.modulo.get_config()


class EditorConfigurazione(QDialog):
    """Editor della configurazione di un progetto esistente."""

    def __init__(self, config: ProgettoConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurazione progetto")
        self.setMinimumWidth(640)
        layout = QVBoxLayout(self)
        self.modulo = ModuloConfig()
        self.modulo.set_config(config)
        layout.addWidget(self.modulo)
        self.avviso = QLabel()
        self.avviso.setStyleSheet("color:#F39C12;")
        layout.addWidget(self.avviso)
        bottoni = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bottoni.accepted.connect(self._conferma)
        bottoni.rejected.connect(self.reject)
        layout.addWidget(bottoni)
        self.nuova_config: Optional[ProgettoConfig] = None

    def _conferma(self):
        config = self.modulo.get_config()
        errori = config.valida()
        if errori:
            self.avviso.setText("  •  " + "  •  ".join(errori))
            return
        self.nuova_config = config
        self.accept()
