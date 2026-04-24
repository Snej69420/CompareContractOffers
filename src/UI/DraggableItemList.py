from PySide6.QtWidgets import QListWidget, QListWidgetItem
from PySide6.QtCore import Qt, Signal

from src.UI.MatchItem import MatchItem
from src.UI.ProductItem import ProductItem

class DraggableItemList(QListWidget):
    itemDropped = Signal()
    itemEjected = Signal(object)

    def __init__(self, side: str):
        super().__init__()
        self.side = side
        self.setDragDropMode(QListWidget.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setAcceptDrops(True)
        self.setStyleSheet("QListWidget { background-color: white; border: 1px solid #ccc; }")

    def dragEnterEvent(self, event):
        if isinstance(event.source(), DraggableItemList) and event.source().side == self.side:
            super().dragEnterEvent(event)
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if isinstance(event.source(), DraggableItemList) and event.source().side == self.side:
            super().dragMoveEvent(event)
        else:
            event.ignore()

    def dropEvent(self, event):
        source = event.source()
        if isinstance(source, DraggableItemList) and source.side == self.side:
            super().dropEvent(event)
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self.itemDropped.emit)
            if source != self:
                QTimer.singleShot(0, source.itemDropped.emit)
        else:
            event.ignore()

    def get_items(self) -> list[MatchItem]:
        return [self.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.count())]

    def get_single_row_height(self) -> int:
        """Dynamically measures the exact pixel height of a row based on current fonts/scaling."""
        if self.count() > 0:
            return self.item(0).sizeHint().height()

        # Fallback for an empty list: build a dummy widget just to measure its sizeHint
        dummy_match = MatchItem({'Naam': 'X', 'Aantal': 0, 'Eenheid': '-'}, -1, self.side)
        dummy_widget = ProductItem(dummy_match)
        return dummy_widget.sizeHint().height()

    def rebuild_ui(self, sorted_items: list[MatchItem]):
        self.clear()
        for match_item in sorted_items:
            li = QListWidgetItem(self)
            # Pass the signal emit as the callback
            custom_widget = ProductItem(match_item, eject_callback=self.itemEjected.emit)
            li.setSizeHint(custom_widget.sizeHint())
            li.setData(Qt.ItemDataRole.UserRole, match_item)

            if match_item.best_match_name:
                li.setToolTip(
                    f"Gekoppeld aan: {match_item.best_match_name}\nZekerheid: {match_item.current_score:.0%}\n\nSleep om aan te passen.")
            else:
                li.setToolTip("Geen match gevonden.\nSleep om aan te passen.")

            self.setItemWidget(li, custom_widget)