import sys
from pathlib import Path
import pandas as pd

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QScrollArea, QTabWidget, QFileDialog, QMessageBox,
    QTableView, QHeaderView
)

from PySide6.QtCore import Qt, Signal, QObject, QTimer, QPoint
from PySide6.QtGui import QColor, QPalette

from src.AIWorker import AIWorker

from src.Compare.loader import ContractLoader
from src.Compare.scoring import ScoringEngine

from src.UI.ManualMatching.MatchItem import MatchItem
from src.UI.ManualMatching.Cluster import Cluster
from src.UI.ManualMatching.Unmatched import Unmatched

from src.UI.DataModel.DataTable import DataTableModel
from src.UI.DataModel.DocumentTab import DocumentTabWidget
from src.UI.DataModel.ReportGenerator import ReportGenerator
from src.UI.DataModel.ComparisonTab import ComparisonTab
from src.UI.DataModel.PreviewTab import PreviewTab

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Offertevergelijker")
        self.resize(1000, 800)

        # --- 1. MAIN WINDOW SETUP ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)

        # --- 2. TOP BAR CONTROLS ---
        top_bar = QHBoxLayout()

        self.load_btn = QPushButton("Offertes inladen 📂")
        self.load_btn.clicked.connect(self.load_documents)

        self.run_btn = QPushButton("Start analyse")
        self.run_btn.setStyleSheet("background-color: #007bff; color: white; font-weight: bold; padding: 8px;")
        self.run_btn.clicked.connect(self.run_comparison)

        self.status_label = QLabel("Klaar voor gebruik.")
        self.status_label.setStyleSheet("color: black;")

        top_bar.addWidget(self.load_btn)
        top_bar.addWidget(self.run_btn)
        top_bar.addWidget(self.status_label)
        top_bar.addStretch()

        self.main_layout.addLayout(top_bar)

        # --- 3. MASTER TAB SYSTEM ---
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)

        # --- 4. AI COMPARISON TAB ---
        self.comparison_tab = ComparisonTab()
        self.tabs.addTab(self.comparison_tab, "AI Vergelijking")

        # --- 5. REPORT PREVIEW TAB ---
        self.preview_tab = PreviewTab()
        self.tabs.addTab(self.preview_tab, "Rapport Voorbeeld")

        # --- 6. EVENT ROUTING ---
        # When ComparisonTab changes, tell MainWindow to push data to PreviewTab
        self.comparison_tab.stateChanged.connect(self.on_comparison_state_changed)
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # --- 7. STATE VARIABLES ---
        self.path_a = None
        self.path_b = None
        self.global_score_lookup = {}

        self.tabs.currentChanged.connect(self.on_tab_changed)

    def on_tab_changed(self, index):
        """Notifies the PreviewTab to fix its UI when it becomes visible."""
        # Check if the newly opened tab is the Preview Tab
        if self.tabs.widget(index) == self.preview_tab:
            self.preview_tab.force_resize()

    def on_comparison_state_changed(self):
        """Passes data from Comparison Tab -> Preview Tab whenever items move."""
        if hasattr(self, 'df_a') and hasattr(self, 'df_b'):
            clusters, unmatched = self.comparison_tab.gather_current_state()
            self.preview_tab.request_update(clusters, unmatched, self.df_a, self.df_b)

    def load_documents(self):
        # 1. Ask for Document A
        path_a, _ = QFileDialog.getOpenFileName(self, "Selecteer Offerte A", "", "Excel Files (*.xlsx *.xls)")
        if not path_a: return  # User cancelled

        # 2. Ask for Document B
        path_b, _ = QFileDialog.getOpenFileName(self, "Selecteer Offerte B", "", "Excel Files (*.xlsx *.xls)")
        if not path_b: return

        self.status_label.setText("Bestanden inladen...")
        QApplication.processEvents()  # Force UI to update

        try:
            self.path_a = Path(path_a)
            self.path_b = Path(path_b)

            loader = ContractLoader()
            df_a = loader.load_excel(self.path_a)
            df_b = loader.load_excel(self.path_b)

            self.df_a = df_a
            self.df_b = df_b

            # 3. Manage Tabs: Remove old document tabs if they exist
            while self.tabs.count() > 2:
                self.tabs.removeTab(0)

            # 4. Create and insert the new Document Tabs
            tab_a = DocumentTabWidget(df_a, self.path_a.name)
            tab_b = DocumentTabWidget(df_b, self.path_b.name)

            self.tabs.insertTab(0, tab_a, "📄 Offerte A")
            self.tabs.insertTab(1, tab_b, "📄 Offerte B")

            # Switch to first tab so user sees the loaded data
            self.tabs.setCurrentIndex(0)
            self.status_label.setText(f"Klaar voor gebruik. ({len(df_a)} en {len(df_b)} items)")

        except Exception as e:
            QMessageBox.critical(self, "Laadfout", f"Fout bij inladen van bestanden:\n{str(e)}")
            self.status_label.setText("Fout bij inladen.")

    def run_comparison(self):
        if not self.path_a or not self.path_b:
            QMessageBox.warning(self, "Geen bestanden", "Laad eerst twee offertes in.")
            return

        self.status_label.setText("Bezig met analyseren... Even geduld.")
        self.run_btn.setEnabled(False)

        self.tabs.setCurrentWidget(self.comparison_tab)

        self.worker = AIWorker(self.path_a, self.path_b)
        self.worker.signals.finished.connect(self.on_ai_finished)
        self.worker.signals.error.connect(self.on_ai_error)
        self.worker.start()

    def on_ai_finished(self, clusters: list[dict], lookup: dict, unmatched_a: list, unmatched_b: list):
        self.status_label.setText(f"Analyse voltooid. {len(clusters)} clusters gevonden.")
        self.run_btn.setEnabled(True)

        # Hand the massive data payload over to the new Tab widget
        self.comparison_tab.populate_from_ai(clusters, lookup, unmatched_a, unmatched_b)

    def on_ai_error(self, err_msg: str):
        self.status_label.setText(f"Foutmelding: {err_msg}")
        self.run_btn.setEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # FORCING LIGHT MODE
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.black)
    app.setPalette(palette)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())