"""Annotazione assistita: parser di formati comuni e wrapper di inferenza.

Funzioni pure senza Qt: i parser convertono annotazioni esterne in geometrie
in pixel; il wrapper esegue modelli ultralytics con import pigro."""

import json
import xml.etree.ElementTree as ET
import numpy as np
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class DatiImport:
    """Esito del parsing: geometrie per riferimento immagine e classi trovate."""

    geometrie: Dict[str, List[dict]] = field(default_factory=dict)
    classi: List[str] = field(default_factory=list)
    scartate: int = 0  # annotazioni senza immagine corrispondente o malformate


def abbina(riferimenti: Dict[str, List[dict]], nomi_immagini: List[str]) -> Tuple[Dict[str, List[dict]], int]:
    """Abbina i riferimenti dei file di annotazione ai nomi immagine del progetto.

    Un riferimento puo' essere il nome completo ('a.jpg') o lo stem ('a'):
    prima la corrispondenza esatta, poi quella per stem. Ritorna le geometrie
    per nome immagine e il numero di annotazioni senza immagine corrispondente.
    """
    per_stem: Dict[str, List[str]] = {}
    for nome in nomi_immagini:
        per_stem.setdefault(Path(nome).stem, []).append(nome)
    risultato: Dict[str, List[dict]] = {}
    scartate = 0
    for riferimento, geometrie in riferimenti.items():
        if riferimento in nomi_immagini:
            bersaglio = riferimento
        else:
            bersagli = per_stem.get(Path(riferimento).stem, [])
            bersaglio = bersagli[0] if bersagli else None
        if bersaglio is None:
            scartate += len(geometrie)
            continue
        risultato.setdefault(bersaglio, []).extend(geometrie)
    return risultato, scartate


def applica_mappa(geometrie: List[dict], mappa: Dict[str, str],
                  soglia: Optional[float] = None) -> List[dict]:
    """Rinomina le classi secondo la mappa fonte -> progetto e filtra le escluse.

    Le classi assenti dalla mappa vengono scartate; con soglia, anche le
    geometrie con confidenza inferiore vengono scartate.
    """
    risultato = []
    for g in geometrie:
        classe = g.get("classe", "")
        if classe not in mappa:
            continue
        if not mappa[classe]:
            continue  # destinazione vuota = ignora
        if soglia is not None and g.get("confidenza") is not None and g["confidenza"] < soglia:
            continue
        nuova = dict(g)
        nuova["classe"] = mappa[classe]
        risultato.append(nuova)
    return risultato


def filtra_e_abbina(dati: DatiImport, nomi_immagini: List[str],
                    mappa: Dict[str, str]) -> Tuple[Dict[str, List[dict]], int]:
    """Pipeline di import: abbinamento nomi, mappatura classi, rimozione dei vuoti.

    Ritorna le geometrie per nome immagine di progetto e il totale delle
    annotazioni scartate (senza immagine o con classe non mappata).
    """
    abbinate, scartate = abbina(dati.geometrie, nomi_immagini)
    risultato: Dict[str, List[dict]] = {}
    for nome, geometrie in abbinate.items():
        mappate = applica_mappa(geometrie, mappa)
        scartate += len(geometrie) - len(mappate)
        if mappate:
            risultato[nome] = mappate
    return risultato, scartate + dati.scartate


def pre_mappa(classi_fonte: List[str], etichette_progetto: List[str],
              mappa_salvata: Dict[str, str]) -> Dict[str, str]:
    """Abbinamento iniziale classe fonte -> etichetta progetto ('' = ignora).

    Prima la mappa salvata nel progetto, poi l'uguaglianza del nome
    (case-insensitive)."""
    per_nome = {e.lower(): e for e in etichette_progetto}
    risultato: Dict[str, str] = {}
    for classe in classi_fonte:
        if classe in mappa_salvata and mappa_salvata[classe] in etichette_progetto:
            risultato[classe] = mappa_salvata[classe]
        else:
            risultato[classe] = per_nome.get(classe.lower(), "")
    return risultato


# ------------------------------------------------------------
# YOLO txt
# ------------------------------------------------------------

def _classi_da_data_yaml(cartella: Path) -> Optional[List[str]]:
    """Nomi dal data.yaml accanto alle label (lista inline o a blocco)."""
    data_yaml = cartella / "data.yaml"
    if not data_yaml.exists():
        return None
    righe = data_yaml.read_text(encoding="utf-8").splitlines()
    for i, riga in enumerate(righe):
        if not riga.strip().startswith("names:"):
            continue
        resto = riga.split("names:", 1)[1].strip()
        if resto.startswith("["):
            nomi = [n.strip().strip("'\"") for n in resto.strip("[]").split(",")]
            return [n for n in nomi if n]
        classi: List[str] = []
        for successiva in righe[i + 1:]:
            testo = successiva.strip()
            if not testo:
                continue
            if testo.startswith("- "):
                classi.append(testo[2:].strip().strip("'\""))
            elif ":" in testo:
                chiave, _, valore = testo.partition(":")
                if chiave.strip().isdigit() and valore.strip():
                    classi.append(valore.strip().strip("'\""))
                else:
                    break
            else:
                break
        return [c for c in classi if c]
    return None


def _classi_da_yolo(cartella: Path, max_indice: int) -> List[str]:
    """Classi per l'import YOLO: classes.txt, poi data.yaml, poi sintetici.

    La lista viene estesa fino a max_indice + 1 con nomi classe_N, cosi'
    ogni indice presente nei file e' mappabile nel dialogo."""
    classi: List[str] = []
    classes_txt = cartella / "classes.txt"
    if classes_txt.exists():
        classi = [r.strip() for r in classes_txt.read_text(encoding="utf-8").splitlines() if r.strip()]
    if not classi:
        classi = _classi_da_data_yaml(cartella) or []
    if len(classi) < max_indice + 1:
        classi += [f"classe_{i}" for i in range(len(classi), max_indice + 1)]
    return classi


def da_yolo(cartella: Path, dimensioni: Dict[str, Tuple[int, int]]) -> DatiImport:
    """Legge le annotazioni YOLO (un .txt per immagine) dalla cartella.

    dimensioni e' {nome_immagine: (larghezza, altezza)} delle immagini del
    progetto; i .txt vengono abbinati per stem. Le righe detection sono
    'idx cx cy w h' normalizzate, quelle segmentation 'idx x1 y1 x2 y2 ...'.
    """
    per_stem: Dict[str, Tuple[int, int]] = {}
    for nome, dim in dimensioni.items():
        per_stem.setdefault(Path(nome).stem, (int(dim[0]), int(dim[1])))
    files = sorted(p for p in cartella.iterdir()
                   if p.suffix.lower() == ".txt" and p.name != "classes.txt")
    if not per_stem or not files:
        return DatiImport()
    righe_per_file = []
    max_indice = -1
    scartate = 0
    for percorso in files:
        righe = [r.split() for r in percorso.read_text(encoding="utf-8").splitlines() if r.strip()]
        righe_per_file.append((percorso.stem, righe))
        for r in righe:
            if len(r) < 5:
                continue
            try:
                max_indice = max(max_indice, int(r[0]))
            except (ValueError, IndexError):
                pass
    classi = _classi_da_yolo(cartella, max_indice)
    geometrie: Dict[str, List[dict]] = {}
    for stem, righe in righe_per_file:
        dim = per_stem.get(stem)
        if dim is None:
            scartate += len(righe)
            continue
        w, h = dim
        per_immagine = geometrie.setdefault(stem, [])
        for r in righe:
            if len(r) < 5:
                scartate += 1
                continue
            try:
                indice = int(r[0])
                valori = [float(v) for v in r[1:]]
            except ValueError:
                scartate += 1
                continue
            if indice < 0:
                scartate += 1
                continue
            classe = classi[indice]
            g: dict = {"classe": classe, "origine": "modello"}
            if len(valori) == 4:
                cx, cy, bw, bh = valori
                g.update({"tipo": "box",
                          "x": (cx - bw / 2) * w, "y": (cy - bh / 2) * h,
                          "w": bw * w, "h": bh * h})
                per_immagine.append(g)
            elif len(valori) >= 6 and len(valori) % 2 == 0:
                punti = [[valori[i] * w, valori[i + 1] * h] for i in range(0, len(valori), 2)]
                g.update({"tipo": "poligono", "punti": punti})
                per_immagine.append(g)
    geometrie = {nome: g for nome, g in geometrie.items() if g}
    return DatiImport(geometrie=geometrie, classi=classi, scartate=scartate)


# ------------------------------------------------------------
# COCO json
# ------------------------------------------------------------

def da_coco(percorso: Path) -> DatiImport:
    """Legge un file COCO (detection o segmentation); le coordinate sono in px.

    La segmentation poligonale vince sul bbox; i file_name vengono ridotti al
    nome file; le annotazioni orfane, con categoria sconosciuta o malformate
    sono scartate e contate. Solleva ValueError se la struttura non e' COCO."""
    dati_json = json.loads(percorso.read_text(encoding="utf-8"))
    if not isinstance(dati_json, dict):
        raise ValueError(f"Struttura COCO non valida in {percorso.name}")
    for sezione in ("categories", "images", "annotations"):
        valore = dati_json.get(sezione)
        if valore is not None and not isinstance(valore, list):
            raise ValueError(f"Sezione '{sezione}' non valida in {percorso.name}")
    categorie = {}
    for c in dati_json.get("categories") or []:
        try:
            categorie[int(c["id"])] = str(c["name"])
        except (KeyError, TypeError, ValueError):
            continue
    classi = [nome for _, nome in sorted(categorie.items())]
    per_id = {}
    for i in dati_json.get("images") or []:
        try:
            per_id[int(i["id"])] = str(i["file_name"])
        except (KeyError, TypeError, ValueError):
            continue
    geometrie: Dict[str, List[dict]] = {}
    scartate = 0
    for ann in dati_json.get("annotations") or []:
        if not isinstance(ann, dict):
            scartate += 1
            continue
        try:
            id_immagine = int(ann.get("image_id", -1))
            id_categoria = int(ann.get("category_id", -1))
        except (TypeError, ValueError):
            scartate += 1
            continue
        riferimento = per_id.get(id_immagine)
        classe = categorie.get(id_categoria)
        if riferimento is None or classe is None:
            scartate += 1
            continue
        riferimento = Path(riferimento).name  # i file_name possono avere percorsi
        poligoni = [s for s in (ann.get("segmentation") or [])
                    if isinstance(s, list) and len(s) >= 6 and len(s) % 2 == 0]
        if poligoni:
            for piatto in poligoni:
                try:
                    punti = [[float(piatto[i]), float(piatto[i + 1])]
                             for i in range(0, len(piatto), 2)]
                except (TypeError, ValueError):
                    scartate += 1
                    continue
                geometrie.setdefault(riferimento, []).append(
                    {"tipo": "poligono", "classe": classe, "punti": punti,
                     "origine": "modello"})
        else:
            try:
                x, y, w, h = (float(v) for v in ann.get("bbox", [0, 0, 0, 0]))
            except (TypeError, ValueError):
                scartate += 1
                continue
            if w > 0 and h > 0:
                geometrie.setdefault(riferimento, []).append(
                    {"tipo": "box", "classe": classe,
                     "x": x, "y": y, "w": w, "h": h, "origine": "modello"})
            else:
                scartate += 1
    return DatiImport(geometrie=geometrie, classi=classi, scartate=scartate)


# ------------------------------------------------------------
# LabelMe json
# ------------------------------------------------------------

def da_labelme(cartella: Path) -> DatiImport:
    """Legge i file json di LabelMe (rectangle e polygon); coordinate in px.

    I file illeggibili o non-dict sono saltati; le shape malformate sono
    scartate e contate; le shape di altri tipi (circle, line, ...) non
    producono geometrie e non inquinano l'elenco classi."""
    geometrie: Dict[str, List[dict]] = {}
    classi: List[str] = []
    scartate = 0
    for percorso in sorted(cartella.glob("*.json")):
        try:
            dati_json = json.loads(percorso.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if not isinstance(dati_json, dict):
            continue
        riferimento = Path(str(dati_json.get("imagePath", ""))).name
        if not riferimento:
            continue
        forme = dati_json.get("shapes") or []
        if not isinstance(forme, list):
            continue  # sezione shapes malformata: file saltato
        per_immagine = geometrie.setdefault(riferimento, [])
        for forma in forme:
            if not isinstance(forma, dict):
                scartate += 1
                continue
            tipo = forma.get("shape_type")
            if tipo not in ("rectangle", "polygon"):
                continue  # tipi non supportati: nessuna geometria
            classe = str(forma.get("label", "")).strip()
            if not classe:
                scartate += 1
                continue
            if classe not in classi:
                classi.append(classe)
            try:
                punti = [[float(p[0]), float(p[1])]
                         for p in forma.get("points") or [] if len(p) >= 2]
            except (TypeError, ValueError):
                scartate += 1
                continue
            if tipo == "rectangle" and len(punti) >= 2:
                (x1, y1), (x2, y2) = punti[0], punti[1]
                w, h = abs(x2 - x1), abs(y2 - y1)
                if w <= 0 or h <= 0:
                    scartate += 1
                    continue
                per_immagine.append({
                    "tipo": "box", "classe": classe, "origine": "modello",
                    "x": min(x1, x2), "y": min(y1, y2), "w": w, "h": h,
                })
            elif tipo == "polygon" and len(punti) >= 3:
                per_immagine.append(
                    {"tipo": "poligono", "classe": classe, "punti": punti,
                     "origine": "modello"})
            else:
                scartate += 1  # shape dichiarata ma con troppo pochi punti
    geometrie = {nome: g for nome, g in geometrie.items() if g}
    return DatiImport(geometrie=geometrie, classi=classi, scartate=scartate)


# ------------------------------------------------------------
# Pascal VOC xml
# ------------------------------------------------------------

def da_voc(cartella: Path) -> DatiImport:
    """Legge i file xml di Pascal VOC (object/bndbox); coordinate in px.

    I file illeggibili sono saltati; gli object senza bndbox o con coordinate
    malformate/degeneri sono scartati e contati."""
    geometrie: Dict[str, List[dict]] = {}
    classi: List[str] = []
    scartate = 0
    for percorso in sorted(cartella.glob("*.xml")):
        try:
            radice = ET.parse(str(percorso)).getroot()
        except ET.ParseError:
            continue
        riferimento = Path((radice.findtext("filename", "") or "").strip()).name
        if not riferimento:
            continue
        per_immagine = geometrie.setdefault(riferimento, [])
        for oggetto in radice.findall("object"):
            classe = (oggetto.findtext("name", "") or "").strip()
            if not classe:
                scartate += 1
                continue
            if classe not in classi:
                classi.append(classe)
            bndbox = oggetto.find("bndbox")
            if bndbox is None:
                scartate += 1
                continue
            try:
                x1 = float(bndbox.findtext("xmin", ""))
                y1 = float(bndbox.findtext("ymin", ""))
                x2 = float(bndbox.findtext("xmax", ""))
                y2 = float(bndbox.findtext("ymax", ""))
            except ValueError:
                scartate += 1
                continue
            if x2 > x1 and y2 > y1:
                per_immagine.append({
                    "tipo": "box", "classe": classe, "origine": "modello",
                    "x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1,
                })
            else:
                scartate += 1
    geometrie = {nome: g for nome, g in geometrie.items() if g}
    return DatiImport(geometrie=geometrie, classi=classi, scartate=scartate)


# ------------------------------------------------------------
# Inferenza in-app (ultralytics, import pigro)
# ------------------------------------------------------------

def ultralytics_disponibile() -> bool:
    """True se il pacchetto ultralytics e' installato e importabile."""
    try:
        from ultralytics import YOLO  # noqa: F401
    except ImportError:
        return False
    return True


def carica_modello(percorso: str):
    """Carica un modello della famiglia YOLO/Ultralytics (.pt o .onnx)."""
    from ultralytics import YOLO

    return YOLO(percorso)


def _in_numpy(valore):
    """Porta un eventuale tensor torch (CUDA/MPS) su CPU prima della conversione."""
    cpu = getattr(valore, "cpu", None)
    if callable(cpu):
        try:
            valore = cpu()
        except Exception:
            pass
    return valore


def geometrie_da_risultato(risultato, nome_modello: str = "") -> List[dict]:
    """Converte un risultato ultralytics (boxes/masks) in geometrie in px.

    Con le maschere produce poligoni, altrimenti box; ogni geometria porta
    origine 'modello', confidenza e nome del modello."""
    boxes = getattr(risultato, "boxes", None)
    if boxes is None:
        return []
    try:
        xyxy = np.asarray(_in_numpy(boxes.xyxy), dtype=float).reshape(-1, 4)
        conf = np.asarray(_in_numpy(boxes.conf), dtype=float).reshape(-1)
        cls = np.asarray(_in_numpy(boxes.cls), dtype=float).reshape(-1)
    except (TypeError, ValueError):
        return []
    nomi = getattr(risultato, "names", None) or {}
    maschere = getattr(risultato, "masks", None)
    punti_maschere = getattr(maschere, "xy", None) if maschere is not None else None
    geometrie: List[dict] = []
    for i in range(len(xyxy)):
        indice_classe = int(cls[i]) if i < len(cls) else -1
        if isinstance(nomi, dict):
            classe = str(nomi.get(indice_classe, indice_classe))
        elif 0 <= indice_classe < len(nomi):
            classe = str(nomi[indice_classe])
        else:
            classe = str(indice_classe)
        comune = {
            "classe": classe,
            "origine": "modello",
            "confidenza": float(conf[i]) if i < len(conf) else None,
            "modello": nome_modello,
        }
        if punti_maschere is not None and i < len(punti_maschere):
            punti = [[float(p[0]), float(p[1])] for p in np.asarray(_in_numpy(punti_maschere[i]))]
            if len(punti) >= 3:
                geometrie.append({"tipo": "poligono", "punti": punti, **comune})
        else:
            x1, y1, x2, y2 = xyxy[i]
            geometrie.append({"tipo": "box", "x": float(x1), "y": float(y1),
                              "w": float(x2 - x1), "h": float(y2 - y1), **comune})
    return geometrie


def annota_immagine(modello, immagine, soglia: float, nome_modello: str = "") -> List[dict]:
    """Predizione su una singola immagine (ndarray BGR) -> geometrie in px."""
    risultati = modello.predict(immagine, conf=soglia, verbose=False)
    if not risultati:
        return []
    return geometrie_da_risultato(risultati[0], nome_modello)
