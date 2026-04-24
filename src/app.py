import sys
import threading
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QScrollArea, QListWidget, QListWidgetItem,
    QFrame
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor, QPalette

from src.Contracts.loader import ContractLoader
from src.Contracts.scoring import ScoringEngine


# ==========================================
# 1. DATA MODELS
# ==========================================
class MatchItem:
    def __init__(self, raw_data: dict, original_id: int, side: str):
        self.raw_data = raw_data
        self.name = raw_data.get('Naam', 'Unknown')
        self.qty = raw_data.get('Aantal', 0)
        self.unit = raw_data.get('Eenheid', '')
        self.original_id = original_id
        self.side = side  # 'A' or 'B'
        self.current_score = 0.0  # Will be updated dynamically

    def display_text(self):
        return f"{self.name} ({self.qty} {self.unit})"


# ==========================================
# 2. CUSTOM WIDGETS
# ==========================================
class DraggableItemList(QListWidget):
    itemDropped = Signal()

    def __init__(self, side: str):
        super().__init__()
        self.side = side
        self.setDragDropMode(QListWidget.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setAcceptDrops(True)
        self.setMinimumHeight(80)
        self.setStyleSheet("color: black; background-color: white;")

    def sort_by_score(self):
        items = []
        while self.count() > 0:
            items.append(self.takeItem(0))

        items.sort(key=lambda li: li.data(Qt.ItemDataRole.UserRole).current_score, reverse=True)
        for li in items:
            self.addItem(li)

    def dragEnterEvent(self, event):
        source = event.source()
        if isinstance(source, DraggableItemList) and source.side == self.side:
            super().dragEnterEvent(event)
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        source = event.source()
        if isinstance(source, DraggableItemList) and source.side == self.side:
            super().dragMoveEvent(event)
        else:
            event.ignore()

    # ----------------------------------------------

    def dropEvent(self, event):
        source = event.source()
        if isinstance(source, DraggableItemList) and source.side == self.side:
            super().dropEvent(event)
            self.itemDropped.emit()

            if source != self:
                source.itemDropped.emit()
        else:
            event.ignore()

    def get_items(self) -> list[MatchItem]:
        items = []
        for i in range(self.count()):
            items.append(self.item(i).data(Qt.ItemDataRole.UserRole))
        return items

    def update_visuals(self):
        for i in range(self.count()):
            list_item = self.item(i)
            match_item = list_item.data(Qt.ItemDataRole.UserRole)

            color = self._get_color_for_score(match_item.current_score)
            list_item.setBackground(color)
            list_item.setToolTip(f"Avg Pair Confidence: {match_item.current_score:.2f}\nDrag to re-assign.")

    def _get_color_for_score(self, score: float) -> QColor:
        if score >= 0.80:
            return QColor(200, 255, 200)  # Light Green
        elif score >= 0.50:
            return QColor(255, 250, 200)  # Light Yellow
        else:
            return QColor(255, 200, 200)  # Light Red


class ClusterWidget(QFrame):
    def __init__(self, cluster_data: dict, index: int, score_lookup: dict):
        super().__init__()
        self.score_lookup = score_lookup
        self.is_approved = False
        self.cluster_index = index  # --- NEW: Store index to keep the title string clean ---

        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet(
            "ClusterWidget { background-color: #f9f9f9; border: 1px solid #ddd; border-radius: 5px; margin: 5px; }")

        self.layout = QVBoxLayout(self)

        header_layout = QHBoxLayout()
        # --- NEW: Initial title will be overwritten almost immediately by recalculate_scores ---
        self.title_label = QLabel(f"📦 Cluster {self.cluster_index}")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: black;")

        self.approve_btn = QPushButton("Approve ✓")
        self.approve_btn.setStyleSheet(
            "background-color: #d4edda; color: black; border: 1px solid #c3e6cb; border-radius: 3px; padding: 5px;")
        self.approve_btn.clicked.connect(self.toggle_approve)

        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.approve_btn)
        self.layout.addLayout(header_layout)

        self.lists_widget = QWidget()
        lists_layout = QHBoxLayout(self.lists_widget)

        self.list_a = DraggableItemList("A")
        self.list_b = DraggableItemList("B")

        self.list_a.itemDropped.connect(self.recalculate_scores)
        self.list_b.itemDropped.connect(self.recalculate_scores)

        lists_layout.addWidget(self.list_a)
        lists_layout.addWidget(self.list_b)
        self.layout.addWidget(self.lists_widget)

        self._populate_initial(cluster_data)
        self.recalculate_scores()

    def _populate_initial(self, cluster_data: dict):
        for raw_a in cluster_data.get('contract_a_items', []):
            item = MatchItem(raw_a, raw_a.get('id', -1), 'A')
            li = QListWidgetItem(item.display_text())
            li.setData(Qt.ItemDataRole.UserRole, item)
            self.list_a.addItem(li)

        for raw_b in cluster_data.get('contract_b_items', []):
            item = MatchItem(raw_b, raw_b.get('id', -1), 'B')
            li = QListWidgetItem(item.display_text())
            li.setData(Qt.ItemDataRole.UserRole, item)
            self.list_b.addItem(li)

    def recalculate_scores(self):
        items_a = self.list_a.get_items()
        items_b = self.list_b.get_items()

        cluster_total_score = 0.0
        total_pairs = 0

        for a_item in items_a:
            item_score = 0.0
            for b_item in items_b:
                score = self.score_lookup.get((a_item.original_id, b_item.original_id), 0.0)
                item_score += score
                cluster_total_score += score
                total_pairs += 1

            a_item.current_score = (item_score / len(items_b)) if items_b else 0.0

        for b_item in items_b:
            item_score = 0.0
            for a_item in items_a:
                score = self.score_lookup.get((a_item.original_id, b_item.original_id), 0.0)
                item_score += score

            b_item.current_score = (item_score / len(items_a)) if items_a else 0.0

        avg_cluster_score = (cluster_total_score / total_pairs) if total_pairs > 0 else 0.0

        # --- NEW: Formats the label so the Cluster Number stays visible alongside the score ---
        self.title_label.setText(f"📦 Cluster {self.cluster_index} | Confidence: {avg_cluster_score:.2f}")

        self.list_a.update_visuals()
        self.list_b.update_visuals()

        self.list_a.sort_by_score()
        self.list_b.sort_by_score()

    def toggle_approve(self):
        self.is_approved = not self.is_approved
        if self.is_approved:
            self.lists_widget.setVisible(False)
            self.approve_btn.setText("Edit ✎")
            self.setStyleSheet(
                "ClusterWidget { background-color: #e2f0e5; border: 1px solid #c3e6cb; border-radius: 5px; margin: 5px; }")
        else:
            self.lists_widget.setVisible(True)
            self.approve_btn.setText("Approve ✓")
            self.setStyleSheet(
                "ClusterWidget { background-color: #f9f9f9; border: 1px solid #ddd; border-radius: 5px; margin: 5px; }")


# ==========================================
# 3. BACKGROUND WORKER & MAIN WINDOW
# ==========================================
class WorkerSignals(QObject):
    finished = Signal(object, object)
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
            clusters, lookup = matcher.match(contract_a, contract_b)

            self.signals.finished.emit(clusters, lookup)
        except Exception as e:
            self.signals.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Contract AI Comparer")
        self.resize(1000, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)

        top_bar = QHBoxLayout()
        self.load_btn = QPushButton("Load Documents (Mocked)")
        self.run_btn = QPushButton("Run AI Comparison")
        self.run_btn.setStyleSheet("background-color: #007bff; color: white; font-weight: bold; padding: 8px;")

        self.status_label = QLabel("Ready.")
        self.status_label.setStyleSheet("color: black;")

        top_bar.addWidget(self.load_btn)
        top_bar.addWidget(self.run_btn)
        top_bar.addWidget(self.status_label)
        top_bar.addStretch()
        self.main_layout.addLayout(top_bar)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.cluster_container = QWidget()
        self.cluster_layout = QVBoxLayout(self.cluster_container)
        self.cluster_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.cluster_container)

        self.main_layout.addWidget(self.scroll_area)
        self.run_btn.clicked.connect(self.run_comparison)

    def run_comparison(self):
        self.status_label.setText("Running Semantic AI... Please wait.")
        self.run_btn.setEnabled(False)

        for i in reversed(range(self.cluster_layout.count())):
            self.cluster_layout.itemAt(i).widget().setParent(None)

        from pathlib import Path
        base_dir = Path(r"C:\Users\jensv\Documents\Steen Vastgoed\Offertes Vergelijken\Pre-Made Templates")
        path_a = base_dir / "JV-Offerte_Template_DeCock.xlsx"
        path_b = base_dir / "JV-Offerte_Template_VNT.xlsx"

        self.worker = AIWorker(path_a, path_b)
        self.worker.signals.finished.connect(self.on_ai_finished)
        self.worker.signals.error.connect(self.on_ai_error)
        self.worker.start()

    def on_ai_finished(self, clusters: list[dict], lookup: dict):
        self.status_label.setText(f"Done. Found {len(clusters)} clusters.")
        self.run_btn.setEnabled(True)

        clusters.sort(key=lambda x: x.get('cluster_score', 0.0), reverse=True)
        for i, cluster_data in enumerate(clusters, 1):
            widget = ClusterWidget(cluster_data, i, lookup)
            self.cluster_layout.addWidget(widget)

    def on_ai_error(self, err_msg: str):
        self.status_label.setText(f"Error: {err_msg}")
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