"""Esportazioni: CSV, COCO, YOLO, LabelMe, maschere PNG indicizzate, report statistiche.

Funzioni pure: nessuna dipendenza da Qt. Le dimensioni immagine sono passate
esplicitamente come dict {nome: (larghezza, altezza)}."""

import base64
import csv
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import cv2
import numpy as np

from labeling_tool.model import (
    Progetto,
    Record,
    area_poligono,
    dimensioni_bbox_poligono,
    dimensioni_oggetto,
)


def _record(progetto: Progetto, nome: str) -> Optional[Record]:
    return progetto.immagini.get(nome)


def _cladizione(progetto: Progetto) -> List[str]:
    return [e.nome for e in progetto.config.etichette]


def _bbox_poligono(punti) -> Tuple[float, float, float, float]:
    xs = [p[0] for p in punti]
    ys = [p[1] for p in punti]
    x, y = min(xs), min(ys)
    return x, y, max(xs) - x, max(ys) - y


# ------------------------------------------------------------
# CSV
# ------------------------------------------------------------

def esporta_csv(progetto: Progetto, nomi: Iterable[str], dest: Path) -> None:
    intestazione = [
        "Nome Immagine", "Num Etichette", "Etichette", "Stato", "Note",
        "Da revisionare", "Revisionata", "Da Verificare", "Data modifica", "Etichettatore",
        "Num Geometrie", "Num Misure", "Geometrie", "Misure",
    ]
    unita = progetto.config.unita_misura
    with dest.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=intestazione)
        writer.writeheader()
        for nome in nomi:
            r = _record(progetto, nome)
            if r is None:
                continue
            writer.writerow({
                "Nome Immagine": r.nome,
                "Num Etichette": len(r.etichette),
                "Etichette": ";".join(r.etichette),
                "Stato": r.stato,
                "Note": r.note,
                "Da revisionare": "Si" if r.da_revisionare else "No",
                "Revisionata": "Si" if r.revisionata else "No",
                "Da Verificare": "Si" if r.da_verificare else "No",
                "Data modifica": r.data_modifica,
                "Etichettatore": r.etichettatore,
                "Num Geometrie": len(r.geometrie),
                "Num Misure": len(r.misure),
                "Geometrie": ";".join(_testo_geometria(g) for g in r.geometrie),
                "Misure": ";".join(_testo_misura(m, unita) for m in r.misure),
            })


def _testo_geometria(g: dict) -> str:
    """Descrizione di una geometria, con la grandezza di box e poligoni."""
    classe = g.get("classe", "")
    if g.get("tipo") == "box":
        return f"box:{classe}:{g['w']:.1f}x{g['h']:.1f}px"
    if g.get("tipo") == "poligono" and g.get("punti"):
        w, h = dimensioni_bbox_poligono(g["punti"])
        return f"poligono:{classe}:{w:.1f}x{h:.1f}px:A:{area_poligono(g['punti']):.1f}px2"
    return f"{g.get('tipo', '')}:{classe}"


def _testo_misura(misura, unita: str) -> str:
    if misura.tipo == "distanza" and misura.valore_px is not None:
        return f"distanza:{misura.valore_px:.1f}px"
    if misura.tipo == "area" and len(misura.punti) >= 3:
        return f"area:{area_poligono(misura.punti):.1f}px2"
    if misura.tipo == "oggetto" and len(misura.punti) >= 2:
        w, h = dimensioni_oggetto(misura.punti)
        return f"oggetto:{w:.1f}x{h:.1f}px"
    return f"{misura.tipo}:{len(misura.punti)}"


# ------------------------------------------------------------
# COCO
# ------------------------------------------------------------

def esporta_coco(
    progetto: Progetto,
    nomi: Iterable[str],
    dest: Path,
    segmentazione: bool = False,
    dimensioni: Optional[Dict[str, Tuple[int, int]]] = None,
    copia_immagini: bool = False,
    percorsi_immagini: Optional[Dict[str, Path]] = None,
) -> None:
    dimensioni = dimensioni or {}
    classi = _cladizione(progetto)
    dati = {
        "images": [],
        "annotations": [],
        "categories": [{"id": i + 1, "name": n, "supercategory": "none"} for i, n in enumerate(classi)],
    }
    id_ann = 1
    for id_img, nome in enumerate(nomi, start=1):
        r = _record(progetto, nome)
        if r is None:
            continue
        dim = dimensioni.get(nome)
        dati["images"].append({
            "id": id_img,
            "file_name": nome,
            "width": dim[0] if dim else None,
            "height": dim[1] if dim else None,
        })
        for g in r.geometrie:
            indice = classi.index(g["classe"]) + 1 if g.get("classe") in classi else None
            if indice is None:
                continue
            if g["tipo"] == "box":
                x, y, w, h = g["x"], g["y"], g["w"], g["h"]
                ann = {
                    "id": id_ann, "image_id": id_img, "category_id": indice,
                    "bbox": [x, y, w, h], "area": w * h, "iscrowd": 0,
                }
            else:
                punti = g["punti"]
                x, y, w, h = _bbox_poligono(punti)
                ann = {
                    "id": id_ann, "image_id": id_img, "category_id": indice,
                    "bbox": [x, y, w, h], "area": area_poligono(punti), "iscrowd": 0,
                }
                if segmentazione:
                    piatto = [c for p in punti for c in p]
                    ann["segmentation"] = [piatto]
            dati["annotations"].append(ann)
            id_ann += 1
    dest.write_text(json.dumps(dati, ensure_ascii=False, indent=2), encoding="utf-8")
    if copia_immagini and percorsi_immagini:
        cartella = dest.parent / "images"
        cartella.mkdir(exist_ok=True)
        for nome, percorso in percorsi_immagini.items():
            if percorso.exists():
                shutil.copy2(str(percorso), str(cartella / nome))


# ------------------------------------------------------------
# YOLO
# ------------------------------------------------------------

def _righe_yolo(r: Record, classi: List[str], w: int, h: int, segmentazione: bool) -> List[str]:
    righe = []
    for g in r.geometrie:
        if g.get("classe") not in classi:
            continue
        indice = classi.index(g["classe"])
        if g["tipo"] == "box":
            cx = (g["x"] + g["w"] / 2) / w
            cy = (g["y"] + g["h"] / 2) / h
            nw, nh = g["w"] / w, g["h"] / h
            righe.append(f"{indice} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")
        else:
            punti = g["punti"]
            if segmentazione:
                piatto = " ".join(f"{p[0] / w:.6f} {p[1] / h:.6f}" for p in punti)
                righe.append(f"{indice} {piatto}")
            else:
                x, y, bw, bh = _bbox_poligono(punti)
                cx, cy = (x + bw / 2) / w, (y + bh / 2) / h
                righe.append(f"{indice} {cx:.6f} {cy:.6f} {bw / w:.6f} {bh / h:.6f}")
    return righe


def esporta_yolo(
    progetto: Progetto,
    nomi: Iterable[str],
    cartella: Path,
    segmentazione: bool = False,
    dimensioni: Optional[Dict[str, Tuple[int, int]]] = None,
    copia_immagini: bool = False,
    percorsi_immagini: Optional[Dict[str, Path]] = None,
) -> None:
    dimensioni = dimensioni or {}
    classi = _cladizione(progetto)
    cartella.mkdir(parents=True, exist_ok=True)
    (cartella / "classes.txt").write_text("\n".join(classi) + "\n", encoding="utf-8")
    for nome in nomi:
        r = _record(progetto, nome)
        dim = dimensioni.get(nome)
        if r is None or not dim:
            continue
        righe = _righe_yolo(r, classi, dim[0], dim[1], segmentazione)
        (cartella / (Path(nome).stem + ".txt")).write_text("\n".join(righe) + ("\n" if righe else ""), encoding="utf-8")
    if copia_immagini and percorsi_immagini:
        img_dir = cartella / "images"
        img_dir.mkdir(exist_ok=True)
        for nome, percorso in percorsi_immagini.items():
            if percorso.exists():
                shutil.copy2(str(percorso), str(img_dir / nome))


# ------------------------------------------------------------
# LabelMe
# ------------------------------------------------------------

def esporta_labelme(
    progetto: Progetto,
    nomi: Iterable[str],
    cartella: Path,
    dimensioni: Optional[Dict[str, Tuple[int, int]]] = None,
    copia_immagini: bool = False,
    percorsi_immagini: Optional[Dict[str, Path]] = None,
) -> None:
    dimensioni = dimensioni or {}
    cartella.mkdir(parents=True, exist_ok=True)
    for nome in nomi:
        r = _record(progetto, nome)
        if r is None:
            continue
        dim = dimensioni.get(nome, (0, 0))
        forme = []
        for g in r.geometrie:
            if g["tipo"] == "box":
                x2, y2 = g["x"] + g["w"], g["y"] + g["h"]
                forme.append({
                    "label": g["classe"],
                    "points": [[g["x"], g["y"]], [x2, y2]],
                    "group_id": None,
                    "shape_type": "rectangle",
                    "flags": {},
                })
            else:
                forme.append({
                    "label": g["classe"],
                    "points": [list(p) for p in g["punti"]],
                    "group_id": None,
                    "shape_type": "polygon",
                    "flags": {},
                })
        dati = {
            "version": "5.2.1",
            "flags": {},
            "shapes": forme,
            "imagePath": nome,
            "imageData": None,
            "imageHeight": dim[1],
            "imageWidth": dim[0],
        }
        (cartella / (Path(nome).stem + ".json")).write_text(
            json.dumps(dati, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    if copia_immagini and percorsi_immagini:
        for nome, percorso in percorsi_immagini.items():
            if percorso.exists():
                shutil.copy2(str(percorso), str(cartella / nome))


# ------------------------------------------------------------
# Maschere PNG indicizzate
# ------------------------------------------------------------

def esporta_maschere(
    progetto: Progetto,
    nomi: Iterable[str],
    cartella: Path,
    dimensioni: Optional[Dict[str, Tuple[int, int]]] = None,
) -> None:
    dimensioni = dimensioni or {}
    classi = _cladizione(progetto)
    cartella.mkdir(parents=True, exist_ok=True)
    (cartella / "legend.csv").write_text(
        "Indice,Classe\n" + "".join(f"{i + 1},{n}\n" for i, n in enumerate(classi)),
        encoding="utf-8",
    )
    for nome in nomi:
        r = _record(progetto, nome)
        dim = dimensioni.get(nome)
        if r is None or not dim:
            continue
        w, h = dim
        maschera = np.zeros((h, w), dtype=np.uint8)
        for g in r.geometrie:
            if g.get("classe") not in classi:
                continue
            valore = classi.index(g["classe"]) + 1
            if g["tipo"] == "box":
                x1, y1 = int(round(g["x"])), int(round(g["y"]))
                x2, y2 = int(round(g["x"] + g["w"])), int(round(g["y"] + g["h"]))
                maschera[max(0, y1):min(h, y2), max(0, x1):min(w, x2)] = valore
            else:
                punti = np.array([[int(round(p[0])), int(round(p[1]))] for p in g["punti"]], dtype=np.int32)
                cv2.fillPoly(maschera, [punti], valore)
        cv2.imwrite(str(cartella / (Path(nome).stem + ".png")), maschera)


# ------------------------------------------------------------
# Report statistiche
# ------------------------------------------------------------

def report_statistiche(progetto: Progetto, nomi: Iterable[str], dest: Path) -> None:
    records = [r for r in (progetto.immagini.get(n) for n in nomi) if r is not None]
    totale = len(records) or 1
    conteggio = Counter(e for r in records for e in r.etichette)
    stati = Counter(r.stato for r in records)
    with dest.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Sezione", "Voce", "Conteggio", "Percentuale"])
        for nome in _cladizione(progetto):
            n = conteggio.get(nome, 0)
            writer.writerow(["Etichetta", nome, n, f"{n / totale * 100:.1f}%"])
        writer.writerow(["Etichetta", "(nessuna)", sum(1 for r in records if not r.etichette),
                         f"{sum(1 for r in records if not r.etichette) / totale * 100:.1f}%"])
        for stato, n in sorted(stati.items()):
            writer.writerow(["Stato", stato, n, f"{n / totale * 100:.1f}%"])
        writer.writerow(["Revisione", "da revisionare", sum(r.da_revisionare for r in records),
                         f"{sum(r.da_revisionare for r in records) / totale * 100:.1f}%"])
        writer.writerow(["Revisione", "revisionate", sum(r.revisionata for r in records),
                         f"{sum(r.revisionata for r in records) / totale * 100:.1f}%"])
        writer.writerow(["Revisione", "da verificare (modello)", sum(r.da_verificare for r in records),
                         f"{sum(r.da_verificare for r in records) / totale * 100:.1f}%"])
        writer.writerow(["Geometrie", "totale", sum(len(r.geometrie) for r in records), ""])
        writer.writerow(["Misure", "totale", sum(len(r.misure) for r in records), ""])
        oggetti = [m for r in records for m in r.misure if m.tipo == "oggetto" and len(m.punti) >= 2]
        if oggetti:
            dimensioni = [dimensioni_oggetto(m.punti) for m in oggetti]
            unita = progetto.config.unita_misura
            scala = progetto.config.scala_px_per_unita
            writer.writerow(["Oggetti", "numero", len(oggetti), ""])
            _righe_dimensione(writer, "Oggetti", "larghezza", [d[0] for d in dimensioni], unita, scala)
            _righe_dimensione(writer, "Oggetti", "altezza", [d[1] for d in dimensioni], unita, scala)
            _righe_dimensione(writer, "Oggetti", "area", [d[0] * d[1] for d in dimensioni], unita, scala, quadrato=True)
        # grandezza dei bounding box, per classe
        unita = progetto.config.unita_misura
        scala = progetto.config.scala_px_per_unita
        box_per_classe: Dict[str, List[Tuple[float, float]]] = {}
        poligoni_per_classe: Dict[str, List[list]] = {}
        for r in records:
            for g in r.geometrie:
                if g.get("tipo") == "box":
                    box_per_classe.setdefault(g.get("classe", ""), []).append((g["w"], g["h"]))
                elif g.get("tipo") == "poligono" and g.get("punti"):
                    poligoni_per_classe.setdefault(g.get("classe", ""), []).append(g["punti"])
        if box_per_classe:
            writer.writerow(["Box", "totale", sum(len(v) for v in box_per_classe.values()), ""])
            for classe, dimensioni in sorted(box_per_classe.items()):
                sezione = f"Box {classe}"
                _righe_dimensione(writer, sezione, "larghezza", [d[0] for d in dimensioni], unita, scala)
                _righe_dimensione(writer, sezione, "altezza", [d[1] for d in dimensioni], unita, scala)
                _righe_dimensione(writer, sezione, "area", [d[0] * d[1] for d in dimensioni], unita, scala, quadrato=True)
        # grandezza dei poligoni, per classe: bounding box e area
        if poligoni_per_classe:
            writer.writerow(["Poligoni", "totale", sum(len(v) for v in poligoni_per_classe.values()), ""])
            for classe, gruppi in sorted(poligoni_per_classe.items()):
                sezione = f"Poligoni {classe}"
                bboxes = [dimensioni_bbox_poligono(p) for p in gruppi]
                _righe_dimensione(writer, sezione, "larghezza", [d[0] for d in bboxes], unita, scala)
                _righe_dimensione(writer, sezione, "altezza", [d[1] for d in bboxes], unita, scala)
                _righe_dimensione(writer, sezione, "area", [area_poligono(p) for p in gruppi], unita, scala, quadrato=True)


def _righe_dimensione(writer, sezione: str, nome: str, valori: List[float], unita: str,
                      scala: float, quadrato: bool = False) -> None:
    """Righe di statistica (media/minimo/massimo) per una dimensione.

    In px se l'unita' del progetto e' px, altrimenti convertite con la scala."""
    suffisso_unita = "px" if unita == "px" else unita
    esponente = "2" if quadrato else ""
    fattore = 1.0 if unita == "px" else (1.0 / scala) ** (2 if quadrato else 1)
    media = sum(valori) / len(valori)
    writer.writerow([f"{sezione} ({suffisso_unita}{esponente})", f"{nome} media",
                     f"{media * fattore:.3f}", ""])
    writer.writerow([f"{sezione} ({suffisso_unita}{esponente})", f"{nome} minimo",
                     f"{min(valori) * fattore:.3f}", ""])
    writer.writerow([f"{sezione} ({suffisso_unita}{esponente})", f"{nome} massimo",
                     f"{max(valori) * fattore:.3f}", ""])


# ------------------------------------------------------------
# Visualizzazione HTML autonoma
# ------------------------------------------------------------

_HTML_JPEG_QUALITA = 82
_HTML_CACHE: Dict[str, str] = {}


def _colore_bgr(colore_hex: str) -> Tuple[int, int, int]:
    h = colore_hex.lstrip("#")
    if len(h) != 6:
        h = "bd1b05"
    return (int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16))


def _disegna_geometrie(img: "np.ndarray", geometrie: List[dict], colori: Dict[str, str]):
    out = img.copy()
    ordinate = sorted(geometrie, key=lambda g: (g.get("y", 0), g.get("x", 0)))
    for i, g in enumerate(ordinate, start=1):
        colore = _colore_bgr(colori.get(g.get("classe", ""), "#bd1b05"))
        if g.get("tipo") == "box":
            p1 = (int(round(g["x"])), int(round(g["y"])))
            p2 = (int(round(g["x"] + g["w"])), int(round(g["y"] + g["h"])))
            cv2.rectangle(out, p1, p2, (255, 255, 255), 4)
            cv2.rectangle(out, p1, p2, colore, 2)
            tx, ty = p1[0], max(p1[1] - 8, 14)
        elif g.get("tipo") == "poligono" and len(g.get("punti", [])) >= 2:
            punti = np.array([[int(round(p[0])), int(round(p[1]))] for p in g["punti"]], dtype=np.int32)
            cv2.polylines(out, [punti], True, (255, 255, 255), 4)
            cv2.polylines(out, [punti], True, colore, 2)
            tx, ty = int(round(g["punti"][0][0])), max(int(round(g["punti"][0][1])) - 8, 14)
        else:
            continue
        cv2.putText(out, str(i), (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 3, cv2.LINE_AA)
        cv2.putText(out, str(i), (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.55, colore, 1, cv2.LINE_AA)
    return out


def _trova_immagine(cartella: Path, nome: str) -> Optional[Path]:
    diretto = cartella / nome
    if diretto.exists():
        return diretto
    if cartella.exists():
        return next(iter(cartella.rglob(nome)), None)
    return None


def _jpeg_b64_annotata(percorso: Path, geometrie: List[dict], colori: Dict[str, str]) -> Optional[str]:
    chiave = json.dumps(geometrie, sort_keys=True, ensure_ascii=False)
    try:
        mtime = percorso.stat().st_mtime_ns
    except OSError:
        mtime = 0
    cache_key = f"{percorso}|{mtime}|{hashlib.md5(chiave.encode('utf-8')).hexdigest()}"
    if cache_key in _HTML_CACHE:
        return _HTML_CACHE[cache_key]
    img = cv2.imread(str(percorso), cv2.IMREAD_COLOR)
    if img is None:
        return None
    if geometrie:
        img = _disegna_geometrie(img, geometrie, colori)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, _HTML_JPEG_QUALITA])
    if not ok:
        return None
    if len(_HTML_CACHE) > 600:
        _HTML_CACHE.clear()
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
    _HTML_CACHE[cache_key] = b64
    return b64


def esporta_html(progetto: Progetto, nomi: Iterable[str], cartella_immagini: Path, dest: Path) -> None:
    """Pagina HTML autonoma: immagini con geometrie disegnate, lightbox con zoom
    e statistiche. Le immagini sono incorporate in base64: il file si apre in
    qualsiasi browser senza installazioni."""
    import html as _html

    config = progetto.config
    colori = {e.nome: e.colore for e in config.etichette}
    figure = []
    dati_immagini = {}
    totale = 0

    for nome in nomi:
        record = progetto.immagini.get(nome)
        geometrie = list(record.geometrie) if record else []
        totale += len(geometrie)
        dati_immagini[nome] = {
            "stato": record.stato if record else "non_etichettata",
            "note": record.note if record else "",
            "geometrie": geometrie,
        }
        percorso = _trova_immagine(cartella_immagini, nome)
        b64 = _jpeg_b64_annotata(percorso, geometrie, colori) if percorso else None
        n = len(geometrie)
        badge = f'<span class="badge">{n} ann.</span>' if n else '<span class="badge zero">0 ann.</span>'
        note = record.note.strip() if record else ""
        note_html = f' <span class="note">note: {_html.escape(note)}</span>' if note else ""
        if b64:
            corpo = f'<img src="data:image/jpeg;base64,{b64}" alt="{_html.escape(nome)}">'
        else:
            corpo = '<div class="missing">immagine non disponibile</div>'
        figure.append(
            f'<figure><figcaption><b>{_html.escape(nome)}</b> {badge}{note_html}</figcaption>{corpo}</figure>'
        )

    dati = {
        "progetto": config.nome_progetto,
        "etichettatore": config.etichettatore,
        "unita": config.unita_misura,
        "scala": config.scala_px_per_unita,
        "classi": colori,
        "totale": totale,
        "immagini": dati_immagini,
    }
    dati_json = json.dumps(dati, ensure_ascii=False).replace("</", "<\\/")
    pagina = _TEMPLATE_HTML.replace("__DATI_JSON__", dati_json).replace("__FIGURE__", "\n".join(figure))
    pagina = pagina.replace("__NOME_PROGETTO__", _html.escape(config.nome_progetto or "progetto"))
    dest.write_text(pagina, encoding="utf-8")


_TEMPLATE_HTML = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Visualizzazione annotazioni</title>
<style>
  body { font-family: -apple-system, "Segoe UI", Arial, sans-serif; margin: 24px auto; max-width: 1150px; padding: 0 16px; background: #f4f4f5; color: #18181b; }
  h1 { font-size: 24px; margin-bottom: 4px; }
  h2 { font-size: 19px; margin-top: 40px; border-bottom: 2px solid #d4d4d8; padding-bottom: 6px; }
  .sottotitolo { color: #71717a; font-size: 14px; }
  .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin: 20px 0; }
  .kpi { background: #fff; border-radius: 10px; padding: 14px; box-shadow: 0 1px 4px rgba(0,0,0,.12); text-align: center; }
  .kpi .v { font-size: 26px; font-weight: 700; }
  .kpi .k { font-size: 12px; color: #71717a; margin-top: 2px; }
  table { border-collapse: collapse; width: 100%; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,.12); font-size: 13px; }
  th, td { padding: 7px 10px; text-align: right; border-bottom: 1px solid #e4e4e7; }
  th { background: #18181b; color: #f4f4f5; font-weight: 600; }
  th:first-child, td:first-child { text-align: left; }
  tr:last-child td { border-bottom: none; }
  .chip { display: inline-block; border-radius: 14px; padding: 2px 10px; font-size: 12px; font-weight: 600; color: #fff; margin-right: 6px; }
  .istogramma { display: flex; align-items: flex-end; gap: 4px; height: 140px; background: #fff; border-radius: 10px; padding: 12px; box-shadow: 0 1px 4px rgba(0,0,0,.12); }
  .istogramma .bin { flex: 1; background: #3b82f6; border-radius: 3px 3px 0 0; min-height: 1px; position: relative; }
  .istogramma .bin span { position: absolute; top: -18px; left: 50%; transform: translateX(-50%); font-size: 10px; color: #52525b; white-space: nowrap; }
  .bin-labels { display: flex; gap: 4px; margin-top: 4px; }
  .bin-labels div { flex: 1; text-align: center; font-size: 10px; color: #71717a; overflow: hidden; white-space: nowrap; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 18px; }
  figure { margin: 0; background: #fff; border-radius: 10px; padding: 10px; box-shadow: 0 1px 4px rgba(0,0,0,.12); }
  figure img { width: 100%; height: auto; display: block; border-radius: 6px; cursor: zoom-in; }
  figcaption { font-size: 13px; padding: 4px 2px 8px; word-break: break-all; }
  .badge { background: #d1fae5; color: #065f46; border-radius: 20px; padding: 1px 10px; font-weight: 600; margin-left: 6px; white-space: nowrap; }
  .badge.zero { background: #e4e4e7; color: #52525b; }
  .note { color: #71717a; margin-left: 6px; font-style: italic; }
  .missing { display:flex; align-items:center; justify-content:center; height:200px; color:#a1a1aa; background:#fafafa; border-radius:6px; font-size:13px; }
  #lightbox { position: fixed; inset: 0; background: rgba(0,0,0,.88); display: none; z-index: 100; touch-action: none; }
  #lightbox.open { display: block; }
  #lbImg { position: absolute; left: 0; top: 0; max-width: none; max-height: none; transform-origin: 0 0; user-select: none; -webkit-user-select: none; }
  #lbCaption { position: absolute; bottom: 12px; left: 0; right: 0; text-align: center; color: #e4e4e7; font-size: 14px; pointer-events: none; padding: 0 60px; }
  #lbClose { position: absolute; top: 10px; right: 14px; color: #fff; font-size: 30px; background: none; border: none; cursor: pointer; line-height: 1; z-index: 102; }
  .lbNav { position: absolute; top: 50%; transform: translateY(-50%); background: rgba(255,255,255,.12); color: #fff; border: none; font-size: 26px; padding: 12px 14px; cursor: pointer; border-radius: 8px; z-index: 102; }
  .lbNav:disabled { opacity: .25; cursor: default; }
  #lbPrev { left: 10px; } #lbNext { right: 10px; }
  #lbZoomHint { position: absolute; top: 14px; left: 50%; transform: translateX(-50%); color: #a1a1aa; font-size: 12px; pointer-events: none; }
  footer { margin-top: 40px; color: #a1a1aa; font-size: 12px; }
</style>
</head>
<body>
<h1>Annotazioni — __NOME_PROGETTO__</h1>
<p class="sottotitolo">Pagina autonoma generata da label anything: apribile in qualsiasi browser senza installazioni. Clic su una immagine per ingrandirla; rotella o pizzica per zoomare; trascina per spostarti; frecce per cambiare immagine.</p>

<h2>Riepilogo</h2>
<div class="kpis" id="kpis"></div>
<div id="chipsClassi"></div>

<h2>Statistiche per classe</h2>
<div id="tabellaClassi"></div>

<h2>Distribuzione delle aree</h2>
<div id="istogramma"></div>

<h2>Dettaglio per immagine</h2>
<div id="tabellaImmagini" style="overflow-x:auto"></div>

<h2>Immagini con annotazioni</h2>
<div class="grid">
__FIGURE__
</div>

<footer>Le caselle numerate sono le annotazioni; i colori seguono le classi del progetto.</footer>

<div id="lightbox">
  <div id="lbZoomHint">rotella / pizzica = zoom &middot; trascina = sposta &middot; &larr; &rarr; = cambia immagine &middot; Esc = chiudi</div>
  <button id="lbClose" aria-label="Chiudi">&times;</button>
  <button id="lbPrev" class="lbNav" aria-label="Precedente">&#8249;</button>
  <button id="lbNext" class="lbNav" aria-label="Successiva">&#8250;</button>
  <img id="lbImg" alt="">
  <div id="lbCaption"></div>
</div>

<script type="application/json" id="dati-json">__DATI_JSON__</script>
<script>
(function () {
  var dati = JSON.parse(document.getElementById('dati-json').textContent);

  // ---------- statistiche ----------
  function unitaVal(px) {
    return (dati.unita && dati.unita !== 'px' && dati.scala) ? px / dati.scala : px;
  }
  function unitaSuffix() {
    return (dati.unita && dati.unita !== 'px') ? ' ' + dati.unita : ' px';
  }
  function fmt(v, dec) {
    if (!isFinite(v)) return '-';
    return v.toFixed(dec === undefined ? 2 : dec);
  }
  function areaPoligono(punti) {
    var s = 0, n = punti.length;
    if (n < 3) return 0;
    for (var i = 0; i < n; i++) {
      var a = punti[i], b = punti[(i + 1) % n];
      s += a[0] * b[1] - b[0] * a[1];
    }
    return Math.abs(s) / 2;
  }
  function dims(g) {
    if (g.tipo === 'box') return { w: g.w, h: g.h, area: g.w * g.h };
    if (g.tipo === 'poligono' && g.punti && g.punti.length) {
      var xs = g.punti.map(function (p) { return p[0]; });
      var ys = g.punti.map(function (p) { return p[1]; });
      var w = Math.max.apply(null, xs) - Math.min.apply(null, xs);
      var h = Math.max.apply(null, ys) - Math.min.apply(null, ys);
      return { w: w, h: h, area: areaPoligono(g.punti) };
    }
    return null;
  }
  function mediana(arr) {
    if (!arr.length) return NaN;
    var s = arr.slice().sort(function (a, b) { return a - b; });
    var m = Math.floor(s.length / 2);
    return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
  }
  function media(arr) { return arr.length ? arr.reduce(function (a, b) { return a + b; }, 0) / arr.length : NaN; }

  var perClasse = {}, perImmagine = [], aree = [];
  Object.keys(dati.immagini).forEach(function (nome) {
    var info = dati.immagini[nome];
    var dd = [], aa = [];
    info.geometrie.forEach(function (g) {
      var d = dims(g);
      if (!d) return;
      dd.push(d);
      aree.push(d.area);
      var c = perClasse[g.classe || ''] || (perClasse[g.classe || ''] = { n: 0, w: [], h: [], a: [] });
      c.n++; c.w.push(d.w); c.h.push(d.h); c.a.push(d.area);
    });
    perImmagine.push({ nome: nome, n: info.geometrie.length, stato: info.stato, note: info.note, dims: dd });
  });

  var conAnn = perImmagine.filter(function (r) { return r.n > 0; }).length;
  document.getElementById('kpis').innerHTML =
    kpi(dati.totale, 'annotazioni totali') +
    kpi(perImmagine.length, 'immagini') +
    kpi(conAnn, 'immagini con annotazioni') +
    kpi(Object.keys(perClasse).length, 'classi usate');
  function kpi(v, k) { return '<div class="kpi"><div class="v">' + v + '</div><div class="k">' + k + '</div></div>'; }

  var chips = '';
  Object.keys(perClasse).sort().forEach(function (c) {
    var colore = dati.classi[c] || '#888';
    chips += '<span class="chip" style="background:' + colore + '">' + c + ': ' + perClasse[c].n + '</span>';
  });
  document.getElementById('chipsClassi').innerHTML = chips;

  var us = unitaSuffix();
  var righe = '';
  Object.keys(perClasse).sort().forEach(function (c) {
    var s = perClasse[c];
    righe += '<tr><td>' + c + '</td><td>' + s.n + '</td><td>' + fmt(unitaVal(media(s.w))) + '</td><td>'
      + fmt(unitaVal(media(s.h))) + '</td><td>' + fmt(unitaVal(media(s.a))) + '</td><td>'
      + fmt(unitaVal(mediana(s.a))) + '</td><td>' + fmt(unitaVal(Math.min.apply(null, s.a))) + '</td><td>'
      + fmt(unitaVal(Math.max.apply(null, s.a))) + '</td></tr>';
  });
  document.getElementById('tabellaClassi').innerHTML =
    '<table><tr><th>Classe</th><th>N</th><th>Larghezza media</th><th>Altezza media</th><th>Area media</th>'
    + '<th>Area mediana</th><th>Area min</th><th>Area max</th></tr>' + righe + '</table>'
    + (us !== ' px' ? '<p class="sottotitolo">Dimensioni in ' + us + ' (1 ' + us.trim() + ' = ' + dati.scala + ' px).</p>' : '');

  if (aree.length) {
    var nb = 12, mn = Math.min.apply(null, aree), mx = Math.max.apply(null, aree);
    if (mx === mn) { mx = mn + 1; }
    var binCounts = new Array(nb).fill(0);
    aree.forEach(function (a) {
      var i = Math.min(nb - 1, Math.floor((a - mn) / (mx - mn) * nb));
      binCounts[i]++;
    });
    var binMax = Math.max.apply(null, binCounts);
    var bars = '', labels = '';
    for (var b = 0; b < nb; b++) {
      var altezza = binCounts[b] / binMax * 100;
      bars += '<div class="bin" style="height:' + altezza + '%"><span>' + (binCounts[b] || '') + '</span></div>';
      labels += '<div>' + fmt(unitaVal(mn + (b + 0.5) * (mx - mn) / nb), 1) + '</div>';
    }
    document.getElementById('istogramma').innerHTML = '<div class="istogramma">' + bars + '</div>'
      + '<div class="bin-labels">' + labels + '</div>'
      + '<p class="sottotitolo">Area per annotazione (px&sup2;' + (us !== ' px' ? ', in ' + us : '') + '); ogni barra = intervallo, il numero sopra = conteggio.</p>';
  } else {
    document.getElementById('istogramma').innerHTML = '<p class="sottotitolo">Nessuna annotazione.</p>';
  }

  righe = '';
  perImmagine.forEach(function (r) {
    var am = r.dims.length ? unitaVal(media(r.dims.map(function (d) { return d.area; }))) : NaN;
    righe += '<tr><td>' + r.nome + '</td><td>' + r.n + '</td><td>' + fmt(am) + '</td><td>' + r.stato
      + '</td><td style="text-align:left">' + (r.note || '') + '</td></tr>';
  });
  document.getElementById('tabellaImmagini').innerHTML =
    '<table><tr><th>Immagine</th><th>N annotazioni</th><th>Area media</th><th>Stato</th><th>Note</th></tr>'
    + righe + '</table>';

  // ---------- lightbox ----------
  var lb = document.getElementById('lightbox');
  var lbImg = document.getElementById('lbImg');
  var lbCap = document.getElementById('lbCaption');
  var btnPrev = document.getElementById('lbPrev');
  var btnNext = document.getElementById('lbNext');
  var items = [].slice.call(document.querySelectorAll('figure img'));
  var cur = -1;
  var scale = 1, tx = 0, ty = 0, minScale = 1;
  var drag = null;

  function vw() { return window.innerWidth; }
  function vh() { return window.innerHeight; }
  function fitScale() {
    var w = lbImg.naturalWidth || 1, h = lbImg.naturalHeight || 1;
    return Math.min(vw() / w, vh() / h);
  }
  function apply() {
    var iw = lbImg.naturalWidth * scale, ih = lbImg.naturalHeight * scale;
    var maxX = Math.max(0, (iw - vw()) / 2), maxY = Math.max(0, (ih - vh()) / 2);
    tx = Math.max(-maxX, Math.min(maxX, tx));
    ty = Math.max(-maxY, Math.min(maxY, ty));
    lbImg.style.transform = 'translate(' + ((vw() - iw) / 2 + tx) + 'px,' + ((vh() - ih) / 2 + ty) + 'px) scale(' + scale + ')';
  }
  function show(i) {
    cur = i;
    var img = items[i];
    tx = 0; ty = 0;
    lbImg.src = img.src;
    lbImg.alt = img.alt;
    lbCap.innerHTML = img.closest('figure').querySelector('figcaption').innerHTML;
    btnPrev.disabled = (i <= 0);
    btnNext.disabled = (i >= items.length - 1);
    lb.classList.add('open');
    lbImg.onload = function () { minScale = fitScale(); scale = minScale; apply(); };
    if (lbImg.complete && lbImg.naturalWidth) { minScale = fitScale(); scale = minScale; apply(); }
  }
  function close() { lb.classList.remove('open'); cur = -1; }

  items.forEach(function (img, i) { img.addEventListener('click', function () { show(i); }); });
  document.getElementById('lbClose').addEventListener('click', close);
  btnPrev.addEventListener('click', function () { if (cur > 0) show(cur - 1); });
  btnNext.addEventListener('click', function () { if (cur < items.length - 1) show(cur + 1); });
  document.addEventListener('keydown', function (e) {
    if (cur < 0) return;
    if (e.key === 'Escape') close();
    if (e.key === 'ArrowLeft' && cur > 0) show(cur - 1);
    if (e.key === 'ArrowRight' && cur < items.length - 1) show(cur + 1);
  });
  window.addEventListener('resize', function () { if (cur >= 0) { minScale = fitScale(); apply(); } });

  function zoomAt(cx, cy, factor) {
    var iw = lbImg.naturalWidth * scale, ih = lbImg.naturalHeight * scale;
    var ox = (vw() - iw) / 2, oy = (vh() - ih) / 2;
    var s1 = Math.max(minScale, Math.min(minScale * 20, scale * factor));
    var p = (cx - ox - tx) / scale, q = (cy - oy - ty) / scale;
    scale = s1;
    var iw1 = lbImg.naturalWidth * scale, ih1 = lbImg.naturalHeight * scale;
    tx = cx - (vw() - iw1) / 2 - p * scale;
    ty = cy - (vh() - ih1) / 2 - q * scale;
    apply();
  }
  lb.addEventListener('wheel', function (e) {
    if (cur < 0) return;
    e.preventDefault();
    zoomAt(e.clientX, e.clientY, e.deltaY < 0 ? 1.2 : 1 / 1.2);
  }, { passive: false });
  lb.addEventListener('pointerdown', function (e) {
    if (e.target.closest('.lbNav') || e.target.id === 'lbClose') return;
    drag = { x: e.clientX, y: e.clientY, tx0: tx, ty0: ty };
    lb.setPointerCapture(e.pointerId);
  });
  lb.addEventListener('pointermove', function (e) {
    if (!drag) return;
    tx = drag.tx0 + (e.clientX - drag.x);
    ty = drag.ty0 + (e.clientY - drag.y);
    apply();
  });
  function endDrag() { drag = null; }
  lb.addEventListener('pointerup', endDrag);
  lb.addEventListener('pointercancel', endDrag);
  var pinch = null;
  lb.addEventListener('touchstart', function (e) {
    if (e.touches.length === 2 && cur >= 0) {
      var d = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
      pinch = { d: d, cx: (e.touches[0].clientX + e.touches[1].clientX) / 2, cy: (e.touches[0].clientY + e.touches[1].clientY) / 2, s0: scale };
    }
  }, { passive: true });
  lb.addEventListener('touchmove', function (e) {
    if (pinch && e.touches.length === 2) {
      e.preventDefault();
      var d = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
      if (d > 0 && pinch.d > 0) zoomAt(pinch.cx, pinch.cy, (d / pinch.d) * (pinch.s0 / scale));
    }
  }, { passive: false });
  lb.addEventListener('touchend', function () { pinch = null; }, { passive: true });
  lb.addEventListener('dblclick', function (e) {
    if (cur < 0 || e.target.closest('.lbNav') || e.target.id === 'lbClose') return;
    e.preventDefault();
    if (scale > minScale * 1.01) { scale = minScale; tx = 0; ty = 0; apply(); }
    else zoomAt(e.clientX, e.clientY, 2.5);
  });
})();
</script>
</body>
</html>
"""
