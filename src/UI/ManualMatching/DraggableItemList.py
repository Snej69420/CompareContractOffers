from PySide6.QtWidgets import QListWidget, QListWidgetItem
from PySide6.QtCore import Qt, Signal, QSize

from src.UI.ManualMatching.MatchItem import MatchItem
from src.UI.ManualMatching.ProductItem import ProductItem

class DraggableItemList(QListWidget):
    itemDropped = Signal()
    itemEjected = Signal(object)
    moveToNeighbor = Signal(object, str)
    navigateBoundary = Signal(str, str)  # contract id, direction ('up', 'down', 'left', 'right')
    requestDragRoute = Signal(object, object, object)  # match_item, source_list, target_list
    requestScrollTo = Signal(object)

    def __init__(self, doc_key: str, all_keys: list[str]):
        super().__init__()
        self.doc_key = doc_key
        self.all_keys = all_keys

        self.setDragDropMode(QListWidget.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setAcceptDrops(True)
        # self.setMinimumWidth(480)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setStyleSheet("""
                    QListWidget { 
                        background-color: white; 
                        border: 1px solid #ccc; 
                        border-radius: 3px;
                    }
                    QListWidget:focus { 
                        border: 2px solid #007bff;  /* Bright blue focus ring */
                        background-color: #f8faff;  /* Very subtle blue tint */
                        outline: none;              /* Removes Qt's default dotted outline */
                    }
                """)

    def dragEnterEvent(self, event):
        if isinstance(event.source(), DraggableItemList) and event.source().doc_key == self.doc_key:
            super().dragEnterEvent(event)
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if isinstance(event.source(), DraggableItemList) and event.source().doc_key == self.doc_key:
            super().dragMoveEvent(event)
        else:
            event.ignore()

    def dropEvent(self, event):
        source = event.source()
        if isinstance(source, DraggableItemList) and source.doc_key == self.doc_key:
            dragged_items = [item.data(Qt.ItemDataRole.UserRole) for item in source.selectedItems()]
            if not dragged_items: return

            match_item = dragged_items[0]

            event.setDropAction(Qt.DropAction.IgnoreAction)
            event.accept()

            self.requestDragRoute.emit(match_item, source, self)

        else:
            event.ignore()

    def keyPressEvent(self, event):
        selected_items = self.selectedItems()
        current_row = self.currentRow()

        if selected_items and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            current_item = selected_items[0].data(Qt.ItemDataRole.UserRole)
            if event.key() == Qt.Key.Key_Up:
                self.moveToNeighbor.emit(current_item, "up")
                return
            elif event.key() == Qt.Key.Key_Down:
                self.moveToNeighbor.emit(current_item, "down")
                return

        if selected_items and event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            saved_row = current_row

            current_item = selected_items[0].data(Qt.ItemDataRole.UserRole)

            self.itemEjected.emit(current_item)

            # Restore focus
            if self.count() > 0:
                next_row = min(saved_row, self.count() - 1)
                self.setCurrentRow(next_row)
                self.setFocus()
            return

        # --- DYNAMIC BOUNDARY NAVIGATION ---
        idx = self.all_keys.index(self.doc_key)

        if event.key() == Qt.Key.Key_Up and current_row <= 0:
            self.navigateBoundary.emit(self.doc_key, "up")
            return
        elif event.key() == Qt.Key.Key_Down and (current_row == self.count() - 1 or current_row == -1):
            self.navigateBoundary.emit(self.doc_key, "down")
            return
        elif event.key() == Qt.Key.Key_Left and idx > 0:
            self.navigateBoundary.emit(self.doc_key, "left")
            return
        elif event.key() == Qt.Key.Key_Right and idx < len(self.all_keys) - 1:
            self.navigateBoundary.emit(self.doc_key, "right")
            return

        super().keyPressEvent(event)

        if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            new_row = self.currentRow()
            if new_row >= 0:
                item = self.item(new_row)
                item_widget = self.itemWidget(item)
                if item_widget:
                    self.requestScrollTo.emit(item_widget)

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

        dummy_match = MatchItem({'Naam': 'X', 'Aantal': 0, 'Eenheid': '-'}, -1, self.doc_key)
        dummy_widget = ProductItem(dummy_match)
        return dummy_widget.sizeHint().height()

    def rebuild_ui(self, sorted_items: list[MatchItem]):
        self.clear()
        for match_item in sorted_items:
            li = QListWidgetItem(self)
            custom_widget = ProductItem(match_item, eject_callback=self.itemEjected.emit)
            li.setSizeHint(custom_widget.sizeHint())
            li.setData(Qt.ItemDataRole.UserRole, match_item)

            # --- THE NEW TOOLTIP ---
            # Shows the full uncut name + the fixed confidence score
            full_name = match_item.name
            li.setToolTip(f"{full_name}\n\nZekerheid: {match_item.current_score:.0%}\nSleep om aan te passen.")

            self.setItemWidget(li, custom_widget)