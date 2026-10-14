"""Esportazioni: CSV, COCO, YOLO, LabelMe, maschere PNG indicizzate, report statistiche.

Funzioni pure: nessuna dipendenza da Qt. Le dimensioni immagine sono passate
esplicitamente come dict {nome: (larghezza, altezza)}."""

import csv
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
        "Da revisionare", "Revisionata", "Data modifica", "Etichettatore",
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
