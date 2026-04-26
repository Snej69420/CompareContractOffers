from PySide6.QtWidgets import QListWidget, QAbstractItemView, QSizePolicy, QFrame, QScrollArea
from PySide6.QtCore import Qt, Signal, QTimer, QPoint
from src.UI.Product import Product


class DragDropList(QListWidget):
    """
    A specialized QListWidget handling Drag & Drop matching logic.
    Separates concern between UI styling, auto-scrolling, and Data-Model manipulation.
    """
    itemsChanged = Signal()

    def __init__(self, column_id):
        super().__init__()
        self.column_id = column_id
        self._setup_ui()
        self._setup_scroller()

    # ==========================================
    # UI & STYLING
    # ==========================================
    def _setup_ui(self):
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setAcceptDrops(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        self.setWordWrap(True)
        self.setMinimumHeight(45)
        self.setFrameShape(QFrame.NoFrame)

        self.setStyleSheet(
            "QListWidget { border: 1px solid rgba(128, 128, 128, 0.3); border-radius: 4px; background: rgba(255,255,255,0.02); }"
            "QListWidget::item { padding: 4px; border-radius: 3px; border-bottom: 1px solid rgba(128, 128, 128, 0.1); margin-bottom: 1px; }"
            "QListWidget::item:selected { background-color: rgba(0, 120, 215, 0.3); color: white; }"
        )

        # Connect signals for dynamic layout
        self.itemClicked.connect(self._handle_expansion)
        self.model().rowsInserted.connect(self.adjust_dynamic_height)
        self.model().rowsRemoved.connect(self.adjust_dynamic_height)

    def adjust_dynamic_height(self):
        """Ensures the list expands to show all items without internal scrollbars."""
        count = self.count()
        # Roughly 38px per item + padding
        new_height = max(45, count * 38 + 10)
        self.setMinimumHeight(new_height)

    def _handle_expansion(self, item):
        """Toggles full-text view for elided items."""
        if hasattr(item, 'is_expanded'):
            item.is_expanded = not item.is_expanded
            item.update_display()
            self.scheduleDelayedItemsLayout()

    # ==========================================
    # AUTO-SCROLLING LOGIC
    # ==========================================
    def _setup_scroller(self):
        self.scroll_timer = QTimer(self)
        self.scroll_timer.setInterval(20)
        self.scroll_timer.timeout.connect(self._do_auto_scroll)
        self.scroll_direction = 0

    def _do_auto_scroll(self):
        scroll_area = self.window().findChild(QScrollArea)
        if scroll_area and self.scroll_direction != 0:
            bar = scroll_area.verticalScrollBar()
            bar.setValue(bar.value() + (15 * self.scroll_direction))

    # ==========================================
    # DRAG & DROP ORCHESTRATION
    # ==========================================
    def dragEnterEvent(self, event):
        source = event.source()
        # Gatekeeper: Only accept items from the same contractor column
        if isinstance(source, DragDropList) and source.column_id == self.column_id:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        super().dragMoveEvent(event)

        # Auto-scroll detection
        scroll_area = self.window().findChild(QScrollArea)
        if scroll_area:
            global_pos = self.mapToGlobal(event.position().toPoint())
            view_pos = scroll_area.viewport().mapFromGlobal(global_pos)
            y = view_pos.y()
            vh = scroll_area.viewport().height()

            if y < 60:
                self.scroll_direction = -1
                if not self.scroll_timer.isActive(): self.scroll_timer.start()
            elif y > vh - 60:
                self.scroll_direction = 1
                if not self.scroll_timer.isActive(): self.scroll_timer.start()
            else:
                self.scroll_direction = 0
                self.scroll_timer.stop()

    def dragLeaveEvent(self, event):
        super().dragLeaveEvent(event)
        self.scroll_timer.stop()

    def dropEvent(self, event):
        """The heart of the matching system. Prevents vanishing items by managing indices explicitly."""
        self.scroll_timer.stop()
        source = event.source()

        if not isinstance(source, DragDropList) or source.column_id != self.column_id:
            event.ignore()
            return

        # 1. Identity the item being moved
        item = source.currentItem()
        if not item:
            selected = source.selectedItems()
            item = selected[0] if selected else None

        if not item:
            event.ignore()
            return

        # 2. Orchestrate the data move
        self._execute_move(source, item, event.position().toPoint())
        event.acceptProposedAction()

    def _execute_move(self, source, item, drop_pos):
        """
        Logic to detach item from source and attach to target.
        Handles the index-shift math to prevent vanishing items.
        """
        # Capture current state
        src_row = source.row(item)

        # Calculate target destination BEFORE modifying the source list
        target_item = self.itemAt(drop_pos)
        dest_row = self.row(target_item) if target_item else self.count()

        # Detach
        taken_item = source.takeItem(src_row)
        if not taken_item:
            return

        # Adjust destination if moving DOWN in the SAME list
        # (Because taking the item from above shifted all items below up by one)
        if source == self and src_row < dest_row:
            dest_row -= 1

        # Insert into new home
        dest_row = max(0, min(dest_row, self.count()))
        self.insertItem(dest_row, taken_item)
        self.setCurrentItem(taken_item)
        taken_item.setSelected(True)

        # Emit signals on a delay. This is CRUCIAL for the AI.
        # It allows the UI layout to settle before refresh_all_scores searches for items.
        QTimer.singleShot(10, self.itemsChanged.emit)
        if source != self:
            QTimer.singleShot(10, source.itemsChanged.emit)

    def dropMimeData(self, index, data, action):
        """Bypass default instantiation to keep our custom Product objects alive."""
        return False