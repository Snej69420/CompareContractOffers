import math
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QPushButton, QLabel
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QShortcut, QKeySequence

# UI Imports
from src.UI.ManualMatching.Cluster import Cluster
from src.UI.ManualMatching.Unmatched import Unmatched
# Data Model Imports
from src.UI.MatchingEngine import MatchingEngine


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
        # --- 1. INITIALIZE THE DATA ENGINE ---
        self.engine = MatchingEngine()
        self._wire_engine_signals()

        self.cluster_widgets = {}  # Map cluster_id to physical UI widgets
        self.parking_lot_widget = None

        # --- 2. SETUP UI LAYOUT ---
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Header Scroll Area
        self.header_row_layout = QHBoxLayout()
        self.header_row_layout.setContentsMargins(0, 5, 20, 0)
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
        self.header_row_layout.addWidget(self.header_scroll, stretch=1)
        self.layout.addLayout(self.header_row_layout)

        # Main Workspace Carousel
        self.scroll_area = PagedScrollArea()
        self.cluster_container = QWidget()
        self.cluster_layout = QVBoxLayout(self.cluster_container)
        self.cluster_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.cluster_layout.setContentsMargins(25, 0, 25, 0)
        self.scroll_area.setWidget(self.cluster_container)
        self.layout.addWidget(self.scroll_area)

        # Sync scrolling
        self.scroll_area.horizontalScrollBar().valueChanged.connect(
            self.header_scroll.horizontalScrollBar().setValue
        )

        # Add Cluster Button
        self.add_cluster_btn = QPushButton("Nieuwe cluster toevoegen")
        self.add_cluster_btn.setStyleSheet(
            "background-color: #007bff; color: white; font-weight: bold; border-radius: 5px; padding: 10px; margin: 10px 25px;"
        )
        self.add_cluster_btn.clicked.connect(self.engine.create_empty_cluster)
        self.layout.addWidget(self.add_cluster_btn)

        # Shortcuts
        self.new_cluster_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        self.new_cluster_shortcut.activated.connect(self.engine.create_empty_cluster)

    def _wire_engine_signals(self):
        """Connects the Data Model's announcements to the UI's drawing functions."""
        self.engine.stateLoaded.connect(self._build_entire_ui)
        self.engine.clusterAdded.connect(self._create_cluster_widget)
        self.engine.clusterRemoved.connect(self._remove_cluster_widget)
        self.engine.clusterUpdated.connect(self._update_cluster_widget)
        self.engine.unmatchedUpdated.connect(self._update_parking_lot_widget)

    # ==========================================
    # --- DATA INGRESS & EGRESS ---
    # ==========================================

    def populate_from_ai(self, doc_keys: list[str], clusters: list[dict], lookup: dict, unmatched_dict: dict):
        """Called by MainWindow. We just pass this straight to the Engine."""
        self.engine.load_ai_data(doc_keys, clusters, lookup, unmatched_dict)

    def gather_current_state(self):
        """No more UI scraping! We just ask the Engine for the data."""
        # We will add an export_state() method to the Engine later,
        # but for now this replaces your old scrape logic perfectly.
        clusters_data = []
        for c_id, c_data in self.engine.clusters.items():
            cluster_dict = {}
            for key, items in c_data.items.items():
                cluster_dict[key] = items
            clusters_data.append(cluster_dict)

        unmatched_items = []
        for items in self.engine.unmatched.values():
            unmatched_items.extend(items)

        return clusters_data, unmatched_items

    # ==========================================
    # --- UI RENDERING METHODS ---
    # ==========================================

    def _build_entire_ui(self):
        """Fires once when a new document is loaded."""
        # 1. Clear Headers
        while self.column_headers_layout.count():
            item = self.column_headers_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        # 2. Rebuild Headers
        for key in self.engine.doc_keys:
            lbl = QLabel(key)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                "font-weight: bold; font-size: 14px; padding: 6px; background-color: #d1d9e6; border-radius: 4px; color: #333;")
            self.column_headers_layout.addWidget(lbl)

        # 3. Clear existing Clusters safely
        for widget in self.cluster_widgets.values():
            widget.setParent(None)
            widget.deleteLater()
        self.cluster_widgets.clear()

        if self.parking_lot_widget:
            self.parking_lot_widget.setParent(None)
            self.parking_lot_widget.deleteLater()
            self.parking_lot_widget = None  # Crucial to prevent ghost references

        # 4. Build new Clusters from Engine state
        for c_id in self.engine.clusters.keys():
            self._create_cluster_widget(c_id)

        # 5. Build Parking Lot
        self.parking_lot_widget = Unmatched(self.engine.doc_keys)
        self.cluster_layout.addWidget(self.parking_lot_widget)
        self._update_parking_lot_widget()

        self.stateChanged.emit()
        QTimer.singleShot(100, self.recalculate_column_widths)

    def _create_cluster_widget(self, cluster_id: int):
        widget = Cluster(cluster_id, self.engine.doc_keys)

        # When the widget says "Delete me", tell the Engine.
        widget.clusterRemoved.connect(self.engine.delete_cluster)

        # When the widget says "Eject this item", route it to the Engine.
        widget.itemEjected.connect(lambda item, c_id: self.engine.move_item(item, c_id, None))

        # (Drag and drop signals will be routed here later)

        # Inject above parking lot
        if self.parking_lot_widget:
            idx = self.cluster_layout.indexOf(self.parking_lot_widget)
            self.cluster_layout.insertWidget(idx, widget)
        else:
            self.cluster_layout.addWidget(widget)

        self.cluster_widgets[cluster_id] = widget
        self._update_cluster_widget(cluster_id)

    def _remove_cluster_widget(self, cluster_id: int):
        if cluster_id in self.cluster_widgets:
            widget = self.cluster_widgets.pop(cluster_id)
            self.cluster_layout.removeWidget(widget)
            widget.deleteLater()
            self.stateChanged.emit()

    def _update_cluster_widget(self, cluster_id: int):
        if cluster_id in self.cluster_widgets and cluster_id in self.engine.clusters:
            data = self.engine.clusters[cluster_id]
            self.cluster_widgets[cluster_id].update_ui(data)
            self.stateChanged.emit()

    def _update_parking_lot_widget(self):
        if self.parking_lot_widget:
            self.parking_lot_widget.update_ui(self.engine.unmatched)
        self.stateChanged.emit()

    # --- 3. THE MATHEMATICAL RESIZER (Keep exactly as we fixed it!) ---
    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(50, self.recalculate_column_widths)

    def recalculate_column_widths(self):
        if not self.engine.doc_keys: return
        viewport_width = self.scroll_area.viewport().width()
        actual_layout_margins = 50
        safe_dead_space = actual_layout_margins + 2
        spacing = 10
        min_col_width = 330
        available_for_lists = viewport_width - safe_dead_space
        visible_cols = max(1, available_for_lists // min_col_width)
        visible_cols = min(visible_cols, len(self.engine.doc_keys))
        total_gaps = (visible_cols - 1) * spacing
        exact_col_width = math.ceil((available_for_lists - total_gaps) / visible_cols)

        snap_step = exact_col_width + spacing
        self.scroll_area.snap_step = snap_step
        self.scroll_area.horizontalScrollBar().setSingleStep(snap_step)

        self.column_headers_layout.setSpacing(spacing)
        for i in range(self.column_headers_layout.count()):
            widget = self.column_headers_layout.itemAt(i).widget()
            if widget: widget.setFixedWidth(exact_col_width)

        for widget in self.cluster_widgets.values():
            for lst in widget.lists.values():
                lst.setFixedWidth(exact_col_width)