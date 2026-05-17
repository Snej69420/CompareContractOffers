from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton
from PySide6.QtCore import Signal, Qt, QSize, QTimer, QItemSelectionModel
from src.UI.ManualMatching.DraggableItemList import DraggableItemList


class BaseCluster(QFrame):
    """Base class providing the layout and height logic for both Clusters and the Parking Lot."""
    requestNeighborMove = Signal(object, object, str)
    requestGlobalNavigation = Signal(object, str, str)
    requestDragRoute = Signal(object, object, object)
    requestScrollTo = Signal(object)

    def __init__(self, title_text: str, doc_keys: list[str]):
        super().__init__()
        self.doc_keys = doc_keys
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)

        self.layout = QVBoxLayout(self)
        # ---> FIX 1: Neutralize hidden Qt margins to fix the visual drift <---
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Header Setup
        self.header_layout = QHBoxLayout()
        # ---> FIX 2: Explicitly give the title its own breathing room <---
        self.header_layout.setContentsMargins(10, 10, 10, 5)

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
        # ---> FIX 3: Ensure lists layout has zero hidden margins <---
        lists_layout.setContentsMargins(0, 0, 0, 0)
        self.lists = {}

        for key in self.doc_keys:
            lst = DraggableItemList(key, self.doc_keys)
            lst.itemDropped.connect(self.on_items_changed)
            lst.moveToNeighbor.connect(self._emit_neighbor_move)
            lst.navigateBoundary.connect(self.handle_boundary_navigation)
            lst.requestDragRoute.connect(self.requestDragRoute.emit)
            lst.requestScrollTo.connect(self.requestScrollTo.emit)

            lists_layout.addWidget(lst)
            self.lists[key] = lst

        self.layout.addWidget(self.lists_widget)

    def _emit_neighbor_move(self, match_item, direction):
        """Passes the request up, identifying self as the source."""
        self.requestNeighborMove.emit(self, match_item, direction)

    def handle_boundary_navigation(self, doc_key, direction):
        idx = self.doc_keys.index(doc_key)

        if direction in ("left", "right"):
            target_idx = idx - 1 if direction == "left" else idx + 1

            if 0 <= target_idx < len(self.doc_keys):
                target_key = self.doc_keys[target_idx]

                # Alert the Tab so it can shift the carousel if needed
                self.requestGlobalNavigation.emit(self, target_key, direction)

                # Now apply the focus locally
                target_list = self.lists[target_key]
                source_list = self.lists[doc_key]

                target_list.setFocus()
                if target_list.count() > 0:
                    row = min(max(0, source_list.currentRow()), target_list.count() - 1)
                    target_list.setCurrentRow(row)
        else:
            # Vertical navigation (Up/Down out of this cluster)
            self.requestGlobalNavigation.emit(self, doc_key, direction)

    def focus_on_item(self, match_item):
        """
        Safe focus mechanism. Because the UI engine destroys and rebuilds
        items on state change, we must defer focus by 0ms so Qt has time
        to finish drawing the new C++ objects before we try to select them.
        """

        def _apply_focus():
            target_list = self.lists[match_item.doc_key]
            for i in range(target_list.count()):
                if target_list.item(i).data(Qt.ItemDataRole.UserRole) is match_item:
                    target_list.setCurrentRow(i)
                    target_list.setFocus()
                    break

        QTimer.singleShot(0, _apply_focus)

    def select_items(self, match_items: list):
        """
        Safely selects multiple items and moves the keyboard focus
        without destroying the selection state.
        """

        def _apply_selection():
            if not match_items:
                return

            target_list = self.lists[match_items[0].doc_key]
            target_list.clearSelection()

            first_row = -1

            for match_item in match_items:
                for i in range(target_list.count()):
                    if target_list.item(i).data(Qt.ItemDataRole.UserRole) is match_item:
                        target_list.item(i).setSelected(True)
                        if first_row == -1:
                            first_row = i
                        break

            if first_row != -1:
                index = target_list.model().index(first_row, 0)
                target_list.selectionModel().setCurrentIndex(
                    index,
                    QItemSelectionModel.SelectionFlag.NoUpdate
                )

            target_list.setFocus()

        QTimer.singleShot(0, _apply_selection)

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

    def set_visible_columns(self, visible_keys: list[str]):
        """Hides or shows columns based on the current active 'window'."""
        for key, lst in self.lists.items():
            lst.setVisible(key in visible_keys)