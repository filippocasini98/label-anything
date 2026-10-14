"""Visualizzatore immagine con zoom/pan, annotazioni geometriche e misure."""

from typing import Callable, List, Optional

import cv2
import numpy as np
from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPixmapItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
)

from labeling_tool.cursors import CURSORE_DEFAULT, CURSORI, crea_cursore, cursore_valido
from labeling_tool.model import area_poligono, distanza_px

MANIGLIA = 10.0  # dimensione in px di scena delle maniglie di resize
MIN_BOX = 5.0    # dimensione minima di un box creato col trascinamento


def cv_to_pixmap(immagine: np.ndarray) -> QPixmap:
    if immagine.ndim == 2:
        qimg = QImage(
            immagine.data, immagine.shape[1], immagine.shape[0],
            immagine.strides[0], QImage.Format_Grayscale8,
        ).copy()
    else:
        rgb = cv2.cvtColor(immagine, cv2.COLOR_BGR2RGB)
        qimg = QImage(
            rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0],
            QImage.Format_RGB888,
        ).copy()
    return QPixmap.fromImage(qimg)


class BoxItem(QGraphicsItem):
    """Box ridimensionabile e spostabile, con 8 maniglie di resize."""

    def __init__(self, indice: int, classe: str, rect: QRectF, colore: str,
                 limite: QRectF, on_modifica: Callable, on_selezione: Callable):
        super().__init__()
        self.indice = indice
        self.classe = classe
        self.colore = QColor(colore)
        self.limite = QRectF(limite)
        self.on_modifica = on_modifica
        self.on_selezione = on_selezione
        self.selezionato = False
        self.set_rect(rect)
        self.setAcceptHoverEvents(True)
        self._modalita = None
        self._prima: Optional[dict] = None

    def set_rect(self, rect: QRectF) -> None:
        self._rect = QRectF(rect)
        self.prepareGeometryChange()
        self.update()

    def boundingRect(self) -> QRectF:
        return self._rect.adjusted(-MANIGLIA, -MANIGLIA, MANIGLIA, MANIGLIA)

    def in_dict(self) -> dict:
        return {
            "tipo": "box", "classe": self.classe,
            "x": self._rect.x(), "y": self._rect.y(),
            "w": self._rect.width(), "h": self._rect.height(),
        }

    def _maniglie(self):
        r = self._rect
        return {
            "tl": QPointF(r.left(), r.top()), "tm": QPointF(r.center().x(), r.top()),
            "tr": QPointF(r.right(), r.top()), "ml": QPointF(r.left(), r.center().y()),
            "mr": QPointF(r.right(), r.center().y()),
            "bl": QPointF(r.left(), r.bottom()), "bm": QPointF(r.center().x(), r.bottom()),
            "br": QPointF(r.right(), r.bottom()),
        }

    def _maniglia_sotto(self, pos: QPointF) -> Optional[str]:
        soglia = MANIGLIA * 1.5
        for nome, centro in self._maniglie().items():
            if (pos - centro).manhattanLength() <= soglia:
                return nome
        return None

    def paint(self, painter: QPainter, option, widget=None) -> None:
        pen = QPen(self.colore, 2)
        if self.selezionato:
            pen.setWidth(3)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self._rect)
        painter.setPen(QPen(QColor("white"), 1))
        painter.setBrush(QBrush(self.colore))
        if self.selezionato:
            for centro in self._maniglie().values():
                painter.drawRect(
                    QRectF(centro.x() - MANIGLIA / 2, centro.y() - MANIGLIA / 2, MANIGLIA, MANIGLIA)
                )

    def mousePressEvent(self, event) -> None:
        pos = event.pos()
        if not self.selezionato and self.on_selezione:
            self.on_selezione(self.indice)
        maniglia = self._maniglia_sotto(pos) if self.selezionato else None
        if maniglia:
            self._modalita = maniglia
        elif self._rect.contains(pos):
            self._modalita = "sposta"
            self._offset = pos - self._rect.topLeft()
        else:
            event.ignore()
            return
        self._prima = self.in_dict()
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        pos = event.pos()
        if self._modalita == "sposta":
            top_left = pos - self._offset
            top_left.setX(max(self.limite.left(), min(top_left.x(), self.limite.right() - self._rect.width())))
            top_left.setY(max(self.limite.top(), min(top_left.y(), self.limite.bottom() - self._rect.height())))
            self.set_rect(QRectF(top_left, self._rect.size()))
        elif self._modalita and self.selezionato:
            r = QRectF(self._rect)
            if "l" in self._modalita:
                r.setLeft(pos.x())
            if "r" in self._modalita:
                r.setRight(pos.x())
            if "t" in self._modalita:
                r.setTop(pos.y())
            if "b" in self._modalita:
                r.setBottom(pos.y())
            r = r.normalized().intersected(self.limite)
            if r.width() >= 1 and r.height() >= 1:
                self.set_rect(r)
        event.accept()

    def leaveEvent(self, event) -> None:
        self._pos_mouse = None
        if self._croce_schermo:
            self.viewport().update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._modalita and self.on_modifica and self._prima is not None:
            dopo = self.in_dict()
            if dopo != self._prima:
                self.on_modifica(self.indice, dopo)
        self._modalita = None
        self._prima = None
        event.accept()


class ImageViewer(QGraphicsView):
    """Viewer con zoom/pan, creazione di box/poligoni, selezione e misure."""

    zoomChanged = Signal(float)
    geometriaAggiunta = Signal(dict)
    geometriaModificata = Signal(int, dict)
    misuraAggiunta = Signal(dict)
    selezioneCambiata = Signal(str, int)  # ("nessuna" | "box" | "poligono", indice)

    STRUMENTI = ("nav", "seleziona", "box", "poligono", "distanza", "area", "conteggio", "oggetto")

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene().addItem(self.pixmap_item)
        self.setRenderHints(QPainter.SmoothPixmapTransform | QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setBackgroundBrush(QColor("#16181D"))
        self._zoom = 1.0
        self._bordo = QColor("#E74C3C")
        self._strumento = "nav"
        self._cursore = CURSORE_DEFAULT
        self._croce_schermo = False
        self._pos_mouse: Optional[QPointF] = None
        self._classe_attiva = ""
        self._colori: dict = {}
        self._unita = "px"
        self._scala = 1.0
        self._mostra_dimensioni = True
        self._boxes: List[BoxItem] = []
        self._altri_items: List[QGraphicsItem] = []
        self._temporanei: List[QGraphicsItem] = []
        self._punti_correnti: List[QPointF] = []
        self._inizio_drag: Optional[QPointF] = None
        self._anteprima_box: Optional[QGraphicsRectItem] = None
        self._distanza_p1: Optional[QPointF] = None

    # ---------------- immagine e zoom ----------------

    def set_image(self, immagine: np.ndarray, colore_bordo: str) -> None:
        self.pixmap_item.setPixmap(cv_to_pixmap(immagine))
        self.scene().setSceneRect(QRectF(self.pixmap_item.pixmap().rect()))
        self._bordo = QColor(colore_bordo)
        self.reset_view()

    def reset_view(self) -> None:
        self.resetTransform()
        if not self.pixmap_item.pixmap().isNull():
            self.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
        self._zoom = 1.0
        self.zoomChanged.emit(self._zoom)

    def zoom_by(self, fattore: float) -> None:
        nuovo = self._zoom * fattore
        if 0.10 <= nuovo <= 20.0:
            self.scale(fattore, fattore)
            self._zoom = nuovo
            self.zoomChanged.emit(self._zoom)

    def wheelEvent(self, event) -> None:
        self.zoom_by(1.20 if event.angleDelta().y() > 0 else 1 / 1.20)

    def mouseDoubleClickEvent(self, event) -> None:
        if self._strumento == "poligono" and self._punti_correnti:
            self._chiudi_poligono()
            event.accept()
            return
        if self._strumento == "area" and self._punti_correnti:
            self._chiudi_area()
            event.accept()
            return
        self.reset_view()
        super().mouseDoubleClickEvent(event)

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        super().drawForeground(painter, rect)
        if not self.pixmap_item.pixmap().isNull():
            pen = QPen(self._bordo, 5 / max(self.transform().m11(), 0.01))
            painter.setPen(pen)
            painter.drawRect(self.pixmap_item.boundingRect())
        if self._croce_schermo and self._strumento != "nav" and self._pos_mouse is not None:
            spessore = 1.0 / max(self.transform().m11(), 0.01)
            x, y = self._pos_mouse.x(), self._pos_mouse.y()
            for colore, fattore in ((QColor(0, 0, 0, 160), 3), (QColor(255, 255, 255), 1)):
                painter.setPen(QPen(colore, spessore * fattore))
                painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
                painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))

    # ---------------- configurazione strumenti ----------------

    def set_strumento(self, strumento: str) -> None:
        if strumento not in self.STRUMENTI:
            return
        self._annulla_disegno_corrente()
        self._strumento = strumento
        if strumento == "nav":
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.setCursor(Qt.ArrowCursor)
        else:
            self.setDragMode(QGraphicsView.NoDrag)
            self.setCursor(crea_cursore(self._cursore))
        self.viewport().update()

    def set_cursore(self, nome: str) -> None:
        """Cursore per gli strumenti di disegno; 'nav' resta col cursore di sistema."""
        self._cursore = cursore_valido(nome)
        self._croce_schermo = CURSORI[self._cursore].schermo_intero
        if self._strumento != "nav":
            self.setCursor(crea_cursore(self._cursore))
        self.viewport().update()

    def set_classe_attiva(self, nome: str) -> None:
        self._classe_attiva = nome

    def set_unita(self, unita: str, scala: float) -> None:
        self._unita = unita
        self._scala = scala if scala > 0 else 1.0

    def set_colori(self, colori: dict) -> None:
        self._colori = dict(colori)

    def set_mostra_dimensioni(self, attivo: bool) -> None:
        """Mostra/nasconde le dimensioni sopra box e poligoni."""
        self._mostra_dimensioni = bool(attivo)

    # ---------------- annotazioni ----------------

    def _colore_classe(self, nome: str) -> str:
        return self._colori.get(nome, "#BDBDBD")

    def pulisci_annotazioni(self) -> None:
        for item in self._boxes + self._altri_items + self._temporanei:
            try:
                self.scene().removeItem(item)
            except RuntimeError:
                pass
        self._boxes.clear()
        self._altri_items.clear()
        self._temporanei.clear()
        self._punti_correnti.clear()
        self._distanza_p1 = None
        self._anteprima_box = None

    def mostra_annotazioni(self, record) -> None:
        """Ricostruisce gli item delle geometrie e delle misure del record."""
        self.pulisci_annotazioni()
        limite = self.pixmap_item.boundingRect()
        for i, g in enumerate(record.geometrie):
            classe = g.get("classe", "")
            colore = self._colore_classe(classe)
            if g.get("tipo") == "box":
                item = BoxItem(
                    i, classe,
                    QRectF(g["x"], g["y"], g["w"], g["h"]), colore, limite,
                    self._on_box_modificato, self._on_box_selezionato,
                )
                self.scene().addItem(item)
                self._boxes.append(item)
                if self._mostra_dimensioni:
                    self._testo_etichetta(
                        self._testo_dimensioni_box(g["w"], g["h"]),
                        QPointF(g["x"], max(0.0, g["y"] - 18)), colore,
                    )
            elif g.get("tipo") == "poligono":
                item = QGraphicsPolygonItem(QPolygonF([QPointF(*p) for p in g["punti"]]))
                qcolore = QColor(colore)
                item.setPen(QPen(qcolore, 2))
                item.setBrush(QBrush(qcolore))
                item.setOpacity(0.45)
                self.scene().addItem(item)
                self._altri_items.append(item)
                if g["punti"] and self._mostra_dimensioni:
                    self._testo_etichetta(
                        self._testo_dimensioni_poligono(g["punti"]),
                        QPointF(g["punti"][0][0], max(0.0, g["punti"][0][1] - 18)),
                        colore,
                    )
        for m in record.misure:
            self._disegna_misura(m)

    def _testo_etichetta(self, testo: str, pos: QPointF, colore: str) -> None:
        item = QGraphicsTextItem(testo)
        item.setDefaultTextColor(QColor("white"))
        item.setPos(pos)
        self.scene().addItem(item)
        self._altri_items.append(item)

    def _testo_misura(self, testo: str, pos: QPointF) -> None:
        item = QGraphicsTextItem(testo)
        item.setDefaultTextColor(QColor("#00E5FF"))
        item.setPos(pos)
        self.scene().addItem(item)
        self._altri_items.append(item)

    def _disegna_misura(self, misura) -> None:
        colore = QColor("#00E5FF")
        if misura.tipo == "distanza" and len(misura.punti) >= 2:
            p1, p2 = QPointF(*misura.punti[0]), QPointF(*misura.punti[1])
            linea = QGraphicsLineItem(p1.x(), p1.y(), p2.x(), p2.y())
            linea.setPen(QPen(colore, 2))
            self.scene().addItem(linea)
            self._altri_items.append(linea)
            valore = misura.valore_px if misura.valore_px is not None else distanza_px(misura.punti[0], misura.punti[1])
            self._testo_misura(
                self._testo_distanza(valore),
                QPointF((p1.x() + p2.x()) / 2, (p1.y() + p2.y()) / 2 - 20),
            )
        elif misura.tipo == "area" and len(misura.punti) >= 3:
            item = QGraphicsPolygonItem(QPolygonF([QPointF(*p) for p in misura.punti]))
            item.setPen(QPen(colore, 2, Qt.DashLine))
            item.setBrush(QBrush(colore))
            item.setOpacity(0.25)
            self.scene().addItem(item)
            self._altri_items.append(item)
            self._testo_misura(
                self._testo_area(area_poligono(misura.punti)),
                QPointF(misura.punti[0][0], max(0.0, misura.punti[0][1] - 20)),
            )
        elif misura.tipo == "conteggio" and misura.punti:
            p = QPointF(*misura.punti[0])
            cerchio = QGraphicsEllipseItem(p.x() - 8, p.y() - 8, 16, 16)
            cerchio.setPen(QPen(colore, 2))
            cerchio.setBrush(QBrush(QColor(0, 229, 255, 60)))
            self.scene().addItem(cerchio)
            self._altri_items.append(cerchio)
            self._testo_misura("#", QPointF(p.x() + 10, p.y() - 14))
        elif misura.tipo == "oggetto" and len(misura.punti) >= 2:
            from labeling_tool.model import dimensioni_oggetto

            rett = QRectF(QPointF(*misura.punti[0]), QPointF(*misura.punti[1])).normalized()
            item = QGraphicsRectItem(rett)
            item.setPen(QPen(colore, 2, Qt.DashLine))
            self.scene().addItem(item)
            self._altri_items.append(item)
            larghezza, altezza = dimensioni_oggetto(misura.punti)
            self._testo_misura(
                self._testo_oggetto(larghezza, altezza),
                QPointF(rett.x(), max(0.0, rett.y() - 20)),
            )

    def _testo_distanza(self, valore_px: float) -> str:
        if self._unita and self._unita != "px":
            return f"{valore_px:.1f}px ({valore_px / self._scala:.2f} {self._unita})"
        return f"{valore_px:.1f}px"

    def _testo_area(self, area_px: float) -> str:
        if self._unita and self._unita != "px":
            return f"{area_px:.0f}px2 ({area_px / self._scala ** 2:.2f} {self._unita}2)"
        return f"{area_px:.0f}px2"

    def _testo_oggetto(self, larghezza: float, altezza: float) -> str:
        area_px = larghezza * altezza
        if self._unita and self._unita != "px":
            return (
                f"{larghezza:.1f}x{altezza:.1f}px "
                f"({larghezza / self._scala:.2f}x{altezza / self._scala:.2f} {self._unita}) "
                f"A: {area_px / self._scala ** 2:.2f} {self._unita}2"
            )
        return f"{larghezza:.1f}x{altezza:.1f}px A: {area_px:.0f}px2"

    def _testo_dimensioni_box(self, larghezza: float, altezza: float) -> str:
        """Grandezza di un bounding box in pixel: solo i numeri."""
        return f"{larghezza:.0f}x{altezza:.0f}"

    def _testo_dimensioni_poligono(self, punti) -> str:
        """Bounding box del poligono in pixel: solo i numeri."""
        from labeling_tool.model import dimensioni_bbox_poligono

        larghezza, altezza = dimensioni_bbox_poligono(punti)
        return f"{larghezza:.0f}x{altezza:.0f}"

    # ---------------- callback item ----------------

    def _on_box_modificato(self, indice: int, dopo: dict) -> None:
        self.geometriaModificata.emit(indice, dopo)

    def _on_box_selezionato(self, indice: int) -> None:
        for i, box in enumerate(self._boxes):
            box.selezionato = i == indice
            box.update()
        self.selezioneCambiata.emit("box", indice)

    def indice_selezionato(self) -> int:
        for i, box in enumerate(self._boxes):
            if box.selezionato:
                return i
        return -1

    # ---------------- disegno interattivo ----------------

    def _annulla_disegno_corrente(self) -> None:
        for item in self._temporanei:
            try:
                self.scene().removeItem(item)
            except RuntimeError:
                pass
        self._temporanei.clear()
        self._punti_correnti.clear()
        self._distanza_p1 = None
        if self._anteprima_box is not None:
            try:
                self.scene().removeItem(self._anteprima_box)
            except RuntimeError:
                pass
            self._anteprima_box = None

    def _aggiungi_temporaneo(self, item: QGraphicsItem) -> None:
        self.scene().addItem(item)
        self._temporanei.append(item)

    def _punto_scene(self, event) -> QPointF:
        return self.mapToScene(event.position().toPoint())

    def mousePressEvent(self, event) -> None:
        if self.pixmap_item.pixmap().isNull() or event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return
        punto = self._punto_scene(event)
        if self._strumento in ("box", "oggetto"):
            self._inizio_drag = punto
            self._anteprima_box = QGraphicsRectItem(QRectF(punto, punto))
            colore_anteprima = QColor("#00E5FF") if self._strumento == "oggetto" else QColor(self._colore_classe(self._classe_attiva))
            self._anteprima_box.setPen(QPen(colore_anteprima, 2, Qt.DashLine))
            self._aggiungi_temporaneo(self._anteprima_box)
            event.accept()
        elif self._strumento == "distanza":
            if self._distanza_p1 is None:
                self._distanza_p1 = punto
                marcatore = QGraphicsEllipseItem(punto.x() - 3, punto.y() - 3, 6, 6)
                marcatore.setPen(QPen(QColor("#00E5FF"), 1))
                marcatore.setBrush(QBrush(QColor("#00E5FF")))
                self._aggiungi_temporaneo(marcatore)
            else:
                p1 = self._distanza_p1
                valore = distanza_px((p1.x(), p1.y()), (punto.x(), punto.y()))
                self._annulla_disegno_corrente()
                self.misuraAggiunta.emit({
                    "tipo": "distanza", "punti": [[p1.x(), p1.y()], [punto.x(), punto.y()]],
                    "valore_px": valore,
                })
            event.accept()
        elif self._strumento in ("poligono", "area"):
            self._punti_correnti.append(punto)
            marcatore = QGraphicsEllipseItem(punto.x() - 3, punto.y() - 3, 6, 6)
            marcatore.setPen(QPen(QColor("#FFD700"), 1))
            marcatore.setBrush(QBrush(QColor("#FFD700")))
            self._aggiungi_temporaneo(marcatore)
            event.accept()
        elif self._strumento == "conteggio":
            self.misuraAggiunta.emit({
                "tipo": "conteggio", "punti": [[punto.x(), punto.y()]], "valore_px": None,
            })
            event.accept()
        elif self._strumento == "seleziona":
            # click su spazio vuoto: deseleziona
            super().mousePressEvent(event)
            if not self.scene().mouseGrabberItem():
                self.deseleziona_tutto()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._croce_schermo:
            self._pos_mouse = self._punto_scene(event)
            self.viewport().update()
        if self._strumento in ("box", "oggetto") and self._anteprima_box is not None and self._inizio_drag is not None:
            punto = self._punto_scene(event)
            limite = self.pixmap_item.boundingRect()
            rett = QRectF(self._inizio_drag, punto).normalized().intersected(limite)
            self._anteprima_box.setRect(rett)
            event.accept()
            return
        if self._strumento == "poligono" and self._punti_correnti:
            # anteprima segmento verso il cursore
            if len(self._temporanei) > len(self._punti_correnti):
                self._temporanei.pop().setParentItem(None)
            punto = self._punto_scene(event)
            linea = QGraphicsLineItem(
                self._punti_correnti[-1].x(), self._punti_correnti[-1].y(), punto.x(), punto.y()
            )
            linea.setPen(QPen(QColor("#FFD700"), 1, Qt.DashLine))
            self._aggiungi_temporaneo(linea)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self._pos_mouse = None
        if self._croce_schermo:
            self.viewport().update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._strumento in ("box", "oggetto") and self._anteprima_box is not None and self._inizio_drag is not None:
            rett = self._anteprima_box.rect().normalized()
            self._annulla_disegno_corrente()
            if rett.width() >= MIN_BOX and rett.height() >= MIN_BOX:
                if self._strumento == "box":
                    self.geometriaAggiunta.emit({
                        "tipo": "box", "classe": self._classe_attiva,
                        "x": rett.x(), "y": rett.y(), "w": rett.width(), "h": rett.height(),
                    })
                else:
                    self.misuraAggiunta.emit({
                        "tipo": "oggetto",
                        "punti": [[rett.x(), rett.y()], [rett.x() + rett.width(), rett.y() + rett.height()]],
                        "valore_px": None,
                    })
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def event(self, e) -> bool:
        # Mentre si disegna, Invio/Esc appartengono al disegno: senza questo
        # reclamo le scorciatoie globali della finestra se li rubano.
        if e.type() == QEvent.ShortcutOverride and self._disegno_in_corso():
            if e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Escape):
                e.accept()
                return True
        return super().event(e)

    def _disegno_in_corso(self) -> bool:
        return bool(
            self._punti_correnti
            or self._anteprima_box is not None
            or self._distanza_p1 is not None
            or self._temporanei
        )

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self._strumento == "poligono":
                self._chiudi_poligono()
                event.accept()
                return
            if self._strumento == "area":
                self._chiudi_area()
                event.accept()
                return
        if event.key() == Qt.Key_Escape:
            self._annulla_disegno_corrente()
            event.accept()
            return
        super().keyPressEvent(event)

    def _chiudi_poligono(self) -> None:
        if len(self._punti_correnti) < 3:
            return
        punti = [[p.x(), p.y()] for p in self._punti_correnti]
        self._annulla_disegno_corrente()
        self.geometriaAggiunta.emit({"tipo": "poligono", "classe": self._classe_attiva, "punti": punti})

    def _chiudi_area(self) -> None:
        if len(self._punti_correnti) < 3:
            return
        punti = [[p.x(), p.y()] for p in self._punti_correnti]
        area_px = area_poligono(punti)
        self._annulla_disegno_corrente()
        self.misuraAggiunta.emit({"tipo": "area", "punti": punti, "valore_px": area_px})

    def deseleziona_tutto(self) -> None:
        for box in self._boxes:
            box.selezionato = False
            box.update()
        self.selezioneCambiata.emit("nessuna", -1)
