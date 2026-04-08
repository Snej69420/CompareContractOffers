import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame,
    QListWidget, QAbstractItemView, QListWidgetItem, QPushButton, QSizePolicy, QDoubleSpinBox
)
from PySide6.QtCore import Qt, Signal, QTimer

MATCH_THRESHOLD = 0.40


class ElidedLabel(QLabel):
    def __init__(self, text, *args, **kwargs):
        super().__init__(text, *args, **kwargs)
        self.full_text = text

    def resizeEvent(self, event):
        fm = self.fontMetrics()
        elided_text = fm.elidedText(self.full_text, Qt.ElideRight, self.width() - 5)
        self.setText(elided_text)
        super().resizeEvent(event)


class ExpandableItem(QListWidgetItem):
    def __init__(self, orig_cat, orig_name, score_data=None, is_extra=False, threshold=0.40):
        super().__init__()
        self.orig_cat = str(orig_cat).strip()
        self.orig_name = str(orig_name).strip()
        self.score_data = score_data
        self.is_extra = is_extra
        self.is_manual = False
        self.is_expanded = False
        self.threshold = threshold

        self.setData(Qt.UserRole, (self.orig_cat, self.orig_name))
        self.update_display()

    def update_display(self):
        list_widget = self.listWidget()
        prefix = ""
        suffix = ""

        if getattr(self, 'is_manual', False):
            prefix = "🧑‍🔧 "
            self.setToolTip(
                f"Originele Categorie: {self.orig_cat}\nVolledige naam:\n{self.orig_name}\n\n🧑‍🔧 Handmatig geplaatst.")
        elif self.is_extra:
            prefix = "🔹 "
            self.setToolTip(f"Originele Categorie: {self.orig_cat}\nVolledige naam:\n{self.orig_name}")
        elif self.score_data:
            total = self.score_data.get('total', 0.0)
            text_s = self.score_data.get('text', 0.0)
            unit_p = self.score_data.get('unit', 0.0)
            qty_s = self.score_data.get('qty', 0.0)
            var_p = self.score_data.get('variance', 0.0)

            icon = "⭐" if total >= self.threshold else "⚠️"
            prefix = f"{icon} "
            suffix = f" ({total:.2f})"

            self.setToolTip(
                f"Originele Categorie: {self.orig_cat}\n"
                f"Volledige naam:\n{self.orig_name}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"TOTAAL SCORE: {total:.2f}\n"
                f"  • Tekst AI Score:  {text_s:.2f}\n"
                f"  • Eenheid Penalty: {unit_p:.2f}\n"
                f"  • Aantal Bonus:    +{qty_s:.2f}\n"
                f"  • Variantie Penalty: {var_p:.2f}"
            )
        else:
            self.setToolTip(f"Originele Categorie: {self.orig_cat}\n{self.orig_name}")

        if not list_widget:
            display_text = self.orig_name[:40] + "..." if len(self.orig_name) > 40 else self.orig_name
            self.setText(f"{prefix}{display_text}{suffix}")
            return

        if self.is_expanded:
            self.setText(f"{prefix}{self.orig_name}{suffix}")
        else:
            fm = list_widget.fontMetrics()
            available_width = list_widget.viewport().width() - 35
            fixed_width = fm.horizontalAdvance(prefix + suffix)
            name_width = available_width - fixed_width

            if name_width > 0:
                elided_name = fm.elidedText(self.orig_name, Qt.ElideRight, name_width)
            else:
                elided_name = self.orig_name
            self.setText(f"{prefix}{elided_name}{suffix}")


class ColumnRestrictedList(QListWidget):
    itemsChanged = Signal()

    def __init__(self, column_id):
        super().__init__()
        self.column_id = column_id

        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setAcceptDrops(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        self.setWordWrap(True)

        self.setStyleSheet(
            "QListWidget { border: 1px solid rgba(128, 128, 128, 0.5); border-radius: 4px; background: transparent; }"
            "QListWidget::item { padding: 6px; border-radius: 3px; border-bottom: 1px solid rgba(128, 128, 128, 0.3); margin-bottom: 2px; }"
            "QListWidget::item:selected { background-color: rgba(0, 120, 215, 0.4); }"
        )

        self.setMinimumHeight(45)
        self.setFrameShape(QFrame.NoFrame)
        self.itemClicked.connect(self.toggle_expansion)
        self.model().rowsInserted.connect(self.adjust_dynamic_height)
        self.model().rowsRemoved.connect(self.adjust_dynamic_height)

        # Smooth Scrolling Engine
        self.scroll_timer = QTimer(self)
        self.scroll_timer.setInterval(20)  # 50 FPS
        self.scroll_timer.timeout.connect(self.do_auto_scroll)
        self.scroll_direction = 0

    def do_auto_scroll(self):
        scroll_area = self.window().findChild(QScrollArea)
        if scroll_area:
            bar = scroll_area.verticalScrollBar()
            bar.setValue(bar.value() + (15 * self.scroll_direction))

    def adjust_dynamic_height(self):
        count = self.count()
        self.setMinimumHeight(max(45, count * 40 + 10))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        for i in range(self.count()):
            item = self.item(i)
            if hasattr(item, 'update_display'):
                item.update_display()

    def toggle_expansion(self, item):
        if isinstance(item, ExpandableItem):
            item.is_expanded = not item.is_expanded
            item.update_display()
            self.scheduleDelayedItemsLayout()

    def dragEnterEvent(self, event):
        source = event.source()
        if isinstance(source, ColumnRestrictedList) and source.column_id == self.column_id:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        super().dragMoveEvent(event)
        scroll_area = self.window().findChild(QScrollArea)
        if scroll_area:
            global_pos = self.mapToGlobal(event.position().toPoint())
            scroll_pos = scroll_area.mapFromGlobal(global_pos)
            y = scroll_pos.y()

            # Expanded trigger zone to 80px for easier scrolling
            if y < 80:
                self.scroll_direction = -1
                if not self.scroll_timer.isActive(): self.scroll_timer.start()
            elif y > scroll_area.viewport().height() - 80:
                self.scroll_direction = 1
                if not self.scroll_timer.isActive(): self.scroll_timer.start()
            else:
                self.scroll_timer.stop()

    def dragLeaveEvent(self, event):
        super().dragLeaveEvent(event)
        self.scroll_timer.stop()

    def dropEvent(self, event):
        self.scroll_timer.stop()
        source = event.source()

        if isinstance(source, ColumnRestrictedList) and source.column_id == self.column_id:
            # FIXED: Do NOT use super().dropEvent(event) as Qt destroys the python class.
            # We manually take the item and move it to preserve 'orig_cat'.
            item = source.currentItem()
            if item:
                source.takeItem(source.row(item))

                drop_pos = event.position().toPoint()
                target_item = self.itemAt(drop_pos)
                if target_item:
                    insert_row = self.row(target_item)
                    self.insertItem(insert_row, item)
                else:
                    self.addItem(item)

                event.accept()
                self.itemsChanged.emit()
                if source != self:
                    source.itemsChanged.emit()
        else:
            event.ignore()


class MatchBucketWidget(QWidget):
    bucketChanged = Signal()

    def __init__(self, all_contracts):
        super().__init__()
        self.all_contracts = all_contracts
        self.lists = {}
        self.init_ui()

    def init_ui(self):
        row_layout = QHBoxLayout(self)
        row_layout.setContentsMargins(5, 8, 5, 8)
        row_layout.setSpacing(10)

        indicator = QLabel("🔗\nGroep")
        indicator.setStyleSheet("font-weight: bold; color: rgba(128, 128, 128, 1.0); font-size: 11px;")
        indicator.setFixedWidth(40)
        indicator.setAlignment(Qt.AlignCenter)
        row_layout.addWidget(indicator)

        for c_name in self.all_contracts:
            lst = ColumnRestrictedList(column_id=c_name)
            lst.itemsChanged.connect(self.bucketChanged.emit)
            self.lists[c_name] = lst
            row_layout.addWidget(lst, stretch=1)

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "MatchBucketWidget { background-color: rgba(128, 128, 128, 0.1); border: 1px solid rgba(128, 128, 128, 0.4); border-radius: 6px; margin-bottom: 5px; }")

    def is_completely_empty(self):
        return all(lst.count() == 0 for lst in self.lists.values())

    def get_export_data(self):
        data = {}
        for c_name, lst in self.lists.items():
            items = []
            for i in range(lst.count()):
                w = lst.item(i)
                items.append((w.orig_cat, w.orig_name))
            data[c_name] = items
        return data


class MappingTab(QWidget):
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
        info.setMargin(10)

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
        bucket = MatchBucketWidget(self.all_contract_names)
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
                widget = ExpandableItem(c1_cat, c1_item, threshold=self.current_threshold)
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
                        widget = ExpandableItem(t_cat, t_item, score_data=best_score_data,
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
                        widget = ExpandableItem(t_cat, t_item, is_extra=True, threshold=self.current_threshold)
                        bucket.lists[contract_name].addItem(widget)
                        widget.update_display()
                        placed = True
                        break

                if not placed:
                    new_bucket = self.add_bucket()
                    widget = ExpandableItem(t_cat, t_item, is_extra=True, threshold=self.current_threshold)
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