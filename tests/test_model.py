from pathlib import Path

import pytest

from labeling_tool.config import EtichettaDef, config_default
from labeling_tool.model import (
    Misura,
    Record,
    Storico,
    area_poligono,
    distanza_px,
)


def progetto_di_prova(tmp_path: Path):
    from labeling_tool.model import Progetto

    config = config_default()
    config.etichette = [EtichettaDef("sana", "#3CB44B", "1"), EtichettaDef("esca", "#F39C12", "2")]
    progetto = Progetto(config=config)
    progetto.immagini["a.jpg"] = Record(
        nome="a.jpg",
        etichette=["sana", "esca"],
        stato="completata",
        note="prova",
        geometrie=[
            {"tipo": "box", "classe": "esca", "x": 10.0, "y": 20.0, "w": 100.0, "h": 80.0},
            {"tipo": "poligono", "classe": "esca", "punti": [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]]},
        ],
        misure=[Misura(tipo="distanza", punti=[[0.0, 0.0], [30.0, 40.0]], valore_px=50.0)],
    )
    return progetto


def test_round_trip_progetto(tmp_path: Path):
    from labeling_tool.model import Progetto

    progetto = progetto_di_prova(tmp_path)
    percorso = tmp_path / "progetto.progetto.json"
    progetto.salva_atomico(percorso)
    caricato = Progetto.carica(percorso)
    assert caricato.config == progetto.config
    assert caricato.immagini == progetto.immagini
    r = caricato.immagini["a.jpg"]
    assert r.etichette == ["sana", "esca"]
    assert r.geometrie[0]["tipo"] == "box"
    assert r.misure[0].valore_px == 50.0


def test_carica_json_corrotto_crea_backup(tmp_path: Path):
    from labeling_tool.model import Progetto

    percorso = tmp_path / "progetto.progetto.json"
    percorso.write_text("{non valido", encoding="utf-8")
    caricato = Progetto.carica(percorso)
    assert caricato.immagini == {}
    assert caricato.config is not None
    backup = tmp_path / "progetto.progetto.json.corrotto"
    assert backup.exists()


def test_distanza_px():
    assert distanza_px((0.0, 0.0), (3.0, 4.0)) == 5.0


def test_area_poligono():
    quadrato = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
    assert area_poligono(quadrato) == pytest.approx(100.0)


def test_storico_annulla_ripristina():
    storico = Storico()
    prima = Record(nome="a.jpg", etichette=[])
    dopo = Record(nome="a.jpg", etichette=["sana"], stato="completata")
    storico.registra(0, prima, dopo)
    assert storico.puo_annullare()
    assert not storico.puo_ripristinare()
    azione = storico.annulla()
    assert azione.prima.etichette == []
    assert storico.puo_ripristinare()
    azione2 = storico.ripristina()
    assert azione2.dopo.etichette == ["sana"]
    assert not storico.puo_ripristinare()


def test_reindicizza_aggiunge_e_mantieni_orfani(tmp_path: Path):
    from labeling_tool.model import Progetto

    progetto = progetto_di_prova(tmp_path)
    percorso_b = tmp_path / "b.jpg"
    percorso_b.write_bytes(b"x")
    progetto.reindicizza([tmp_path / "a.jpg", percorso_b])
    assert "b.jpg" in progetto.immagini
    assert progetto.immagini["b.jpg"].stato == "non_etichettata"
    progetto.reindicizza([percorso_b])
    assert "a.jpg" in progetto.immagini
    assert progetto.immagini["a.jpg"].stato == "rimossa"


def test_dimensioni_oggetto():
    from labeling_tool.model import dimensioni_oggetto

    assert dimensioni_oggetto([[10.0, 20.0], [110.0, 60.0]]) == (100.0, 40.0)
    assert dimensioni_oggetto([[110.0, 60.0], [10.0, 20.0]]) == (100.0, 40.0)
    assert dimensioni_oggetto([[1.0, 1.0]]) == (0.0, 0.0)


def test_dimensioni_bbox_poligono():
    from labeling_tool.model import dimensioni_bbox_poligono

    punti = [[0.0, 0.0], [50.0, 10.0], [40.0, 60.0], [10.0, 30.0]]
    assert dimensioni_bbox_poligono(punti) == (50.0, 60.0)
    assert dimensioni_bbox_poligono([]) == (0.0, 0.0)
