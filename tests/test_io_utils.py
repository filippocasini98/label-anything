from pathlib import Path

from labeling_tool.io_utils import (
    chiave_naturale,
    elenco_immagini,
    leggi_cv,
    leggi_ultima_cartella,
    salva_ultima_cartella,
)


def test_chiave_naturale_ordina_numericamente():
    assert chiave_naturale("img2.jpg") < chiave_naturale("img10.jpg")
    assert chiave_naturale("a1") < chiave_naturale("a2") < chiave_naturale("a10")


def test_elenco_immagini_filtra_estensioni(tmp_path: Path):
    (tmp_path / "a.jpg").write_bytes(b"x")
    (tmp_path / "b.PNG").write_bytes(b"x")
    (tmp_path / "c.txt").write_bytes(b"x")
    (tmp_path / "ignora.jpg").mkdir()
    files = elenco_immagini(tmp_path, {".jpg", ".png"}, ricorsivo=False)
    nomi = [f.name for f in files]
    assert nomi == ["a.jpg", "b.PNG"]


def test_elenco_immagini_ricorsivo(tmp_path: Path):
    (tmp_path / "a.jpg").write_bytes(b"x")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.jpg").write_bytes(b"x")
    files = elenco_immagini(tmp_path, {".jpg"}, ricorsivo=False)
    assert [f.name for f in files] == ["a.jpg"]
    files = elenco_immagini(tmp_path, {".jpg"}, ricorsivo=True)
    assert len(files) == 2


def test_elenco_immagini_ordina_naturalmente(tmp_path: Path):
    for nome in ("img10.jpg", "img2.jpg", "img1.jpg"):
        (tmp_path / nome).write_bytes(b"x")
    files = elenco_immagini(tmp_path, {".jpg"}, ricorsivo=False)
    assert [f.name for f in files] == ["img1.jpg", "img2.jpg", "img10.jpg"]


def test_cartella_mancante_solleva(tmp_path: Path):
    import pytest

    with pytest.raises(FileNotFoundError):
        elenco_immagini(tmp_path / "inesistente", {".jpg"}, ricorsivo=False)


def test_leggi_cv_immagine_valida(tmp_path: Path):
    import numpy as np

    immagine = np.zeros((4, 6, 3), dtype=np.uint8)
    percorso = tmp_path / "t.png"
    import cv2

    assert cv2.imwrite(str(percorso), immagine)
    caricata = leggi_cv(percorso)
    assert caricata is not None
    assert caricata.shape == (4, 6, 3)


def test_leggi_cv_file_non_immagine(tmp_path: Path):
    percorso = tmp_path / "t.jpg"
    percorso.write_bytes(b"non sono un'immagine")
    assert leggi_cv(percorso) is None


def test_leggi_cv_file_mancante(tmp_path: Path):
    assert leggi_cv(tmp_path / "non_esiste.png") is None


def test_ultima_cartella_round_trip(tmp_path: Path):
    stato = tmp_path / "ultima.txt"
    assert leggi_ultima_cartella(stato) is None  # file inesistente
    cartella = tmp_path / "immagini"
    cartella.mkdir()
    salva_ultima_cartella(cartella, stato)
    assert leggi_ultima_cartella(stato) == cartella


def test_ultima_cartella_ignora_cartella_cancellata(tmp_path: Path):
    stato = tmp_path / "ultima.txt"
    cartella = tmp_path / "sparita"
    salva_ultima_cartella(cartella, stato)
    assert leggi_ultima_cartella(stato) is None  # la cartella non esiste piu'


def test_cartella_dati(tmp_path: Path):
    from labeling_tool.io_utils import cartella_dati

    assert cartella_dati(tmp_path, 1) == tmp_path          # immagine singola: stessa cartella
    assert cartella_dati(tmp_path, 0) == tmp_path
    assert cartella_dati(tmp_path, 5) == tmp_path / "etichettatura"
