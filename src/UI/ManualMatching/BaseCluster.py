from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton
from PySide6.QtCore import Signal, Qt, QSize
from src.UI.ManualMatching.DraggableItemList import DraggableItemList

class BaseCluster(QFrame):
    """Base class providing the layout and height logic for both Clusters and the Parking Lot."""
    requestNeighborMove = Signal(object, object, str)
    requestGlobalNavigation = Signal(object, str, str)

    def __init__(self, title_text: str, doc_keys: list[str]):
        super().__init__()
        self.doc_keys = doc_keys
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.layout = QVBoxLayout(self)

        # Header Setup (same as your current code)
        self.header_layout = QHBoxLayout()
        self.icon_label = QPushButton()
        self.icon_label.setFlat(True)
        self.icon_label.setEnabled(False)
        self.icon_label.setStyleSheet("border: none; background: transparent; padding: 0px;")
        self.icon_label.setIconSize(QSize(20, 20))
        self.header_layout.addWidget(self.icon_label)
        self.title_label = QLabel(title_text)
        self.header_layout.addWidget(self.title_label)
        self.header_layout.addStretch()
        self.layout.addLayout(self.header_layout)

        # --- DYNAMIC LIST GENERATION ---
        self.lists_widget = QWidget()
        lists_layout = QHBoxLayout(self.lists_widget)
        self.lists = {}

        for key in self.doc_keys:
            lst = DraggableItemList(key, self.doc_keys)
            lst.itemDropped.connect(self.on_items_changed)
            lst.moveToNeighbor.connect(self._emit_neighbor_move)
            lst.navigateBoundary.connect(self.handle_boundary_navigation)

            lists_layout.addWidget(lst)
            self.lists[key] = lst

        self.layout.addWidget(self.lists_widget)

    def _emit_neighbor_move(self, match_item, direction):
        """Passes the request up, identifying self as the source."""
        self.requestNeighborMove.emit(self, match_item, direction)

    def handle_boundary_navigation(self, doc_key, direction):
        idx = self.doc_keys.index(doc_key)

        if direction == "left" and idx > 0:
            target_list = self.lists[self.doc_keys[idx - 1]]
            source_list = self.lists[doc_key]

            target_list.setFocus()
            if target_list.count() > 0:
                row = min(source_list.currentRow(), target_list.count() - 1)
                target_list.setCurrentRow(max(0, row))

        elif direction == "right" and idx < len(self.doc_keys) - 1:
            target_list = self.lists[self.doc_keys[idx + 1]]
            source_list = self.lists[doc_key]

            target_list.setFocus()
            if target_list.count() > 0:
                row = min(source_list.currentRow(), target_list.count() - 1)
                target_list.setCurrentRow(max(0, row))
        else:
            self.requestGlobalNavigation.emit(self, doc_key, direction)

    def remove_item_silently(self, match_item):
        target_list = self.lists[match_item.doc_key]
        items = [i for i in target_list.get_items() if i is not match_item]
        target_list.rebuild_ui(items)
        self.on_items_changed()

    def inject_item(self, match_item):
        target_list = self.lists[match_item.doc_key]
        items = target_list.get_items()
        items.append(match_item)
        target_list.rebuild_ui(items)
        self.on_items_changed()

    def focus_on_item(self, match_item):
        target_list = self.lists[match_item.doc_key]
        for i in range(target_list.count()):
            if target_list.item(i).data(Qt.ItemDataRole.UserRole) is match_item:
                target_list.setCurrentRow(i)
                target_list.setFocus()
                break

    def on_items_changed(self):
        """To be overridden by child classes to handle re-calculations."""
        pass

    def adjust_list_heights(self, max_visible_rows: int = 6):
        # Calculate max items across ALL columns
        max_items = max([len(lst.get_items()) for lst in self.lists.values()] + [1])
        visible_rows = min(max_items, max_visible_rows)

        # Get highest single row height safely
        actual_row_height = max([lst.get_single_row_height() for lst in self.lists.values()])

        # Use first list to grab padding
        padding = list(self.lists.values())[0].frameWidth() * 2
        target_height = (visible_rows * actual_row_height) + padding

        for lst in self.lists.values():
            lst.setFixedHeight(target_height)