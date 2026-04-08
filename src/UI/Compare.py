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
            "<b>Sorteer items in 'Groepen' om ze naast elkaar te plaatsen in Excel.</b><br>"
            "Sleep meerdere items naar dezelfde kolom als een aannemer iets heeft opgesplitst (1-op-N relaties)."
        )
        info.setFrameShape(QFrame.StyledPanel)
        info.setContentsMargins(10, 10, 10, 10) # Replaced deprecated setMargin

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
            lbl.setStyleSheet("font-weight: bold; font-size: 14px;")
            header_layout.addWidget(lbl, stretch=1)

        self.scroll_layout.addLayout(header_layout)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("color: rgba(128, 128, 128, 0.5);")
        self.scroll_layout.addWidget(separator)

        self.bucket_container = QVBoxLayout()
        self.bucket_container.setSpacing(0)
        self.scroll_layout.addLayout(self.bucket_container)

        self.scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

    def reapply_threshold(self, value):
        self.current_threshold = value
        for bucket in self.buckets:
            bucket.setParent(None)
            bucket.deleteLater()
        self.buckets.clear()
        self.populate_ai_data()

    def add_bucket(self):
        bucket = MatchBucket(self.all_contract_names)
        bucket.bucketChanged.connect(self.cleanup_empty_buckets)
        bucket.bucketChanged.connect(self.refresh_all_scores)
        self.buckets.append(bucket)
        self.bucket_container.addWidget(bucket)
        return bucket

    def cleanup_empty_buckets(self):
        empty_buckets = [b for b in self.buckets if b.is_completely_empty()]

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
                c1_item_map[c1_item] = bucket

        unmapped_items = {c: [] for c in self.target_contracts.keys()}

        for contract_name, contract_info in self.target_contracts.items():
            ai_mapping = contract_info['ai']['items']
            target_data = contract_info['data']

            for t_cat, t_items in target_data.items():
                for t_item in t_items:
                    best_global_score = -1
                    best_global_m_name = None
                    best_score_data = None

                    for m_cat in ai_mapping.get(t_cat, {}).keys():
                        m_cat_data = ai_mapping[t_cat][m_cat].get(t_item, {})
                        scores_dict = m_cat_data.get('scores', {})

                        for m_item, score_data in scores_dict.items():
                            total = score_data.get('total', 0.0) if isinstance(score_data, dict) else float(score_data)
                            if total > best_global_score:
                                best_global_score = total
                                best_global_m_name = m_item
                                best_score_data = score_data

                    placed = False
                    if best_global_score >= self.current_threshold and best_global_m_name in c1_item_map:
                        target_bucket = c1_item_map[best_global_m_name]
                        widget = Product(t_cat, t_item, score_data=best_score_data,
                                                threshold=self.current_threshold)
                        target_bucket.lists[contract_name].addItem(widget)
                        widget.update_display()
                        placed = True

                    if not placed:
                        unmapped_items[contract_name].append((t_cat, t_item))

        for contract_name, item_tuples in unmapped_items.items():
            for t_cat, t_item in item_tuples:
                group_id = self.global_item_groups.get(t_item)
                placed = False

                for bucket in self.buckets:
                    if bucket.lists["Contract 1"].count() > 0: continue

                    row_belongs_to_group = False
                    for other_contract in self.target_contracts.keys():
                        lst = bucket.lists[other_contract]
                        for idx in range(lst.count()):
                            existing_val = lst.item(idx).orig_name
                            if self.global_item_groups.get(existing_val) == group_id:
                                row_belongs_to_group = True
                                break

                    if row_belongs_to_group:
                        widget = Product(t_cat, t_item, is_extra=True, threshold=self.current_threshold)
                        bucket.lists[contract_name].addItem(widget)
                        widget.update_display()
                        placed = True
                        break

                if not placed:
                    new_bucket = self.add_bucket()
                    widget = Product(t_cat, t_item, is_extra=True, threshold=self.current_threshold)
                    new_bucket.lists[contract_name].addItem(widget)
                    widget.update_display()

        self.cleanup_empty_buckets()

    def refresh_all_scores(self):
        for bucket in self.buckets:
            anchor_item = None
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
                        item_widget.threshold = self.current_threshold
                        item_widget.update_display()
                        continue

                    t_cat = item_widget.orig_cat
                    t_item = item_widget.orig_name

                    if anchor_item:
                        ai_mapping = contract_info['ai']['items']
                        score_data = None

                        for m_cat in ai_mapping.get(t_cat, {}).keys():
                            lookup = ai_mapping.get(t_cat, {}).get(m_cat, {}).get(t_item, {}).get('scores', {}).get(
                                anchor_item)
                            if lookup:
                                score_data = lookup
                                break

                        item_widget.score_data = score_data
                        item_widget.is_extra = False

                        # Mark as manual if the AI didn't calculate a score for this grouping
                        item_widget.is_manual = (score_data is None)
                    else:
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