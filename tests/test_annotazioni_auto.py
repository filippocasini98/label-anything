import json

import pytest

import numpy as np

from labeling_tool.annotazioni_auto import (
    DatiImport,
    abbina,
    annota_immagine,
    applica_mappa,
    da_coco,
    da_labelme,
    da_voc,
    da_yolo,
    filtra_e_abbina,
    geometrie_da_risultato,
    pre_mappa,
    ultralytics_disponibile,
)

BOX_UVA = {"tipo": "box", "classe": "uva", "x": 0.0, "y": 0.0, "w": 10.0, "h": 5.0,
           "origine": "modello"}
BOX_ALTRO = {"tipo": "box", "classe": "altro", "x": 1.0, "y": 1.0, "w": 2.0, "h": 2.0}


def test_abbina_nome_esatto_e_stem():
    riferimenti = {"a.jpg": [BOX_UVA], "b": [BOX_ALTRO], "x.jpg": [dict(BOX_UVA)]}
    risultato, scartate = abbina(riferimenti, ["a.jpg", "b.png"])
    assert list(risultato) == ["a.jpg", "b.png"]
    assert risultato["a.jpg"] == [BOX_UVA]
    assert risultato["b.png"] == [BOX_ALTRO]
    assert scartate == 1


def test_applica_mappa_rinomina_e_filtra():
    geometrie = [dict(BOX_UVA), dict(BOX_ALTRO)]
    risultato = applica_mappa(geometrie, {"uva": "acino"})
    assert len(risultato) == 1
    assert risultato[0]["classe"] == "acino"
    assert risultato[0]["origine"] == "modello"
    assert geometrie[0]["classe"] == "uva"  # l'input non viene mutato


def test_applica_mappa_soglia():
    geometrie = [
        dict(BOX_UVA, confidenza=0.9),
        dict(BOX_UVA, confidenza=0.1),
        dict(BOX_UVA),
    ]
    risultato = applica_mappa(geometrie, {"uva": "acino"}, soglia=0.25)
    assert len(risultato) == 2
    assert all(g.get("confidenza") != 0.1 for g in risultato)


def test_filtra_e_abbina_end_to_end():
    dati = DatiImport(
        geometrie={"a.jpg": [dict(BOX_UVA), dict(BOX_ALTRO)], "zz.jpg": [dict(BOX_UVA)]},
        classi=["uva", "altro"],
        scartate=0,
    )
    risultato, scartate = filtra_e_abbina(dati, ["a.jpg"], {"uva": "acino"})
    assert list(risultato) == ["a.jpg"]
    assert risultato["a.jpg"][0]["classe"] == "acino"
    assert scartate == 2  # zz.jpg senza immagine + classe 'altro' non mappata


def test_filtra_e_abbina_scartate_parse():
    dati = DatiImport(geometrie={"a.jpg": [dict(BOX_UVA)]}, classi=["uva"], scartate=3)
    risultato, scartate = filtra_e_abbina(dati, ["a.jpg"], {"uva": "acino"})
    assert scartate == 3


def test_pre_mappa_salvata_poi_nome():
    mappa = pre_mappa(["uva", "Foglia"], ["acino", "foglia"], {"uva": "acino"})
    assert mappa == {"uva": "acino", "Foglia": "foglia"}


def test_pre_mappa_senza_abbinamento_ignora():
    mappa = pre_mappa(["strano"], ["acino"], {})
    assert mappa == {"strano": ""}


def _scrivi(percorso, testo):
    percorso.write_text(testo, encoding="utf-8")


def test_da_yolo_detection(tmp_path):
    _scrivi(tmp_path / "classes.txt", "uva\nfoglia\n")
    _scrivi(tmp_path / "a.txt", "0 0.5 0.5 0.5 0.4\n")
    dati = da_yolo(tmp_path, {"a.jpg": (200, 100)})
    assert dati.classi == ["uva", "foglia"]
    g = dati.geometrie["a"][0]
    assert g["tipo"] == "box"
    assert g["classe"] == "uva"
    assert g["origine"] == "modello"
    assert g["x"] == pytest.approx(50.0)    # (0.5 - 0.25) * 200
    assert g["y"] == pytest.approx(30.0)    # (0.5 - 0.20) * 100
    assert g["w"] == pytest.approx(100.0)
    assert g["h"] == pytest.approx(40.0)


def test_da_yolo_segmentation(tmp_path):
    _scrivi(tmp_path / "a.txt", "1 0.1 0.1 0.9 0.1 0.9 0.9\n")
    dati = da_yolo(tmp_path, {"a.jpg": (100, 100)})
    g = dati.geometrie["a"][0]
    assert g["tipo"] == "poligono"
    assert g["punti"] == [[10.0, 10.0], [90.0, 10.0], [90.0, 90.0]]
    assert g["classe"] == "classe_1"


def test_da_yolo_senza_classes_txt(tmp_path):
    _scrivi(tmp_path / "a.txt", "0 0.5 0.5 0.2 0.2\n")
    dati = da_yolo(tmp_path, {"a.jpg": (100, 100)})
    assert dati.classi == ["classe_0"]
    assert dati.geometrie["a"][0]["classe"] == "classe_0"


def test_da_yolo_data_yaml_lista_inline(tmp_path):
    _scrivi(tmp_path / "data.yaml", "names: [uva, foglia]\n")
    _scrivi(tmp_path / "a.txt", "1 0.5 0.5 0.2 0.2\n")
    dati = da_yolo(tmp_path, {"a.jpg": (100, 100)})
    assert dati.classi == ["uva", "foglia"]


def test_da_yolo_data_yaml_a_blocco(tmp_path):
    _scrivi(tmp_path / "data.yaml", "train: x\nnames:\n- uva\n- foglia\nval: y\n")
    _scrivi(tmp_path / "a.txt", "0 0.5 0.5 0.2 0.2\n")
    dati = da_yolo(tmp_path, {"a.jpg": (100, 100)})
    assert dati.classi == ["uva", "foglia"]


def test_da_yolo_file_senza_immagine_scartato(tmp_path):
    _scrivi(tmp_path / "classes.txt", "uva\n")
    _scrivi(tmp_path / "b.txt", "0 0.5 0.5 0.2 0.2\n")
    _scrivi(tmp_path / "a.txt", "0 0.5 0.5 0.2 0.2\n")
    dati = da_yolo(tmp_path, {"a.jpg": (100, 100)})
    assert list(dati.geometrie) == ["a"]
    assert dati.scartate == 1


def test_da_yolo_cartella_vuota(tmp_path):
    dati = da_yolo(tmp_path, {"a.jpg": (100, 100)})
    assert dati.geometrie == {}
    assert dati.classi == []


def test_da_yolo_indice_negativo_scartato(tmp_path):
    _scrivi(tmp_path / "classes.txt", "uva\nfoglia\n")
    _scrivi(tmp_path / "a.txt", "-1 0.5 0.5 0.2 0.2\n0 0.5 0.5 0.2 0.2\n")
    dati = da_yolo(tmp_path, {"a.jpg": (100, 100)})
    assert len(dati.geometrie["a"]) == 1
    assert dati.geometrie["a"][0]["classe"] == "uva"
    assert dati.scartate == 1


def test_da_yolo_indice_oltre_classes_txt_estende(tmp_path):
    _scrivi(tmp_path / "classes.txt", "uva\n")
    _scrivi(tmp_path / "a.txt", "2 0.5 0.5 0.2 0.2\n")
    dati = da_yolo(tmp_path, {"a.jpg": (100, 100)})
    assert dati.classi == ["uva", "classe_1", "classe_2"]
    assert dati.geometrie["a"][0]["classe"] == "classe_2"


def test_da_yolo_righe_malformate_contate(tmp_path):
    _scrivi(tmp_path / "classes.txt", "uva\n")
    _scrivi(tmp_path / "a.txt", "0 0.5 0.5 0.2 0.2\nxx non numerica\n9 corto\n")
    dati = da_yolo(tmp_path, {"a.jpg": (100, 100)})
    assert len(dati.geometrie["a"]) == 1
    assert dati.scartate == 2


def test_da_coco_detection(tmp_path):
    coco = {
        "images": [{"id": 1, "file_name": "a.jpg"}],
        "categories": [{"id": 1, "name": "sana"}, {"id": 2, "name": "esca"}],
        "annotations": [
            {"id": 1, "image_id": 1, "category_id": 2, "bbox": [10, 20, 100, 40], "iscrowd": 0},
        ],
    }
    percorso = tmp_path / "coco.json"
    percorso.write_text(json.dumps(coco), encoding="utf-8")
    dati = da_coco(percorso)
    assert dati.classi == ["sana", "esca"]
    g = dati.geometrie["a.jpg"][0]
    assert g == {"tipo": "box", "classe": "esca", "x": 10.0, "y": 20.0,
                 "w": 100.0, "h": 40.0, "origine": "modello"}


def test_da_coco_segmentation_precede_bbox(tmp_path):
    coco = {
        "images": [{"id": 1, "file_name": "sub/a.jpg"}],
        "categories": [{"id": 1, "name": "sana"}],
        "annotations": [{
            "id": 1, "image_id": 1, "category_id": 1, "bbox": [0, 0, 50, 50],
            "segmentation": [[0, 0, 50, 0, 50, 50]], "iscrowd": 0,
        }],
    }
    percorso = tmp_path / "coco.json"
    percorso.write_text(json.dumps(coco), encoding="utf-8")
    dati = da_coco(percorso)
    assert len(dati.geometrie["a.jpg"]) == 1
    g = dati.geometrie["a.jpg"][0]
    assert g["tipo"] == "poligono"
    assert g["punti"] == [[0.0, 0.0], [50.0, 0.0], [50.0, 50.0]]


def test_da_coco_annotazione_orfana_ignorata(tmp_path):
    coco = {
        "images": [{"id": 1, "file_name": "a.jpg"}],
        "categories": [{"id": 1, "name": "sana"}],
        "annotations": [
            {"id": 1, "image_id": 99, "category_id": 1, "bbox": [1, 1, 2, 2], "iscrowd": 0},
            {"id": 2, "image_id": 1, "category_id": 99, "bbox": [1, 1, 2, 2], "iscrowd": 0},
        ],
    }
    percorso = tmp_path / "coco.json"
    percorso.write_text(json.dumps(coco), encoding="utf-8")
    dati = da_coco(percorso)
    assert dati.geometrie == {}


def test_da_coco_segmentazione_dispari_ignorata(tmp_path):
    coco = {
        "images": [{"id": 1, "file_name": "a.jpg"}],
        "categories": [{"id": 1, "name": "sana"}],
        "annotations": [{
            "id": 1, "image_id": 1, "category_id": 1, "bbox": [1, 2, 3, 4],
            "segmentation": [[0, 0, 50, 0, 50, 50, 20]], "iscrowd": 0,
        }],
    }
    percorso = tmp_path / "coco.json"
    percorso.write_text(json.dumps(coco), encoding="utf-8")
    dati = da_coco(percorso)
    # poligono degenere (7 coordinate, dispari) scartato, resta il bbox
    assert len(dati.geometrie["a.jpg"]) == 1
    assert dati.geometrie["a.jpg"][0]["tipo"] == "box"


def test_da_coco_rle_cade_su_bbox(tmp_path):
    coco = {
        "images": [{"id": 1, "file_name": "a.jpg"}],
        "categories": [{"id": 1, "name": "sana"}],
        "annotations": [{
            "id": 1, "image_id": 1, "category_id": 1, "bbox": [1, 2, 3, 4],
            "segmentation": {"size": [10, 10], "counts": "..."}, "iscrowd": 1,
        }],
    }
    percorso = tmp_path / "coco.json"
    percorso.write_text(json.dumps(coco), encoding="utf-8")
    dati = da_coco(percorso)
    assert dati.geometrie["a.jpg"][0]["tipo"] == "box"


def test_da_coco_bbox_malformato_scartato_e_contato(tmp_path):
    coco = {
        "images": [{"id": 1, "file_name": "a.jpg"}],
        "categories": [{"id": 1, "name": "sana"}],
        "annotations": [
            {"id": 1, "image_id": 1, "category_id": 1, "bbox": [1, 2, "x", 4], "iscrowd": 0},
        ],
    }
    percorso = tmp_path / "coco.json"
    percorso.write_text(json.dumps(coco), encoding="utf-8")
    dati = da_coco(percorso)
    assert dati.geometrie == {}
    assert dati.scartate == 1


def test_da_coco_poligono_con_null_scartato(tmp_path):
    coco = {
        "images": [{"id": 1, "file_name": "a.jpg"}],
        "categories": [{"id": 1, "name": "sana"}],
        "annotations": [{
            "id": 1, "image_id": 1, "category_id": 1,
            "segmentation": [[0, 0, 50, None, 50, 50]], "iscrowd": 0,
        }],
    }
    percorso = tmp_path / "coco.json"
    percorso.write_text(json.dumps(coco), encoding="utf-8")
    dati = da_coco(percorso)
    assert dati.geometrie == {}
    assert dati.scartate == 1


def test_da_coco_json_non_coco_solleva_value_error(tmp_path):
    percorso = tmp_path / "coco.json"
    percorso.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(ValueError):
        da_coco(percorso)


def test_da_coco_annotazione_non_dict_scartata(tmp_path):
    coco = {
        "images": [{"id": 1, "file_name": "a.jpg"}],
        "categories": [{"id": 1, "name": "sana"}],
        "annotations": [None, "spazzatura"],
    }
    percorso = tmp_path / "coco.json"
    percorso.write_text(json.dumps(coco), encoding="utf-8")
    dati = da_coco(percorso)
    assert dati.geometrie == {}
    assert dati.scartate == 2


def test_da_labelme(tmp_path):
    dati_json = {
        "imagePath": "a.jpg", "imageHeight": 100, "imageWidth": 200,
        "shapes": [
            {"label": "uva", "shape_type": "rectangle", "points": [[10, 20], [110, 60]]},
            {"label": "foglia", "shape_type": "polygon", "points": [[0, 0], [10, 0], [10, 10]]},
            {"label": "cerchio", "shape_type": "circle", "points": [[5, 5], [7, 7]]},
        ],
    }
    (tmp_path / "a.json").write_text(json.dumps(dati_json), encoding="utf-8")
    dati = da_labelme(tmp_path)
    assert dati.classi == ["uva", "foglia"]  # 'cerchio' non produce geometrie né classi
    assert len(dati.geometrie["a.jpg"]) == 2
    box = dati.geometrie["a.jpg"][0]
    assert box == {"tipo": "box", "classe": "uva", "x": 10.0, "y": 20.0,
                   "w": 100.0, "h": 40.0, "origine": "modello"}
    pol = dati.geometrie["a.jpg"][1]
    assert pol["tipo"] == "poligono"
    assert pol["classe"] == "foglia"
    assert pol["punti"] == [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]]


def test_da_labelme_json_corrotto_saltato(tmp_path):
    (tmp_path / "cattivo.json").write_text("{non valido", encoding="utf-8")
    dati = da_labelme(tmp_path)
    assert dati.geometrie == {}


def test_da_labelme_shape_malformata_scartata(tmp_path):
    dati_json = {
        "imagePath": "a.jpg",
        "shapes": [
            {"label": "uva", "shape_type": "rectangle", "points": [[0, None], [10, 10]]},
            {"label": "ok", "shape_type": "polygon", "points": [[0, 0], [10, 0], [10, 10]]},
            "non-dict",
            {"label": "corto", "shape_type": "rectangle", "points": [[1, 1]]},
        ],
    }
    (tmp_path / "a.json").write_text(json.dumps(dati_json), encoding="utf-8")
    dati = da_labelme(tmp_path)
    assert len(dati.geometrie["a.jpg"]) == 1
    assert dati.scartate == 3  # None, non-dict, rectangle con un punto solo


def test_da_labelme_json_non_dict_saltato(tmp_path):
    (tmp_path / "lista.json").write_text(json.dumps([1, 2]), encoding="utf-8")
    dati = da_labelme(tmp_path)
    assert dati.geometrie == {}


def test_da_labelme_label_vuota_e_shapes_non_lista(tmp_path):
    (tmp_path / "a.json").write_text(
        json.dumps({"imagePath": "a.jpg", "shapes": 5}), encoding="utf-8")
    (tmp_path / "b.json").write_text(
        json.dumps({"imagePath": "b.jpg", "shapes": [
            {"label": "", "shape_type": "rectangle", "points": [[0, 0], [10, 10]]},
        ]}), encoding="utf-8")
    dati = da_labelme(tmp_path)
    assert dati.geometrie == {}  # shapes non-lista: file saltato; label vuota: scartata
    assert dati.scartate == 1


def test_da_labelme_box_degenere_scartato(tmp_path):
    dati_json = {"imagePath": "a.jpg", "shapes": [
        {"label": "uva", "shape_type": "rectangle", "points": [[5, 5], [5, 5]]},
    ]}
    (tmp_path / "a.json").write_text(json.dumps(dati_json), encoding="utf-8")
    dati = da_labelme(tmp_path)
    assert dati.geometrie == {}
    assert dati.scartate == 1


VOC_XML = """<annotation>
  <filename>a.jpg</filename>
  <object>
    <name>uva</name>
    <bndbox><xmin>10</xmin><ymin>20</ymin><xmax>110</xmax><ymax>60</ymax></bndbox>
  </object>
  <object>
    <name>uva</name>
    <bndbox><xmin>1</xmin><ymin>1</ymin><xmax>0</xmax><ymax>5</ymax></bndbox>
  </object>
</annotation>"""


def test_da_voc(tmp_path):
    (tmp_path / "a.xml").write_text(VOC_XML, encoding="utf-8")
    dati = da_voc(tmp_path)
    assert dati.classi == ["uva"]
    assert len(dati.geometrie["a.jpg"]) == 1  # il box degenere (xmax<xmin) e' scartato
    assert dati.scartate == 1
    g = dati.geometrie["a.jpg"][0]
    assert g == {"tipo": "box", "classe": "uva", "x": 10.0, "y": 20.0,
                 "w": 100.0, "h": 40.0, "origine": "modello"}


def test_da_voc_xml_corrotto_saltato(tmp_path):
    (tmp_path / "cattivo.xml").write_text("<annotation><filename>x.jpg", encoding="utf-8")
    dati = da_voc(tmp_path)
    assert dati.geometrie == {}


def test_da_voc_object_senza_bndbox_e_non_numerico(tmp_path):
    xml = """<annotation><filename>b.jpg</filename>
  <object><name>uva</name></object>
  <object><name>uva</name><bndbox><xmin>a</xmin><ymin>0</ymin><xmax>9</xmax><ymax>9</ymax></bndbox></object>
</annotation>"""
    (tmp_path / "b.xml").write_text(xml, encoding="utf-8")
    dati = da_voc(tmp_path)
    assert dati.geometrie == {}
    assert dati.scartate == 2


def test_da_voc_name_vuoto_scartato(tmp_path):
    xml = """<annotation><filename>c.jpg</filename>
  <object><name></name><bndbox><xmin>0</xmin><ymin>0</ymin><xmax>9</xmax><ymax>9</ymax></bndbox></object>
</annotation>"""
    (tmp_path / "c.xml").write_text(xml, encoding="utf-8")
    dati = da_voc(tmp_path)
    assert dati.geometrie == {}
    assert dati.scartate == 1


def test_da_voc_bndbox_parziale_scartato(tmp_path):
    xml = """<annotation><filename>c.jpg</filename>
  <object><name>uva</name><bndbox><xmax>9</xmax><ymax>9</ymax></bndbox></object>
</annotation>"""
    (tmp_path / "c.xml").write_text(xml, encoding="utf-8")
    dati = da_voc(tmp_path)
    assert dati.geometrie == {}
    assert dati.scartate == 1


def test_da_yolo_tutte_righe_malformate_vuoto(tmp_path):
    _scrivi(tmp_path / "classes.txt", "uva\n")
    _scrivi(tmp_path / "a.txt", "xx malformata\n")
    dati = da_yolo(tmp_path, {"a.jpg": (100, 100)})
    assert dati.geometrie == {}
    assert dati.scartate == 1


class FintoBoxes:
    def __init__(self, xyxy, conf, cls):
        self.xyxy = np.array(xyxy, dtype=float)
        self.conf = np.array(conf, dtype=float)
        self.cls = np.array(cls, dtype=float)


class FintoRisultato:
    def __init__(self, boxes, masks=None):
        self.boxes = boxes
        self.masks = masks
        self.names = {0: "uva", 1: "foglia"}


class FintoModello:
    def __init__(self, risultato):
        self.risultato = risultato
        self.ultima_soglia = None

    def predict(self, immagine, conf=0.25, verbose=False):
        self.ultima_soglia = conf
        return [self.risultato]


def test_ultralytics_disponibile_torna_bool():
    assert isinstance(ultralytics_disponibile(), bool)


def test_geometrie_da_risultato_box():
    boxes = FintoBoxes([[10, 20, 110, 60]], [0.87], [0])
    geometrie = geometrie_da_risultato(FintoRisultato(boxes), "yolo11n.pt")
    assert len(geometrie) == 1
    g = geometrie[0]
    assert g["tipo"] == "box"
    assert g["classe"] == "uva"
    assert (g["x"], g["y"], g["w"], g["h"]) == (10.0, 20.0, 100.0, 40.0)
    assert g["origine"] == "modello"
    assert g["confidenza"] == pytest.approx(0.87)
    assert g["modello"] == "yolo11n.pt"


def test_geometrie_da_risultato_maschere_poligoni():
    boxes = FintoBoxes([[0, 0, 10, 10], [5, 5, 15, 15]], [0.9, 0.4], [0, 1])

    class FinteMaschere:
        xy = [np.array([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]]),
              np.array([[5.0, 5.0], [15.0, 5.0], [15.0, 15.0]])]

    geometrie = geometrie_da_risultato(FintoRisultato(boxes, masks=FinteMaschere()), "m.pt")
    assert len(geometrie) == 2
    assert all(g["tipo"] == "poligono" for g in geometrie)
    assert geometrie[0]["punti"][0] == [0.0, 0.0]
    assert geometrie[1]["classe"] == "foglia"


def test_annota_immagine_passa_soglia_al_modello():
    boxes = FintoBoxes([[10, 20, 110, 60]], [0.87], [0])
    modello = FintoModello(FintoRisultato(boxes))
    geometrie = annota_immagine(modello, np.zeros((4, 4, 3), dtype=np.uint8), 0.5, "m.pt")
    assert modello.ultima_soglia == 0.5
    assert geometrie[0]["classe"] == "uva"


def test_annota_immagine_zero_risultati():
    class FintoModelloVuoto:
        def predict(self, immagine, conf=0.25, verbose=False):
            return []

    geometrie = annota_immagine(
        FintoModelloVuoto(), np.zeros((4, 4, 3), dtype=np.uint8), 0.25, "m.pt")
    assert geometrie == []


def test_import_pigro_ultralytics():
    import importlib
    import sys

    sys.modules.pop("ultralytics", None)
    importlib.reload(importlib.import_module("labeling_tool.annotazioni_auto"))
    assert "ultralytics" not in sys.modules


def test_geometrie_da_risultato_tensor_con_cpu():
    class FintoTensore:
        def __init__(self, dati):
            self._dati = np.array(dati, dtype=float)

        def cpu(self):
            return self._dati

    class FintiBoxesTensor:
        def __init__(self):
            self.xyxy = FintoTensore([[10, 20, 110, 60]])
            self.conf = FintoTensore([0.87])
            self.cls = FintoTensore([0])

    geometrie = geometrie_da_risultato(FintoRisultato(FintiBoxesTensor()), "m.pt")
    assert len(geometrie) == 1
    assert geometrie[0]["tipo"] == "box"
    assert geometrie[0]["w"] == 100.0


def test_geometrie_da_risultato_maschere_più_corte_dei_box():
    boxes = FintoBoxes([[0, 0, 10, 10]], [0.9], [0])

    class FinteMaschereCorte:
        xy = []

    geometrie = geometrie_da_risultato(FintoRisultato(boxes, masks=FinteMaschereCorte()), "m.pt")
    assert len(geometrie) == 1
    assert geometrie[0]["tipo"] == "box"
