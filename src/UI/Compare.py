from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QDoubleSpinBox, QScrollArea, QSizePolicy
)
from src.UI.Product import Product
from src.UI.Matching import MatchBucket


class CompareTab(QWidget):
    def __init__(self, master_dict, target_contracts):
        super().__init__()
        self.contract_1_data = master_dict
        self.target_contracts = target_contracts

        self.all_contract_names = ["Contract 1"] + list(target_contracts.keys())
        self.current_threshold = 0.40

        self.buckets = []
        self.global_item_groups = {}

        self.build_global_groups()
        self.init_ui()
        self.populate_ai_data()

    def build_global_groups(self):
        for cat, items in self.contract_1_data.items():
            for item in items:
                self.global_item_groups[item] = str(item).lower().strip()

        for c_info in self.target_contracts.values():
            for items in c_info['data'].values():
                for item in items:
                    self.global_item_groups[item] = str(item).lower().strip()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        controls_layout = QHBoxLayout()
        info = QLabel(
            "<b>Sorteer items in 'Groepen' om ze naast elkaar te plaatsen.</b><br>"
            "Sleep items handmatig om de AI te corrigeren. De scores worden live bijgewerkt."
        )
        info.setFrameShape(QFrame.StyledPanel)
        info.setContentsMargins(10, 10, 10, 10)

        thresh_layout = QVBoxLayout()
        thresh_layout.addWidget(QLabel("<b>AI Drempelwaarde:</b>"))

        self.spin_thresh = QDoubleSpinBox()
        self.spin_thresh.setRange(0.0, 1.0)
        self.spin_thresh.setSingleStep(0.05)
        self.spin_thresh.setValue(self.current_threshold)
        self.spin_thresh.valueChanged.connect(self.reapply_threshold)
        thresh_layout.addWidget(self.spin_thresh)

        controls_layout.addWidget(info, stretch=1)
        controls_layout.addLayout(thresh_layout)
        main_layout.addLayout(controls_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setSpacing(0)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 10)

        header_layout.addSpacing(50)
        for c_name in self.all_contract_names:
            lbl = QLabel(c_name)
            lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #555;")
            header_layout.addWidget(lbl, stretch=1)

        self.scroll_layout.addLayout(header_layout)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("color: rgba(128, 128, 128, 0.2);")
        self.scroll_layout.addWidget(separator)

        self.bucket_container = QVBoxLayout()
        self.bucket_container.setSpacing(0)
        self.scroll_layout.addLayout(self.bucket_container)

        self.scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

    def reapply_threshold(self, value):
        self.current_threshold = value
        # Refresh all products to show warning icons if they fall below new threshold
        self.refresh_all_scores()

    def add_bucket(self):
        bucket = MatchBucket(self.all_contract_names)
        bucket.bucketChanged.connect(self.cleanup_empty_buckets)
        bucket.bucketChanged.connect(self.refresh_all_scores)
        self.buckets.append(bucket)
        self.bucket_container.addWidget(bucket)
        return bucket

    def cleanup_empty_buckets(self):
        empty_buckets = [b for b in self.buckets if b.is_completely_empty()]
        # Keep at least one empty bucket at the bottom for new drops
        while len(empty_buckets) > 1:
            b_to_remove = empty_buckets.pop(0)
            self.buckets.remove(b_to_remove)
            self.bucket_container.removeWidget(b_to_remove)
            b_to_remove.deleteLater()

        if not empty_buckets:
            self.add_bucket()

    def populate_ai_data(self):
        c1_item_map = {}
        for c1_cat, c1_items in self.contract_1_data.items():
            for c1_item in c1_items:
                bucket = self.add_bucket()
                widget = Product(c1_cat, c1_item, threshold=self.current_threshold)
                bucket.lists["Contract 1"].addItem(widget)
                if c1_item not in c1_item_map:
                    c1_item_map[c1_item] = []
                c1_item_map[c1_item].append(bucket)

        unmapped_items = {c: [] for c in self.target_contracts.keys()}

        for contract_name, contract_info in self.target_contracts.items():
            ai_mapping = contract_info['ai']['items']
            best_matches = {}

            for t_cat, m_cats in ai_mapping.items():
                for m_cat, t_items in m_cats.items():
                    for t_unique_key, match_data in t_items.items():
                        t_item_raw = match_data.get('target_raw_name', t_unique_key.split(' [Row')[0])

                        if t_unique_key not in best_matches:
                            best_matches[t_unique_key] = {
                                't_cat': t_cat, 't_item_raw': t_item_raw,
                                'best_score': -1, 'best_master_raw': None, 'score_data': None
                            }

                        scores_dict = match_data.get('scores', {})
                        for m_unique, score_data in scores_dict.items():
                            total = score_data.get('total', 0.0) if isinstance(score_data, dict) else float(score_data)
                            if total > best_matches[t_unique_key]['best_score']:
                                best_matches[t_unique_key]['best_score'] = total
                                best_matches[t_unique_key]['best_master_raw'] = score_data.get('master_raw_name',
                                                                                               m_unique.split(' [Row')[
                                                                                                   0])
                                best_matches[t_unique_key]['score_data'] = score_data

            for t_unique_key, b_match in best_matches.items():
                placed = False
                if b_match['best_score'] >= self.current_threshold and b_match['best_master_raw'] in c1_item_map:
                    target_bucket = c1_item_map[b_match['best_master_raw']][0]
                    widget = Product(b_match['t_cat'], b_match['t_item_raw'], score_data=b_match['score_data'],
                                     threshold=self.current_threshold)
                    target_bucket.lists[contract_name].addItem(widget)
                    placed = True

                if not placed:
                    unmapped_items[contract_name].append((b_match['t_cat'], b_match['t_item_raw']))

        # Handle leftovers via shared groups or new buckets
        for contract_name, item_tuples in unmapped_items.items():
            for t_cat, t_item in item_tuples:
                group_id = self.global_item_groups.get(t_item)
                placed = False
                for bucket in self.buckets:
                    if bucket.lists["Contract 1"].count() > 0: continue

                    match_found = False
                    for other_c in self.target_contracts.keys():
                        lst = bucket.lists[other_c]
                        for idx in range(lst.count()):
                            if self.global_item_groups.get(lst.item(idx).orig_name) == group_id:
                                match_found = True;
                                break
                        if match_found: break

                    if match_found:
                        widget = Product(t_cat, t_item, is_extra=True, threshold=self.current_threshold)
                        bucket.lists[contract_name].addItem(widget)
                        placed = True;
                        break

                if not placed:
                    new_bucket = self.add_bucket()
                    widget = Product(t_cat, t_item, is_extra=True, threshold=self.current_threshold)
                    new_bucket.lists[contract_name].addItem(widget)

        self.cleanup_empty_buckets()

    def refresh_all_scores(self):
        """Recalculates scores based on current bucket positions."""
        for bucket in self.buckets:
            anchor_item = None
            # Find the master item in this bucket
            if bucket.lists["Contract 1"].count() > 0:
                anchor_item = bucket.lists["Contract 1"].item(0).orig_name

            for contract_name, contract_info in self.target_contracts.items():
                lst = bucket.lists[contract_name]
                for idx in range(lst.count()):
                    item_widget = lst.item(idx)

                    if contract_name == "Contract 1":
                        item_widget.score_data = None
                        item_widget.is_manual = False
                        item_widget.is_extra = False
                    else:
                        t_cat = item_widget.orig_cat
                        t_item_raw = item_widget.orig_name

                        if anchor_item:
                            ai_mapping = contract_info['ai']['items']
                            score_found = None

                            # Search through AI results for this target vs the anchor master
                            for m_cat, t_items in ai_mapping.get(t_cat, {}).items():
                                for t_unique, match_data in t_items.items():
                                    # Relaxed matching check for the raw names
                                    if match_data.get('target_raw_name') == t_item_raw:
                                        for m_unique, s_data in match_data.get('scores', {}).items():
                                            if s_data.get('master_raw_name') == anchor_item:
                                                if not score_found or s_data.get('total', 0) > score_found.get('total',
                                                                                                               0):
                                                    score_found = s_data

                            item_widget.score_data = score_found
                            item_widget.is_extra = False
                            # If no AI score exists for this specific combination, mark as manual
                            item_widget.is_manual = (score_found is None)
                        else:
                            # Item is in a bucket without a master item (Extra Item)
                            item_widget.score_data = None
                            item_widget.is_manual = False
                            item_widget.is_extra = True

                    item_widget.threshold = self.current_threshold
                    item_widget.update_display()

    def extract_final_mapping(self):
        buckets_data = []
        for bucket in self.buckets:
            if bucket.is_completely_empty(): continue
            buckets_data.append(bucket.get_export_data())
        return buckets_data