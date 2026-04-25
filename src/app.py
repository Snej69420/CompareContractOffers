import sys
import threading
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QScrollArea, QTabWidget, QFileDialog, QMessageBox,
)

from PySide6.QtCore import Qt, Signal, QObject, QTimer, QPoint
from PySide6.QtGui import QColor, QPalette

from src.Compare.loader import ContractLoader
from src.Compare.scoring import ScoringEngine

from src.UI.ManualMatching.MatchItem import MatchItem
from src.UI.ManualMatching.Cluster import Cluster
from src.UI.ManualMatching.Unmatched import Unmatched
from src.UI.DataModel.DocumentTab import DocumentTabWidget

class WorkerSignals(QObject):
    finished = Signal(object, object, object, object)
    error = Signal(str)


class AIWorker(threading.Thread):
    def __init__(self, path_a, path_b):
        super().__init__()
        self.path_a = path_a
        self.path_b = path_b
        self.signals = WorkerSignals()

    def run(self):
        try:
            loader = ContractLoader()
            contract_a = loader.load_excel(self.path_a)
            contract_b = loader.load_excel(self.path_b)

            matcher = ScoringEngine(threshold=0.4)
            # Expecting the updated tuple return from match()
            clusters, lookup, unmatched_a, unmatched_b = matcher.match(contract_a, contract_b)
            self.signals.finished.emit(clusters, lookup, unmatched_a, unmatched_b)
        except Exception as e:
            self.signals.error.emit(str(e))


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

        # --- 4. AI COMPARISON TAB (Your existing UI) ---
        self.comparison_tab = QWidget()
        self.comparison_layout = QVBoxLayout(self.comparison_tab)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.cluster_container = QWidget()
        self.cluster_layout = QVBoxLayout(self.cluster_container)
        self.cluster_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.cluster_container)

        # CRITICAL FIX: Add scroll area to the comparison tab's layout, NOT the main layout
        self.comparison_layout.addWidget(self.scroll_area)

        # Finally, register this tab into the Tab System
        self.tabs.addTab(self.comparison_tab, "AI Vergelijking")

        # --- 5. STATE VARIABLES ---
        self.path_a = None
        self.path_b = None
        self.global_score_lookup = {}
        self.cluster_count = 0

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

            # 3. Manage Tabs: Remove old document tabs if they exist
            while self.tabs.count() > 1:
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

        # Clear existing clusters
        for i in reversed(range(self.cluster_layout.count())):
            self.cluster_layout.itemAt(i).widget().setParent(None)

        # Automatically switch to the AI Compare Tab
        self.tabs.setCurrentWidget(self.comparison_tab)

        # Pass the dynamic paths to the worker
        self.worker = AIWorker(self.path_a, self.path_b)
        self.worker.signals.finished.connect(self.on_ai_finished)
        self.worker.signals.error.connect(self.on_ai_error)
        self.worker.start()

    def on_ai_finished(self, clusters: list[dict], lookup: dict, unmatched_a: list, unmatched_b: list):
        self.status_label.setText(f"Analyse voltooid. {len(clusters)} clusters gevonden.")
        self.run_btn.setEnabled(True)
        self.global_score_lookup = lookup
        self.cluster_count = 0

        clusters.sort(key=lambda x: x.get('cluster_score', 0.0), reverse=True)

        # 1. Render AI Clusters
        for cluster_data in clusters:
            self.cluster_count += 1
            self.auto_create_cluster(cluster_data, self.cluster_count)

        # 2. Add Centralized "New Cluster" Button
        self.add_cluster_btn = QPushButton("Nieuwe cluster toevoegen")
        self.add_cluster_btn.setStyleSheet(
            "background-color: #007bff; color: white; font-weight: bold; border-radius: 5px; padding: 10px; margin: 10px 50px;")
        self.add_cluster_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_cluster_btn.clicked.connect(self.create_cluster)
        self.cluster_layout.addWidget(self.add_cluster_btn)

        # 3. Render Parking Lot at the very bottom
        self.parking_lot = Unmatched(unmatched_a, unmatched_b)
        self.cluster_layout.addWidget(self.parking_lot)
        self.parking_lot.requestNeighborMove.connect(self.handle_neighbor_move)
        self.parking_lot.requestGlobalNavigation.connect(self.handle_global_navigation)
        self.parking_lot.list_a.currentItemChanged.connect(
            lambda current, previous, lw=self.parking_lot.list_a: self.auto_scroll_to_item(lw, current)
        )
        self.parking_lot.list_b.currentItemChanged.connect(
            lambda current, previous, lw=self.parking_lot.list_b: self.auto_scroll_to_item(lw, current)
        )
        self.parking_lot.update_parking_lot()

    def on_ai_error(self, err_msg: str):
        self.status_label.setText(f"Foutmelding: {err_msg}")
        self.run_btn.setEnabled(True)

    def auto_create_cluster(self, cluster_data: dict, index: int):
        widget = Cluster(cluster_data, index, self.global_score_lookup)
        widget.itemToParkingLot.connect(self.send_to_unmatched)
        widget.clusterRemoved.connect(self.remove_cluster)
        widget.requestNeighborMove.connect(self.handle_neighbor_move)
        widget.requestGlobalNavigation.connect(self.handle_global_navigation)

        widget.list_a.currentItemChanged.connect(
            lambda current, previous, lw=widget.list_a: self.auto_scroll_to_item(lw, current)
        )
        widget.list_b.currentItemChanged.connect(
            lambda current, previous, lw=widget.list_b: self.auto_scroll_to_item(lw, current)
        )

        # Insert above the 'Add Cluster' button if it exists, else append
        if hasattr(self, 'add_cluster_btn'):
            idx = self.cluster_layout.indexOf(self.add_cluster_btn)
            self.cluster_layout.insertWidget(idx, widget)
        else:
            self.cluster_layout.addWidget(widget)

    def create_cluster(self):
        self.cluster_count += 1
        empty_data = {'contract_a_items': [], 'contract_b_items': []}
        self.auto_create_cluster(empty_data, self.cluster_count)

        # Scroll down slightly to show the newly added cluster
        scroll_bar = self.scroll_area.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())

    def remove_cluster(self, widget: Cluster, items_a: list, items_b: list):
        if items_a or items_b:
            self.parking_lot.receive_items(items_a + items_b)

        # Safely destroy the UI element
        widget.deleteLater()
        self.cluster_layout.removeWidget(widget)

    def send_to_unmatched(self, match_item: MatchItem):
        self.parking_lot.receive_items([match_item])

    def handle_neighbor_move(self, source_widget, match_item, direction):
        # 1. Find where the source widget lives in the layout
        idx = self.cluster_layout.indexOf(source_widget)

        # 2. Calculate target index
        target_idx = idx - 1 if direction == "up" else idx + 1

        # 3. Boundary check (Can't go up from the top, or down past the bottom)
        if target_idx < 0 or target_idx >= self.cluster_layout.count():
            return

        target_widget = self.cluster_layout.itemAt(target_idx).widget()

        # Skip over the "Nieuw cluster toevoegen" button if we hit it
        if isinstance(target_widget, QPushButton):
            target_idx = target_idx - 1 if direction == "up" else target_idx + 1
            if target_idx < 0 or target_idx >= self.cluster_layout.count():
                return
            target_widget = self.cluster_layout.itemAt(target_idx).widget()

        # 4. Execute the transfer
        source_widget.remove_item_silently(match_item)

        # Wake up or sleep the item based on where it's landing
        if hasattr(target_widget, "update_parking_lot"):  # It's the Parking Lot
            match_item.is_parked = True
        else:  # It's a normal cluster
            match_item.is_parked = False

        target_widget.inject_item(match_item)
        target_widget.focus_on_item(match_item)

    def handle_global_navigation(self, source_widget, side, direction):
        idx = self.cluster_layout.indexOf(source_widget)
        target_idx = idx - 1 if direction == "up" else idx + 1

        if target_idx < 0 or target_idx >= self.cluster_layout.count():
            return

        target_widget = self.cluster_layout.itemAt(target_idx).widget()

        # Skip over the "Nieuw cluster toevoegen" button
        if isinstance(target_widget, QPushButton):
            target_idx = target_idx - 1 if direction == "up" else target_idx + 1
            if target_idx < 0 or target_idx >= self.cluster_layout.count():
                return
            target_widget = self.cluster_layout.itemAt(target_idx).widget()

        # Figure out which list to focus on
        target_list = target_widget.list_a if side == 'A' else target_widget.list_b

        target_list.setFocus()
        if target_list.count() > 0:
            if direction == "up":
                # Coming from below, select the bottom-most item
                target_list.setCurrentRow(target_list.count() - 1)
            else:
                # Coming from above, select the top-most item
                target_list.setCurrentRow(0)

    def auto_scroll_to_item(self, list_widget, item):
        """Defers the scroll math by 0ms so Qt has time to internally layout the list."""
        if not item:
            return
        # By using QTimer, we wait for Qt's event loop to physically draw the item first!
        QTimer.singleShot(0, lambda: self._perform_auto_scroll(list_widget, item))

    def _perform_auto_scroll(self, list_widget, item):
        if not item:
            return

        # 1. Force the list to ensure the item is fully rendered in its internal view
        list_widget.scrollToItem(item)

        # 2. Get the exact Y center of the item
        item_rect = list_widget.visualItemRect(item)

        # Safe fallback if the layout engine is still catching up
        if item_rect.isNull():
            return

        item_center_y = item_rect.center().y()

        # 3. Map this Y coordinate from the list's viewport directly up to our infinite scroll container
        pos_in_container = list_widget.viewport().mapTo(self.cluster_container, QPoint(0, int(item_center_y)))
        absolute_y = pos_in_container.y()

        # 4. Get scrollbar and viewport metrics
        scrollbar = self.scroll_area.verticalScrollBar()
        current_scroll = scrollbar.value()
        viewport_height = self.scroll_area.viewport().height()

        # 5. Define the absolute coordinates of our "Deadzone" (The middle third)
        deadzone_top = current_scroll + (viewport_height / 3)
        deadzone_bottom = current_scroll + (2 * viewport_height / 3)

        # 6. Push the scrollbar only if the item's absolute Y falls outside the deadzone
        if absolute_y < deadzone_top:
            # Item is too high up, pull the "camera" up
            scrollbar.setValue(int(absolute_y - (viewport_height / 3)))

        elif absolute_y > deadzone_bottom:
            # Item is too low down, push the "camera" down
            scrollbar.setValue(int(absolute_y - (2 * viewport_height / 3)))


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