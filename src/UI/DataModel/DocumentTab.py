import pandas as pd
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableView, QHeaderView
from PySide6.QtCore import Qt
from src.UI.DataModel.DataTable import DataTableModel


class DocumentTabWidget(QWidget):
    def __init__(self, df: pd.DataFrame, file_name: str):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)

        # Safely drop the 'Opmerkingen' column if it exists
        drop_cols = [c for c in df.columns if c.strip().lower() == 'opmerkingen']
        df_display = df.drop(columns=drop_cols)

        info_text = f"📄 Bestand: {file_name}   |   📊 Aantal items: {len(df_display)}"
        self.info_label = QLabel(info_text)
        self.info_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 5px; color: #333;")
        self.layout.addWidget(self.info_label)

        self.table_view = QTableView()
        self.table_model = DataTableModel(df_display)
        self.table_view.setModel(self.table_model)

        self.table_view.setAlternatingRowColors(True)
        self.table_view.setStyleSheet("alternate-background-color: #f5f5f5; background-color: #ffffff;")
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)

        # Enable Word Wrap and tell rows to grow dynamically based on wrapped text
        self.table_view.setWordWrap(True)
        self.table_view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        # --- NEW: Smart Stretching Logic ---
        header = self.table_view.horizontalHeader()
        header.setStretchLastSection(False)

        # 1. Start by packing everything tightly to get baseline widths
        self.table_view.resizeColumnsToContents()

        # 2. Identify text-heavy columns that should absorb all empty screen space
        stretch_candidates = ['naam', 'omschrijving', 'beschrijving', 'categorie', 'tekst']
        stretched_any = False

        for i in range(self.table_model.columnCount()):
            col_name = str(self.table_model.headerData(i, Qt.Orientation.Horizontal)).lower()

            if any(candidate in col_name for candidate in stretch_candidates):
                # This column will stretch dynamically as the user resizes the window
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
                stretched_any = True
            else:
                # --- FIXED: Lock the column width and disable manual dragging ---
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)

        # Fallback: if we didn't find standard names, just stretch the second column (usually 'Naam')
        if not stretched_any and self.table_model.columnCount() > 1:
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        self.layout.addWidget(self.table_view)