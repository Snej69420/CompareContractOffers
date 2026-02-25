import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QPushButton, QFileDialog, QTableView, QTabWidget, QHBoxLayout,
    QFormLayout, QGroupBox, QHeaderView, QLabel, QSplitter,
    QAbstractItemView, QMessageBox, QSizePolicy,
)
from PySide6.QtCore import Qt, QAbstractTableModel
from PySide6.QtGui import QColor, QBrush

from DataHandler import DataHandler


# --- Custom Table Model for displaying Pandas Data ---
class PandasModel(QAbstractTableModel):
    def __init__(self, data):
        super().__init__()
        self._data = data

    def rowCount(self, parent=None):
        return self._data.shape[0]

    def columnCount(self, parent=None):
        return self._data.shape[1]

    def data(self, index, role=Qt.ItemDataRole):
        if not index.isValid():
            return None

        value = self._data.iloc[index.row(), index.column()]

        # Text Display
        if role == Qt.DisplayRole:
            if isinstance(value, (int, float)):
                # Format currency columns
                col_name = self._data.columns[index.column()]
                if "Prijs" in col_name:
                    return f"€ {value:,.2f}"
                return f"{value:.2f}" if isinstance(value, float) else str(value)
            return str(value)

        # Text Alignment (Numbers right, Text left)
        if role == Qt.TextAlignmentRole:
            if isinstance(value, (int, float)):
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        return None

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._data.columns[section])
            if orientation == Qt.Vertical:
                return str(section + 1)
        return None


# --- Widget to Recreate the Template Layout ---
class ContractWidget(QWidget):
    def __init__(self, contract_dict):
        super().__init__()

        self.metadata = contract_dict['metadata']
        self.df = contract_dict['data']

        self._setup_ui()
        self._merge_cells()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # 1. TOP SECTION: Metadata (Replicating "Werf Info")
        meta_group = QGroupBox("Werf Informatie")
        meta_layout = QFormLayout()

        # Style for labels to look like the Excel header
        label_style = "font-weight: bold;"

        # Specific keys we want to show first if they exist
        priority_keys = ["Werf Naam", "Werf Status", "Straatnaam en Nummer", "Postcode en Gemeente"]

        # Add priority keys first
        for key in priority_keys:
            if key in self.metadata:
                lbl_key = QLabel(key + ":")
                lbl_key.setStyleSheet(label_style)
                meta_layout.addRow(lbl_key, QLabel(str(self.metadata[key])))

        # Add remaining keys (excluding the ones we just added)
        for key, val in self.metadata.items():
            if key not in priority_keys and key != "Bestandsnaam":
                lbl_key = QLabel(key + ":")
                lbl_key.setStyleSheet(label_style)
                meta_layout.addRow(lbl_key, QLabel(str(val)))

        meta_group.setLayout(meta_layout)

        # 2. BOTTOM SECTION: Data Table
        self.table_view = QTableView()
        self.model = PandasModel(self.df)
        self.table_view.setModel(self.model)

        # Table Styling
        self.table_view.setAlternatingRowColors(True)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)

        # Layout Assembly
        # We use a splitter so user can resize the meta section vs table section
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(meta_group)
        splitter.addWidget(self.table_view)
        splitter.setStretchFactor(1, 1)  # Give table more space

        main_layout.addWidget(splitter)

    def _merge_cells(self):
        """Merges consecutive rows in the 'Categorie' column."""
        if 'Categorie' not in self.df.columns:
            return

        col_idx = self.df.columns.get_loc('Categorie')

        # Iterate over rows to find spans
        start_row = 0
        if self.df.empty: return

        current_val = self.df.iloc[0, col_idx]

        for i in range(1, len(self.df)):
            val = self.df.iloc[i, col_idx]
            if val != current_val:
                # Apply span for the previous block
                span_size = i - start_row
                if span_size > 1:
                    self.table_view.setSpan(start_row, col_idx, span_size, 1)

                # Reset
                current_val = val
                start_row = i

        # Apply final span
        span_size = len(self.df) - start_row
        if span_size > 1:
            self.table_view.setSpan(start_row, col_idx, span_size, 1)


# --- Main Window ---
class ContractApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Offerte Vergelijking - Native View")
        self.resize(1200, 800)

        self.data_handler = DataHandler()
        self._setup_ui()

        self.loaded_contracts = []

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)

        # Toolbar / Buttons
        btn_layout = QHBoxLayout()
        self.btn_load = QPushButton("📂 Laad Offertes")
        self.btn_load.setStyleSheet("padding: 8px; font-size: 14px; font-weight: bold;")
        self.btn_load.clicked.connect(self.load_files)

        self.btn_export = QPushButton("💾 Exporteer Overzicht naar Excel")
        self.btn_export.setStyleSheet("padding: 10px; font-weight: bold; color: green;")
        self.btn_export.clicked.connect(self.export_data)
        self.btn_export.setEnabled(False)  # Disabled until data is loaded

        btn_layout.addWidget(self.btn_load)
        btn_layout.addWidget(self.btn_export)

        # Tab Widget to hold multiple contracts
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)

        layout.addLayout(btn_layout)
        layout.addWidget(self.tabs)

    def load_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Selecteer Offertes",
            "",
            "Excel Files (*.xlsx *.xls)"
        )

        if not files:
            return

        contracts = self.data_handler.load_files(files)
        self.loaded_contracts.extend(contracts)

        for contract in contracts:
            # Create a dedicated tab/page for this contract
            page = ContractWidget(contract)
            tab_name = contract['metadata'].get('Bestandsnaam', 'Unknown')
            self.tabs.addTab(page, tab_name)

        if self.loaded_contracts:
            self.btn_export.setEnabled(True)

    def close_tab(self, index):
        if 0 <= index < len(self.loaded_contracts):
            del self.loaded_contracts[index]

        self.tabs.removeTab(index)

        if not self.loaded_contracts:
            self.btn_export.setEnabled(False)

    def export_data(self):
        if not self.loaded_contracts:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Comparison", "Offerte_Vergelijking.xlsx", "Excel Files (*.xlsx)"
        )

        if not file_path:
            return

        naam_excel_width = None

        # Try to get width from the currently visible tab
        current_widget = self.tabs.currentWidget()
        if current_widget and isinstance(current_widget, ContractWidget):
            try:
                # Find the "Naam" column index in the model
                df_cols = current_widget.df.columns.tolist()
                if "Naam" in df_cols:
                    col_idx = df_cols.index("Naam")

                    # Get pixel width from the view
                    px_width = current_widget.table_view.columnWidth(col_idx)

                    # Convert to Excel units (approx 1 char ~ 7 pixels for default font)
                    naam_excel_width = int(px_width / 7)
            except Exception as e:
                print(f"Could not extract column width: {e}")

        try:
            self.data_handler.export_contracts(self.loaded_contracts, file_path, naam_excel_width)
            QMessageBox.information(self, "Success", f"Export saved to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export:\n{str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ContractApp()
    window.show()
    sys.exit(app.exec())