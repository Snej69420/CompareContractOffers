import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QFileDialog, QMessageBox
)

from PySide6.QtCore import Qt, QStandardPaths
from PySide6.QtGui import QColor, QPalette

from src.UI.Utils import set_reproducibility
from src.AIWorker import AIWorker

from src.Backend.loader import ContractLoader
from src.UI.DataProcessing.DataNormaliser import DataNormaliser
from src.UI.DataProcessing.ExcelExporter import ExcelExporter
from src.UI.Controls import TopBarControls
from src.UI.TabManager import MainTabWidget

from src.UI.Settings import settings

set_reproducibility(42)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Offertevergelijker")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)

        # --- 1. UI COMPONENTS ---
        self.top_bar = TopBarControls()
        self.top_bar.exportRequested.connect(self._handle_excel_export)
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
        downloads = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Selecteer Offertes", downloads, "Excel Files (*.xlsx *.xls)")
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
        self.top_bar.set_export_enabled(False)

        self.tab_manager.setCurrentWidget(self.tab_manager.comparison_tab)

        # Pass the entire N-document dictionary directly to the worker!
        self.worker = AIWorker(self.loaded_documents)
        self.worker.signals.finished.connect(self.on_ai_finished)
        self.worker.signals.error.connect(self.on_ai_error)
        self.worker.start()

    def on_ai_finished(self, clusters: list[dict], lookup: dict, unmatched_dict: dict):
        self.top_bar.set_status(f"Analyse voltooid. {len(clusters)} clusters gevonden.")
        self.top_bar.set_analyze_enabled(True)
        self.top_bar.set_export_enabled(True)

        #  Extract dynamic document names straight from the dictionary keys
        doc_keys = list(unmatched_dict.keys())

        #  Pass them to the N-document generalized ComparisonTab
        self.tab_manager.comparison_tab.populate_from_ai(doc_keys, clusters, lookup, unmatched_dict)

    def on_ai_error(self, err_msg: str):
        self.top_bar.set_status(f"Foutmelding: {err_msg}")
        self.top_bar.set_analyze_enabled(True)



    def _handle_excel_export(self):
        # 1. Ask the user where to save the file
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Exporteer Excel",
            "Offerte Vergelijking.xlsx",
            "Excel Files (*.xlsx)"
        )

        # If the user cancels the save dialog, abort.
        if not filepath:
            return

        clusters, unmatched = self.tab_manager.comparison_tab.gather_current_state()

        contract_names = {}
        for path, df in self.loaded_documents.items():
            contract_names[path.name] = df.attrs.get('contractor', path.stem)

        # Normalize directly before Excel Export
        normalizer = DataNormaliser(list(contract_names.keys()))
        norm_clusters, norm_unmatched = normalizer.normalize(clusters, unmatched)

        try:
            exporter = ExcelExporter(contract_names)
            exporter.export(norm_clusters, norm_unmatched, filepath=filepath)

            self.top_bar.set_status(f"Succesvol geëxporteerd naar {Path(filepath).name}")
            QMessageBox.information(self, "Export Succesvol", f"Het bestand is opgeslagen in:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Export Fout", f"Er is een fout opgetreden bij het exporteren:\n{str(e)}")

    def on_comparison_state_changed(self):
        if len(self.loaded_documents) >= 2:
            # 1. Gather raw data
            clusters, unmatched = self.tab_manager.comparison_tab.gather_current_state()

            # 2. Normalize missing data/slots
            keys = [path.name for path in self.loaded_documents.keys()]  # Or however doc_keys are tracked
            normalizer = DataNormaliser(keys)
            norm_clusters, norm_unmatched = normalizer.normalize(clusters, unmatched)

            # 3. Pass clean data downwards
            self.tab_manager.preview_tab.request_update(norm_clusters, norm_unmatched, self.loaded_documents)

if __name__ == "__main__":
    app = QApplication(sys.argv)

    def update_global_font(new_size):
        # Grab the current global font, change its size, and reapply it
        global_font = app.font()
        global_font.setPointSize(new_size)
        app.setFont(global_font)
    settings.fontSizeChanged.connect(update_global_font)

    update_global_font(settings.font_size)

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
    window.resize(1200, 800)
    window.showMaximized()
    sys.exit(app.exec())