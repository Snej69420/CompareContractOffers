from PySide6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QPushButton
from PySide6.QtCore import Qt, Signal, QTimer, QPoint

from src.UI.ManualMatching.Cluster import Cluster
from src.UI.ManualMatching.Unmatched import Unmatched
from src.UI.ManualMatching.MatchItem import MatchItem


class ComparisonTab(QWidget):
    # Emitted whenever items are moved, dropped, or deleted.
    stateChanged = Signal()

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
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

    def populate_from_ai(self, clusters: list[dict], lookup: dict, unmatched_a: list, unmatched_b: list):
        """Builds the entire UI based on the AI output."""
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

        # 3. Render Parking Lot at the very bottom
        self.parking_lot = Unmatched(unmatched_a, unmatched_b)
        self.cluster_layout.addWidget(self.parking_lot)

        # 4. Wire up Navigation and Scrolling
        self.parking_lot.requestNeighborMove.connect(self.handle_neighbor_move)
        self.parking_lot.requestGlobalNavigation.connect(self.handle_global_navigation)
        self.parking_lot.list_a.currentItemChanged.connect(
            lambda current, previous, lw=self.parking_lot.list_a: self.auto_scroll_to_item(lw, current)
        )
        self.parking_lot.list_b.currentItemChanged.connect(
            lambda current, previous, lw=self.parking_lot.list_b: self.auto_scroll_to_item(lw, current)
        )

        # 5. Connect UI changes to the stateChanged signal
        self.parking_lot.list_a.itemDropped.connect(self.stateChanged.emit)
        self.parking_lot.list_b.itemDropped.connect(self.stateChanged.emit)
        self.parking_lot.list_a.itemEjected.connect(lambda _: self.stateChanged.emit())
        self.parking_lot.list_b.itemEjected.connect(lambda _: self.stateChanged.emit())

        self.parking_lot.update_parking_lot()
        self.stateChanged.emit()

    def auto_create_cluster(self, cluster_data: dict, index: int):
        widget = Cluster(cluster_data, index, self.global_score_lookup)
        widget.itemToParkingLot.connect(self.send_to_unmatched)
        widget.clusterRemoved.connect(self.remove_cluster)
        widget.requestNeighborMove.connect(self.handle_neighbor_move)
        widget.requestGlobalNavigation.connect(self.handle_global_navigation)

        widget.list_a.currentItemChanged.connect(
            lambda current, previous, lw=widget.list_a: self.auto_scroll_to_item(lw, current)
        )
        widget.list_b.currentItemChanged.connect(
            lambda current, previous, lw=widget.list_b: self.auto_scroll_to_item(lw, current)
        )

        widget.list_a.itemDropped.connect(self.stateChanged.emit)
        widget.list_b.itemDropped.connect(self.stateChanged.emit)
        widget.list_a.itemEjected.connect(lambda _: self.stateChanged.emit())
        widget.list_b.itemEjected.connect(lambda _: self.stateChanged.emit())

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

    def remove_cluster(self, widget: Cluster, items_a: list, items_b: list):
        if items_a or items_b:
            self.parking_lot.receive_items(items_a + items_b)

        widget.deleteLater()
        self.cluster_layout.removeWidget(widget)
        self.stateChanged.emit()

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

    def handle_global_navigation(self, source_widget, side, direction):
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

        target_list = target_widget.list_a if side == 'A' else target_widget.list_b
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
            if hasattr(widget, 'list_a') and not hasattr(widget, 'update_parking_lot'):
                items_a = widget.list_a.get_items()
                items_b = widget.list_b.get_items()
                if items_a or items_b:
                    clusters_data.append({'A': items_a, 'B': items_b})

        unmatched_a = self.parking_lot.list_a.get_items()
        unmatched_b = self.parking_lot.list_b.get_items()

        return clusters_data, unmatched_a + unmatched_b