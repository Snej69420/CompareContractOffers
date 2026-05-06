import pandas as pd
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableView, QHeaderView
from PySide6.QtCore import Qt, QTimer

from src.UI.DataRepresentation.DataTable import DataTableModel
from src.UI.DataProcessing.ReportGenerator import ReportGenerator
from src.UI.DataRepresentation.DynamicTable import DynamicTable

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

        # 1. Fingerprint Clusters
        for idx, cluster in enumerate(clusters_data):
            cluster_str = ""
            items_dict = cluster.get('items', cluster)  # Fallback to raw cluster just in case
            is_excluded = cluster.get('is_excluded', False)

            for key in sorted(items_dict.keys()):
                names = ",".join([str(i.name) for i in items_dict[key]])
                cluster_str += f"{key}[{names}]"

            fingerprint += f"C{idx}(excl:{is_excluded}):{cluster_str}|"

        # 2. Fingerprint Unmatched (Now handled as pseudo-clusters)
        u_str = ""
        for idx, pseudo_cluster in enumerate(unmatched_items):
            items_dict = pseudo_cluster.get('items', pseudo_cluster)
            for key in sorted(items_dict.keys()):
                names = ",".join([str(i.name) for i in items_dict[key]])
                u_str += f"{key}[{names}]"

        fingerprint += f"U:[{u_str}]"

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

        self.header_label.setText(f"Project: {project_name}")

        # ---> THE NEW GENERATOR CALL <---
        generator = ReportGenerator(names)
        df_data, df_colors, v_spans, h_spans = generator.generate(self._pending_clusters, self._pending_unmatched)

        # Render Table Model
        model = DataTableModel(df_data, df_colors)
        self.table.setModel(model)

        self.table.clearSpans()

        # ---> 1. Apply the new Horizontal Spans (Headers & Titles) <---
        for row, col, row_span, col_span in h_spans:
            self.table.setSpan(row, col, row_span, col_span)

        # ---> 2. Apply Vertical Spans safely from raw Data <---
        for row_start, row_span, c_name in v_spans:
            for col_idx in range(model.columnCount()):
                # Lookup the raw tuple in the dataframe directly!
                col_tuple = df_data.columns[col_idx]
                if c_name == col_tuple[0]:
                    self.table.setSpan(row_start, col_idx, row_span, 1)