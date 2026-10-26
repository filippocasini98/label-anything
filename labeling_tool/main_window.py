"""Finestra principale dell'applicazione di etichettatura."""

import os
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from labeling_tool.config import ProgettoConfig, versione_app
from labeling_tool.cursors import CURSORI, leggi_cursore, salva_cursore
from labeling_tool.export import (
    esporta_coco,
    esporta_csv,
    esporta_html,
    esporta_labelme,
    esporta_maschere,
    esporta_yolo,
    report_statistiche,
)
from labeling_tool.image_view import ImageViewer
from labeling_tool.io_utils import (
    ImageCache,
    cartella_dati,
    elenco_immagini,
    leggi_cv,
    salva_ultima_cartella,
)
from labeling_tool.model import Azione, Misura, Progetto, Record, adesso_iso
from labeling_tool.settings_dialog import EditorConfigurazione

COLORE_NON_ASSEGNATA = "#E74C3C"
COLORE_REVISIONE = "#00A8E8"
PRECARICA_PRIMA = 2
PRECARICA_DOPO = 4


class FinestraPrincipale(QMainWindow):
    """Finestra principale: etichettatura, annotazioni, misure e analisi."""

    def __init__(self, cartella: Path, progetto: Progetto, percorso_caricato: Optional[Path] = None):
        super().__init__()
        self.cartella = cartella
        salva_ultima_cartella(cartella)
        self.progetto = progetto
        config = progetto.config
        self.immagini = elenco_immagini(cartella, set(config.estensioni), config.ricorsivo)
        if not self.immagini:
            raise RuntimeError("Nessuna immagine trovata nella cartella selezionata.")
        # Cartella dati: sottocartella se ci sono piu' immagini, altrimenti accanto all'immagine
        self.cartella_dati = cartella_dati(cartella, len(self.immagini))
        self.percorso_progetto = self.cartella_dati / f"{progetto.config.nome_progetto}.progetto.json"
        # Migrazione: progetti salvati nella vecchia posizione (radice) finiscono nella cartella dati
        if (
            percorso_caricato is not None
            and percorso_caricato != self.percorso_progetto
            and percorso_caricato.exists()
        ):
            try:
                self.cartella_dati.mkdir(parents=True, exist_ok=True)
                os.replace(str(percorso_caricato), str(self.percorso_progetto))
            except OSError:
                pass
        progetto.reindicizza(self.immagini)
        for record in progetto.immagini.values():
            record.etichettatore = record.etichettatore or config.etichettatore

        self.cache = ImageCache()
        self.storico = []
        self.storico_redo = []
        self.indice = self._prima_da_completare()
        self.indici_visibili: List[int] = []
        self.salvato = True
        self._caricamento_ui = False

        self.setWindowTitle(f"Label Anything {versione_app()} - {config.nome_progetto}")
        self.resize(1600, 1000)
        self.setMinimumSize(1100, 720)
        self._costruisci_ui()
        self._azioni()
        self._stile()
        self.aggiorna_filtri()
        self.mostra_indice(self.indice)

        self.timer_salvataggio = QTimer(self)
        self.timer_salvataggio.setSingleShot(True)
        self.timer_salvataggio.timeout.connect(self.salva)

    # ------------------------------------------------------------ avvio

    @staticmethod
    def apri_progetto(cartella: Path) -> "FinestraPrincipale":
        """Apre un progetto esistente nella cartella (cartella dati o radice) o lancia il wizard."""
        candidati = set((cartella / "etichettatura").glob("*.progetto.json"))
        candidati |= set(cartella.glob("*.progetto.json"))
        percorsi = sorted((p for p in candidati if p.is_file()),
                          key=lambda p: p.stat().st_mtime, reverse=True)
        if percorsi:
            percorso = percorsi[0]
            progetto = Progetto.carica(percorso)
            return FinestraPrincipale(cartella, progetto, percorso_caricato=percorso)
        from labeling_tool.settings_dialog import WizardProgetto

        wizard = WizardProgetto()
        wizard.modulo.set_config(ProgettoConfig(nome_progetto=cartella.name))
        if wizard.exec() != WizardProgetto.Accepted:
            raise RuntimeError("Creazione del progetto annullata.")
        cartella_scelta, config = wizard.risultati()
        progetto = Progetto(config=config)
        finestra = FinestraPrincipale(cartella_scelta, progetto)
        finestra.salva()
        return finestra

    def _record_completato(self, record: Record) -> bool:
        """Un'immagine e' completata con le geometrie o con le etichette, a seconda del workflow."""
        if self.progetto.config.workflow == "geometrie":
            return bool(record.geometrie)
        return bool(record.etichette)

    def _prima_da_completare(self) -> int:
        for i, percorso in enumerate(self.immagini):
            record = self.progetto.immagini[percorso.name]
            if not self._record_completato(record) and not record.da_revisionare:
                return i
        return 0

    # ------------------------------------------------------------ UI

    def _costruisci_ui(self):
        centrale = QWidget()
        self.setCentralWidget(centrale)
        root = QVBoxLayout(centrale)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        alto = QHBoxLayout()
        self.titolo = QLabel()
        self.titolo.setObjectName("titoloImmagine")
        self.badge = QLabel()
        self.badge.setAlignment(Qt.AlignCenter)
        self.badge.setMinimumWidth(150)
        self.badge.setObjectName("badge")
        alto.addWidget(self.titolo, 1)
        alto.addWidget(self.badge)
        root.addLayout(alto)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        area_centrale = QWidget()
        centro = QVBoxLayout(area_centrale)
        centro.setContentsMargins(0, 0, 0, 0)
        self.viewer = ImageViewer()
        self.viewer.set_colori({e.nome: e.colore for e in self.progetto.config.etichette})
        self.viewer.set_unita(self.progetto.config.unita_misura, self.progetto.config.scala_px_per_unita)
        self.viewer.zoomChanged.connect(lambda z: self.zoom_label.setText(f"Zoom {z:.2f}x"))
        self.viewer.geometriaAggiunta.connect(self._geometria_aggiunta)
        self.viewer.geometriaModificata.connect(self._geometria_modificata)
        self.viewer.misuraAggiunta.connect(self._misura_aggiunta)
        centro.addWidget(self.viewer, 1)

        self.miniature = QListWidget()
        self.miniature.setFlow(QListWidget.LeftToRight)
        self.miniature.setViewMode(QListWidget.IconMode)
        self.miniature.setIconSize(QSize(120, 80))
        self.miniature.setFixedHeight(125)
        self.miniature.setSpacing(5)
        self.miniature.itemClicked.connect(self._miniatura_cliccata)
        centro.addWidget(self.miniature)
        splitter.addWidget(area_centrale)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(330)
        scroll.setMaximumWidth(430)
        pannello = QWidget()
        side = QVBoxLayout(pannello)
        side.setSpacing(8)

        self.sezione_etichette = self._sezione("ETICHETTE")
        side.addWidget(self.sezione_etichette)
        self.contenitore_etichette = QWidget()
        self.pannello_etichette = QVBoxLayout(self.contenitore_etichette)
        self.pannello_etichette.setContentsMargins(0, 0, 0, 0)
        side.addWidget(self.contenitore_etichette)

        self.check_revisione = QCheckBox("Da revisionare [X]")
        self.check_revisione.stateChanged.connect(self._toggle_revisionare)
        side.addWidget(self.check_revisione)
        self.bottone_conferma_revisione = QPushButton("Conferma revisione [Invio]")
        self.bottone_conferma_revisione.clicked.connect(self._conferma_revisione)
        side.addWidget(self.bottone_conferma_revisione)

        side.addWidget(self._sezione("NOTE"))
        self.note_edit = QPlainTextEdit()
        self.note_edit.setPlaceholderText("Annotazioni libere sull'immagine...")
        self.note_edit.setMaximumHeight(80)
        self.note_edit.textChanged.connect(self._note_modificate)
        side.addWidget(self.note_edit)

        side.addWidget(self._sezione("STRUMENTI"))
        self.combo_strumenti = QComboBox()
        self.combo_strumenti.setToolTip(
            "Tieni premuto Spazio (o trascina col tasto centrale del mouse) "
            "per muoverti nell'immagine mentre usi qualsiasi strumento"
        )
        self._popola_strumenti()
        self.combo_strumenti.currentIndexChanged.connect(self._strumento_cambiato)
        side.addWidget(self.combo_strumenti)

        self.combo_classe = QComboBox()
        self.combo_classe.currentIndexChanged.connect(self._classe_cambiata)
        side.addWidget(self.combo_classe)

        side.addWidget(self._sezione("FILTRI"))
        self.combo_filtro = QComboBox()
        self.combo_filtro.currentTextChanged.connect(self.aggiorna_filtri)
        side.addWidget(self.combo_filtro)
        self._popola_filtri()

        side.addWidget(self._sezione("VISUALIZZAZIONE"))
        self.slider_luminosita = QSlider(Qt.Horizontal)
        self.slider_luminosita.setRange(-100, 100)
        self.slider_luminosita.valueChanged.connect(self._visualizzazione_modificata)
        self.slider_contrasto = QSlider(Qt.Horizontal)
        self.slider_contrasto.setRange(25, 250)
        self.slider_contrasto.setValue(100)
        self.slider_contrasto.valueChanged.connect(self._visualizzazione_modificata)
        eff = QHBoxLayout()
        self.check_grigi = QCheckBox("Grigi [G]")
        self.check_equalizza = QCheckBox("Equalizza [H]")
        self.check_dimensioni = QCheckBox("Dimensioni box")
        self.check_dimensioni.setChecked(True)
        self.check_dimensioni.toggled.connect(self._dimensioni_cambiate)
        self.check_grigi.stateChanged.connect(self._visualizzazione_modificata)
        self.check_equalizza.stateChanged.connect(self._visualizzazione_modificata)
        eff.addWidget(self.check_grigi)
        eff.addWidget(self.check_equalizza)
        eff.addWidget(self.check_dimensioni)
        side.addWidget(QLabel("Luminosità"))
        side.addWidget(self.slider_luminosita)
        side.addWidget(QLabel("Contrasto"))
        side.addWidget(self.slider_contrasto)
        side.addLayout(eff)
        bottone_reset_vis = QPushButton("Ripristina visualizzazione [R]")
        bottone_reset_vis.clicked.connect(self.reset_visualizzazione)
        side.addWidget(bottone_reset_vis)

        self.check_statistiche = QCheckBox("Mostra statistiche")
        self.check_statistiche.setChecked(True)
        self.check_statistiche.stateChanged.connect(self._aggiorna_statistiche)
        side.addWidget(self.check_statistiche)
        self.etichetta_statistiche = QLabel()
        self.etichetta_statistiche.setObjectName("statistiche")
        self.etichetta_statistiche.setTextFormat(Qt.RichText)
        side.addWidget(self.etichetta_statistiche)
        side.addStretch()

        scroll.setWidget(pannello)
        splitter.addWidget(scroll)
        splitter.setSizes([1150, 400])

        basso = QHBoxLayout()
        self.bottone_prec = QPushButton("◀ Precedente [A]")
        self.bottone_succ = QPushButton("Successiva [D] ▶")
        self.bottone_prec.clicked.connect(self.precedente)
        self.bottone_succ.clicked.connect(self.successiva)
        self.progresso = QProgressBar()
        self.zoom_label = QLabel("Zoom 1.00x")
        basso.addWidget(self.bottone_prec)
        basso.addWidget(self.progresso, 1)
        basso.addWidget(self.zoom_label)
        basso.addWidget(self.bottone_succ)
        root.addLayout(basso)

        stato = QStatusBar()
        self.setStatusBar(stato)
        self.stato_label = QLabel("Pronto")
        stato.addWidget(self.stato_label, 1)
        self.salvataggio_label = QLabel("Salvato")
        stato.addPermanentWidget(self.salvataggio_label)

        self._popola_etichette()

    @staticmethod
    def _sezione(testo: str) -> QLabel:
        titolo = QLabel(testo)
        titolo.setObjectName("sezione")
        return titolo

    def _popola_filtri(self) -> None:
        self.combo_filtro.blockSignals(True)
        self.combo_filtro.clear()
        voci = ["Tutte", "Non etichettate", "Da revisionare", "Revisionate", "Con note", "Con geometrie"]
        voci += [f"Etichetta: {e.nome}" for e in self.progetto.config.etichette]
        self.combo_filtro.addItems(voci)
        self.combo_filtro.blockSignals(False)

    def _popola_strumenti(self) -> None:
        """Ricostruisce il combobox strumenti dalla configurazione corrente.

        Conserva lo strumento attivo se resta disponibile, altrimenti
        torna a 'Naviga' e lo applica anche al viewer."""
        self.combo_strumenti.blockSignals(True)
        corrente = self.combo_strumenti.currentData()
        self.combo_strumenti.clear()
        self.combo_strumenti.addItem("Naviga (pan)", "nav")
        self.combo_strumenti.addItem("Seleziona/modifica", "seleziona")
        self._strumenti_geometrici = []
        if self.progetto.config.workflow in ("classificazione+geometrie", "geometrie"):
            self.combo_strumenti.addItem("Disegna box", "box")
            self.combo_strumenti.addItem("Disegna poligono", "poligono")
            self._strumenti_geometrici += ["box", "poligono"]
        if self.progetto.config.misure_abilitate:
            self.combo_strumenti.addItem("Misura distanza", "distanza")
            self.combo_strumenti.addItem("Misura area", "area")
            self.combo_strumenti.addItem("Conteggio oggetti", "conteggio")
            self.combo_strumenti.addItem("Dimensioni oggetto", "oggetto")
            self._strumenti_geometrici += ["distanza", "area", "conteggio", "oggetto"]
        indice = self.combo_strumenti.findData(corrente)
        if indice < 0:
            indice = 0
            self.viewer.set_strumento("nav")
        self.combo_strumenti.setCurrentIndex(indice)
        self.combo_strumenti.blockSignals(False)

    def _popola_etichette(self) -> None:
        solo_geometrie = self.progetto.config.workflow == "geometrie"
        self.sezione_etichette.setVisible(not solo_geometrie)
        self.contenitore_etichette.setVisible(not solo_geometrie)
        while self.pannello_etichette.count():
            item = self.pannello_etichette.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.bottoni_etichetta = {}
        for e in self.progetto.config.etichette:
            testo_tasto = f"  [{e.tasto}]" if e.tasto else ""
            bottone = QPushButton(f"{e.nome}{testo_tasto}")
            bottone.setMinimumHeight(38)
            bottone.setStyleSheet(
                f"QPushButton {{ border-left: 8px solid {e.colore}; text-align:left; padding-left:12px; }}"
            )
            bottone.clicked.connect(lambda checked=False, nome=e.nome: self._etichetta_cliccata(nome))
            self.pannello_etichette.addWidget(bottone)
            self.bottoni_etichetta[e.nome] = bottone
        self.combo_classe.blockSignals(True)
        self.combo_classe.clear()
        for e in self.progetto.config.etichette:
            self.combo_classe.addItem(e.nome)
        self.combo_classe.blockSignals(False)
        if self.combo_classe.count():
            self.viewer.set_classe_attiva(self.combo_classe.currentText())

    def _azioni(self) -> None:
        toolbar = QToolBar("Azioni")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        def aggiungi(testo: str, scorciatoia: str, callback) -> None:
            azione = QAction(testo, self)
            azione.setShortcut(QKeySequence(scorciatoia))
            azione.triggered.connect(callback)
            toolbar.addAction(azione)
            return azione

        self.azione_apri = aggiungi("Apri cartella", "Ctrl+O", self.apri_cartella)
        self.azione_salva = aggiungi("Salva", "Ctrl+S", self.salva)
        self.azione_annulla = aggiungi("Annulla", "Ctrl+Z", self.annulla)
        self.azione_ripristina = aggiungi("Ripristina", "Ctrl+Y", self.ripristina)
        self.azione_config = aggiungi("Configurazione", "Ctrl+E", self.modifica_configurazione)
        aggiungi("Prossima da etichettare", "N", self.prossima_da_etichettare)

        toolbar.addWidget(self._bottone_export())

        self.combo_cursore = QComboBox()
        self.combo_cursore.setToolTip("Puntatore per gli strumenti di disegno")
        for definizione in CURSORI.values():
            self.combo_cursore.addItem(definizione.etichetta, definizione.nome)
        nome_cursore = leggi_cursore()
        indice = self.combo_cursore.findData(nome_cursore)
        self.combo_cursore.setCurrentIndex(max(indice, 0))
        self.combo_cursore.currentIndexChanged.connect(self._cursore_cambiato)
        toolbar.addWidget(self.combo_cursore)
        self.viewer.set_cursore(nome_cursore)

        for e in self.progetto.config.etichette:
            if e.tasto:
                azione = QAction(self)
                azione.setShortcut(QKeySequence(e.tasto))
                azione.triggered.connect(lambda checked=False, nome=e.nome: self._etichetta_cliccata(nome))
                self.addAction(azione)

        scorciatoie = [
            ("A", self.precedente), ("D", self.successiva),
            ("X", self._inverti_revisionare), ("Return", self._conferma_revisione),
            ("G", self._inverti_grigi), ("H", self._inverti_equalizza),
            ("R", self.reset_visualizzazione),
            ("+", lambda: self.viewer.zoom_by(1.2)),
            ("-", lambda: self.viewer.zoom_by(1 / 1.2)),
            ("Delete", self._elimina_selezionato),
            ("Escape", self._escape),
        ]
        for scorciatoia, callback in scorciatoie:
            azione = QAction(self)
            azione.setShortcut(QKeySequence(scorciatoia))
            azione.triggered.connect(callback)
            self.addAction(azione)

    def _bottone_export(self) -> QPushButton:
        bottone = QPushButton("Export")
        menu = bottone.menu()
        from PySide6.QtWidgets import QMenu

        menu = QMenu(bottone)
        definizioni = [
            ("CSV etichette", self._export_csv),
            ("COCO detection", lambda: self._export_coco(False)),
            ("COCO segmentation", lambda: self._export_coco(True)),
            ("YOLO detection", lambda: self._export_yolo(False)),
            ("YOLO segmentation", lambda: self._export_yolo(True)),
            ("LabelMe", self._export_labelme),
            ("Maschere PNG", self._export_maschere),
            ("Report statistiche", self._export_report),
            ("Visualizzazione HTML", self._export_html),
        ]
        for testo, callback in definizioni:
            menu.addAction(testo, callback)
        bottone.setMenu(menu)
        return bottone

    def _stile(self) -> None:
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #22252B; color: #ECEFF4; font-size: 13px; }
            QPushButton { background: #343942; border: 1px solid #4B515C; border-radius: 7px; padding: 7px; }
            QPushButton:hover { background: #414854; }
            QPushButton:pressed { background: #2A2E35; }
            QComboBox, QPlainTextEdit, QLineEdit { background: #17191E; border: 1px solid #4B515C; border-radius: 6px; padding: 5px; }
            QProgressBar { border: 1px solid #4B515C; border-radius: 6px; text-align: center; background: #17191E; }
            QProgressBar::chunk { background: #3CB44B; border-radius: 5px; }
            QListWidget { background: #17191E; border: 1px solid #343942; }
            QToolBar { background: #1B1E23; border-bottom: 1px solid #3A3F48; spacing: 5px; }
            QToolButton { background: #343942; border-radius: 5px; padding: 6px; }
            #titoloImmagine { font-size: 18px; font-weight: 700; }
            #sezione { font-size: 15px; font-weight: 700; }
            #badge { font-weight: 700; border-radius: 8px; padding: 8px; }
            #statistiche { background: #17191E; border-radius: 8px; padding: 10px; }
        """)

    # ------------------------------------------------------------ visualizzazione immagine

    def _immagine_visualizzata(self, originale: np.ndarray) -> np.ndarray:
        alpha = self.slider_contrasto.value() / 100.0
        beta = self.slider_luminosita.value()
        img = cv2.convertScaleAbs(originale, alpha=alpha, beta=beta)
        if self.check_grigi.isChecked():
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            if self.check_equalizza.isChecked():
                img = cv2.equalizeHist(img)
        elif self.check_equalizza.isChecked():
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            l = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(l)
            img = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)
        return img

    def _colore_record(self, record: Record) -> str:
        if record.da_revisionare:
            return COLORE_REVISIONE
        if self.progetto.config.workflow == "geometrie":
            if record.geometrie:
                return self.progetto.config.colore_di(record.geometrie[0].get("classe", ""))
            return COLORE_NON_ASSEGNATA
        if record.etichette:
            return self.progetto.config.colore_di(record.etichette[0])
        return COLORE_NON_ASSEGNATA

    def mostra_indice(self, indice: int) -> None:
        if not (0 <= indice < len(self.immagini)):
            return
        self.indice = indice
        percorso = self.immagini[indice]
        record = self.progetto.immagini[percorso.name]
        originale = self.cache.get(percorso)
        if originale is None:
            self.stato_label.setText(f"Impossibile leggere {percorso.name}")
            return

        self._caricamento_ui = True
        self.note_edit.setPlainText(record.note)
        self.check_revisione.setChecked(record.da_revisionare)
        self._caricamento_ui = False

        img = self._immagine_visualizzata(originale)
        self.viewer.set_image(img, self._colore_record(record))
        self.viewer.set_colori({e.nome: e.colore for e in self.progetto.config.etichette})
        self.viewer.mostra_annotazioni(record)

        self.titolo.setText(f"{indice + 1}/{len(self.immagini)} — {percorso.name}")
        if self.progetto.config.workflow == "geometrie":
            badge = f"{len(record.geometrie)} OGGETTI" if record.geometrie else "NON ETICHETTATA"
        else:
            badge = " • ".join(record.etichette).upper() if record.etichette else "NON ETICHETTATA"
        if record.da_revisionare:
            badge += " • DA REVISIONARE"
        if record.revisionata:
            badge += " • REV"
        self.badge.setText(badge)
        self.badge.setStyleSheet(f"background:{self._colore_record(record)}; color:white;")
        self._evidenzia_bottoni_etichette(record)

        self._aggiorna_progresso()
        self._aggiorna_statistiche()
        self._aggiorna_miniature()
        QTimer.singleShot(0, lambda: self.cache.preload(
            self.immagini[max(0, indice - PRECARICA_PRIMA):indice + PRECARICA_DOPO + 1]
        ))
        self.stato_label.setText(self._testo_stato(record))

    def _evidenzia_bottoni_etichette(self, record: Record) -> None:
        for nome, bottone in self.bottoni_etichetta.items():
            attivo = nome in record.etichette
            colore = self.progetto.config.colore_di(nome)
            spessore = 4 if attivo else 1
            bottone.setStyleSheet(
                f"QPushButton {{ border:{spessore}px solid {colore}; "
                f"border-left:10px solid {colore}; text-align:left; padding-left:12px; "
                f"font-weight:{'bold' if attivo else 'normal'}; }}"
            )

    @staticmethod
    def _testo_stato(r: Record) -> str:
        parti = [r.stato]
        if r.note:
            parti.append("con note")
        if r.da_revisionare:
            parti.append("da revisionare")
        if r.geometrie:
            parti.append(f"{len(r.geometrie)} geometrie")
        if r.misure:
            parti.append(f"{len(r.misure)} misure")
        if r.data_modifica:
            parti.append(f"modificata {r.data_modifica}")
        return " | ".join(parti)

    def _aggiorna_progresso(self) -> None:
        completate = sum(
            self._record_completato(self.progetto.immagini[p.name]) for p in self.immagini
        )
        self.progresso.setMaximum(len(self.immagini))
        self.progresso.setValue(completate)
        self.progresso.setFormat(f"{completate}/{len(self.immagini)} — %p%")

    def _aggiorna_statistiche(self) -> None:
        if not self.check_statistiche.isChecked():
            self.etichetta_statistiche.hide()
            return
        self.etichetta_statistiche.show()
        records = [self.progetto.immagini[p.name] for p in self.immagini]
        totale = len(records) or 1
        righe = ["<b>Distribuzione</b><br>"]
        for e in self.progetto.config.etichette:
            n = sum(e.nome in r.etichette for r in records)
            pct = n / totale * 100
            righe.append(f'<span style="color:{e.colore}">●</span> {e.nome}: <b>{n}</b> ({pct:.1f}%)<br>')
        righe.append(f"<br>Da revisionare: <b>{sum(r.da_revisionare for r in records)}</b>")
        righe.append(f"<br>Revisionate: <b>{sum(r.revisionata for r in records)}</b>")
        righe.append(f"<br>Geometrie: <b>{sum(len(r.geometrie) for r in records)}</b>")
        righe.append(f"<br>Misure: <b>{sum(len(r.misure) for r in records)}</b>")
        self.etichetta_statistiche.setText("".join(righe))

    def _aggiorna_miniature(self) -> None:
        self.miniature.clear()
        inizio = max(0, self.indice - 3)
        fine = min(len(self.immagini), self.indice + 4)
        from labeling_tool.image_view import cv_to_pixmap

        for i in range(inizio, fine):
            percorso = self.immagini[i]
            record = self.progetto.immagini[percorso.name]
            item = QListWidgetItem(percorso.name)
            item.setData(Qt.UserRole, i)
            img = self.cache.get(percorso)
            if img is not None:
                item.setIcon(cv_to_pixmap(img).scaled(120, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            item.setForeground(QColor(self._colore_record(record)))
            if i == self.indice:
                item.setBackground(QColor("#4A505B"))
            self.miniature.addItem(item)

    def _miniatura_cliccata(self, item: QListWidgetItem) -> None:
        self.mostra_indice(int(item.data(Qt.UserRole)))

    def _visualizzazione_modificata(self) -> None:
        originale = self.cache.get(self.immagini[self.indice])
        if originale is None:
            return
        record = self.progetto.immagini[self.immagini[self.indice].name]
        self.viewer.set_image(self._immagine_visualizzata(originale), self._colore_record(record))
        self.viewer.mostra_annotazioni(record)

    def reset_visualizzazione(self) -> None:
        self.slider_luminosita.setValue(0)
        self.slider_contrasto.setValue(100)
        self.check_grigi.setChecked(False)
        self.check_equalizza.setChecked(False)
        self.viewer.reset_view()

    def _inverti_grigi(self) -> None:
        self.check_grigi.setChecked(not self.check_grigi.isChecked())

    def _inverti_equalizza(self) -> None:
        self.check_equalizza.setChecked(not self.check_equalizza.isChecked())

    # ------------------------------------------------------------ modifica record

    def _record_corrente(self) -> Record:
        return self.progetto.immagini[self.immagini[self.indice].name]

    def _modifica_record(self, nuovo: Record) -> None:
        record = self._record_corrente()
        prima = record.copia()
        nuovo.data_modifica = adesso_iso()
        nuovo.etichettatore = self.progetto.config.etichettatore
        if nuovo == prima:
            return
        self.progetto.immagini[record.nome] = nuovo
        self.storico.append(Azione(self.indice, prima, nuovo.copia()))
        self.storico_redo.clear()
        self._imposta_non_salvato()
        self.aggiorna_filtri(mantieni_corrente=True)

    def _etichetta_cliccata(self, nome: str) -> None:
        record = self._record_corrente()
        nuovo = record.copia()
        if self.progetto.config.multi_label:
            if nome in nuovo.etichette:
                nuovo.etichette.remove(nome)
            else:
                nuovo.etichette.append(nome)
        else:
            nuovo.etichette = [] if nuovo.etichette == [nome] else [nome]
        if nuovo.etichette:
            nuovo.stato = "completata"
        elif nuovo.da_revisionare:
            nuovo.stato = "da_revisionare"
        else:
            nuovo.stato = "non_etichettata"
        self._modifica_record(nuovo)
        self.mostra_indice(self.indice)
        self._programma_salvataggio()
        if not self.progetto.config.multi_label and nuovo.etichette:
            self._successiva_preferendo_da_fare()

    def _toggle_revisionare(self) -> None:
        if self._caricamento_ui:
            return
        record = self._record_corrente()
        nuovo = record.copia()
        nuovo.da_revisionare = self.check_revisione.isChecked()
        if nuovo.da_revisionare and not nuovo.etichette:
            nuovo.stato = "da_revisionare"
        elif nuovo.etichette:
            nuovo.stato = "completata"
        else:
            nuovo.stato = "non_etichettata"
        self._modifica_record(nuovo)
        self.mostra_indice(self.indice)
        self._programma_salvataggio()

    def _inverti_revisionare(self) -> None:
        self.check_revisione.setChecked(not self.check_revisione.isChecked())

    def _conferma_revisione(self) -> None:
        record = self._record_corrente()
        nuovo = record.copia()
        nuovo.revisionata = True
        nuovo.da_revisionare = False
        nuovo.stato = "completata" if nuovo.etichette else "non_etichettata"
        self._modifica_record(nuovo)
        self.mostra_indice(self.indice)
        self._programma_salvataggio()

    def _note_modificate(self) -> None:
        if self._caricamento_ui:
            return
        record = self._record_corrente()
        nuovo = record.copia()
        nuovo.note = self.note_edit.toPlainText().strip()
        self._modifica_record(nuovo)
        self._programma_salvataggio()

    def _geometria_aggiunta(self, geometria: dict) -> None:
        record = self._record_corrente()
        nuovo = record.copia()
        nuovo.geometrie.append(geometria)
        self._modifica_record(nuovo)
        self.viewer.mostra_annotazioni(nuovo)
        self._programma_salvataggio()

    def _geometria_modificata(self, indice: int, geometria: dict) -> None:
        record = self._record_corrente()
        nuovo = record.copia()
        nuovo.geometrie[indice] = geometria
        self._modifica_record(nuovo)
        self.viewer.mostra_annotazioni(nuovo)
        self._programma_salvataggio()

    def _misura_aggiunta(self, misura: dict) -> None:
        record = self._record_corrente()
        nuovo = record.copia()
        nuovo.misure.append(Misura.da_dict(misura))
        self._modifica_record(nuovo)
        self.viewer.mostra_annotazioni(nuovo)
        self._programma_salvataggio()

    def _elimina_selezionato(self) -> None:
        indice_box = self.viewer.indice_selezionato()
        record = self._record_corrente()
        nuovo = record.copia()
        if indice_box >= 0 and nuovo.geometrie:
            nuovo.geometrie.pop(indice_box)
        elif nuovo.misure:
            nuovo.misure.pop()
        elif nuovo.geometrie:
            nuovo.geometrie.pop()
        else:
            nuovo.etichette = []
            nuovo.stato = "non_etichettata"
        self._modifica_record(nuovo)
        self.viewer.mostra_annotazioni(nuovo)
        self.mostra_indice(self.indice)
        self._programma_salvataggio()

    def _escape(self) -> None:
        self.viewer._annulla_disegno_corrente()

    def _strumento_cambiato(self) -> None:
        self.viewer.set_strumento(self.combo_strumenti.currentData())

    def _cursore_cambiato(self) -> None:
        nome = self.combo_cursore.currentData()
        self.viewer.set_cursore(nome)
        salva_cursore(nome)
        if self.combo_strumenti.currentData() == "nav":
            self.stato_label.setText(
                "Puntatore applicato agli strumenti di disegno: scegline uno (es. Disegna box) per vederlo"
            )

    def _dimensioni_cambiate(self) -> None:
        self.viewer.set_mostra_dimensioni(self.check_dimensioni.isChecked())
        self.viewer.mostra_annotazioni(self._record_corrente())

    def _classe_cambiata(self) -> None:
        nome = self.combo_classe.currentText()
        self.viewer.set_classe_attiva(nome)
        # un box selezionato cambia etichetta quando si sceglie un'altra classe
        indice_box = self.viewer.indice_selezionato()
        if indice_box >= 0:
            record = self._record_corrente()
            nuovo = record.copia()
            if 0 <= indice_box < len(nuovo.geometrie) and nuovo.geometrie[indice_box].get("tipo") == "box":
                nuovo.geometrie[indice_box]["classe"] = nome
                self._modifica_record(nuovo)
                self.viewer.mostra_annotazioni(nuovo)
                self._programma_salvataggio()

    # ------------------------------------------------------------ salvataggio

    def _programma_salvataggio(self) -> None:
        self.timer_salvataggio.start(350)

    def _imposta_non_salvato(self) -> None:
        self.salvato = False
        self.salvataggio_label.setText("Modifiche non salvate")
        self.salvataggio_label.setStyleSheet("color:#F39C12; font-weight:bold;")

    def salva(self) -> None:
        try:
            self.cartella_dati.mkdir(parents=True, exist_ok=True)
            self.progetto.salva_atomico(self.percorso_progetto)
            self.salvato = True
            self.salvataggio_label.setText("Salvato")
            self.salvataggio_label.setStyleSheet("color:#3CB44B; font-weight:bold;")
        except OSError as errore:
            self.salvataggio_label.setText("Errore salvataggio")
            QMessageBox.critical(self, "Errore", f"Impossibile salvare il progetto:\n{errore}")
            return
        self._scrivi_csv_dati()

    def _scrivi_csv_dati(self) -> None:
        """File sempre aggiornati nella cartella dati: dettaglio per immagine,
        statistiche e visualizzazione HTML autonoma (da condividere senza
        installare il programma)."""
        nomi = [p.name for p in self.immagini]
        try:
            esporta_csv(self.progetto, nomi, self.cartella_dati / "etichette.csv")
            report_statistiche(self.progetto, nomi, self.cartella_dati / "statistiche.csv")
        except OSError as errore:
            self.stato_label.setText(f"Avviso: CSV non aggiornati ({errore})")
        try:
            esporta_html(self.progetto, nomi, self.cartella, self.cartella_dati / "visualizzazione.html")
        except (OSError, ValueError) as errore:
            self.stato_label.setText(f"Avviso: visualizzazione HTML non aggiornata ({errore})")

    # ------------------------------------------------------------ undo/redo

    def annulla(self) -> None:
        if not self.storico:
            return
        azione = self.storico.pop()
        self.progetto.immagini[azione.prima.nome] = azione.prima
        self.storico_redo.append(azione)
        self.indice = azione.indice
        self._imposta_non_salvato()
        self.aggiorna_filtri(mantieni_corrente=True)
        self.mostra_indice(self.indice)
        self._programma_salvataggio()

    def ripristina(self) -> None:
        if not self.storico_redo:
            return
        azione = self.storico_redo.pop()
        self.progetto.immagini[azione.dopo.nome] = azione.dopo
        self.storico.append(azione)
        self.indice = azione.indice
        self._imposta_non_salvato()
        self.aggiorna_filtri(mantieni_corrente=True)
        self.mostra_indice(self.indice)
        self._programma_salvataggio()

    # ------------------------------------------------------------ navigazione e filtri

    def aggiorna_filtri(self, *args, mantieni_corrente: bool = False) -> None:
        testo = self.combo_filtro.currentText() if hasattr(self, "combo_filtro") else "Tutte"
        self.indici_visibili = []
        for i, percorso in enumerate(self.immagini):
            r = self.progetto.immagini[percorso.name]
            ok = (
                testo == "Tutte"
                or (testo == "Non etichettate" and not self._record_completato(r))
                or (testo == "Da revisionare" and r.da_revisionare)
                or (testo == "Revisionate" and r.revisionata)
                or (testo == "Con note" and bool(r.note))
                or (testo == "Con geometrie" and bool(r.geometrie))
                or (testo.startswith("Etichetta: ") and testo[len("Etichetta: "):] in r.etichette)
            )
            if ok:
                self.indici_visibili.append(i)
        if not mantieni_corrente and self.indice not in self.indici_visibili and self.indici_visibili:
            self.mostra_indice(self.indici_visibili[0])

    def _passo_filtrato(self, direzione: int) -> None:
        lista = self.indici_visibili or list(range(len(self.immagini)))
        if self.indice not in lista:
            if lista:
                self.mostra_indice(lista[0])
            return
        pos = lista.index(self.indice)
        nuovo = pos + direzione
        if 0 <= nuovo < len(lista):
            self.mostra_indice(lista[nuovo])
        else:
            self.stato_label.setText("Limite del filtro raggiunto")

    def precedente(self) -> None:
        self._passo_filtrato(-1)

    def successiva(self) -> None:
        self._passo_filtrato(1)

    def _successiva_preferendo_da_fare(self) -> None:
        for i in range(self.indice + 1, len(self.immagini)):
            r = self.progetto.immagini[self.immagini[i].name]
            if not self._record_completato(r) and not r.da_revisionare:
                self.mostra_indice(i)
                return
        self.successiva()

    def prossima_da_etichettare(self) -> None:
        for offset in range(1, len(self.immagini) + 1):
            i = (self.indice + offset) % len(self.immagini)
            r = self.progetto.immagini[self.immagini[i].name]
            if not self._record_completato(r):
                self.mostra_indice(i)
                return
        self.stato_label.setText("Tutte le immagini sono etichettate")

    # ------------------------------------------------------------ configurazione ed export

    def modifica_configurazione(self) -> None:
        dialogo = EditorConfigurazione(self.progetto.config, self)
        if dialogo.exec() != EditorConfigurazione.Accepted or dialogo.nuova_config is None:
            return
        vecchio_nome = self.progetto.config.nome_progetto
        self.progetto.config = dialogo.nuova_config
        if vecchio_nome != self.progetto.config.nome_progetto:
            percorso_vecchio = self.percorso_progetto
            self.percorso_progetto = self.cartella / f"{self.progetto.config.nome_progetto}.progetto.json"
            try:
                percorso_vecchio.unlink()
            except OSError:
                pass
        self.immagini = elenco_immagini(
            self.cartella, set(self.progetto.config.estensioni), self.progetto.config.ricorsivo
        )
        self.progetto.reindicizza(self.immagini)
        self.viewer.set_unita(self.progetto.config.unita_misura, self.progetto.config.scala_px_per_unita)
        self._popola_etichette()
        self._popola_filtri()
        self._popola_strumenti()
        self.setWindowTitle(f"Label Anything {versione_app()} - {self.progetto.config.nome_progetto}")
        self.indice = min(self.indice, max(0, len(self.immagini) - 1))
        self.salva()
        self.mostra_indice(self.indice)
        self.stato_label.setText("Configurazione aggiornata")

    def _nomi_visibili(self) -> List[str]:
        return [self.immagini[i].name for i in (self.indici_visibili or range(len(self.immagini)))]

    def _dimensioni_visibili(self) -> dict:
        nomi = set(self._nomi_visibili())
        dimensioni = {}
        for percorso in self.immagini:
            if percorso.name not in nomi:
                continue
            img = leggi_cv(percorso)
            if img is not None:
                dimensioni[percorso.name] = (img.shape[1], img.shape[0])
        return dimensioni

    def _destinazione(self, messaggio: str) -> Optional[Path]:
        cartella = QFileDialog.getExistingDirectory(
            self, messaggio, str(self.cartella),
            QFileDialog.Option.DontUseNativeDialog,
        )
        return Path(cartella) if cartella else None

    def _export_csv(self) -> None:
        dest = self._destinazione("Cartella per il CSV")
        if not dest:
            return
        percorso = dest / "etichette.csv"
        esporta_csv(self.progetto, self._nomi_visibili(), percorso)
        self.stato_label.setText(f"Esportato {percorso}")

    def _export_coco(self, segmentazione: bool) -> None:
        dest = self._destinazione("Cartella per l'export COCO")
        if not dest:
            return
        percorso = dest / ("coco_segmentation.json" if segmentazione else "coco_detection.json")
        esporta_coco(
            self.progetto, self._nomi_visibili(), percorso,
            segmentazione=segmentazione, dimensioni=self._dimensioni_visibili(),
        )
        self.stato_label.setText(f"Esportato {percorso}")

    def _export_yolo(self, segmentazione: bool) -> None:
        dest = self._destinazione("Cartella per l'export YOLO")
        if not dest:
            return
        cartella = dest / ("yolo_seg" if segmentazione else "yolo_det")
        esporta_yolo(
            self.progetto, self._nomi_visibili(), cartella,
            segmentazione=segmentazione, dimensioni=self._dimensioni_visibili(),
        )
        self.stato_label.setText(f"Esportato {cartella}")

    def _export_labelme(self) -> None:
        dest = self._destinazione("Cartella per l'export LabelMe")
        if not dest:
            return
        cartella = dest / "labelme"
        esporta_labelme(self.progetto, self._nomi_visibili(), cartella, dimensioni=self._dimensioni_visibili())
        self.stato_label.setText(f"Esportato {cartella}")

    def _export_maschere(self) -> None:
        dest = self._destinazione("Cartella per le maschere PNG")
        if not dest:
            return
        cartella = dest / "maschere"
        esporta_maschere(self.progetto, self._nomi_visibili(), cartella, dimensioni=self._dimensioni_visibili())
        self.stato_label.setText(f"Esportato {cartella}")

    def _export_html(self) -> None:
        dest = self._destinazione("Cartella per la visualizzazione HTML")
        if not dest:
            return
        percorso = dest / "visualizzazione.html"
        esporta_html(self.progetto, self._nomi_visibili(), self.cartella, percorso)
        self.stato_label.setText(f"Esportato {percorso}")

    def _export_report(self) -> None:
        dest = self._destinazione("Cartella per il report statistiche")
        if not dest:
            return
        percorso = dest / "report_statistiche.csv"
        report_statistiche(self.progetto, self._nomi_visibili(), percorso)
        self.stato_label.setText(f"Esportato {percorso}")

    def apri_cartella(self) -> None:
        cartella = QFileDialog.getExistingDirectory(
            self, "Seleziona la cartella delle immagini", str(self.cartella),
            QFileDialog.Option.DontUseNativeDialog,
        )
        if not cartella:
            return
        self.salva()
        try:
            nuova = FinestraPrincipale.apri_progetto(Path(cartella))
        except (FileNotFoundError, NotADirectoryError, RuntimeError) as errore:
            QMessageBox.critical(self, "Errore", str(errore))
            return
        nuova.show()
        self._finestra_figlia = nuova
        self.close()

    def closeEvent(self, event) -> None:
        if not self.salvato:
            self.salva()
        event.accept()
