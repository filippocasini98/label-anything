# Piano: distribuzione self-contained e ottimizzazione

> Piano di lavoro per distribuire Label Anything come eseguibile autonomo (nessuna installazione di Python richiesta) e ottimizzare peso, avvio e CI. Ticket di riferimento per l'implementazione: ogni fase diventa una o più PR.

## Obiettivi

- **Zero prerequisiti per l'utente finale**: scaricare la release, estrarre, doppio click. Niente Python, venv, `setup.bat`, `start.bat`.
- **Peso contenuto**: da ~150 MB (PyInstaller naif con `opencv-python` full e onefile) a **~70-90 MB** per piattaforma.
- **Avvio rapido**: **< 1 secondo** evitando la modalità `onefile`.
- **CI efficiente**: build con cache pip, ~2-3 min per job.
- **Affidabilità**: smoke test automatico del binario prima di pubblicarlo nella release.

## Strategia

**PyInstaller** in modalità **onedir** (distribuita come zip), integrato nella pipeline di release esistente (`.github/workflows/release.yml`). Motivazioni:

- PyInstaller è lo standard de facto per app PySide6; nessuna risorsa esterna da includere (i cursori sono generati via Qt, l'app non carica file `.png`/`.ico`).
- `onedir` zippato batte `onefile`: avvio ~istantaneo, molti meno falsi positivi antivirus, stessa esperienza utente (un solo zip da estrarre).
- La build deve avvenire **su ciascun OS** (nessun cross-compile): job in matrice su `windows-latest`, `macos-latest`, `ubuntu-latest`.

---

## Fase 1 — Preparazione del repo

1. **`requirements-build.txt`** — dipendenze solo runtime, senza `pytest`, e con OpenCV headless (vedi Ottimizzazione 1):
   ```text
   PySide6>=6.5
   opencv-python-headless>=4.8
   numpy>=1.24
   ```
2. **`label-anything.spec`** — spec PyInstaller (più manutenibile delle flag CLI):
   - `console=False` (nessun terminale);
   - `onedir` su tutte le piattaforme;
   - `excludes` per moduli inutilizzati: `tkinter`, `PySide6.QtWebEngineCore`, `PySide6.QtWebEngineWidgets`, `PySide6.QtQml`, `PySide6.QtQuick`, `PySide6.Qt3DCore`, `PySide6.QtCharts`, `PySide6.QtMultimedia`, `PySide6.QtSql`, `PySide6.QtTest`, `PySide6.QtXml`, `PySide6.QtDesigner`;
   - filtro di `a.binaries`/`a.datas` per rimuovere plugin Qt non necessari (`qtwebengine`, `qt3d`, `qtquick`, `qtvirtualkeyboard`);
   - versione dell'app letta da variabile d'ambiente `APP_VERSION` (impostata dalla CI dal tag della release).
3. **`scripts/build.sh`** — build locale riproducibile per sviluppare/testare senza CI.
4. **`labeling_tool/config.py`** — esporre la versione dell'app (default `dev`, override da env) per mostrarla nella GUI.

## Fase 2 — CI: job di build nella release pipeline

5. Estendere `.github/workflows/release.yml` con un job `build` che, **dopo la creazione della release**:
   - gira in matrice su `windows-latest` / `macos-latest` / `ubuntu-latest`;
   - `actions/setup-python@v5` (3.12) con **cache pip** (`actions/cache@v4`, key su `hashFiles('requirements-build.txt')`);
   - `pip install -r requirements-build.txt pyinstaller`;
   - `pyinstaller label-anything.spec` con `APP_VERSION` = tag della release;
   - produce gli artefatti:
     - Windows: `LabelAnything-<tag>-win64.zip` (cartella `dist/LabelAnything/`);
     - macOS: `LabelAnything-<tag>-macOS.zip` (contenente `Label Anything.app`);
     - Linux: `LabelAnything-<tag>-linux64.zip`;
   - li allega alla release appena creata con `gh release upload` (usa `GH_TOKEN` già presente nella workflow).
6. **Smoke test in CI** (prima dell'upload): avviare l'eseguibile headless con `QT_QPA_PLATFORM=offscreen` e una cartella di immagini di test, verificare che il progetto `*.progetto.json` venga creato; in caso di fallimento, il job fallisce e l'artefatto non viene pubblicato.
7. **Pulizia release vecchie** (opzionale): step che rimuove gli asset binari dalle release precedenti per contenere lo spazio (ogni release con 3 zip ≈ 250-300 MB).

## Fase 3 — Distribuzione per piattaforma

8. **Windows**: zip onedir; l'utente estrae e doppio click su `LabelAnything.exe`. Nessun installer per ora; fase futura opzionale: Inno Setup (`.msi`/`.exe` con scorciatoie e disinstallatore).
9. **macOS**: `Label Anything.app` in zip. Senza Apple Developer ID il Gatekeeper blocca l'app non firmata: istruzioni nel README (tasto destro → Apri, oppure `xattr -cr` dopo l'estrazione). Firma + notarizzazione = fase futura a pagamento ($99/anno), fuori scope.
10. **Linux**: zip onedir; nel README documentare che su distribuzioni minimali servono `libgl1` e `libegl1` (`sudo apt install libgl1 libegl1`).

## Fase 4 — Documentazione

11. **README**: nuova sezione in cima "Download (no Python needed)" con i tre binari per OS; spostare le istruzioni venv/setup in "Run from source (developers)"; istruzioni Gatekeeper per macOS e librerie Linux.
12. **Note di release**: la workflow già genera `note.md`; aggiungere automaticamente la riga "Self-contained binaries for Windows, macOS and Linux".

---

## Ottimizzazioni integrate

| # | Ottimizzazione | Effetto |
|---|---|---|
| 1 | `opencv-python-headless` al posto di `opencv-python` nella build (la GUI è PySide6, `cv2.imshow` non è usato) | −40/50 MB, rimuove il doppio stack GUI |
| 2 | `excludes` dei moduli Qt non usati nel `.spec` | −20/40 MB |
| 3 | `onedir` zippato invece di `onefile` su tutti gli OS | avvio da 2-5 s a <1 s, meno falsi positivi antivirus |
| 4 | Filtro plugin Qt in `a.binaries`/`a.datas` | −10/20 MB |
| 5 | Cache pip nella CI | −2-3 min per job |
| 6 | Smoke test del binario reale in CI (`QT_QPA_PLATFORM=offscreen`) | nessun binario rotto pubblicato |

## Risultato atteso

| Metrica | Prima (PyInstaller naif) | Dopo |
|---|---|---|
| Binario per piattaforma | ~150 MB (onefile, opencv full) | ~70-90 MB (onedir zip, headless, excludes) |
| Avvio | 2-5 s (scompattamento onefile) | <1 s |
| Job CI di build | ~4-5 min | ~2-3 min |
| Esperienza utente | install.bat + venv + Python | scarica zip → doppio click |

## Rischi e mitigazioni

- **Esclusioni Qt troppo aggressive** (es. `QtNetwork` a volte richiesto dietro le quinte): mitigate dallo smoke test in CI sull'eseguibile reale.
- **Gatekeeper macOS**: non eliminabile senza certificato; mitigato con istruzioni chiare nel README.
- **Spazio release**: 3 zip × ~80 MB per release; mitigato dalla pulizia degli asset vecchi (Fase 2, punto 7).
- **Compatibilità distribuzioni Linux**: PyInstaller non include `libGL`/`libEGL` di sistema; documentato nel README.

## Ordine di lavoro

| Step | Deliverable | Verifica |
|---|---|---|
| Fase 1 | `requirements-build.txt`, `label-anything.spec`, `scripts/build.sh`, versione in `config.py` | build locale riuscita e funzionante |
| Fase 2 | `release.yml` estesa con job `build` + smoke test | run CI verde con artefatti allegati |
| Fase 3 | Artefatti per i 3 OS | download e avvio manuali |
| Fase 4 | README + note di release aggiornate | review |

Stima: Fase 1 ≈ 1 giornata; Fase 2 ≈ 1-2 giornate (tuning esclusioni e smoke test headless è la parte più iterativa); Fasi 3-4 ≈ mezza giornata.
