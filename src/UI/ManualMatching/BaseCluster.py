from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton
from PySide6.QtCore import Signal, Qt, QSize
from src.UI.ManualMatching.DraggableItemList import DraggableItemList

class BaseCluster(QFrame):
    """Base class providing the layout and height logic for both Clusters and the Parking Lot."""
    requestNeighborMove = Signal(object, object, str)
    requestGlobalNavigation = Signal(object, str, str)

    def __init__(self, title_text: str):
        super().__init__()
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)

        self.layout = QVBoxLayout(self)

        # Header Layout (Children can add buttons to this)
        self.header_layout = QHBoxLayout()
        self.icon_label = QPushButton()
        self.icon_label.setFlat(True)  # Removes button borders/styling
        self.icon_label.setEnabled(False)  # Prevents the user from clicking it
        self.icon_label.setStyleSheet("border: none; background: transparent; padding: 0px;")
        self.icon_label.setIconSize(QSize(20, 20))
        self.header_layout.addWidget(self.icon_label)
        self.title_label = QLabel(title_text)
        self.header_layout.addWidget(self.title_label)
        self.header_layout.addStretch()
        self.layout.addLayout(self.header_layout)

        # Lists Container
        self.lists_widget = QWidget()
        lists_layout = QHBoxLayout(self.lists_widget)

        self.list_a = DraggableItemList("A")
        self.list_b = DraggableItemList("B")

        # Route drop events to an overridable handler
        self.list_a.itemDropped.connect(self.on_items_changed)
        self.list_b.itemDropped.connect(self.on_items_changed)

        lists_layout.addWidget(self.list_a)
        lists_layout.addWidget(self.list_b)
        self.layout.addWidget(self.lists_widget)

        self.list_a.moveToNeighbor.connect(self._emit_neighbor_move)
        self.list_b.moveToNeighbor.connect(self._emit_neighbor_move)

        self.list_a.navigateBoundary.connect(self.handle_boundary_navigation)
        self.list_b.navigateBoundary.connect(self.handle_boundary_navigation)

    def _emit_neighbor_move(self, match_item, direction):
        """Passes the request up, identifying self as the source."""
        self.requestNeighborMove.emit(self, match_item, direction)

    def handle_boundary_navigation(self, side, direction):
        if direction == "left" and side == "B":
            # Jump from B to A
            self.list_a.setFocus()
            if self.list_a.count() > 0:
                # Try to stay on the same row index, or the bottom if it's shorter
                row = min(self.list_b.currentRow(), self.list_a.count() - 1)
                self.list_a.setCurrentRow(max(0, row))

        elif direction == "right" and side == "A":
            # Jump from A to B
            self.list_b.setFocus()
            if self.list_b.count() > 0:
                row = min(self.list_a.currentRow(), self.list_b.count() - 1)
                self.list_b.setCurrentRow(max(0, row))

        else:
            # Up or Down requires leaving the cluster, tell MainWindow!
            self.requestGlobalNavigation.emit(self, side, direction)

    def remove_item_silently(self, match_item):
        """Removes an item without emitting ejection signals."""
        items_a = self.list_a.get_items()
        items_b = self.list_b.get_items()

        if match_item.side == 'A':
            items_a = [i for i in items_a if i is not match_item]
        else:
            items_b = [i for i in items_b if i is not match_item]

        self.list_a.rebuild_ui(items_a)
        self.list_b.rebuild_ui(items_b)
        self.on_items_changed()  # Triggers recalculate/resort

    def inject_item(self, match_item):
        """Safely inserts an item coming from a neighbor."""
        items_a = self.list_a.get_items()
        items_b = self.list_b.get_items()

        if match_item.side == 'A':
            items_a.append(match_item)
        else:
            items_b.append(match_item)

        self.list_a.rebuild_ui(items_a)
        self.list_b.rebuild_ui(items_b)
        self.on_items_changed()

    def focus_on_item(self, match_item):
        """Finds the newly injected item and gives it keyboard focus."""
        target_list = self.list_a if match_item.side == 'A' else self.list_b
        for i in range(target_list.count()):
            if target_list.item(i).data(Qt.ItemDataRole.UserRole) is match_item:
                target_list.setCurrentRow(i)
                target_list.setFocus()
                break

    def on_items_changed(self):
        """To be overridden by child classes to handle re-calculations."""
        pass

    def adjust_list_heights(self, max_visible_rows: int = 6):
        """Centralized dynamic height calculation."""
        items_a = self.list_a.get_items()
        items_b = self.list_b.get_items()

        max_items = max(1, len(items_a), len(items_b))
        visible_rows = min(max_items, max_visible_rows)

        actual_row_height = max(self.list_a.get_single_row_height(), self.list_b.get_single_row_height())
        padding = self.list_a.frameWidth() * 2

        target_height = (visible_rows * actual_row_height) + padding

        self.list_a.setFixedHeight(target_height)
        self.list_b.setFixedHeight(target_height)