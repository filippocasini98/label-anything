"""Test della registry dei cursori, delle factory e della persistenza."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication

from labeling_tool.cursors import (
    CURSORE_DEFAULT,
    LATO_LOGICO,
    CURSORI,
    crea_cursore,
    cursore_valido,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_registry_sette_cursori_in_ordine_stabile():
    assert list(CURSORI) == [
        "crosshair", "precision", "annotation", "target",
        "punto", "freccia", "invisibile",
    ]


def test_nomi_ed_etichette_univoci():
    assert CURSORE_DEFAULT in CURSORI
    nomi = [d.nome for d in CURSORI.values()]
    etichette = [d.etichetta for d in CURSORI.values()]
    assert len(nomi) == len(set(nomi))
    assert len(etichette) == len(set(etichette))
    assert all(d.etichetta.strip() for d in CURSORI.values())


def test_cursore_valido_fallback():
    assert cursore_valido("target") == "target"
    assert cursore_valido("pippo") == CURSORE_DEFAULT
    assert cursore_valido("") == CURSORE_DEFAULT
    assert cursore_valido(None) == CURSORE_DEFAULT


def test_factory_cursori_standard(qapp):
    assert crea_cursore("crosshair").shape() == Qt.CursorShape.CrossCursor
    assert crea_cursore("freccia").shape() == Qt.CursorShape.ArrowCursor
    assert crea_cursore("invisibile").shape() == Qt.CursorShape.BlankCursor
    assert crea_cursore("pippo").shape() == Qt.CursorShape.CrossCursor


@pytest.mark.parametrize("nome", ["precision", "annotation", "target", "punto"])
def test_factory_cursori_custom(qapp, nome):
    cursore = crea_cursore(nome)
    pm = cursore.pixmap()
    assert not pm.isNull()
    assert pm.width() == LATO_LOGICO * 2  # fisico 48x48
    assert pm.devicePixelRatio() == 2.0   # logico 24x24
    hotspot = cursore.hotSpot()
    assert hotspot == QPoint(LATO_LOGICO // 2, LATO_LOGICO // 2)


def test_persistenza_round_trip(tmp_path):
    from labeling_tool.cursors import leggi_cursore, salva_cursore

    percorso = tmp_path / "sotto" / "cursore.txt"
    assert leggi_cursore(percorso) == CURSORE_DEFAULT  # file assente -> default
    salva_cursore("target", percorso)
    assert leggi_cursore(percorso) == "target"
    assert percorso.parent.exists()  # le directory vengono create


def test_persistenza_normalizza_e_resiste_a_garbage(tmp_path):
    from labeling_tool.cursors import leggi_cursore, salva_cursore

    percorso = tmp_path / "cursore.txt"
    salva_cursore("pippo", percorso)          # nome non valido: salvato il default
    assert leggi_cursore(percorso) == CURSORE_DEFAULT
    percorso.write_text("robaccia\n", encoding="utf-8")
    assert leggi_cursore(percorso) == CURSORE_DEFAULT
    percorso.write_bytes(b"\x80\x81\xff")
    assert leggi_cursore(percorso) == CURSORE_DEFAULT
