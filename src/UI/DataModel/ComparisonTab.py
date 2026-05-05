import math
from pathlib import Path
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QPushButton, QLabel
from PySide6.QtCore import Qt, Signal, QTimer, QPoint
from PySide6.QtGui import QIcon, QShortcut, QKeySequence

from src.UI.ManualMatching.Cluster import Cluster
from src.UI.ManualMatching.Unmatched import Unmatched
from src.UI.ManualMatching.MatchItem import MatchItem
from src.UI.DataModel.Shortcut import ShortcutDialog


# --- 1. THE CUSTOM SNAP SCROLL AREA ---
class PagedScrollArea(QScrollArea):
    """A custom scroll area that waits for the user to stop scrolling, then mathematically snaps to the nearest column."""

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.snap_step = 400

        # Debounce timer to wait for trackpad/mouse wheel to stop
        self.snap_timer = QTimer()
        self.snap_timer.setSingleShot(True)
        self.snap_timer.timeout.connect(self.snap_to_column)
        self.horizontalScrollBar().valueChanged.connect(self.on_scroll)

    def on_scroll(self):
        # Start a 250ms countdown every time the scrollbar moves.
        h_bar = self.horizontalScrollBar()
        if 0 < h_bar.value() < h_bar.maximum():
            self.snap_timer.start(250)

    def snap_to_column(self):
        if self.snap_step <= 0: return
        h_bar = self.horizontalScrollBar()
        current_val = h_bar.value()

        # Find nearest exact column index
        target_val = round(current_val / self.snap_step) * self.snap_step

        # Clamp the value so we don't try to snap past the end of the scroll area
        target_val = max(0, min(target_val, h_bar.maximum()))

        if abs(current_val - target_val) > 2:
            h_bar.setValue(target_val)


class ComparisonTab(QWidget):
    stateChanged = Signal()

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.header_row_layout = QHBoxLayout()
        self.header_row_layout.setContentsMargins(0, 5, 20, 0)

        # The Sticky Header Scroll Area
        self.header_scroll = QScrollArea()
        self.header_scroll.setWidgetResizable(True)
        self.header_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.header_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.header_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.header_scroll.setFixedHeight(45)

        self.column_headers_container = QWidget()
        self.column_headers_layout = QHBoxLayout(self.column_headers_container)
        self.column_headers_layout.setContentsMargins(25, 0, 25, 0)
        self.header_scroll.setWidget(self.column_headers_container)

        # The Info Button
        self.info_btn = QPushButton()
        icon_dir = Path(__file__).parent.parent.parent.parent / "assets"
        self.info_btn.setIcon(QIcon(str(icon_dir / "info.svg")))
        self.info_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.info_btn.setToolTip("Bekijk sneltoetsen")
        self.info_btn.setStyleSheet("""
            QPushButton { background-color: transparent; border: none; border-radius: 12px; padding: 4px; }
            QPushButton:hover { background-color: #e0e0e0; }
        """)
        self.info_btn.clicked.connect(self.show_shortcuts_info)

        # Mount Header Row
        self.header_row_layout.addWidget(self.header_scroll, stretch=1)
        self.header_row_layout.addWidget(self.info_btn, alignment=Qt.AlignmentFlag.AlignBottom)
        self.layout.addLayout(self.header_row_layout)

        # The Main Workspace (Using our Custom Snap Area!)
        self.scroll_area = PagedScrollArea()
        self.cluster_container = QWidget()
        self.cluster_layout = QVBoxLayout(self.cluster_container)
        self.cluster_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.cluster_layout.setContentsMargins(25, 0, 25, 0)
        self.scroll_area.setWidget(self.cluster_container)
        self.layout.addWidget(self.scroll_area)

        # Link Header to Scroll Area
        self.scroll_area.horizontalScrollBar().valueChanged.connect(
            self.header_scroll.horizontalScrollBar().setValue
        )

        self.add_cluster_btn = QPushButton("Nieuwe cluster toevoegen")
        self.add_cluster_btn.setStyleSheet(
            "background-color: #007bff; color: white; font-weight: bold; border-radius: 5px; padding: 10px; margin: 10px 25px;"
        )
        self.add_cluster_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_cluster_btn.clicked.connect(self.create_cluster)
        self.layout.addWidget(self.add_cluster_btn)

        # State Variables
        self.global_score_lookup = {}
        self.cluster_count = 0
        self.parking_lot = None
        self.add_cluster_btn = None
        self.doc_keys: list[str] = []

        self.new_cluster_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        self.new_cluster_shortcut.activated.connect(self.create_cluster)

    # --- 2. THE MATHEMATICAL RESIZER ---
    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(50, self.recalculate_column_widths)


    def recalculate_column_widths(self):
        if not self.doc_keys: return

        viewport_width = self.scroll_area.viewport().width()

        # Update Dead Space to match layout margins.
        # header_row_layout has (25 left + 5 right) = 50px
        actual_layout_margins = 50

        # You may need a tiny buffer for standard Qt layout borders, but 70 was too much.
        safe_dead_space = actual_layout_margins + 2
        spacing = 10
        min_col_width = 330

        available_for_lists = viewport_width - safe_dead_space

        visible_cols = max(1, available_for_lists // min_col_width)
        visible_cols = min(visible_cols, len(self.doc_keys))

        total_gaps = (visible_cols - 1) * spacing

        # Use math.ceil instead of int()
        # This ensures we push the fraction OFF-screen rather than pulling the next ON-screen.
        exact_col_width = math.ceil((available_for_lists - total_gaps) / visible_cols)

        snap_step = exact_col_width + spacing
        self.scroll_area.snap_step = snap_step
        self.scroll_area.horizontalScrollBar().setSingleStep(snap_step)

        # Headers
        self.column_headers_layout.setSpacing(spacing)
        for i in range(self.column_headers_layout.count()):
            widget = self.column_headers_layout.itemAt(i).widget()
            if widget: widget.setFixedWidth(exact_col_width)

        # Lists
        for i in range(self.cluster_layout.count()):
            widget = self.cluster_layout.itemAt(i).widget()
            if hasattr(widget, 'lists'):
                for lst in widget.lists.values():
                    lst.setFixedWidth(exact_col_width)

    def show_shortcuts_info(self):
        dialog = ShortcutDialog(self)
        dialog.exec()

    def populate_from_ai(self, doc_keys: list[str], clusters: list[dict], lookup: dict, unmatched_dict: dict):
        self.doc_keys = doc_keys
        self.global_score_lookup = lookup
        self.cluster_count = 0

        while self.column_headers_layout.count():
            item = self.column_headers_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        for key in self.doc_keys:
            lbl = QLabel(key)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("font-weight: bold; font-size: 14px; padding: 6px; background-color: #d1d9e6; border-radius: 4px; color: #333;")
            self.column_headers_layout.addWidget(lbl)

        for i in reversed(range(self.cluster_layout.count())):
            widget = self.cluster_layout.itemAt(i).widget()
            if widget: widget.setParent(None)

        self.parking_lot = None
        clusters.sort(key=lambda x: x.get('cluster_score', 0.0), reverse=True)

        for cluster_data in clusters:
            self.cluster_count += 1
            self.auto_create_cluster(cluster_data, self.cluster_count)

        self.parking_lot = Unmatched(self.doc_keys, unmatched_dict)
        self.cluster_layout.addWidget(self.parking_lot)

        self.parking_lot.requestNeighborMove.connect(self.handle_neighbor_move)
        self.parking_lot.requestGlobalNavigation.connect(self.handle_global_navigation)

        for key, lst in self.parking_lot.lists.items():
            lst.currentItemChanged.connect(lambda current, previous, lw=lst: self.auto_scroll_to_item(lw, current))
            lst.itemDropped.connect(self.stateChanged.emit)
            lst.itemEjected.connect(lambda _: self.stateChanged.emit())

        self.parking_lot.update_parking_lot()
        self.stateChanged.emit()
        QTimer.singleShot(100, self.recalculate_column_widths)

    def auto_create_cluster(self, cluster_data: dict, index: int):
        widget = Cluster(self.doc_keys, cluster_data, index, self.global_score_lookup)
        widget.itemToParkingLot.connect(self.send_to_unmatched)
        widget.clusterRemoved.connect(self.remove_cluster)
        widget.requestNeighborMove.connect(self.handle_neighbor_move)
        widget.requestGlobalNavigation.connect(self.handle_global_navigation)

        for key, lst in widget.lists.items():
            lst.currentItemChanged.connect(lambda current, previous, lw=lst: self.auto_scroll_to_item(lw, current))
            lst.itemDropped.connect(self.stateChanged.emit)
            lst.itemEjected.connect(lambda _: self.stateChanged.emit())

        # Clean routing: Just inject it right above the parking lot
        if self.parking_lot:
            idx = self.cluster_layout.indexOf(self.parking_lot)
            self.cluster_layout.insertWidget(idx, widget)
        else:
            self.cluster_layout.addWidget(widget)

    def create_cluster(self):
        self.cluster_count += 1
        empty_data = {'contract_a_items': [], 'contract_b_items': []}
        self.auto_create_cluster(empty_data, self.cluster_count)

        scroll_bar = self.scroll_area.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())

    def remove_cluster(self, widget: Cluster, all_items: list):
        if all_items:
            self.parking_lot.receive_items(all_items)

        active_key = self.doc_keys[0] if self.doc_keys else None
        for key, lst in widget.lists.items():
            if lst.hasFocus():
                active_key = key
                break

        idx = self.cluster_layout.indexOf(widget)
        target_idx = idx - 1 if idx > 0 else idx + 1

        target_widget = None
        if 0 <= target_idx < self.cluster_layout.count():
            target_widget = self.cluster_layout.itemAt(target_idx).widget()
            # If it hits the parking lot, reverse direction to focus on a cluster
            if target_widget == self.parking_lot:
                target_idx = idx - 1
                if 0 <= target_idx < self.cluster_layout.count():
                    target_widget = self.cluster_layout.itemAt(target_idx).widget()

        widget.deleteLater()
        self.cluster_layout.removeWidget(widget)
        self.stateChanged.emit()

        if target_widget and hasattr(target_widget, 'lists') and active_key:
            target_list = target_widget.lists.get(active_key)
            if target_list:
                target_list.setFocus()
                if target_list.count() > 0:
                    target_list.setCurrentRow(0)

    def send_to_unmatched(self, match_item: MatchItem):
        self.parking_lot.receive_items([match_item])
        self.stateChanged.emit()

    def handle_neighbor_move(self, source_widget, match_item, direction):
        idx = self.cluster_layout.indexOf(source_widget)
        target_idx = idx - 1 if direction == "up" else idx + 1

        if target_idx < 0 or target_idx >= self.cluster_layout.count():
            return

        target_widget = self.cluster_layout.itemAt(target_idx).widget()

        if isinstance(target_widget, QPushButton):
            target_idx = target_idx - 1 if direction == "up" else target_idx + 1
            if target_idx < 0 or target_idx >= self.cluster_layout.count():
                return
            target_widget = self.cluster_layout.itemAt(target_idx).widget()

        source_widget.remove_item_silently(match_item)

        if hasattr(target_widget, "update_parking_lot"):
            match_item.is_parked = True
        else:
            match_item.is_parked = False

        target_widget.inject_item(match_item)
        target_widget.focus_on_item(match_item)
        self.stateChanged.emit()

    def handle_global_navigation(self, source_widget, doc_key, direction):
        idx = self.cluster_layout.indexOf(source_widget)
        target_idx = idx - 1 if direction == "up" else idx + 1

        if target_idx < 0 or target_idx >= self.cluster_layout.count():
            return

        target_widget = self.cluster_layout.itemAt(target_idx).widget()

        if isinstance(target_widget, QPushButton):
            target_idx = target_idx - 1 if direction == "up" else target_idx + 1
            if target_idx < 0 or target_idx >= self.cluster_layout.count():
                return
            target_widget = self.cluster_layout.itemAt(target_idx).widget()

        target_list = target_widget.lists[doc_key]
        target_list.setFocus()

        if target_list.count() > 0:
            if direction == "up":
                target_list.setCurrentRow(target_list.count() - 1)
            else:
                target_list.setCurrentRow(0)

    def auto_scroll_to_item(self, list_widget, item):
        if not item: return
        QTimer.singleShot(0, lambda: self._perform_auto_scroll(list_widget, item))

    def _perform_auto_scroll(self, list_widget, item):
        if not item: return
        try:
            list_widget.scrollToItem(item)
            item_rect = list_widget.visualItemRect(item)
            if item_rect.isNull(): return

            item_center_y = item_rect.center().y()
            pos_in_container = list_widget.viewport().mapTo(self.cluster_container, QPoint(0, int(item_center_y)))
            absolute_y = pos_in_container.y()

            scrollbar = self.scroll_area.verticalScrollBar()
            current_scroll = scrollbar.value()
            viewport_height = self.scroll_area.viewport().height()

            deadzone_top = current_scroll + (viewport_height / 3)
            deadzone_bottom = current_scroll + (2 * viewport_height / 3)

            if absolute_y < deadzone_top:
                scrollbar.setValue(int(absolute_y - (viewport_height / 3)))
            elif absolute_y > deadzone_bottom:
                scrollbar.setValue(int(absolute_y - (2 * viewport_height / 3)))
        except RuntimeError:
            return

    def gather_current_state(self):
        """Scrapes the UI to build the data structure needed by the ReportGenerator."""
        clusters_data = []

        if not self.parking_lot:
            return [], []

        for i in range(self.cluster_layout.count()):
            widget = self.cluster_layout.itemAt(i).widget()
            if isinstance(widget, QPushButton):
                continue

            # Look for 'lists' instead of 'list_a'
            if hasattr(widget, 'lists') and not hasattr(widget, 'update_parking_lot'):
                cluster_dict = {}
                has_items = False

                # Dynamically scrape all N columns
                for key, lst in widget.lists.items():
                    items = lst.get_items()
                    cluster_dict[key] = items
                    if items:
                        has_items = True

                if has_items:
                    clusters_data.append(cluster_dict)

        # Flatten all unmatched items from N columns into a single list
        unmatched_items = []
        for lst in self.parking_lot.lists.values():
            unmatched_items.extend(lst.get_items())

        return clusters_data, unmatched_items