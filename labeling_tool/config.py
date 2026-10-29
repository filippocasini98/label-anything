"""Schema della configurazione del progetto: caricamento, salvataggio, validazione."""

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List

_RE_COLORE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def versione_app() -> str:
    """Versione dell'applicazione: 'dev' in sviluppo, il tag della release nella build."""
    return os.environ.get("APP_VERSION", "dev")
WORKFLOW_VALIDI = ("classificazione", "classificazione+geometrie", "geometrie")
ESTENSIONI_DEFAULT = [".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"]


@dataclass
class EtichettaDef:
    """Una classe/etichetta configurabile: nome, colore e tasto scorciatoia."""

    nome: str
    colore: str
    tasto: str

    def in_dict(self) -> dict:
        return {"nome": self.nome, "colore": self.colore, "tasto": self.tasto}

    @staticmethod
    def da_dict(d: dict) -> "EtichettaDef":
        return EtichettaDef(
            nome=str(d.get("nome", "")).strip(),
            colore=str(d.get("colore", "#BDBDBD")).strip(),
            tasto=str(d.get("tasto", "")).strip(),
        )


@dataclass
class ProgettoConfig:
    """Configurazione completa di un progetto di etichettatura."""

    nome_progetto: str = "progetto"
    etichettatore: str = ""
    multi_label: bool = False
    workflow: str = "classificazione"
    etichette: List[EtichettaDef] = field(default_factory=list)
    estensioni: List[str] = field(default_factory=lambda: list(ESTENSIONI_DEFAULT))
    ricorsivo: bool = False
    unita_misura: str = "px"
    scala_px_per_unita: float = 1.0
    misure_abilitate: bool = True
    filtri_abilitati: bool = True
    # annotazione assistita
    modello_percorso: str = ""
    modello_soglia: float = 0.25
    mappa_classi: Dict[str, str] = field(default_factory=dict)
    salta_gia_annotate: bool = True

    def valida(self) -> List[str]:
        """Ritorna la lista degli errori di configurazione (vuota se valida)."""
        errori: List[str] = []
        if not self.nome_progetto.strip():
            errori.append("Il nome del progetto non puo' essere vuoto.")
        if self.workflow not in WORKFLOW_VALIDI:
            errori.append(f"Workflow non valido: {self.workflow!r}")
        nomi = [e.nome for e in self.etichette]
        tasti = [e.tasto for e in self.etichette]
        if len(nomi) != len(set(nomi)):
            duplicati = sorted({n for n in nomi if nomi.count(n) > 1})
            errori.append(f"Nome etichetta duplicato: {', '.join(duplicati)}")
        tasti_pieni = [t for t in tasti if t]
        if len(tasti_pieni) != len(set(tasti_pieni)):
            duplicati = sorted({t for t in tasti_pieni if tasti_pieni.count(t) > 1})
            errori.append(f"Tasto scorciatoia duplicato: {', '.join(duplicati)}")
        for e in self.etichette:
            if not e.nome.strip():
                errori.append("Esiste un'etichetta con nome vuoto.")
                break
        for e in self.etichette:
            if not _RE_COLORE.match(e.colore):
                errori.append(f"Colore non valido per '{e.nome}': {e.colore!r} (atteso #RRGGBB).")
        if self.workflow in ("classificazione+geometrie", "geometrie") and not self.etichette:
            errori.append("Servono almeno 2 etichette nei workflow con geometrie.")
        if self.scala_px_per_unita <= 0:
            errori.append("La scala px/unita' deve essere maggiore di zero.")
        return errori

    def colore_di(self, nome_etichetta: str) -> str:
        for e in self.etichette:
            if e.nome == nome_etichetta:
                return e.colore
        return "#BDBDBD"

    def etichetta_da_tasto(self, tasto: str) -> str:
        for e in self.etichette:
            if e.tasto == tasto:
                return e.nome
        return ""


def config_default() -> ProgettoConfig:
    return ProgettoConfig(
        nome_progetto="progetto",
        etichettatore="",
        multi_label=False,
        workflow="classificazione",
        etichette=[
            EtichettaDef("positivo", "#3CB44B", "1"),
            EtichettaDef("negativo", "#D83A3A", "2"),
            EtichettaDef("dubbio", "#F39C12", "3"),
        ],
        estensioni=list(ESTENSIONI_DEFAULT),
        ricorsivo=False,
        unita_misura="px",
        scala_px_per_unita=1.0,
        misure_abilitate=True,
        filtri_abilitati=True,
    )


def config_in_dict(c: ProgettoConfig) -> dict:
    return {
        "nome_progetto": c.nome_progetto,
        "etichettatore": c.etichettatore,
        "multi_label": c.multi_label,
        "workflow": c.workflow,
        "etichette": [e.in_dict() for e in c.etichette],
        "estensioni": list(c.estensioni),
        "ricorsivo": c.ricorsivo,
        "unita_misura": c.unita_misura,
        "scala_px_per_unita": c.scala_px_per_unita,
        "misure_abilitate": c.misure_abilitate,
        "filtri_abilitati": c.filtri_abilitati,
        "modello_percorso": c.modello_percorso,
        "modello_soglia": c.modello_soglia,
        "mappa_classi": dict(c.mappa_classi),
        "salta_gia_annotate": c.salta_gia_annotate,
    }


def config_da_dict(d: dict) -> ProgettoConfig:
    default = config_default()
    etichette = [EtichettaDef.da_dict(e) for e in d.get("etichette", [])]
    estensioni = d.get("estensioni") or default.estensioni
    scala = d.get("scala_px_per_unita", default.scala_px_per_unita)
    try:
        scala = float(scala)
    except (TypeError, ValueError):
        scala = default.scala_px_per_unita
    try:
        soglia_modello = float(d.get("modello_soglia", default.modello_soglia))
    except (TypeError, ValueError):
        soglia_modello = default.modello_soglia
    return ProgettoConfig(
        nome_progetto=str(d.get("nome_progetto", default.nome_progetto)).strip() or default.nome_progetto,
        etichettatore=str(d.get("etichettatore", "")),
        multi_label=bool(d.get("multi_label", False)),
        workflow=d.get("workflow", default.workflow),
        etichette=etichette,
        estensioni=[str(e) for e in estensioni],
        ricorsivo=bool(d.get("ricorsivo", False)),
        unita_misura=str(d.get("unita_misura", default.unita_misura)),
        scala_px_per_unita=scala,
        misure_abilitate=bool(d.get("misure_abilitate", True)),
        filtri_abilitati=bool(d.get("filtri_abilitati", True)),
        modello_percorso=str(d.get("modello_percorso", "")),
        modello_soglia=soglia_modello,
        mappa_classi={str(k): str(v) for k, v in d.get("mappa_classi", {}).items()},
        salta_gia_annotate=bool(d.get("salta_gia_annotate", True)),
    )
