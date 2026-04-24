from PySide6.QtWidgets import QPushButton, QMessageBox
from PySide6.QtCore import Signal

from src.UI.BaseCluster import BaseClusterWidget
from src.UI.MatchItem import MatchItem

class Cluster(BaseClusterWidget):
    itemToParkingLot = Signal(object)
    clusterRemoved = Signal(object, list, list)

    def __init__(self, cluster_data: dict, index: int, score_lookup: dict):
        super().__init__(f"📦 Cluster {index}")
        self.score_lookup = score_lookup
        self.is_approved = False
        self.cluster_index = index

        self.setStyleSheet(
            "ClusterWidget { background-color: #f9f9f9; border: 1px solid #ddd; border-radius: 5px; margin: 5px; }")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: black;")

        # Add specific buttons to the inherited header
        self.delete_btn = QPushButton("🗑️")
        self.delete_btn.setStyleSheet(
            "background-color: #ffebee; color: #c62828; border: 1px solid #ffcdd2; border-radius: 3px; padding: 5px;")
        self.delete_btn.setToolTip("Cluster verwijderen")
        self.delete_btn.clicked.connect(self.request_removal)

        self.approve_btn = QPushButton("Bevestigen ✓")
        self.approve_btn.setStyleSheet(
            "background-color: #d4edda; color: black; border: 1px solid #c3e6cb; border-radius: 3px; padding: 5px;")
        self.approve_btn.clicked.connect(self.toggle_approve)

        self.header_layout.addWidget(self.delete_btn)
        self.header_layout.addWidget(self.approve_btn)

        # Wire up ejection logic to the inherited lists
        self.list_a.itemEjected.connect(self.eject_item)
        self.list_b.itemEjected.connect(self.eject_item)

        self._populate_initial(cluster_data)
        self.recalculate_scores()

    def on_items_changed(self):
        """Override base drop handler"""
        self.recalculate_scores()

    def eject_item(self, match_item):
        if match_item.side == 'A':
            items = [i for i in self.list_a.get_items() if i is not match_item]
            self.list_a.rebuild_ui(items)
        else:
            items = [i for i in self.list_b.get_items() if i is not match_item]
            self.list_b.rebuild_ui(items)

        self.recalculate_scores()
        self.itemToParkingLot.emit(match_item)

    def request_removal(self):
        items_a = self.list_a.get_items()
        items_b = self.list_b.get_items()

        if not items_a and not items_b:
            self.clusterRemoved.emit(self, [], [])
        else:
            reply = QMessageBox.question(
                self, 'Cluster Verwijderen',
                'Dit cluster bevat nog items. Weet je zeker dat je dit wilt verwijderen?\nDe items gaan naar de Parking Lot.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.clusterRemoved.emit(self, items_a, items_b)

    def _populate_initial(self, cluster_data: dict):
        items_a, items_b = [], []
        for raw_a in cluster_data.get('contract_a_items', []):
            items_a.append(MatchItem(raw_a, raw_a.get('id', -1), 'A'))
        for raw_b in cluster_data.get('contract_b_items', []):
            items_b.append(MatchItem(raw_b, raw_b.get('id', -1), 'B'))

        self.list_a.rebuild_ui(items_a)
        self.list_b.rebuild_ui(items_b)

    def recalculate_scores(self):
        items_a = self.list_a.get_items()
        items_b = self.list_b.get_items()

        for item in items_a + items_b:
            item.is_parked = False

        # --- 1. CALCULATE CLUSTER TOTALS FOR QUANTITY LOGIC ---
        totals_a = {}
        totals_b = {}
        for item in items_a:
            totals_a[item.unit] = totals_a.get(item.unit, 0.0) + item.qty
        for item in items_b:
            totals_b[item.unit] = totals_b.get(item.unit, 0.0) + item.qty

        cluster_total_score = 0.0
        total_pairs = 0

        # --- 2. CALCULATE A ITEMS ---
        for a_item in items_a:
            best_score = 0.0
            best_name = ""
            for b_item in items_b:
                score = self.score_lookup.get((a_item.original_id, b_item.original_id), 0.0)
                cluster_total_score += score
                total_pairs += 1
                if score >= best_score:
                    best_score = score
                    best_name = b_item.name

            a_item.current_score = best_score
            a_item.best_match_name = best_name if items_b else ""

            # Aggregate Checks
            a_item.is_unit_matched = a_item.unit in totals_b
            # Allow tiny floating point differences
            a_item.is_qty_balanced = abs(totals_a.get(a_item.unit, 0.0) - totals_b.get(a_item.unit, 0.0)) < 0.01

        # --- 3. CALCULATE B ITEMS ---
        for b_item in items_b:
            best_score = 0.0
            best_name = ""
            for a_item in items_a:
                score = self.score_lookup.get((a_item.original_id, b_item.original_id), 0.0)
                if score >= best_score:
                    best_score = score
                    best_name = a_item.name

            b_item.current_score = best_score
            b_item.best_match_name = best_name if items_a else ""

            # Aggregate Checks
            b_item.is_unit_matched = b_item.unit in totals_a
            b_item.is_qty_balanced = abs(totals_b.get(b_item.unit, 0.0) - totals_a.get(b_item.unit, 0.0)) < 0.01

        # --- 4. UPDATE TITLE ---
        avg_cluster_score = (cluster_total_score / total_pairs) if total_pairs > 0 else 0.0
        if avg_cluster_score >= 0.70:
            quality = "Hoog"
        elif avg_cluster_score >= 0.40:
            quality = "Te controleren"
        else:
            quality = "Laag"

        self.title_label.setText(f"📦 Cluster {self.cluster_index} | Zekerheid: {quality} ({avg_cluster_score:.0%})")

        # --- 5. SORT & REBUILD UI ---
        # Sort the items in memory
        items_a.sort(key=lambda x: x.current_score, reverse=True)
        items_b.sort(key=lambda x: x.current_score, reverse=True)

        # Inject fresh widgets
        self.list_a.rebuild_ui(items_a)
        self.list_b.rebuild_ui(items_b)

        # --- 6. DYNAMIC SYMMETRICAL HEIGHT ---
        max_items = max(1, len(items_a), len(items_b))
        visible_rows = min(max_items, 6)

        # 1. Ask the UI engine for the actual height of a row (handles font/scaling changes)
        actual_row_height = max(self.list_a.get_single_row_height(), self.list_b.get_single_row_height())

        # 2. Account for the list widget's native borders (usually 1px or 2px per side)
        padding = self.list_a.frameWidth() * 2

        # 3. Calculate target
        target_height = (visible_rows * actual_row_height) + padding

        self.list_a.setFixedHeight(target_height)
        self.list_b.setFixedHeight(target_height)

    def toggle_approve(self):
        self.is_approved = not self.is_approved
        if self.is_approved:
            self.lists_widget.setVisible(False)
            self.approve_btn.setText("Aanpassen ✎")
            self.setStyleSheet(
                "ClusterWidget { background-color: #e2f0e5; border: 1px solid #c3e6cb; border-radius: 5px; margin: 5px; }")
        else:
            self.lists_widget.setVisible(True)
            self.approve_btn.setText("Approve ✓")
            self.setStyleSheet(
                "ClusterWidget { background-color: #f9f9f9; border: 1px solid #ddd; border-radius: 5px; margin: 5px; }")
