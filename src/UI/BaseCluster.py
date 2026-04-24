from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from src.UI.DraggableItemList import DraggableItemList

class BaseClusterWidget(QFrame):
    """Base class providing the layout and height logic for both Clusters and the Parking Lot."""

    def __init__(self, title_text: str):
        super().__init__()
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)

        self.layout = QVBoxLayout(self)

        # Header Layout (Children can add buttons to this)
        self.header_layout = QHBoxLayout()
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