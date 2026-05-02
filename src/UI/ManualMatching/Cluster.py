from pathlib import Path
from PySide6.QtWidgets import QPushButton, QMessageBox
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QShortcut, QKeySequence

from src.UI.ManualMatching.BaseCluster import BaseCluster
from src.UI.ManualMatching.MatchItem import MatchItem


class Cluster(BaseCluster):
    itemToParkingLot = Signal(object)
    # Changed signal to emit a single generalized list of all items
    clusterRemoved = Signal(object, list)

    def __init__(self, doc_keys: list[str], cluster_data: dict, index: int, score_lookup: dict):
        # Pass the dynamic keys up to the BaseCluster
        super().__init__(f"Cluster {index}", doc_keys)

        self.score_lookup = score_lookup
        self.is_approved = False
        self.cluster_index = index

        icon_dir = Path(__file__).parent.parent.parent.parent / "assets"
        self.open_icon = QIcon(str(icon_dir / "package-open.svg"))
        self.closed_icon = QIcon(str(icon_dir / "package-closed.svg"))
        self.approve_icon = QIcon(str(icon_dir / "check.svg"))
        self.edit_icon = QIcon(str(icon_dir / "pencil.svg"))
        self.icon_label.setIcon(self.open_icon)

        self.setStyleSheet(
            "ClusterWidget { background-color: #f9f9f9; border: 1px solid #ddd; border-radius: 5px; margin: 5px; }")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: black;")

        # Header buttons
        self.delete_btn = QPushButton()
        self.delete_btn.setIcon(QIcon(str(icon_dir / "trash.svg")))
        self.delete_btn.setStyleSheet(
            "background-color: #ffebee; color: #c62828; border: 1px solid #ffcdd2; border-radius: 3px; padding: 5px;")
        self.delete_btn.setToolTip("Cluster verwijderen")
        self.delete_btn.clicked.connect(self.request_removal)

        self.approve_btn = QPushButton("Bevestigen")
        self.approve_btn.setIcon(self.approve_icon)
        self.approve_btn.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.approve_btn.clicked.connect(self.toggle_approve)
        self.approve_btn.setStyleSheet(
            "background-color: #f9f9f9; color: black; border: 1px solid #c3e6cb; border-radius: 3px; padding: 5px;"
        )

        self.header_layout.addWidget(self.delete_btn)
        self.header_layout.addWidget(self.approve_btn)

        # Wire up ejection logic to the dynamically generated lists
        for lst in self.lists.values():
            lst.itemEjected.connect(self.eject_item)

        self.del_shortcut = QShortcut(QKeySequence("Shift+Del"), self)
        self.del_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.del_shortcut.activated.connect(self.request_removal)

        self.backspace_shortcut = QShortcut(QKeySequence("Shift+Backspace"), self)
        self.backspace_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.backspace_shortcut.activated.connect(self.request_removal)

        self._populate_initial(cluster_data)
        self.recalculate_scores()

    def on_items_changed(self):
        """Override base drop handler"""
        self.recalculate_scores()

    def eject_item(self, match_item):
        # Dynamically find the list this item belongs to
        target_list = self.lists[match_item.doc_key]
        items = [i for i in target_list.get_items() if i is not match_item]

        target_list.rebuild_ui(items)
        self.recalculate_scores()
        self.itemToParkingLot.emit(match_item)

    def request_removal(self):
        # Gather all items from all N columns
        all_items = []
        for lst in self.lists.values():
            all_items.extend(lst.get_items())

        if not all_items:
            self.clusterRemoved.emit(self, [])
        else:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle('Cluster Verwijderen')
            msg_box.setText(
                'Deze cluster is niet leeg, weet je zeker dat je deze wilt verwijderen?'
                '\nDe items zullen toegevoegd worden aan de lijst met ongekoppelde items')
            msg_box.setIcon(QMessageBox.Icon.Question)
            msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg_box.setDefaultButton(QMessageBox.StandardButton.No)
            msg_box.setButtonText(QMessageBox.StandardButton.Yes, "Ja")
            msg_box.setButtonText(QMessageBox.StandardButton.No, "Nee")

            if msg_box.exec() == QMessageBox.StandardButton.Yes:
                self.clusterRemoved.emit(self, all_items)

    def _populate_initial(self, cluster_data: dict):
        items_dict = {key: [] for key in self.doc_keys}

        # Legacy AI Output mapping (Bridge to old backend format)
        legacy_keys = ['contract_a_items', 'contract_b_items']

        for i, key in enumerate(self.doc_keys):
            # If backend uses old keys, pull those. Otherwise assume Future Backend uses doc_keys
            data_key = legacy_keys[i] if i < 2 and legacy_keys[i] in cluster_data else key

            for raw in cluster_data.get(data_key, []):
                items_dict[key].append(MatchItem(raw, raw.get('id', -1), key))

        for key, items in items_dict.items():
            self.lists[key].rebuild_ui(items)

    def recalculate_scores(self):
        items_by_doc = {key: self.lists[key].get_items() for key in self.doc_keys}

        for items in items_by_doc.values():
            for item in items:
                item.is_parked = False

        # --- 1. CALCULATE CLUSTER TOTALS FOR QUANTITY LOGIC ---
        totals = {key: {} for key in self.doc_keys}
        for key, items in items_by_doc.items():
            for item in items:
                totals[key][item.unit] = totals[key].get(item.unit, 0.0) + item.qty

        avg_cluster_score = 0.0

        # --- 2. TEMPORARY 2-DOCUMENT MATH BRIDGE ---
        # Until the AI backend is upgraded, scoring only works perfectly between the first 2 docs
        if len(self.doc_keys) >= 2:
            key_a, key_b = self.doc_keys[0], self.doc_keys[1]
            items_a, items_b = items_by_doc[key_a], items_by_doc[key_b]

            cluster_total_score = 0.0
            total_pairs = 0

            # CALCULATE A ITEMS
            for a_item in items_a:
                best_score = 0.0
                best_name = ""
                for b_item in items_b:
                    score = self.score_lookup.get((a_item.original_id, b_item.original_id), 0.0)
                    cluster_total_score += score
                    total_pairs += 1
                    if score >= best_score:
                        best_score, best_name = score, b_item.name

                a_item.current_score = best_score
                a_item.best_match_name = best_name if items_b else ""
                a_item.is_unit_matched = a_item.unit in totals[key_b]
                a_item.is_qty_balanced = abs(
                    totals[key_a].get(a_item.unit, 0.0) - totals[key_b].get(a_item.unit, 0.0)) < 0.01

            # CALCULATE B ITEMS
            for b_item in items_b:
                best_score = 0.0
                best_name = ""
                for a_item in items_a:
                    score = self.score_lookup.get((a_item.original_id, b_item.original_id), 0.0)
                    if score >= best_score:
                        best_score, best_name = score, a_item.name

                b_item.current_score = best_score
                b_item.best_match_name = best_name if items_a else ""
                b_item.is_unit_matched = b_item.unit in totals[key_a]
                b_item.is_qty_balanced = abs(
                    totals[key_b].get(b_item.unit, 0.0) - totals[key_a].get(b_item.unit, 0.0)) < 0.01

            avg_cluster_score = (cluster_total_score / total_pairs) if total_pairs > 0 else 0.0

        # --- 3. UPDATE TITLE ---
        if avg_cluster_score >= 0.70:
            quality = "Hoog"
        elif avg_cluster_score >= 0.40:
            quality = "Te controleren"
        else:
            quality = "Laag"

        self.title_label.setText(f"Cluster {self.cluster_index} | Zekerheid: {quality} ({avg_cluster_score:.0%})")

        # --- 4. SORT & REBUILD UI ---
        for key, items in items_by_doc.items():
            items.sort(key=lambda x: x.current_score, reverse=True)
            self.lists[key].rebuild_ui(items)

        # --- 5. DYNAMIC SYMMETRICAL HEIGHT ---
        max_items = max([len(lst) for lst in items_by_doc.values()] + [1])
        self.adjust_list_heights(max_visible_rows=min(max_items, 6))

    def toggle_approve(self):
        self.is_approved = not self.is_approved
        if self.is_approved:
            self.lists_widget.setVisible(False)
            self.approve_btn.setText("Aanpassen")
            self.approve_btn.setIcon(self.edit_icon)
            self.icon_label.setIcon(self.closed_icon)
            self.setStyleSheet(
                "ClusterWidget { background-color: #e2f0e5; border: 1px solid #c3e6cb; border-radius: 5px; margin: 5px; }")
        else:
            self.lists_widget.setVisible(True)
            self.approve_btn.setText("Bevestigen")
            self.approve_btn.setIcon(self.approve_icon)
            self.icon_label.setIcon(self.open_icon)
            self.setStyleSheet(
                "ClusterWidget { background-color: #f9f9f9; border: 1px solid #ddd; border-radius: 5px; margin: 5px; }")

    def mouseDoubleClickEvent(self, event):
        if self.is_approved:
            self.toggle_approve()
        super().mouseDoubleClickEvent(event)