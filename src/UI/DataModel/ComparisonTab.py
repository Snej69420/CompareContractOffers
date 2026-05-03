from pathlib import Path
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QPushButton, QMessageBox
from PySide6.QtCore import Qt, Signal, QTimer, QPoint
from PySide6.QtGui import QIcon, QShortcut, QKeySequence

from src.UI.ManualMatching.Cluster import Cluster
from src.UI.ManualMatching.Unmatched import Unmatched
from src.UI.ManualMatching.MatchItem import MatchItem
from src.UI.DataModel.Shortcut import ShortcutDialog


class ComparisonTab(QWidget):
    # Emitted whenever items are moved, dropped, or deleted.
    stateChanged = Signal()

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # --- NEW: Top Header Bar for the Info Button ---
        self.top_bar_layout = QHBoxLayout()
        self.top_bar_layout.setContentsMargins(0, 10, 20, 5)

        self.info_btn = QPushButton()
        # Ensure you have an info.svg in your assets folder!
        icon_dir = Path(__file__).parent.parent.parent.parent / "assets"
        self.info_btn.setIcon(QIcon(str(icon_dir / "info.svg")))
        self.info_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.info_btn.setToolTip("Bekijk sneltoetsen")
        self.info_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 12px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        self.info_btn.clicked.connect(self.show_shortcuts_info)

        # Push the button to the right side
        self.top_bar_layout.addStretch()
        self.top_bar_layout.addWidget(self.info_btn)

        self.layout.addLayout(self.top_bar_layout)
        # -----------------------------------------------

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; }")
        self.cluster_container = QWidget()
        self.cluster_layout = QVBoxLayout(self.cluster_container)
        self.cluster_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.cluster_container)

        self.layout.addWidget(self.scroll_area)

        # State Variables
        self.global_score_lookup = {}
        self.cluster_count = 0
        self.parking_lot = None
        self.add_cluster_btn = None

        self.doc_keys:list[str] = []

        self.new_cluster_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        self.new_cluster_shortcut.activated.connect(self.create_cluster)

    def show_shortcuts_info(self):
        dialog = ShortcutDialog(self)
        dialog.exec()

    def populate_from_ai(self, doc_keys: list[str], clusters: list[dict], lookup: dict, unmatched_dict: dict):
        """Builds the entire UI based on the AI output."""
        self.doc_keys = doc_keys
        self.global_score_lookup = lookup
        self.cluster_count = 0

        # Clear existing clusters cleanly
        for i in reversed(range(self.cluster_layout.count())):
            widget = self.cluster_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        self.add_cluster_btn = None
        self.parking_lot = None

        clusters.sort(key=lambda x: x.get('cluster_score', 0.0), reverse=True)

        # 1. Render AI Clusters
        for cluster_data in clusters:
            self.cluster_count += 1
            self.auto_create_cluster(cluster_data, self.cluster_count)

        # 2. Add Centralized "New Cluster" Button
        self.add_cluster_btn = QPushButton("Nieuwe cluster toevoegen")
        self.add_cluster_btn.setStyleSheet(
            "background-color: #007bff; color: white; font-weight: bold; border-radius: 5px; padding: 10px; margin: 10px 50px;")
        self.add_cluster_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_cluster_btn.clicked.connect(self.create_cluster)
        self.cluster_layout.addWidget(self.add_cluster_btn)

        self.parking_lot = Unmatched(self.doc_keys, unmatched_dict)
        self.cluster_layout.addWidget(self.parking_lot)

        self.parking_lot.requestNeighborMove.connect(self.handle_neighbor_move)
        self.parking_lot.requestGlobalNavigation.connect(self.handle_global_navigation)

        # Dynamically bind signals for N lists
        for key, lst in self.parking_lot.lists.items():
            lst.currentItemChanged.connect(
                lambda current, previous, lw=lst: self.auto_scroll_to_item(lw, current)
            )
            lst.itemDropped.connect(self.stateChanged.emit)
            lst.itemEjected.connect(lambda _: self.stateChanged.emit())

        self.parking_lot.update_parking_lot()
        self.stateChanged.emit()

    def auto_create_cluster(self, cluster_data: dict, index: int):
        widget = Cluster(self.doc_keys, cluster_data, index, self.global_score_lookup)
        widget.itemToParkingLot.connect(self.send_to_unmatched)
        widget.clusterRemoved.connect(self.remove_cluster)
        widget.requestNeighborMove.connect(self.handle_neighbor_move)
        widget.requestGlobalNavigation.connect(self.handle_global_navigation)

        for key, lst in widget.lists.items():
            lst.currentItemChanged.connect(
                lambda current, previous, lw=lst: self.auto_scroll_to_item(lw, current)
            )
            lst.itemDropped.connect(self.stateChanged.emit)
            lst.itemEjected.connect(lambda _: self.stateChanged.emit())

        if self.add_cluster_btn:
            idx = self.cluster_layout.indexOf(self.add_cluster_btn)
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

        # --- 1. UX FEATURE: Remember Focus State ---
        # Find out which specific column the user was actively focused on
        active_key = self.doc_keys[0] if self.doc_keys else None
        for key, lst in widget.lists.items():
            if lst.hasFocus():
                active_key = key
                break

        # --- 2. Find the Neighboring Cluster ---
        idx = self.cluster_layout.indexOf(widget)
        # Default to the cluster above it. If it's the top cluster, try the one below it.
        target_idx = idx - 1 if idx > 0 else idx + 1

        target_widget = None
        if 0 <= target_idx < self.cluster_layout.count():
            target_widget = self.cluster_layout.itemAt(target_idx).widget()

            # If the neighbor happens to be the "New Cluster" button, skip over it!
            if isinstance(target_widget, QPushButton):
                target_idx = target_idx + 1 if idx == 0 else target_idx - 1
                if 0 <= target_idx < self.cluster_layout.count():
                    target_widget = self.cluster_layout.itemAt(target_idx).widget()

        # --- 3. Destroy the Widget ---
        widget.deleteLater()
        self.cluster_layout.removeWidget(widget)
        self.stateChanged.emit()

        # --- 4. Apply Focus to the Neighbor ---
        if target_widget and hasattr(target_widget, 'lists') and active_key:
            target_list = target_widget.lists.get(active_key)
            if target_list:
                target_list.setFocus()
                # Select the first item in the neighbor so they can keep typing immediately
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