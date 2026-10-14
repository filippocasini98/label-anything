# Labeling Tool universale - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Applicazione desktop PySide6/OpenCV per etichettare (multi-label, box, poligoni), misurare e analizzare qualsiasi immagine, interamente configurabile da GUI, con progetto JSON e export multipli.

**Architecture:** Pacchetto `labeling_tool` con logica pura separata dalla GUI: `config.py` (schema+load/save), `model.py` (Record, undo/redo, progetto), `io_utils.py` (scansione, cache LRU), `export.py` (CSV/COCO/YOLO/LabelMe/maschere, funzioni pure), GUI in `image_view.py`, `settings_dialog.py`, `main_window.py`. Launcher `run_labeling.py`.

**Tech Stack:** Python 3, PySide6 >= 6.5, opencv-python, numpy, pytest per la logica pura.

**Nota ambiente:** la cartella Labelling NON è un repo git: al posto dei commit, ogni task termina con la verifica dei test (checkpoint).

## Contratti principali (usati da tutti i task)

```python
# config.py
@dataclass
class EtichettaDef:  # nome univoco, colore hex "#RRGGBB", tasto shortcut
    nome: str; colore: str; tasto: str
@dataclass
class ProgettoConfig:
    nome_progetto: str; etichettatore: str; multi_label: bool
    workflow: str  # "classificazione" | "classificazione+geometrie"
    etichette: List[EtichettaDef]
    estensioni: List[str]; ricorsivo: bool
    unita_misura: str; scala_px_per_unita: float
    misure_abilitate: bool; filtri_abilitati: bool
    def valida() -> List[str]  # lista errori (nomi duplicati, tasti duplicati, colore non hex)
def config_da_dict(d) -> ProgettoConfig
def config_in_dict(c: ProgettoConfig) -> dict

# model.py
@dataclass
class Geometria:  # tipo "box" (x,y,w,h float) | "poligono" (punti List[List[float]])
@dataclass
class Misura:     # tipo "distanza"|"area"|"conteggio", punti, valore_px (distanza) o None
@dataclass
class Record:     # nome, etichette List[str], stato, note, da_revisionare,
                  # revisionata, data_modifica, etichettatore, geometrie, misure
class Progetto:   # config + immagini: Dict[nome, Record]
    @staticmethod carica(path: Path) -> "Progetto"   # JSON; se corrotto: backup e progetto vuoto
    salva_atomico(path: Path)
    reindicizza(percorsi: List[Path])  # aggiunge record mancanti, rimuove orfani (a) opzionale
class Storico:    # undo/redo a Azione (indice, prima: Record, dopo: Record)

# io_utils.py
def elenco_immagini(cartella: Path, estensioni: Set[str], ricorsivo: bool) -> List[Path]
def chiave_naturale(s: str)
class ImageCache  # LRU su leggi_cv (OpenCV, gestisce percorsi unicode)

# export.py (funzioni pure, nessuna dipendenza Qt)
def esporta_csv(progetto, percorsi: List[Path], dest: Path)
def esporta_coco(progetto, percorsi, dest, segmentazione: bool, copia_immagini: bool)
def esporta_yolo(progetto, percorsi, dest, segmentazione: bool, copia_immagini: bool)
def esporta_labelme(progetto, percorsi, dest, copia_immagini: bool)
def esporta_maschere(progetto, percorsi, dest)
def report_statistiche(progetto, percorsi, dest: Path)
def distanza_px(p1, p2) -> float          # in model.py, usata anche dalle misure
def area_poligono(punti) -> float          # shoe-lace; in model.py
```

## Task 1: Skeleton + config.py (TDD)

**Files:** Create `labeling_tool/__init__.py`, `labeling_tool/config.py`, `tests/test_config.py`, `pytest.ini`.

- [ ] Scrivere `tests/test_config.py`: round-trip `config_in_dict`/`config_da_dict`, `valida()` con nome duplicato, tasto duplicato, colore non hex, workflow non valido; default ragionevoli (multi_label False, estensioni jpg/png/..., scala 1.0).
- [ ] `pytest tests/test_config.py` -> FAIL (modulo mancante).
- [ ] Implementare `config.py` completo dei contratti sopra.
- [ ] `pytest tests/test_config.py` -> PASS.

## Task 2: io_utils.py (TDD)

**Files:** Create `labeling_tool/io_utils.py`, `tests/test_io_utils.py`.

- [ ] Test: `chiave_naturale("img2" ) < chiave_naturale("img10")`; `elenco_immagini` con tmp_path: filtra estensioni (case-insensitive), ordina naturale, rispetta `ricorsivo=True` (include sottocartelle) e False.
- [ ] Run pytest -> FAIL.
- [ ] Implementare `elenco_immagini` (rglob se ricorsivo), `chiave_naturale`, `leggi_cv` (np.fromfile+imdecode, None su errore), `ImageCache` LRU con `get`/`preload` e `max_items` configurabile.
- [ ] Run pytest -> PASS.

## Task 3: model.py con misure (TDD)

**Files:** Create `labeling_tool/model.py`, `tests/test_model.py`.

- [ ] Test: round-trip Progetto (config + 1 record con geometrie e misure) tramite `carica`/`salva_atomico` su tmp_path; JSON corrotto -> backup `.corrotto` e progetto vuoto; `distanza_px((0,0),(3,4))==5`; `area_poligono` quadrato 10x10 == 100; `Storico.annulla/ripristina` ripristina il record precedente; `reindicizza` aggiunge i nuovi e segna gli orfani con `stato="rimossa"` (li conserva, non li cancella).
- [ ] Run pytest -> FAIL.
- [ ] Implementare dataclass, `Progetto`, `Storico`, `distanza_px`, `area_poligono`, `salva_atomico` (tempfile + os.replace + fsync).
- [ ] Run pytest -> PASS.

## Task 4: export.py (TDD)

**Files:** Create `labeling_tool/export.py`, `tests/test_export.py`.

- [ ] Test su progetto campione (2 immagini, 1 box, 1 poligono, 1 misura, 2 etichette):
  CSV con colonne "Nome Immagine","Etichette","Stato","Note","Da revisionare","Revisionata","Data modifica","Etichettatore","Geometrie","Misure";
  COCO detection: `images`, `annotations` con bbox `[x,y,w,h]`, `categories` in ordine etichette; COCO segmentation: `segmentation` flat;
  YOLO det: `classes.txt` + `.txt` normalizzati per immagine; YOLO seg con maschere poligono normalizzate;
  LabelMe: JSON per immagine con `shapes` (rectangle/polygon) e `imageWidth/Height`;
  maschere PNG indicizzate (colore = indice classe +1); `report_statistiche` produce CSV con conteggi per etichetta e stato.
- [ ] Run pytest -> FAIL.
- [ ] Implementare con solo stdlib + cv2/numpy; dimensioni immagine via `leggi_cv` quando servono (parametro `dimensioni: Dict[nome,(w,h)]` per purità nei test).
- [ ] Run pytest -> PASS.

## Task 5: image_view.py (GUI, verifica manuale)

**Files:** Create `labeling_tool/image_view.py`.

- [ ] `ImageViewer(QGraphicsView)`: pixmap item, zoom wheel (0.1-20x), pan scroll-hand, doppio click reset, bordo colorato per stato (come script attuale).
- [ ] Livello annotazioni: QGraphicsItemGroup per box (QGraphicsRectItem con 8 maniglie di resize + drag spostamento, clamp entro immagine) e poligoni (QGraphicsPolygonItem, creazione a clic, chiusura Invio, annulla Esc).
- [ ] Overlay misure: linea distanza con etichetta valore px/unita, area con valore, conteggio con marker numerati.
- [ ] Segnali: `geometriaModificata(dict)`, `misuraCompletata(dict)`, `selezioneCambiata`.
- [ ] API: `set_image(np.ndarray, colore_bordo)`, `mostra_annotazioni(record)`, `set_stumento("nav"|"box"|"poligono"|"distanza"|"area"|"conteggio")`, `set_classe_attiva(nome)`.
- [ ] Verifica: script temporaneo `scratchpad/check_view.py` che apre la finestra con immagine di prova e disegna; verifica manuale a schermo.

## Task 6: settings_dialog.py (GUI)

**Files:** Create `labeling_tool/settings_dialog.py`.

- [ ] `WizardProgetto(QDialog)`: cartella (QFileDialog, indicazione scansione ricorsiva), nome progetto, etichettatore, workflow, multi-label, tabella etichette (nome/colore QColorDialog/tasto QKeySequenceEdit), estensioni (checkbox), unita + scala (QDoubleSpinBox), misure/filtri on-off.
- [ ] `EditorConfigurazione(QDialog)`: stessi controlli pre-popolati; ritorna nuova `ProgettoConfig` solo se `valida()` vuota, altrimenti messaggi inline.
- [ ] Verifica: import e costruzione dialog senza errori in test headless (istanziazione QApplication offscreen `QT_QPA_PLATFORM=offscreen`).

## Task 7: main_window.py (GUI)

**Files:** Create `labeling_tool/main_window.py`, `labeling_tool/main.py`, `run_labeling.py`, `requirements.txt`.

- [ ] Assembla: toolbar (apri, salva, annulla/ripristina, editor configurazione, export menu, statistiche report), pannello etichette dinamiche da config (toggle in multi-label, radio in mono-label), note, filtri, slider luminosita/contrasto, checkbox grigi/equalizza, statistiche live, miniature, progresso, status bar con stato salvataggio.
- [ ] Autosave QTimer 350 ms + salvataggio su closeEvent; undo/redo su ogni modifica record; scorciatoie dinamiche dai tasti configurati + A/D navigazione, N prossima non etichettata, X revisione, Invio conferma revisione, R reset visualizzazione, +/- zoom, Delete rimuove etichette/geometria selezionata.
- [ ] Gestione immagini: cache LRU, precaricamento vicine, filtri per stato/etichetta.
- [ ] All'avvio: cerca `*.progetto.json` nella cartella; se assente parte il wizard.
- [ ] Verifica manuale con cartella di prova generata (`scratchpad/cartella_prova/` con 5 immagini sintetiche via cv2).

## Task 8: verifica finale

- [ ] `pytest` completo verde (config, io_utils, model, export).
- [ ] Run GUI su cartella di prova: wizard, etichettatura mono e multi, box, poligono, misure, statistiche, export CSV/COCO/YOLO/LabelMe/maschere, undo/redo, autosave riapertura progetto.
- [ ] Aggiornare README con avvio e scorciatoie.
