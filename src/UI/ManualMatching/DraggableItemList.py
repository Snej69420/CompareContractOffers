from PySide6.QtWidgets import QListWidget, QListWidgetItem, QScrollArea, QApplication
from PySide6.QtCore import Qt, Signal, QSize, QTimer, QPoint
from PySide6.QtGui import QCursor

from src.UI.ManualMatching.MatchItem import MatchItem
from src.UI.ManualMatching.ProductItem import ProductItem

class DraggableItemList(QListWidget):
    itemDropped = Signal()
    itemEjected = Signal(object)
    moveToNeighbor = Signal(object, str)
    navigateBoundary = Signal(str, str)
    requestDragRoute = Signal(object, object, object)
    requestScrollTo = Signal(object)

    shared_scroll_timer = None
    active_scroll_area = None

    def __init__(self, doc_key: str, all_keys: list[str]):
        super().__init__()
        self.doc_key = doc_key
        self.all_keys = all_keys

        # Initialize the static timer once for all lists
        if DraggableItemList.shared_scroll_timer is None:
            DraggableItemList.shared_scroll_timer = QTimer()
            DraggableItemList.shared_scroll_timer.timeout.connect(DraggableItemList._handle_shared_auto_scroll)

        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.setDragDropMode(QListWidget.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setAcceptDrops(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setStyleSheet("""
            QListWidget { 
                background-color: white; 
                border: 1px solid #ccc; 
                border-radius: 3px;
            }
            QListWidget:focus { 
                border: 2px solid #64748b;  
                background-color: #f8fafc;  
                outline: none;              
            }
            QListWidget::item:selected {
                background-color: #cce5ff;
                border: 2px solid #007bff;
                border-radius: 4px;
            }
            QListWidget::item:focus:!selected {
                border: 2px dashed #888;
                border-radius: 4px;
            }
            QListWidget::item {
                border: 2px solid transparent; 
                border-radius: 4px;
            }
        """)
        self.currentItemChanged.connect(self._on_item_changed)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.doItemsLayout()

    # ==========================================
    # --- DRAG AUTO-SCROLL LOGIC ---
    # ==========================================
    def _get_parent_scroll_area(self) -> QScrollArea:
        parent = self.parent()
        while parent:
            if isinstance(parent, QScrollArea):
                return parent
            parent = parent.parent()
        return None

    @staticmethod
    def _handle_shared_auto_scroll():
        scroll_area = DraggableItemList.active_scroll_area
        if not scroll_area or not scroll_area.isVisible():
            DraggableItemList.shared_scroll_timer.stop()
            return

        # Use the viewport of the SCROLL AREA, not the list
        viewport = scroll_area.viewport()
        global_pos = QCursor.pos()
        local_pos = viewport.mapFromGlobal(global_pos)

        y = local_pos.y()
        view_h = viewport.height()

        # Increase the sensitivity zone or check if we are near the edges of the AREA
        if y < 50:  # Top of the whole scrollable area
            vbar = scroll_area.verticalScrollBar()
            vbar.setValue(vbar.value() - 15)
        elif y > view_h - 50:  # Bottom of the whole scrollable area
            vbar = scroll_area.verticalScrollBar()
            vbar.setValue(vbar.value() + 15)

    # ==========================================
    # --- DRAG & DROP EVENTS ---
    # ==========================================
    def dragEnterEvent(self, event):
        if isinstance(event.source(), DraggableItemList) and event.source().doc_key == self.doc_key:
            super().dragEnterEvent(event)
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if isinstance(event.source(), DraggableItemList) and event.source().doc_key == self.doc_key:
            super().dragMoveEvent(event)

            # Ensure the master timer is awake while we drag
            DraggableItemList.active_scroll_area = self._get_parent_scroll_area()
            if DraggableItemList.active_scroll_area and not DraggableItemList.shared_scroll_timer.isActive():
                DraggableItemList.shared_scroll_timer.start(20)  # 20ms = Smooth 50fps scrolling
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        if DraggableItemList.shared_scroll_timer:
            DraggableItemList.shared_scroll_timer.stop()

        source = event.source()
        if isinstance(source, DraggableItemList) and source.doc_key == self.doc_key:
            # Grab EVERY selected item
            dragged_items = [item.data(Qt.ItemDataRole.UserRole) for item in source.selectedItems()]
            if not dragged_items: return

            event.setDropAction(Qt.DropAction.IgnoreAction)
            event.accept()

            self.requestDragRoute.emit(dragged_items, source, self)
        else:
            event.ignore()

    # ==========================================
    # --- KEYBOARD & FOCUS LOGIC ---
    # ==========================================
    def keyPressEvent(self, event):
        selected_items = self.selectedItems()
        current_row = self.currentRow()

        # --- MULTI-MOVE VIA KEYBOARD (Now uses ALT instead of CTRL) ---
        if selected_items and (event.modifiers() & Qt.KeyboardModifier.AltModifier):
            items_to_move = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]

            if event.key() == Qt.Key.Key_Up:
                self.moveToNeighbor.emit(items_to_move, "up")
                return
            elif event.key() == Qt.Key.Key_Down:
                self.moveToNeighbor.emit(items_to_move, "down")
                return

        # --- MULTI-DELETE VIA KEYBOARD ---
        if selected_items and event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            saved_row = current_row
            items_to_eject = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]

            # Fire the eject signal for every selected item
            for current_item in items_to_eject:
                self.itemEjected.emit(current_item)

            # Restore focus safely
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

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._trigger_tooltip(self.currentItem())

    def focusOutEvent(self, event):
        """Clears the visual selection when the user navigates away from this list."""
        self.clearSelection()
        current = self.currentItem()
        if current:
            widget = self.itemWidget(current)
            if isinstance(widget, ProductItem):
                widget.hide_tooltip()

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
            self.setItemWidget(li, custom_widget)

    def _on_item_changed(self, current, previous):
        if previous:
            prev_widget = self.itemWidget(previous)
            if isinstance(prev_widget, ProductItem):
                prev_widget.hide_tooltip()

        self._trigger_tooltip(current)

    def _trigger_tooltip(self, item):
        if not item or not self.hasFocus():
            return

        curr_widget = self.itemWidget(item)
        if isinstance(curr_widget, ProductItem):
            curr_widget.show_tooltip()
