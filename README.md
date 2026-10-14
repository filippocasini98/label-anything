# Label Anything

Strumento desktop (PySide6 + OpenCV) per etichettare, annotare e analizzare qualsiasi tipo di immagine. Interamente configurabile da GUI: nessun file di configurazione da editare a mano.

## Requisiti

Python 3.9 o superiore (macOS, Windows o Linux). Tutto il resto viene installato automaticamente.

## Scarica

**[⬇️ Scarica l'ultima versione](https://github.com/filippocasini98/label-anything/releases/latest)** dalla pagina Releases (asset *Source code*), scompatta lo zip e prosegui con la prima installazione.

Oppure scarica e prepara tutto con un unico comando:

**macOS / Linux:**

```bash
curl -fsSL https://raw.githubusercontent.com/filippocasini98/label-anything/main/install.sh | bash
```

**Windows:** scarica [`install.bat`](https://github.com/filippocasini98/label-anything/raw/main/install.bat) ed eseguilo con doppio clic.

## Prima installazione (una volta sola)

Doppio clic su `setup.command` (macOS) o `setup.bat` (Windows): crea l'ambiente virtuale e installa PySide6, OpenCV e numpy.

## Avvio

Doppio clic su `start.command` (macOS) o `start.bat` (Windows), oppure:

```bash
./venv/bin/python run_labeling.py
```

Il programma **ricorda l'ultima cartella aperta** e riparte direttamente da lì: il selettore di cartelle appare solo al primo avvio (o con `Ctrl+O` per cambiare cartella). Puoi anche passare la cartella da riga di comando: `python run_labeling.py /percorso/cartella`.

Al primo avvio in una cartella: seleziona la cartella immagini, il wizard crea il progetto (`nome.progetto.json` dentro la cartella). Riaprendo la cartella il progetto viene caricato automaticamente.

### Applicazione macOS a doppio clic (facoltativo)

Per un lancio senza terminale puoi creare un bundle `Label Anything.app`:

```bash
mkdir -p "Label Anything.app/Contents/MacOS"
cat > "Label Anything.app/Contents/MacOS/LabelAnything" <<'SH'
#!/bin/bash
exec "/percorso/del/progetto/venv/bin/python" "/percorso/del/progetto/run_labeling.py" "$@"
SH
chmod +x "Label Anything.app/Contents/MacOS/LabelAnything"
```

con un `Contents/Info.plist` che punti a `CFBundleExecutable` `LabelAnything` (vedi la struttura standard dei bundle macOS).

## Funzioni

- **Classificazione**: etichette con tasti scorciatoia configurabili; modalità mono-label (auto-avanzamento dopo l'assegnazione) o multi-label (toggle).
- **Geometrie** (workflow "classificazione + geometrie" oppure "solo geometrie"): bounding box trascinate sullo schermo, ridimensionabili con 8 maniglie e spostabili; poligoni a clic, chiusi con Invio. Classe per oggetto selezionabile. La **grandezza di ogni geometria** è mostrata sull'immagine, riportata in `etichette.csv` e aggregata per classe in `statistiche.csv`: per i box larghezza/altezza/area, per i poligoni bounding box e area (media, minimo, massimo, in px o nell'unità configurata).
- **Misure** (se abilitate): distanza tra due clic (px e unità configurabile via scala px/unità), area di poligono, conteggio oggetti a clic, **dimensioni di oggetti** (rettangolo trascinato: larghezza, altezza e area in px e nell'unità configurata - utile ad es. per misurare stomi in immagini al microscopio elettronico). Tutte le misure sono salvate e rimostrate.
- **Analisi visiva**: luminosità, contrasto, scala di grigi, equalizzazione CLAHE, zoom/pan.
- **Statistiche**: distribuzione etichette, progresso, revisioni, conteggio geometrie e misure; esportabili in CSV.
- **Filtri**: per stato (non etichettate, da revisionare, revisionate, con note, con geometrie) e per etichetta.
- **Undo/redo** su ogni modifica, autosave atomico a 350 ms e su chiusura.
- **Workflow "Solo geometrie"**: disegno di box e poligoni senza classificazione dell'immagine; la sezione etichette si nasconde e un'immagine è completata quando ha geometrie. Le etichette restano obblatorie perché sono le classi degli oggetti.
- **Selettore del puntatore**: 8 cursori per gli strumenti di disegno e misura (crosshair, croce a tutto schermo, precision, annotation, target, punto, freccia, invisibile), selezionabili al volo da un combobox in toolbar e salvati come preferenza globale.

## Scorciatoie

- `Ctrl+O` apri cartella, `Ctrl+S` salva, `Ctrl+Z`/`Ctrl+Y` annulla/ripristina
- `Ctrl+E` configurazione, `N` prossima da etichettare
- Tasti `1..9` (configurabili): assegna/toggle etichetta
- `A`/`D` precedente/successiva, `X` da revisionare, `Invio` conferma revisione
- `G` grigi, `H` equalizza, `R` ripristina visualizzazione, `+`/`-` zoom
- `Invio` chiude poligono/area, `Esc` annulla disegno, `Delete` elimina geometria/misura selezionata (o le etichette)
- Il poligono/area si chiude anche con un clic sul primo vertice oppure con doppio clic; il combo etichette cambia la classe del box selezionato

## Dati ed export

I dati stanno in una **cartella dati dedicata**:

- cartella con più immagini → sottocartella `etichettatura/` dentro la cartella immagini
- immagine singola → accanto all'immagine, senza sottocartella

Dentro la cartella dati:

- `nome.progetto.json` — il progetto: configurazione + annotazioni + misure. Salvataggio atomico; se corrotto viene messo da parte come `.corrotto` e il progetto riparte. I progetti creati con versioni precedenti (nella radice) vengono migrati automaticamente.
- `etichette.csv` — aggiornato a ogni salvataggio: una riga per immagine con nome, numero di etichette, etichette, stato, note, conteggi di geometrie e misure.
- `statistiche.csv` — aggiornato a ogni salvataggio: distribuzione etichette, stati, progresso e statistiche degli oggetti misurati (numero, larghezza/altezza/area media, minimo e massimo, in px o nell'unità configurata).

Export aggiuntivi dal menu "Export": COCO detection/segmentation, YOLO detection/segmentation, LabelMe, maschere PNG indicizzate (con `legend.csv`), CSV e report statistiche in una cartella a scelta.

## Sviluppo

```bash
./venv/bin/python -m pytest        # test logica pura (config, model, io, export)
```

Struttura: `labeling_tool/` — `config.py` (schema e validazione), `model.py` (record, progetto, undo/redo, calcoli), `io_utils.py` (scansione e cache), `export.py` (formati, funzioni pure), `cursors.py` (cursori di annotazione), `image_view.py` (viewer annotazioni), `settings_dialog.py` (wizard ed editor), `main_window.py` (UI principale).

Ogni merge in `main` produce automaticamente una release (tag con bump della minor e `Source-code.zip` allegato) tramite GitHub Actions (`.github/workflows/release.yml`).

## Condividere il programma

La cartella del programma è autonoma: basta copiarla o zipparla (senza `venv/`, `__pycache__/` e i progetti di etichettatura `*.progetto.json`). Chi la riceve esegue `setup` una volta e poi `start`. I dati di etichettatura restano sempre nella cartella immagini dell'utente, non dentro il programma.

## Licenza

Distribuito sotto licenza MIT: vedi il file `LICENSE`.
