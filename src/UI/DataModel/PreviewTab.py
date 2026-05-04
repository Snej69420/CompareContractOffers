import pandas as pd
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableView, QHeaderView
from PySide6.QtCore import Qt, QTimer

from src.UI.DataModel.DataTable import DataTableModel
from src.UI.DataModel.ReportGenerator import ReportGenerator
from src.UI.DataModel.DynamicTable import DynamicTable

class PreviewTab(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)

        # Header
        self.header_label = QLabel("Project: ...")
        self.header_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.layout.addWidget(self.header_label)

        # Table Setup
        self.table = DynamicTable()
        self.layout.addWidget(self.table)

        # Internal Debouncer
        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self._generate_and_render)

        # State Tracking
        self._pending_clusters = []
        self._pending_unmatched = []
        self._loaded_documents = {}
        self._last_fingerprint = ""

    def request_update(self, clusters_data: list, unmatched_items: list, loaded_documents: dict):
        self._pending_clusters = clusters_data
        self._pending_unmatched = unmatched_items
        self._loaded_documents = loaded_documents
        self.preview_timer.start(100)

    def force_resize(self):
        """Forces Qt to recalculate row heights when the tab becomes physically visible."""
        self.table.resizeRowsToContents()

    def _get_state_fingerprint(self, clusters_data, unmatched_items):
        """Creates a unique string identifying the current exact layout of items."""
        fingerprint = ""
        for idx, cluster in enumerate(clusters_data):
            # Dynamically sort and append whatever keys are in the cluster
            cluster_str = ""
            for key in sorted(cluster.keys()):
                names = ",".join([str(i.name) for i in cluster[key]])
                cluster_str += f"{key}[{names}]"
            fingerprint += f"C{idx}:{cluster_str}|"

        u_names = ",".join([str(i.name) for i in unmatched_items])
        fingerprint += f"U:[{u_names}]"

        return fingerprint

    def _generate_and_render(self):
        if not self._loaded_documents:
            return

        fingerprint = self._get_state_fingerprint(self._pending_clusters, self._pending_unmatched)
        if self._last_fingerprint == fingerprint:
            return
        self._last_fingerprint = fingerprint

        # Extract Metadata
        names = {}
        project_name = "Project Onbekend"

        for path, df in self._loaded_documents.items():
            names[path.name] = df.attrs.get('contractor', path.stem)
            if project_name == "Project Onbekend":
                project_name = df.attrs.get('project', 'Project Onbekend')

        self.header_label.setText(f"📁 Project: {project_name}")

        # Generate Data
        generator = ReportGenerator(names)
        df_data, df_colors, spans = generator.generate(self._pending_clusters, self._pending_unmatched)

        # Render Table Model
        model = DataTableModel(df_data, df_colors)
        self.table.setModel(model)

        # --- 3. Initial Layout & Spans ---
        # We clear old spans, set initial stretch for the first load, and apply the new spans.
        self.table.clearSpans()

        # VITAL: Re-apply the vertical cell merging for the report
        for row_start, row_span, c_name in spans:
            for col_idx in range(model.columnCount()):
                col_header = str(model.headerData(col_idx, Qt.Orientation.Horizontal))
                if c_name in col_header:
                    self.table.setSpan(row_start, col_idx, row_span, 1)