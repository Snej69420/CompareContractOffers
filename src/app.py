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
from src.UI.Controls import TopBarControls
from src.UI.TabManager import MainTabWidget

from src.UI.DataModel.DocumentTab import DocumentTabWidget
from src.UI.DataModel.ComparisonTab import ComparisonTab
from src.UI.DataModel.PreviewTab import PreviewTab

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Offertevergelijker")
        self.resize(1000, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)

        # --- 1. UI COMPONENTS ---
        self.top_bar = TopBarControls()
        self.tab_manager = MainTabWidget()

        self.main_layout.addWidget(self.top_bar)
        self.main_layout.addWidget(self.tab_manager)

        # --- 2. STATE TRACKING ---
        # Future-proofed for N-documents: { Path: DataFrame }
        self.loaded_documents = {}

        # --- 3. EVENT ROUTING ---
        self.top_bar.loadRequested.connect(self.load_documents)
        self.top_bar.analyzeRequested.connect(self.run_comparison)

        self.tab_manager.documentUnloaded.connect(self.unload_document)
        self.tab_manager.stateChanged.connect(self.on_comparison_state_changed)

    def load_documents(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Selecteer Offertes", "", "Excel Files (*.xlsx *.xls)")
        if not file_paths:
            return

        self.top_bar.set_status("Bestanden inladen...")
        QApplication.processEvents()

        loader = ContractLoader()
        errors = []

        for file_path in file_paths:
            path = Path(file_path)
            try:
                # Prevent unnecessary reloading
                if path not in self.loaded_documents:
                    df = loader.load_excel(path)
                    self.loaded_documents[path] = df
                    self.tab_manager.add_document_tab(df, path)
            except Exception as e:
                errors.append(f"{path.name}: {str(e)}")

        if errors:
            err_msg = "\n".join(errors)
            QMessageBox.warning(self, "Fout bij inladen",
                                f"Enkele bestanden konden niet geladen worden:\n{err_msg}")

        self.top_bar.set_status(f"Klaar voor gebruik. ({len(self.loaded_documents)} offertes geladen)")

    def unload_document(self, path: Path):
        """Called when a user closes a document tab."""
        if path in self.loaded_documents:
            del self.loaded_documents[path]
            self.top_bar.set_status(f"Klaar voor gebruik. ({len(self.loaded_documents)} offertes geladen)")

    def run_comparison(self):
        if len(self.loaded_documents) < 2:
            QMessageBox.warning(self, "Geen bestanden", "Laad minstens twee offertes in.")
            return

        self.top_bar.set_status("Bezig met analyseren... Even geduld.")
        self.top_bar.set_analyze_enabled(False)

        self.tab_manager.setCurrentWidget(self.tab_manager.comparison_tab)

        # Temporary bridge: Pass the first two documents to the current AIWorker.
        # When your backend supports N docs, you can just pass the whole dictionary/list!
        paths = list(self.loaded_documents.keys())
        self.worker = AIWorker(paths[0], paths[1])
        self.worker.signals.finished.connect(self.on_ai_finished)
        self.worker.signals.error.connect(self.on_ai_error)
        self.worker.start()

    def on_ai_finished(self, clusters: list[dict], lookup: dict, unmatched_a: list, unmatched_b: list):
        self.top_bar.set_status(f"Analyse voltooid. {len(clusters)} clusters gevonden.")
        self.top_bar.set_analyze_enabled(True)

        # 1. Grab the keys for the two currently processed documents
        paths = list(self.loaded_documents.keys())
        doc_keys = [paths[0].name, paths[1].name]

        # 2. Package the unmatched lists into the new generalized dictionary
        unmatched_dict = {
            doc_keys[0]: unmatched_a,
            doc_keys[1]: unmatched_b
        }

        # 3. Pass all arguments in the exact correct order!
        self.tab_manager.comparison_tab.populate_from_ai(doc_keys, clusters, lookup, unmatched_dict)

    def on_ai_error(self, err_msg: str):
        self.top_bar.set_status(f"Foutmelding: {err_msg}")
        self.top_bar.set_analyze_enabled(True)

    def on_comparison_state_changed(self):
        """Passes data to Preview Tab whenever items move."""
        if len(self.loaded_documents) >= 2:
            clusters, unmatched = self.tab_manager.comparison_tab.gather_current_state()
            # Pass the entire dictionary of N-documents
            self.tab_manager.preview_tab.request_update(clusters, unmatched, self.loaded_documents)


if __name__ == "__main__":
    app = QApplication(sys.argv)

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