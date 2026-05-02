from PySide6.QtWidgets import QListWidget, QListWidgetItem
from PySide6.QtCore import Qt, Signal

from src.UI.ManualMatching.MatchItem import MatchItem
from src.UI.ManualMatching.ProductItem import ProductItem

class DraggableItemList(QListWidget):
    itemDropped = Signal()
    itemEjected = Signal(object)
    moveToNeighbor = Signal(object, str)
    navigateBoundary = Signal(str, str)  # side ('A' or 'B'), direction ('up', 'down', 'left', 'right')

    def __init__(self, doc_key: str, all_keys: list[str]):
        super().__init__()
        self.doc_key = doc_key
        self.all_keys = all_keys

        self.setDragDropMode(QListWidget.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setAcceptDrops(True)
        self.setStyleSheet("QListWidget { background-color: white; border: 1px solid #ccc; }")

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
            # 1. Capture the Python objects BEFORE Qt serializes them
            dragged_items = [item.data(Qt.ItemDataRole.UserRole) for item in source.selectedItems()]
            if not dragged_items:
                return
            match_item = dragged_items[0]

            from PySide6.QtCore import QTimer, QSignalBlocker

            # --- THE SHIELD ---
            # 2. Block signals so the visual drop doesn't trigger the auto-scroll on the doomed item
            with QSignalBlocker(self), QSignalBlocker(source):
                super().dropEvent(event)

                # Re-attach the Python objects
                for i, new_item in enumerate(self.selectedItems()):
                    if i < len(dragged_items):
                        new_item.setData(Qt.ItemDataRole.UserRole, dragged_items[i])

            # --- THE KEYBOARD LOGIC PIPELINE ---
            # 3. Create a callback that forces the Rebuild -> Select order
            def finalize_drop():
                # A. Trigger the Rebuild (this deletes the old items and makes new ones)
                self.itemDropped.emit()
                if source != self:
                    source.itemDropped.emit()

                # B. Find the brand new C++ item and select it manually
                for i in range(self.count()):
                    if self.item(i).data(Qt.ItemDataRole.UserRole) is match_item:
                        self.setCurrentRow(i)  # This triggers the safe auto-scroll!
                        self.setFocus()
                        break

            # 4. Defer this logic by 0ms so Qt can safely finish its internal C++ Drop routine first
            QTimer.singleShot(0, finalize_drop)

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

        # Dynamically jump left if we aren't the first list
        elif event.key() == Qt.Key.Key_Left and idx > 0:
            self.navigateBoundary.emit(self.doc_key, "left")
            return
        # Dynamically jump right if we aren't the last list
        elif event.key() == Qt.Key.Key_Right and idx < len(self.all_keys) - 1:
            self.navigateBoundary.emit(self.doc_key, "right")
            return

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

        dummy_match = MatchItem({'Naam': 'X', 'Aantal': 0, 'Eenheid': '-'}, -1, self.doc_key)
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