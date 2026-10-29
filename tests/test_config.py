import pytest

from labeling_tool.config import (
    EtichettaDef,
    ProgettoConfig,
    config_da_dict,
    config_in_dict,
    config_default,
)


def test_config_default_coerente():
    c = config_default()
    assert isinstance(c, ProgettoConfig)
    assert c.multi_label is False
    assert c.workflow == "classificazione"
    assert ".jpg" in c.estensioni
    assert c.scala_px_per_unita == 1.0
    assert len(c.etichette) >= 1
    assert c.valida() == []


def test_round_trip_dict():
    c = config_default()
    c.etichette.append(EtichettaDef(nome="esca", colore="#F39C12", tasto="2"))
    d = config_in_dict(c)
    c2 = config_da_dict(d)
    assert c2 == c


def test_valida_nome_duplicato():
    c = config_default()
    c.etichette = [
        EtichettaDef("sana", "#3CB44B", "1"),
        EtichettaDef("sana", "#FF0000", "2"),
    ]
    errori = c.valida()
    assert any("nome" in e.lower() for e in errori)


def test_valida_tasto_duplicato():
    c = config_default()
    c.etichette = [
        EtichettaDef("sana", "#3CB44B", "1"),
        EtichettaDef("morta", "#D83A3A", "1"),
    ]
    errori = c.valida()
    assert any("tasto" in e.lower() for e in errori)


def test_valida_colore_non_hex():
    c = config_default()
    c.etichette = [EtichettaDef("sana", "rosso", "1")]
    errori = c.valida()
    assert any("colore" in e.lower() for e in errori)


def test_valida_workflow_sconosciuto():
    c = config_default()
    c.workflow = "segmentazione"
    assert c.valida() != []


def test_da_dict_tollerante():
    d = config_in_dict(config_default())
    del d["multi_label"]
    del d["scala_px_per_unita"]
    c = config_da_dict(d)
    assert c.multi_label is False
    assert c.scala_px_per_unita == 1.0


def test_config_campi_modello_default():
    c = config_default()
    assert c.modello_percorso == ""
    assert c.modello_soglia == 0.25
    assert c.mappa_classi == {}
    assert c.salta_gia_annotate is True


def test_round_trip_campi_modello():
    c = config_default()
    c.modello_percorso = "yolo11n.pt"
    c.modello_soglia = 0.5
    c.mappa_classi = {"uva": "acino"}
    c.salta_gia_annotate = False
    assert config_da_dict(config_in_dict(c)) == c


def test_da_dict_campi_modello_mancanti():
    d = config_in_dict(config_default())
    for chiave in ("modello_percorso", "modello_soglia", "mappa_classi", "salta_gia_annotate"):
        del d[chiave]
    c = config_da_dict(d)
    assert c.modello_percorso == ""
    assert c.modello_soglia == 0.25
    assert c.mappa_classi == {}
    assert c.salta_gia_annotate is True


def test_da_dict_soglia_modello_non_numerica():
    d = config_in_dict(config_default())
    d["modello_soglia"] = "alto"
    c = config_da_dict(d)
    assert c.modello_soglia == 0.25
