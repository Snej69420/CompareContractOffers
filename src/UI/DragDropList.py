from PySide6.QtWidgets import QListWidget, QAbstractItemView, QSizePolicy, QFrame, QScrollArea
from PySide6.QtCore import Qt, Signal, QTimer
from src.UI.Product import Product

class DragDropList(QListWidget):
    itemsChanged = Signal()

    def __init__(self, column_id):
        super().__init__()
        self.column_id = column_id

        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setAcceptDrops(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        self.setWordWrap(True)

        self.setStyleSheet(
            "QListWidget { border: 1px solid rgba(128, 128, 128, 0.5); border-radius: 4px; background: transparent; }"
            "QListWidget::item { padding: 6px; border-radius: 3px; border-bottom: 1px solid rgba(128, 128, 128, 0.3); margin-bottom: 2px; }"
            "QListWidget::item:selected { background-color: rgba(0, 120, 215, 0.4); }"
        )

        self.setMinimumHeight(45)
        self.setFrameShape(QFrame.NoFrame)
        self.itemClicked.connect(self.toggle_expansion)
        self.model().rowsInserted.connect(self.adjust_dynamic_height)
        self.model().rowsRemoved.connect(self.adjust_dynamic_height)

        # Smooth Scrolling Engine
        self.scroll_timer = QTimer(self)
        self.scroll_timer.setInterval(20)  # 50 FPS
        self.scroll_timer.timeout.connect(self.do_auto_scroll)
        self.scroll_direction = 0

    def do_auto_scroll(self):
        scroll_area = self.window().findChild(QScrollArea)
        if scroll_area:
            bar = scroll_area.verticalScrollBar()
            bar.setValue(bar.value() + (15 * self.scroll_direction))

    def adjust_dynamic_height(self):
        count = self.count()
        self.setMinimumHeight(max(45, count * 40 + 10))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        for i in range(self.count()):
            item = self.item(i)
            if hasattr(item, 'update_display'):
                item.update_display()

    def toggle_expansion(self, item):
        if isinstance(item, Product):
            item.is_expanded = not item.is_expanded
            item.update_display()
            self.scheduleDelayedItemsLayout()

    def dragEnterEvent(self, event):
        source = event.source()
        if isinstance(source, DragDropList) and source.column_id == self.column_id:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        super().dragMoveEvent(event)
        scroll_area = self.window().findChild(QScrollArea)
        if scroll_area:
            global_pos = self.mapToGlobal(event.position().toPoint())
            scroll_pos = scroll_area.mapFromGlobal(global_pos)
            y = scroll_pos.y()

            if y < 80:
                self.scroll_direction = -1
                if not self.scroll_timer.isActive(): self.scroll_timer.start()
            elif y > scroll_area.viewport().height() - 80:
                self.scroll_direction = 1
                if not self.scroll_timer.isActive(): self.scroll_timer.start()
            else:
                self.scroll_timer.stop()

    def dragLeaveEvent(self, event):
        super().dragLeaveEvent(event)
        self.scroll_timer.stop()

    def dropEvent(self, event):
        self.scroll_timer.stop()
        source = event.source()

        if isinstance(source, DragDropList) and source.column_id == self.column_id:
            item = source.currentItem()
            if item:
                source.takeItem(source.row(item))

                drop_pos = event.position().toPoint()
                target_item = self.itemAt(drop_pos)
                if target_item:
                    insert_row = self.row(target_item)
                    self.insertItem(insert_row, item)
                else:
                    self.addItem(item)

                event.accept()
                self.itemsChanged.emit()
                if source != self:
                    source.itemsChanged.emit()
        else:
            event.ignore()