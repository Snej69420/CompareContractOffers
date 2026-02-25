import sys
import copy
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QPushButton, QFileDialog, QTableView, QTabWidget, QHBoxLayout,
    QFormLayout, QGroupBox, QHeaderView, QLabel, QSplitter,
    QAbstractItemView, QMessageBox, QSizePolicy,
)
from PySide6.QtCore import Qt, QAbstractTableModel
from PySide6.QtGui import QColor, QBrush

from DataHandler import DataHandler

# Import our new AI & UI Classes
from Matcher import ContractMatcher
from UserMatching import MappingTab


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

        # 1. TOP SECTION: Metadata
        meta_group = QGroupBox("Werf Informatie")
        meta_layout = QFormLayout()

        label_style = "font-weight: bold;"
        priority_keys = ["Werf Naam", "Werf Status", "Straatnaam en Nummer", "Postcode en Gemeente"]

        for key in priority_keys:
            if key in self.metadata:
                lbl_key = QLabel(key + ":")
                lbl_key.setStyleSheet(label_style)
                meta_layout.addRow(lbl_key, QLabel(str(self.metadata[key])))

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

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(meta_group)
        splitter.addWidget(self.table_view)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

    def _merge_cells(self):
        if 'Categorie' not in self.df.columns:
            return

        col_idx = self.df.columns.get_loc('Categorie')
        start_row = 0
        if self.df.empty: return

        current_val = self.df.iloc[0, col_idx]

        for i in range(1, len(self.df)):
            val = self.df.iloc[i, col_idx]
            if val != current_val:
                span_size = i - start_row
                if span_size > 1:
                    self.table_view.setSpan(start_row, col_idx, span_size, 1)
                current_val = val
                start_row = i

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
        self.loaded_contracts = []

        self._setup_ui()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Toolbar / Buttons
        btn_layout = QHBoxLayout()

        self.btn_load = QPushButton("📂 Laad Offertes")
        self.btn_load.setStyleSheet("padding: 8px; font-size: 14px; font-weight: bold;")
        self.btn_load.clicked.connect(self.load_files)

        self.btn_map = QPushButton("🤖 Vergelijk Offertes (AI)")
        self.btn_map.setStyleSheet("padding: 8px; font-size: 14px; font-weight: bold; color: #0056b3;")
        self.btn_map.clicked.connect(self.generate_mapping)
        self.btn_map.setEnabled(False)

        self.btn_export = QPushButton("💾 Exporteer Overzicht naar Excel")
        self.btn_export.setStyleSheet("padding: 10px; font-weight: bold; color: green;")
        self.btn_export.clicked.connect(self.export_data)
        self.btn_export.setEnabled(False)

        btn_layout.addWidget(self.btn_load)
        btn_layout.addWidget(self.btn_map)
        btn_layout.addWidget(self.btn_export)

        # Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)

        layout.addLayout(btn_layout)
        layout.addWidget(self.tabs)

    def load_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Selecteer Offertes", "", "Excel Files (*.xlsx *.xls)"
        )

        if not files: return

        contracts = self.data_handler.load_files(files)
        self.loaded_contracts.extend(contracts)

        for contract in contracts:
            page = ContractWidget(contract)
            tab_name = contract['metadata'].get('Bestandsnaam', 'Unknown')
            self.tabs.addTab(page, tab_name)

        self._update_button_states()

    def close_tab(self, index):
        # Only delete from memory if it's one of the contract tabs (not the mapping tab)
        tab_name = self.tabs.tabText(index)

        if tab_name != "⚙️ AI Mapping" and 0 <= index < len(self.loaded_contracts):
            del self.loaded_contracts[index]

        self.tabs.removeTab(index)
        self._update_button_states()

    def _update_button_states(self):
        has_data = len(self.loaded_contracts) > 0
        has_multiple = len(self.loaded_contracts) >= 2

        self.btn_export.setEnabled(has_data)
        self.btn_map.setEnabled(has_multiple)

    def generate_mapping(self):
        """Runs the semantic matcher and opens the Mapping Tab."""
        if len(self.loaded_contracts) < 2: return

        # Remove existing mapping tab if present
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == "⚙️ AI Mapping":
                self.tabs.removeTab(i)
                break

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            matcher = ContractMatcher()
            df_master = self.loaded_contracts[0]['data']
            master_dict = df_master.groupby('Categorie', sort=False)['Naam'].apply(lambda x: list(x.unique())).to_dict()

            target_contracts = {}
            for i in range(1, len(self.loaded_contracts)):
                # We use strict naming so we can map it back during export
                contract_name = f"Contract {i + 1}"
                df_target = self.loaded_contracts[i]['data']

                t_dict = df_target.groupby('Categorie', sort=False)['Naam'].apply(lambda x: list(x.unique())).to_dict()
                ai_results = matcher.match_contracts(df_master, df_target)

                target_contracts[contract_name] = {
                    'data': t_dict,
                    'ai': ai_results
                }

            # Create and add the UI Tab
            self.mapping_tab_widget = MappingTab(master_dict, target_contracts)
            tab_idx = self.tabs.addTab(self.mapping_tab_widget, "⚙️ AI Mapping")
            self.tabs.setCurrentIndex(tab_idx)

        except Exception as e:
            QMessageBox.critical(self, "AI Fout", f"Het genereren van de AI mapping is mislukt:\n{str(e)}")
        finally:
            QApplication.restoreOverrideCursor()

    def export_data(self):
        """Reads mapping, aligns the dataframes via hidden columns, and triggers Excel write."""
        if not self.loaded_contracts: return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Comparison", "Offerte_Vergelijking.xlsx", "Excel Files (*.xlsx)"
        )
        if not file_path: return

        export_contracts = copy.deepcopy(self.loaded_contracts)

        # 1. Create hidden alignment columns for ALL contracts
        for c in export_contracts:
            c['data']['Align_Cat'] = c['data']['Categorie']
            c['data']['Align_Naam'] = c['data']['Naam']

        mapping_tab = None
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == "⚙️ AI Mapping":
                mapping_tab = self.tabs.widget(i)
                break

        if mapping_tab:
            final_mapping = mapping_tab.extract_final_mapping()

            for i in range(1, len(export_contracts)):
                contract_name = f"Contract {i + 1}"
                if contract_name not in final_mapping: continue

                df = export_contracts[i]['data'].copy()
                mapping_for_this_contract = final_mapping[contract_name]

                row_map = {}
                cat_map = {}

                for m_cat, map_info in mapping_for_this_contract.items():
                    t_cat = map_info.get('target_cat')
                    if not t_cat: continue

                    t_cat_clean = str(t_cat).strip()
                    m_cat_clean = str(m_cat).strip()
                    cat_map[t_cat_clean] = m_cat_clean

                    for m_item, t_item in map_info.get('items', {}).items():
                        if t_item:
                            row_map[(t_cat_clean, str(t_item).strip())] = (m_cat_clean, str(m_item).strip())

                # 2. Apply mapping strictly to the Alignment columns (Leave original Categorie/Naam alone)
                new_cats = []
                new_items = []

                for _, row in df.iterrows():
                    c = str(row['Categorie']).strip()
                    n = str(row['Naam']).strip()

                    if (c, n) in row_map:
                        new_c, new_n = row_map[(c, n)]
                        new_cats.append(new_c)
                        new_items.append(new_n)
                    else:
                        new_cats.append(cat_map.get(c, c))
                        new_items.append(n)

                df['Align_Cat'] = new_cats
                df['Align_Naam'] = new_items
                export_contracts[i]['data'] = df

        # Get visual column width for 'Naam' if possible
        naam_excel_width = None
        current_widget = self.tabs.currentWidget()
        if isinstance(current_widget, ContractWidget):
            try:
                df_cols = current_widget.df.columns.tolist()
                if "Naam" in df_cols:
                    col_idx = df_cols.index("Naam")
                    naam_excel_width = int(current_widget.table_view.columnWidth(col_idx) / 7)
            except Exception as e:
                pass

        try:
            self.data_handler.export_contracts(export_contracts, file_path, naam_excel_width)
            QMessageBox.information(self, "Success", f"Export saved to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export:\n{str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ContractApp()
    window.show()
    sys.exit(app.exec())