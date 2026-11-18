"""Modello dati: record per immagine, progetto JSON, undo/redo, calcoli di misura."""

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from labeling_tool.config import ProgettoConfig, config_da_dict, config_in_dict

SCHEMA_VERSION = 1


@dataclass
class Misura:
    """Una misura fatta sull'immagine."""

    tipo: str  # "distanza" | "area" | "conteggio"
    punti: List[List[float]] = field(default_factory=list)
    valore_px: Optional[float] = None

    def in_dict(self) -> dict:
        return {"tipo": self.tipo, "punti": [list(p) for p in self.punti], "valore_px": self.valore_px}

    @staticmethod
    def da_dict(d: dict) -> "Misura":
        return Misura(
            tipo=str(d.get("tipo", "")),
            punti=[[float(c) for c in p] for p in d.get("punti", [])],
            valore_px=float(d["valore_px"]) if d.get("valore_px") is not None else None,
        )


@dataclass
class Record:
    """Stato di annotazione di una singola immagine."""

    nome: str
    etichette: List[str] = field(default_factory=list)
    stato: str = "non_etichettata"
    note: str = ""
    da_revisionare: bool = False
    revisionata: bool = False
    da_verificare: bool = False
    data_modifica: str = ""
    etichettatore: str = ""
    geometrie: List[dict] = field(default_factory=list)
    misure: List[Misura] = field(default_factory=list)

    def copia(self) -> "Record":
        return Record(
            nome=self.nome,
            etichette=list(self.etichette),
            stato=self.stato,
            note=self.note,
            da_revisionare=self.da_revisionare,
            revisionata=self.revisionata,
            da_verificare=self.da_verificare,
            data_modifica=self.data_modifica,
            etichettatore=self.etichettatore,
            geometrie=[dict(g) for g in self.geometrie],
            misure=[Misura(m.tipo, [list(p) for p in m.punti], m.valore_px) for m in self.misure],
        )

    def in_dict(self) -> dict:
        return {
            "etichette": list(self.etichette),
            "stato": self.stato,
            "note": self.note,
            "da_revisionare": self.da_revisionare,
            "revisionata": self.revisionata,
            "da_verificare": self.da_verificare,
            "data_modifica": self.data_modifica,
            "etichettatore": self.etichettatore,
            "geometrie": self.geometrie,
            "misure": [m.in_dict() for m in self.misure],
        }

    @staticmethod
    def da_dict(nome: str, d: dict) -> "Record":
        return Record(
            nome=nome,
            etichette=[str(e) for e in d.get("etichette", [])],
            stato=str(d.get("stato", "non_etichettata")),
            note=str(d.get("note", "")),
            da_revisionare=bool(d.get("da_revisionare", False)),
            revisionata=bool(d.get("revisionata", False)),
            da_verificare=bool(d.get("da_verificare", False)),
            data_modifica=str(d.get("data_modifica", "")),
            etichettatore=str(d.get("etichettatore", "")),
            geometrie=list(d.get("geometrie", [])),
            misure=[Misura.da_dict(m) for m in d.get("misure", [])],
        )


@dataclass
class Azione:
    """Una modifica annullabile a un record."""

    indice: int
    prima: Record
    dopo: Record


class Storico:
    """Stack undo/redo di azioni sui record."""

    def __init__(self):
        self.undo: List[Azione] = []
        self.redo: List[Azione] = []

    def registra(self, indice: int, prima: Record, dopo: Record) -> None:
        if prima == dopo:
            return
        self.undo.append(Azione(indice, prima, dopo))
        self.redo.clear()

    def puo_annullare(self) -> bool:
        return bool(self.undo)

    def puo_ripristinare(self) -> bool:
        return bool(self.redo)

    def annulla(self) -> Optional[Azione]:
        if not self.undo:
            return None
        azione = self.undo.pop()
        self.redo.append(azione)
        return azione

    def ripristina(self) -> Optional[Azione]:
        if not self.redo:
            return None
        azione = self.redo.pop()
        self.undo.append(azione)
        return azione

    def svuota(self) -> None:
        self.undo.clear()
        self.redo.clear()


class Progetto:
    """Configurazione + annotazioni, persistito come JSON."""

    def __init__(self, config: ProgettoConfig, immagini: Optional[Dict[str, Record]] = None):
        self.config = config
        self.immagini: Dict[str, Record] = immagini if immagini is not None else {}

    def reindicizza(self, percorsi) -> None:
        """Sincronizza i record con l'elenco immagini: aggiunge i mancanti,
        segna come 'rimossa' quelli che non esistono piu' (senza cancellarli)."""
        nomi = [p.name for p in percorsi]
        for nome in nomi:
            if nome not in self.immagini:
                self.immagini[nome] = Record(nome=nome)
        for nome, record in self.immagini.items():
            if nome not in nomi and record.stato != "rimossa":
                record.stato = "rimossa"

    def in_dict(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "config": config_in_dict(self.config),
            "immagini": {nome: r.in_dict() for nome, r in self.immagini.items()},
        }

    @staticmethod
    def da_dict(d: dict) -> "Progetto":
        config = config_da_dict(d.get("config", {}))
        immagini = {
            str(nome): Record.da_dict(str(nome), r) for nome, r in d.get("immagini", {}).items()
        }
        return Progetto(config=config, immagini=immagini)

    def salva_atomico(self, percorso) -> None:
        dati = json.dumps(self.in_dict(), ensure_ascii=False, indent=2)
        temporaneo = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=str(percorso.parent),
                prefix=f".{percorso.stem}_", suffix=".tmp", delete=False
            ) as f:
                temporaneo = f.name
                f.write(dati)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporaneo, percorso)
        except OSError:
            if temporaneo and os.path.exists(temporaneo):
                try:
                    os.remove(temporaneo)
                except OSError:
                    pass
            raise

    @staticmethod
    def carica(percorso) -> "Progetto":
        if not percorso.exists():
            return Progetto(config_da_dict({}))
        try:
            with percorso.open("r", encoding="utf-8") as f:
                dati = json.load(f)
            return Progetto.da_dict(dati)
        except (OSError, ValueError) as errore:
            backup = percorso.with_name(percorso.name + ".corrotto")
            try:
                os.replace(str(percorso), str(backup))
            except OSError:
                pass
            print(f"Avviso: progetto non leggibile ({errore}), backup in {backup}")
            return Progetto(config_da_dict({}))


# ------------------------------------------------------------
# Calcoli di misura
# ------------------------------------------------------------

def distanza_px(p1, p2) -> float:
    return float(((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2) ** 0.5)


def area_poligono(punti) -> float:
    """Formula del laccio (shoelace); ritorna l'area in px quadrati."""
    n = len(punti)
    if n < 3:
        return 0.0
    somma = 0.0
    for i in range(n):
        x1, y1 = punti[i][0], punti[i][1]
        x2, y2 = punti[(i + 1) % n][0], punti[(i + 1) % n][1]
        somma += x1 * y2 - x2 * y1
    return abs(somma) / 2.0


def adesso_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def dimensioni_oggetto(punti) -> tuple:
    """Larghezza e altezza (px) di una misura 'oggetto' definita da due angoli opposti."""
    if len(punti) < 2:
        return 0.0, 0.0
    (x1, y1), (x2, y2) = punti[0], punti[1]
    return abs(x2 - x1), abs(y2 - y1)


def dimensioni_bbox_poligono(punti) -> tuple:
    """Larghezza e altezza (px) del bounding box di un poligono."""
    if not punti:
        return 0.0, 0.0
    xs = [p[0] for p in punti]
    ys = [p[1] for p in punti]
    return max(xs) - min(xs), max(ys) - min(ys)
