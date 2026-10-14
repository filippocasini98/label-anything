# Design: Labeling Tool universale e configurabile

Data: 2026-10-14
Stato: approvato dall'utente

## Obiettivo

Sostituire `etichettatura_immagini_pyside6.py` con uno strumento desktop (PySide6 + OpenCV) per etichettare e analizzare qualsiasi tipo di immagine, interamente configurabile da GUI, senza file di configurazione da editare a mano.

## Requisiti (confermati con l'utente)

1. Classificazione multi-label: più etichette per immagine, tasti configurabili che attivano/disattivano.
2. Annotazioni geometriche: bounding box ridimensionabili/spostabili e poligoni, con classe per oggetto.
3. Strumenti di misura: distanza tra due punti (px + unità configurata via scala px/unità), area poligonale, conteggio oggetti a clic. Le misure sono salvate e rimostrate.
4. Configurazione solo GUI: wizard al primo avvio + editor integrato applicabile a caldo.
5. Persistenza: progetto JSON nella cartella immagini (config + annotazioni), salvataggio atomico, autosave 350 ms.
6. Export: CSV, COCO detection/segmentation, YOLO det/seg, LabelMe, maschere PNG indicizzate.
7. Analisi immagine: luminosità, contrasto, grigi, equalizzazione CLAHE, zoom/pan; statistiche live ed esportazione report.

## Architettura

Pacchetto modulare `labeling_tool/` nella cartella Labelling, con launcher `run_labeling.py`:

- `main.py`: entry point, avvio Qt.
- `config.py`: schema configurazione (ProgettoConfig, LabelDef: nome/colore/tasto), load/save JSON, default, validazione.
- `model.py`: Record per immagine (etichette: lista, stato, note, flag revisione, geometrie, misure), undo/redo a stack di azioni, confronto/copie.
- `io_utils.py`: scansione immagini con estensioni configurabili e opzione sottocartelle ricorsive, ordinamento naturale, cache LRU (OpenCV).
- `image_view.py`: QGraphicsView con zoom/pan, disegno/modifica di box (maniglie) e poligoni, overlay misure.
- `settings_dialog.py`: wizard primo avvio + editor configurazione.
- `export.py`: funzioni pure di esportazione (CSV, COCO, YOLO, LabelMe, maschere).
- `main_window.py`: finestra principale, toolbar, scorciatoie, filtri, statistiche, autosave.

## Flusso dati

1. Avvio: wizard se non esiste progetto JSON; altrimenti caricamento progetto.
2. Scansione cartella (ricorsiva opzionale) -> lista immagini ordinate naturalmente.
3. Ogni modifica crea un'azione undo/redo e programma l'autosave atomico.
4. Export su richiesta verso una cartella scelta dall'utente.

## Configurazione (dettaglio)

Contenuto: nome progetto, etichettatore, workflow (classificazione / classificazione+geometrie), multi-label on/off, etichette (nome, colore, tasto, attiva in geometrie), estensioni immagine, scansione ricorsiva, unità di misura e scala px/unità, strumenti abilitati (misure, filtri visualizzazione), CSV di destinazione opzionale.

Editor: dialog raggiungibile da toolbar; modifiche applicate a caldo (riabilitazione scorciatoie, ricostruzione pannelli etichette); il JSON del progetto viene aggiornato al salvataggio.

## Formato progetto JSON (schema v1)

```json
{
  "schema_version": 1,
  "config": { "nome_progetto": "...", "etichettatore": "...", "multi_label": true,
              "etichette": [{"nome": "sana", "colore": "#3CB44B", "tasto": "1"}],
              "unita_misura": "mm", "scala_px_per_unita": 0.5, "estensioni": [".jpg"],
              "ricorsivo": false, "workflow": "classificazione+geometrie" },
  "immagini": {
    "nome_file.jpg": {
      "etichette": ["sana"], "stato": "completata", "note": "",
      "da_revisionare": false, "revisionata": false,
      "data_modifica": "...", "etichettatore": "...",
      "geometrie": [{"tipo": "box", "classe": "esca", "x": 10, "y": 20, "w": 100, "h": 80},
                    {"tipo": "poligono", "classe": "esca", "punti": [[x, y], ...]}],
      "misure": [{"tipo": "distanza", "punti": [[x, y], [x, y]], "valore_px": 120.5},
                 {"tipo": "area", "punti": [[x, y], ...]},
                 {"tipo": "conteggio", "punti": [[x, y], ...]}]
    }
  }
}
```

## Gestione errori

- Cartella mancante o vuota: messaggio e ritorno al wizard.
- Immagine non leggibile: segnalata in status bar, il record resta accessibile.
- Salvataggio fallito: indicatore di errore, nessuna perdita dati (autosalvataggio riprovato alla modifica successiva).
- Progetto JSON corrotto: backup del file e ripartenza dai soli dati leggibili con avviso.

## Test

- pytest sulla logica pura: round-trip configurazione, modello/undo-redo, esportazioni (contenuto COCO/YOLO/LabelMe valido su dati campione), calcolo misure, scansione immagini.
- Verifica GUI manuale con una cartella di prova generata.

## Fuori scope (per ora)

- Segmentazione a livello di pixel con maschere disegnate a pennello.
- Collaborazione multiutente o server.
- Annotazione video.
