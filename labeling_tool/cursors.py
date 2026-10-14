"""Cursori di annotazione selezionabili: registry, factory e preferenza su file."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QCursor, QPainter, QPen, QPixmap

CURSORE_DEFAULT = "crosshair"
LATO_LOGICO = 24  # px logici; 48 fisici con DPR 2
DPR = 2
PERCORSO_CURSORE = Path.home() / ".config" / "labeling-tool" / "cursore.txt"


@dataclass(frozen=True)
class CursorDef:
    nome: str
    etichetta: str
    factory: Callable[[], QCursor]


def _pixmap_logica() -> QPixmap:
    """Pixmap 24x24 logiche (48x48 fisiche, DPR 2): nitida su schermi Hi-DPI."""
    pm = QPixmap(LATO_LOGICO * DPR, LATO_LOGICO * DPR)
    pm.setDevicePixelRatio(DPR)
    pm.fill(Qt.transparent)
    return pm


def _cursore_custom(forma: Callable[[QPainter, QColor, float], None]) -> QCursor:
    """Disegna la forma due volte (contorno nero spesso, tratto bianco sottile)
    cosi' il cursore resta visibile su qualsiasi sfondo."""
    pm = _pixmap_logica()
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    forma(p, QColor(0, 0, 0, 200), 3)
    forma(p, QColor(255, 255, 255, 255), 1)
    p.end()
    # Hotspot in coordinate logiche, non fisiche
    return QCursor(pm, LATO_LOGICO // 2, LATO_LOGICO // 2)


def _forma_precisione(p: QPainter, colore: QColor, spessore: float) -> None:
    """Croce sottile con gap di 3 px al centro: il pixel esatto resta visibile."""
    c = LATO_LOGICO // 2
    gap = 3
    p.setPen(QPen(colore, spessore))
    p.drawLine(c, 0, c, c - gap)
    p.drawLine(c, c + gap, c, LATO_LOGICO)
    p.drawLine(0, c, c - gap, c)
    p.drawLine(c + gap, c, LATO_LOGICO, c)


def _forma_annotation(p: QPainter, colore: QColor, spessore: float) -> None:
    """Croce completa con cerchietto al centro."""
    c = LATO_LOGICO // 2
    p.setPen(QPen(colore, spessore))
    p.drawLine(c, 0, c, LATO_LOGICO)
    p.drawLine(0, c, LATO_LOGICO, c)
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(c - 4, c - 4, 8, 8)


def _forma_target(p: QPainter, colore: QColor, spessore: float) -> None:
    """Cerchio con tacche a croce all'esterno."""
    c = LATO_LOGICO // 2
    p.setPen(QPen(colore, spessore))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(c - 8, c - 8, 16, 16)
    gap = 3
    for x1, y1, x2, y2 in (
        (c, 0, c, gap), (c, LATO_LOGICO - gap, c, LATO_LOGICO),
        (0, c, gap, c), (LATO_LOGICO - gap, c, LATO_LOGICO, c),
    ):
        p.drawLine(x1, y1, x2, y2)


def _forma_punto(p: QPainter, colore: QColor, spessore: float) -> None:
    """Punto pieno di ~2 px: massima precisione sul pixel."""
    c = LATO_LOGICO // 2
    p.setPen(QPen(colore, spessore))
    p.setBrush(colore)
    p.drawEllipse(c - 1, c - 1, 2, 2)


CURSORI: Dict[str, CursorDef] = {
    "crosshair": CursorDef("crosshair", "Crosshair", lambda: QCursor(Qt.CrossCursor)),
    "precision": CursorDef("precision", "Precision crosshair", lambda: _cursore_custom(_forma_precisione)),
    "annotation": CursorDef("annotation", "Annotation crosshair", lambda: _cursore_custom(_forma_annotation)),
    "target": CursorDef("target", "Target", lambda: _cursore_custom(_forma_target)),
    "punto": CursorDef("punto", "Punto (pixel)", lambda: _cursore_custom(_forma_punto)),
    "freccia": CursorDef("freccia", "Freccia", lambda: QCursor(Qt.ArrowCursor)),
    "invisibile": CursorDef("invisibile", "Invisibile", lambda: QCursor(Qt.BlankCursor)),
}


def cursore_valido(nome: Optional[str]) -> str:
    """Nome normalizzato: il nome stesso se valido, altrimenti il default."""
    return nome if nome in CURSORI else CURSORE_DEFAULT


def crea_cursore(nome: Optional[str]) -> QCursor:
    return CURSORI[cursore_valido(nome)].factory()


def leggi_cursore(percorso: Optional[Path] = None) -> str:
    """Cursore salvato dall'utente; default se assente o non valido."""
    percorso = percorso or PERCORSO_CURSORE
    try:
        testo = percorso.read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return CURSORE_DEFAULT
    return cursore_valido(testo)


def salva_cursore(nome: str, percorso: Optional[Path] = None) -> None:
    """Scrive il nome normalizzato; errori di I/O ignorati."""
    percorso = percorso or PERCORSO_CURSORE
    try:
        percorso.parent.mkdir(parents=True, exist_ok=True)
        percorso.write_text(cursore_valido(nome), encoding="utf-8")
    except OSError:
        pass
