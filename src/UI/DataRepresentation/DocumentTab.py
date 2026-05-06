import pandas as pd
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableView, QHeaderView
from PySide6.QtCore import Qt
from src.UI.DataRepresentation.DataTable import DataTableModel
from src.UI.DataRepresentation.DynamicTable import DynamicTable

class DocumentTab(QWidget):
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

        # --- The Magic of Component Architecture ---
        self.table = DynamicTable()
        self.table_model = DataTableModel(df_display)
        self.table.setModel(self.table_model)

        # We keep this here because selection behavior is specific to how you interact with THIS tab
        from PySide6.QtWidgets import QAbstractItemView
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.layout.addWidget(self.table)