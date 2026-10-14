"""Scansione delle immagini e cache LRU basata su OpenCV."""

import re
from collections import OrderedDict
from pathlib import Path
from typing import List, Optional, Set

import cv2
import numpy as np

PERCORSO_ULTIMA_CARTELLA = Path.home() / ".config" / "labeling-tool" / "ultima_cartella.txt"


def leggi_ultima_cartella(percorso: Optional[Path] = None) -> Optional[Path]:
    """Ultima cartella immagini usata, se esiste ancora."""
    percorso = percorso or PERCORSO_ULTIMA_CARTELLA
    try:
        testo = percorso.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if testo and Path(testo).is_dir():
        return Path(testo)
    return None


def salva_ultima_cartella(cartella: Path, percorso: Optional[Path] = None) -> None:
    percorso = percorso or PERCORSO_ULTIMA_CARTELLA
    try:
        percorso.parent.mkdir(parents=True, exist_ok=True)
        percorso.write_text(str(cartella), encoding="utf-8")
    except OSError:
        pass


def chiave_naturale(testo: str):
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", testo)]


def elenco_immagini(cartella: Path, estensioni: Set[str], ricorsivo: bool = False) -> List[Path]:
    """Elenco dei file immagine nella cartella, ordinato naturalmente."""
    if not cartella.exists():
        raise FileNotFoundError(f"Cartella non trovata: {cartella}")
    if not cartella.is_dir():
        raise NotADirectoryError(f"Il percorso non e' una cartella: {cartella}")
    estensioni_basse = {e.lower() for e in estensioni}
    iterator = cartella.rglob("*") if ricorsivo else cartella.iterdir()
    files = [p for p in iterator if p.is_file() and p.suffix.lower() in estensioni_basse]
    files.sort(key=lambda p: chiave_naturale(str(p)))
    return files


def leggi_cv(path: Path) -> Optional[np.ndarray]:
    """Legge un'immagine con OpenCV, gestendo percorsi con caratteri speciali."""
    try:
        dati = np.fromfile(str(path), dtype=np.uint8)
        return cv2.imdecode(dati, cv2.IMREAD_COLOR) if dati.size else None
    except (OSError, ValueError, cv2.error):
        return None


class ImageCache:
    """Cache LRU delle immagini decodificate."""

    def __init__(self, max_items: int = 12):
        self.max_items = max_items
        self._data: "OrderedDict[str, np.ndarray]" = OrderedDict()

    def get(self, path: Path) -> Optional[np.ndarray]:
        key = str(path)
        if key in self._data:
            self._data.move_to_end(key)
            return self._data[key]
        immagine = leggi_cv(path)
        if immagine is not None:
            self._data[key] = immagine
            while len(self._data) > self.max_items:
                self._data.popitem(last=False)
        return immagine

    def preload(self, paths: List[Path]) -> None:
        for p in paths:
            self.get(p)

    def rimuovi(self, path: Path) -> None:
        self._data.pop(str(path), None)


def cartella_dati(cartella: Path, num_immagini: int, nome: str = "etichettatura") -> Path:
    """Cartella dove salvare i dati del progetto.

    Con piu' immagini: sottocartella dedicata dentro la cartella immagini.
    Con una sola immagine: la cartella stessa, accanto all'immagine."""
    if num_immagini <= 1:
        return cartella
    return cartella / nome
