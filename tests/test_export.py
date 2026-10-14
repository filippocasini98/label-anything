import csv
import json
from pathlib import Path

import pytest

from labeling_tool.config import EtichettaDef, config_default
from labeling_tool.export import (
    esporta_coco,
    esporta_csv,
    esporta_labelme,
    esporta_maschere,
    esporta_yolo,
    report_statistiche,
)
from labeling_tool.model import Misura, Record

DIMENSIONI = {"a.jpg": (200, 100), "b.jpg": (200, 100)}


def progetto_esempio():
    from labeling_tool.model import Progetto

    config = config_default()
    config.etichette = [EtichettaDef("sana", "#3CB44B", "1"), EtichettaDef("esca", "#F39C12", "2")]
    progetto = Progetto(config=config)
    progetto.immagini["a.jpg"] = Record(
        nome="a.jpg",
        etichette=["sana", "esca"],
        stato="completata",
        geometrie=[
            {"tipo": "box", "classe": "esca", "x": 10.0, "y": 20.0, "w": 100.0, "h": 40.0},
            {"tipo": "poligono", "classe": "sana", "punti": [[0.0, 0.0], [50.0, 0.0], [50.0, 50.0], [0.0, 50.0]]},
        ],
        misure=[Misura("distanza", [[0, 0], [30, 40]], 50.0)],
    )
    progetto.immagini["b.jpg"] = Record(nome="b.jpg", stato="non_etichettata", note="dubbio")
    return progetto


def test_esporta_csv(tmp_path: Path):
    dest = tmp_path / "etichette.csv"
    esporta_csv(progetto_esempio(), ["a.jpg", "b.jpg"], dest)
    with dest.open(newline="", encoding="utf-8-sig") as f:
        righe = list(csv.DictReader(f))
    assert righe[0]["Nome Immagine"] == "a.jpg"
    assert righe[0]["Etichette"] == "sana;esca"
    assert righe[0]["Geometrie"] == "box:esca:100.0x40.0px;poligono:sana:50.0x50.0px:A:2500.0px2"
    assert righe[0]["Misure"] == "distanza:50.0px"
    assert righe[1]["Nome Immagine"] == "b.jpg"


def test_esporta_coco_detection(tmp_path: Path):
    dest = tmp_path / "coco.json"
    esporta_coco(progetto_esempio(), ["a.jpg", "b.jpg"], dest, dimensioni=DIMENSIONI)
    dati = json.loads(dest.read_text(encoding="utf-8"))
    assert [c["name"] for c in dati["categories"]] == ["sana", "esca"]
    assert len(dati["images"]) == 2
    assert dati["images"][0]["file_name"] == "a.jpg"
    box_ann = [a for a in dati["annotations"] if a["bbox"] == [10.0, 20.0, 100.0, 40.0]]
    assert len(box_ann) == 1
    assert box_ann[0]["category_id"] == 2  # esca -> indice 1 + 1


def test_esporta_coco_segmentation(tmp_path: Path):
    dest = tmp_path / "coco_seg.json"
    esporta_coco(progetto_esempio(), ["a.jpg"], dest, segmentazione=True, dimensioni=DIMENSIONI)
    dati = json.loads(dest.read_text(encoding="utf-8"))
    poligoni = [a for a in dati["annotations"] if a.get("segmentation")]
    assert any(a["segmentation"] == [[0.0, 0.0, 50.0, 0.0, 50.0, 50.0, 0.0, 50.0]] for a in poligoni)


def test_esporta_yolo_detection(tmp_path: Path):
    out = tmp_path / "yolo"
    out.mkdir()
    esporta_yolo(progetto_esempio(), ["a.jpg"], out, dimensioni=DIMENSIONI)
    classi = (out / "classes.txt").read_text(encoding="utf-8").splitlines()
    assert classi == ["sana", "esca"]
    righe = (out / "a.txt").read_text(encoding="utf-8").strip().splitlines()
    # box: x=10 y=20 w=100 h=40 su immagine 200x100 -> cx 0.30 cy 0.40 w 0.5 h 0.4
    prima = righe[0].split()
    assert prima[0] == "1"
    assert float(prima[1]) == pytest.approx(0.30, abs=1e-6)
    assert float(prima[2]) == pytest.approx(0.40, abs=1e-6)


def test_esporta_yolo_segmentation(tmp_path: Path):
    out = tmp_path / "yolo_seg"
    out.mkdir()
    esporta_yolo(progetto_esempio(), ["a.jpg"], out, segmentazione=True, dimensioni=DIMENSIONI)
    testo = (out / "a.txt").read_text(encoding="utf-8").strip()
    assert "0.25" in testo  # poligono 50x50 normalizzato su 200x100


def test_esporta_labelme(tmp_path: Path):
    out = tmp_path / "labelme"
    out.mkdir()
    esporta_labelme(progetto_esempio(), ["a.jpg"], out, dimensioni=DIMENSIONI)
    dati = json.loads((out / "a.json").read_text(encoding="utf-8"))
    assert dati["imageWidth"] == 200
    forme = dati["shapes"]
    assert any(s["shape_type"] == "rectangle" and s["label"] == "esca" for s in forme)
    assert any(s["shape_type"] == "polygon" and s["label"] == "sana" for s in forme)


def test_esporta_maschere(tmp_path: Path):
    import cv2
    import numpy as np

    out = tmp_path / "maschere"
    out.mkdir()
    esporta_maschere(progetto_esempio(), ["a.jpg"], out, dimensioni=DIMENSIONI)
    dati = np.fromfile(str(out / "a.png"), dtype=np.uint8)
    maschera = cv2.imdecode(dati, cv2.IMREAD_GRAYSCALE)
    assert maschera is not None
    assert maschera.shape == (100, 200)
    assert maschera.max() == 2  # box esca (classe 2) e poligono sana (classe 1)
    assert maschera[0, 0] == 1  # il poligono sana copre l'angolo in alto a sinistra
    assert maschera[30, 100] == 2  # interno del box esca, fuori dal poligono
    legenda = (out / "legend.csv").read_text(encoding="utf-8")
    assert "sana" in legenda


def test_report_statistiche(tmp_path: Path):
    dest = tmp_path / "report.csv"
    report_statistiche(progetto_esempio(), ["a.jpg", "b.jpg"], dest)
    testo = dest.read_text(encoding="utf-8-sig")
    assert "sana" in testo and "esca" in testo
    assert "Etichetta" in testo


def test_esporta_csv_colonna_num_etichette(tmp_path: Path):
    dest = tmp_path / "e.csv"
    esporta_csv(progetto_esempio(), ["a.jpg", "b.jpg"], dest)
    with dest.open(newline="", encoding="utf-8-sig") as f:
        righe = list(csv.DictReader(f))
    assert righe[0]["Num Etichette"] == "2"
    assert righe[0]["Etichette"] == "sana;esca"
    assert righe[1]["Num Etichette"] == "0"


def test_esporta_csv_misura_oggetto(tmp_path: Path):
    from labeling_tool.model import Progetto

    p = progetto_esempio()
    p.immagini["a.jpg"].misure.append(Misura("oggetto", [[10.0, 20.0], [110.0, 60.0]], None))
    dest = tmp_path / "e.csv"
    esporta_csv(p, ["a.jpg"], dest)
    testo = dest.read_text(encoding="utf-8-sig")
    assert "oggetto:100.0x40.0px" in testo


def test_report_statistiche_oggetti(tmp_path: Path):
    dest = tmp_path / "r.csv"
    p = progetto_esempio()
    p.immagini["a.jpg"].misure.append(Misura("oggetto", [[0.0, 0.0], [100.0, 40.0]], None))
    p.immagini["b.jpg"].misure.append(Misura("oggetto", [[0.0, 0.0], [200.0, 40.0]], None))
    report_statistiche(p, ["a.jpg", "b.jpg"], dest)
    testo = dest.read_text(encoding="utf-8-sig")
    assert "Oggetti" in testo and "numero,2" in testo.replace("\r", "")
    assert "larghezza media,150.000" in testo.replace("\r", "")  # (100+200)/2
    assert "area media,6000.000" in testo.replace("\r", "")      # (4000+8000)/2


def test_report_statistiche_oggetti_con_unita(tmp_path: Path):
    from labeling_tool.model import Progetto

    dest = tmp_path / "r.csv"
    p = progetto_esempio()
    p.config.unita_misura = "um"
    p.config.scala_px_per_unita = 10.0  # 10 px = 1 um
    p.immagini["a.jpg"].misure.append(Misura("oggetto", [[0.0, 0.0], [100.0, 40.0]], None))
    report_statistiche(p, ["a.jpg"], dest)
    testo = dest.read_text(encoding="utf-8-sig").replace("\r", "")
    assert "Oggetti (um)" in testo
    assert "larghezza media,10.000" in testo   # 100px / 10
    assert "altezza media,4.000" in testo       # 40px / 10
    assert "area media,40.000" in testo         # 4000 px2 / 100


def test_esporta_csv_geometrie_con_dimensioni_box(tmp_path: Path):
    dest = tmp_path / "e.csv"
    esporta_csv(progetto_esempio(), ["a.jpg"], dest)
    testo = dest.read_text(encoding="utf-8-sig")
    assert "box:esca:100.0x40.0px" in testo
    assert "poligono:sana:50.0x50.0px:A:2500.0px2" in testo


def test_report_statistiche_box_per_classe(tmp_path: Path):
    dest = tmp_path / "r.csv"
    p = progetto_esempio()
    # box esca 100x40 su a.jpg; ne aggiungo uno 50x20 su b.jpg della stessa classe
    p.immagini["b.jpg"].geometrie.append(
        {"tipo": "box", "classe": "esca", "x": 0.0, "y": 0.0, "w": 50.0, "h": 20.0}
    )
    report_statistiche(p, ["a.jpg", "b.jpg"], dest)
    testo = dest.read_text(encoding="utf-8-sig").replace("\r", "")
    assert "Box,totale,2" in testo
    assert "Box esca (px)" in testo
    assert "larghezza media,75.000" in testo   # (100+50)/2
    assert "altezza media,30.000" in testo      # (40+20)/2
    assert "area media,2500.000" in testo        # (4000+1000)/2


def test_report_statistiche_poligoni_per_classe(tmp_path: Path):
    dest = tmp_path / "r.csv"
    p = progetto_esempio()
    # poligono sana 50x50 (area 2500) su a.jpg; aggiungo 10x10 (area 100) su b.jpg
    p.immagini["b.jpg"].geometrie.append(
        {"tipo": "poligono", "classe": "sana",
         "punti": [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]}
    )
    report_statistiche(p, ["a.jpg", "b.jpg"], dest)
    testo = dest.read_text(encoding="utf-8-sig").replace("\r", "")
    assert "Poligoni,totale,2" in testo
    assert "Poligoni sana (px)" in testo
    assert "larghezza media,30.000" in testo    # (50+10)/2
    assert "altezza media,30.000" in testo       # (50+10)/2
    assert "area media,1300.000" in testo        # (2500+100)/2
