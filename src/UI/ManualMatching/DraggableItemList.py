from PySide6.QtWidgets import QListWidget, QListWidgetItem
from PySide6.QtCore import Qt, Signal

from src.UI.ManualMatching.MatchItem import MatchItem
from src.UI.ManualMatching.ProductItem import ProductItem

class DraggableItemList(QListWidget):
    itemDropped = Signal()
    itemEjected = Signal(object)
    moveToNeighbor = Signal(object, str)
    navigateBoundary = Signal(str, str)  # side ('A' or 'B'), direction ('up', 'down', 'left', 'right')

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

    def keyPressEvent(self, event):
        selected_items = self.selectedItems()
        current_row = self.currentRow()

        # Handle Ctrl + Up/Down (Item moving)
        if selected_items and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            current_item = selected_items[0].data(Qt.ItemDataRole.UserRole)
            if event.key() == Qt.Key.Key_Up:
                self.moveToNeighbor.emit(current_item, "up")
                return
            elif event.key() == Qt.Key.Key_Down:
                self.moveToNeighbor.emit(current_item, "down")
                return

        # Handle Delete/Backspace
        if selected_items and event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            current_item = selected_items[0].data(Qt.ItemDataRole.UserRole)
            self.itemEjected.emit(current_item)
            return

        # --- NEW: Handle Boundary Navigation (Moving Focus) ---
        # <= 0 handles both the top row (0) and empty lists (-1)
        if event.key() == Qt.Key.Key_Up and current_row <= 0:
            self.navigateBoundary.emit(self.side, "up")
            return

        elif event.key() == Qt.Key.Key_Down and (current_row == self.count() - 1 or current_row == -1):
            self.navigateBoundary.emit(self.side, "down")
            return

        elif event.key() == Qt.Key.Key_Left and self.side == 'B':
            self.navigateBoundary.emit(self.side, "left")
            return

        elif event.key() == Qt.Key.Key_Right and self.side == 'A':
            self.navigateBoundary.emit(self.side, "right")
            return

        # Default behavior (Normal Up/Down selection)
        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        """Clears the visual selection when the user navigates away from this list."""
        self.clearSelection()
        super().focusOutEvent(event)

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