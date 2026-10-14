# Design: Selettore del puntatore (cursori di annotazione)

Data: 2026-10-14
Stato: approvato dall'utente

## Obiettivo

Permettere all'utente di scegliere il cursore usato dagli strumenti di disegno e misura nell'immagine, tra 7 tipi utili per l'etichettatura, selezionabile al volo da un combobox in toolbar e salvato come preferenza globale (non nel progetto).

## Requisiti (confermati con l'utente)

1. Cursore globale: preferenza d'interfaccia valida per tutti i progetti, persistente tra gli avvii su file di testo `~/.config/labeling-tool/cursore.txt` (stesso pattern di `ultima_cartella.txt` in `io_utils.py`).
2. Selezione al volo: combobox sempre visibile in toolbar, come gli altri combobox esistenti; nessun riavvio.
3. Set di 7 cursori:
   - `crosshair` (default): CrossCursor standard di Qt.
   - `precision`: precision crosshair — croce sottile con gap al centro (pixmap custom).
   - `annotation`: annotation crosshair — croce con cerchietto al centro (pixmap custom).
   - `target`: cerchio con tacche a croce (pixmap custom).
   - `punto`: dot di 2 pixel, massima precisione sul pixel esatto (pixmap custom).
   - `freccia`: ArrowCursor di sistema.
   - `invisibile`: cursore nascosto (BlankCursor di Qt).
4. Ambito: la scelta vale per gli strumenti di disegno e misura (box, poligono, distanza, area, conteggio). Lo strumento "navigazione" (pan con trascinamento) mantiene il cursore di sistema, che comunica "sto navigando".
5. Fallback robusto: nome non riconosciuto o assente -> `crosshair`.

## Architettura

- Nuovo modulo `labeling_tool/cursors.py`: registry ordinata `CURSORI` come `dict nome -> CursorDef` dove `CursorDef` contiene etichetta visibile e factory che produce la `QCursor`. I cursori custom sono disegnati via `QPainter` su `QPixmap` (nessun asset binario); le pixmap usano devicePixelRatio 2 per restare nitide su schermi Hi-DPI. Hotspot al centro per tutti i cursori custom, e lettura/scrittura della preferenza su file.
- `ImageViewer` (in `image_view.py`): nuovo metodo `set_cursore(nome)` che memorizza la scelta; `set_strumento` usa il cursore scelto per gli strumenti di disegno e lascia invariato il comportamento per "nav".
- `Finestra` (in `main_window.py`): nuovo `combo_cursore` in toolbar, costruito dalla registry; alla modifica chiama `salva_cursore(nome)` sul file e `viewer.set_cursore`. All'avvio legge `leggi_cursore()` e applica.

## Flusso dati

Avvio: leggi `~/.config/labeling-tool/cursore.txt` (`leggi_cursore()`) -> `viewer.set_cursore(nome)` -> `combo_cursore` allineato. Cambio dal combobox: applica subito al viewer + `salva_cursore(nome)` sul file.

## Error handling e fallback

- Nome cursore non presente nella registry (valore corrotto o versione futura): la factory non viene chiamata, si ricade su `crosshair` senza errori.
- Il modulo dei cursori non tocca la logica di annotazione: un errore qui al massimo lascia il cursore precedente.

## Test

Nuovo `tests/test_cursors.py` (logica pura, QApplication condivisa se necessaria):
1. La registry contiene esattamente i 7 nomi previsti, in ordine stabile.
2. Nomi ed etichette univoci, etichette non vuote.
3. Per ogni cursore custom: pixmap logica 24x24 px (48x48 fisici con DPR 2) e hotspot dentro i limiti del pixmap.
4. Funzione di risoluzione: nome sconosciuto/None -> `crosshair`; nome valido -> se stesso.
5. Persistenza: round trip salva_cursore/leggi_cursore su file temporaneo; file assente o contenuto non valido -> crosshair.

Non si testa visivamente il rendering dei pixel del cursore (coperto dal disegno deterministico via QPainter).

## Fuori scope

- Cursori caricabili da file PNG esterni (approccio plugin): escluso per YAGNI.
- Anteprime grafiche dei cursori dentro il combobox: il testo dell'etichetta è sufficiente.
- Cursore dedicato per lo strumento navigazione.
