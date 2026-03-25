import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame,
    QListWidget, QAbstractItemView, QListWidgetItem, QPushButton, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer

# The minimum AI Confidence Score required to auto-match (0.0 to 1.0)
MATCH_THRESHOLD = 0.40


class ColumnRestrictedList(QListWidget):
    itemsChanged = Signal()

    def __init__(self, column_id, is_unmapped=False, is_category=False):
        super().__init__()
        self.column_id = column_id
        self.is_unmapped = is_unmapped
        self.is_category = is_category

        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setAcceptDrops(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        if self.is_category:
            self.setFixedHeight(50)
            self.setStyleSheet("QListWidget { border: 2px dashed #bbb; border-radius: 5px; background: transparent; }")
        else:
            self.setFixedHeight(35)
            if self.is_unmapped:
                self.setStyleSheet(
                    "QListWidget { border: 1px dashed #ccc; border-radius: 3px; background: transparent; }")
            else:
                self.setStyleSheet(
                    "QListWidget { border: 1px solid #ddd; border-radius: 3px; background: transparent; }")

        self.setFrameShape(QFrame.NoFrame)

    def dragEnterEvent(self, event):
        source = event.source()
        if isinstance(source, ColumnRestrictedList) and source.column_id == self.column_id:
            if source.is_category == self.is_category:
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()

    def dropEvent(self, event):
        source = event.source()
        if source == self:
            super().dropEvent(event)
            return

        if isinstance(source, ColumnRestrictedList) and source.column_id == self.column_id:
            item_to_swap_back = None
            if self.count() > 0:
                item_to_swap_back = self.takeItem(0)

            super().dropEvent(event)

            if item_to_swap_back:
                source.addItem(item_to_swap_back)

            self.itemsChanged.emit()
            if source != self:
                source.itemsChanged.emit()
        else:
            event.ignore()


class CategoryMappingBlock(QWidget):
    def __init__(self, m_cat, m_items, target_contracts, global_item_groups):
        super().__init__()
        self.m_cat = m_cat
        self.m_items = m_items
        self.target_contracts = target_contracts
        self.global_item_groups = global_item_groups

        self.cat_lists = {}
        self.item_lists = {}
        self.extra_lists = {}
        self.extra_row_widgets = []

        self.init_ui()

    def init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 5, 0, 5)
        self.main_layout.setSpacing(0)

        cat_layout = QHBoxLayout()
        cat_layout.setContentsMargins(0, 0, 0, 0)

        master_cat_container = QWidget()
        master_cat_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        mc_layout = QHBoxLayout(master_cat_container)
        mc_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_toggle = QPushButton("▼" if self.m_items else "-")
        self.btn_toggle.setFixedSize(28, 28)
        self.btn_toggle.clicked.connect(self.toggle_items)
        if not self.m_items:
            self.btn_toggle.setEnabled(False)

        lbl_master = QLabel(f"📁 {self.m_cat}")
        font = lbl_master.font()
        font.setBold(True)
        lbl_master.setFont(font)

        mc_layout.addWidget(self.btn_toggle)
        mc_layout.addWidget(lbl_master)
        cat_layout.addWidget(master_cat_container, stretch=1)

        for contract_name in self.target_contracts.keys():
            lst = ColumnRestrictedList(column_id=contract_name, is_category=True)
            # When category changes, update items underneath it
            lst.itemsChanged.connect(lambda c=contract_name: QTimer.singleShot(0, lambda: self.update_items(c)))
            self.cat_lists[contract_name] = lst
            cat_layout.addWidget(lst, stretch=1)

        self.main_layout.addLayout(cat_layout)

        self.items_widget = QWidget()
        items_layout = QVBoxLayout(self.items_widget)
        items_layout.setContentsMargins(0, 5, 0, 15)
        items_layout.setSpacing(5)

        for m_item in self.m_items:
            self.item_lists[m_item] = {}
            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(0, 0, 0, 0)

            lbl_container = QWidget()
            lbl_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            l_layout = QHBoxLayout(lbl_container)
            l_layout.setContentsMargins(35, 0, 0, 0)
            l_layout.addWidget(QLabel(f"↳ {m_item}"))
            row_layout.addWidget(lbl_container, stretch=1)

            for contract_name in self.target_contracts.keys():
                lst = ColumnRestrictedList(column_id=contract_name, is_category=False)
                lst.itemsChanged.connect(lambda: QTimer.singleShot(0, self.refresh_scores))
                self.item_lists[m_item][contract_name] = lst
                row_layout.addWidget(lst, stretch=1)

            items_layout.addLayout(row_layout)

        lbl_extra = QLabel("<i>Extra Items (Niet in Master)</i>")
        lbl_extra.setStyleSheet("color: #777; margin-top: 10px; margin-left: 35px;")
        items_layout.addWidget(lbl_extra)

        self.extra_items_layout = QVBoxLayout()
        self.extra_items_layout.setContentsMargins(0, 0, 0, 0)
        self.extra_items_layout.setSpacing(5)
        items_layout.addLayout(self.extra_items_layout)

        self.add_extra_item_row()

        self.main_layout.addWidget(self.items_widget)
        self.items_widget.setVisible(False)

    def add_extra_item_row(self):
        i = len(self.extra_lists)
        self.extra_lists[i] = {}

        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)

        lbl_container = QWidget()
        lbl_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        l_layout = QHBoxLayout(lbl_container)
        l_layout.setContentsMargins(35, 0, 0, 0)
        lbl = QLabel("↳ Extra")
        lbl.setStyleSheet("color: #aaa;")
        l_layout.addWidget(lbl)
        row_layout.addWidget(lbl_container, stretch=1)

        for contract_name in self.target_contracts.keys():
            lst = ColumnRestrictedList(column_id=contract_name, is_unmapped=True, is_category=False)
            lst.itemsChanged.connect(lambda: QTimer.singleShot(0, self.ensure_empty_extra_item_row))
            lst.itemsChanged.connect(lambda: QTimer.singleShot(0, self.refresh_scores))
            self.extra_lists[i][contract_name] = lst
            row_layout.addWidget(lst, stretch=1)

        self.extra_items_layout.addWidget(row_widget)
        self.extra_row_widgets.append(row_widget)

    def ensure_empty_extra_item_row(self):
        empty_indices = []
        for i in range(len(self.extra_lists)):
            is_empty = all(self.extra_lists[i][c].count() == 0 for c in self.target_contracts.keys())
            if is_empty:
                empty_indices.append(i)

        for idx in empty_indices:
            self.extra_row_widgets[idx].setVisible(False)

        if empty_indices:
            idx_to_show = empty_indices[0]
            widget = self.extra_row_widgets[idx_to_show]
            self.extra_items_layout.removeWidget(widget)
            self.extra_items_layout.addWidget(widget)
            widget.setVisible(True)
        else:
            self.add_extra_item_row()

    def get_or_create_empty_item_row(self):
        for i in range(len(self.extra_lists)):
            is_empty = all(self.extra_lists[i][c].count() == 0 for c in self.target_contracts.keys())
            if is_empty:
                if not self.extra_row_widgets[i].isVisible():
                    self.extra_items_layout.removeWidget(self.extra_row_widgets[i])
                    self.extra_items_layout.addWidget(self.extra_row_widgets[i])
                    self.extra_row_widgets[i].setVisible(True)
                return i
        self.add_extra_item_row()
        return len(self.extra_lists) - 1

    def toggle_items(self):
        is_visible = self.items_widget.isVisible()
        self.items_widget.setVisible(not is_visible)
        self.btn_toggle.setText("▶" if is_visible else "▼")

    def update_items(self, contract_name):
        cat_list = self.cat_lists[contract_name]
        t_cat = cat_list.item(0).data(Qt.UserRole) if cat_list.count() > 0 else None

        for m_item in self.m_items:
            self.item_lists[m_item][contract_name].clear()
        for i in range(len(self.extra_lists)):
            self.extra_lists[i][contract_name].clear()

        if not t_cat:
            self.ensure_empty_extra_item_row()
            return

        contract_info = self.target_contracts[contract_name]
        target_dict = contract_info['data']
        ai_mapping = contract_info['ai']

        t_items = target_dict.get(t_cat, [])
        match_candidates = []
        unmapped_items = []

        for t_item in t_items:
            ai_item_match = ai_mapping['items'].get(t_cat, {}).get(self.m_cat, {}).get(t_item, {})
            scores = ai_item_match.get('scores', {})

            best_m_item = None
            best_score = -1
            for m_item in self.m_items:
                score_data = scores.get(m_item, {})
                # Safely extract the total score from our new dictionary structure
                score = score_data.get('total', 0.0) if isinstance(score_data, dict) else float(
                    score_data if score_data else 0.0)

                if score > best_score:
                    best_score = score
                    best_m_item = m_item

            if best_m_item and best_score >= 0.40:  # STRICT MATCH THRESHOLD
                match_candidates.append({'t_item': t_item, 'm_item': best_m_item, 'score': best_score})
            else:
                unmapped_items.append(t_item)

        match_candidates.sort(key=lambda x: x['score'], reverse=True)

        for candidate in match_candidates:
            t_item = candidate['t_item']
            m_item = candidate['m_item']

            item_widget = QListWidgetItem(t_item)
            item_widget.setData(Qt.UserRole, t_item)

            if self.item_lists[m_item][contract_name].count() == 0:
                self.item_lists[m_item][contract_name].addItem(item_widget)
            else:
                unmapped_items.append(t_item)

        for t_item in unmapped_items:
            group_id = self.global_item_groups.get(t_item)
            placed = False

            for i in range(len(self.extra_lists)):
                if not self.extra_row_widgets[i].isVisible(): continue

                row_belongs_to_group = False
                for other_contract in self.target_contracts.keys():
                    lst = self.extra_lists[i][other_contract]
                    if lst.count() > 0:
                        existing_val = lst.item(0).data(Qt.UserRole)
                        if self.global_item_groups.get(existing_val) == group_id:
                            row_belongs_to_group = True
                            break

                if row_belongs_to_group and self.extra_lists[i][contract_name].count() == 0:
                    widget = QListWidgetItem(t_item)
                    widget.setData(Qt.UserRole, t_item)
                    self.extra_lists[i][contract_name].addItem(widget)
                    placed = True
                    break

            if not placed:
                idx = self.get_or_create_empty_item_row()
                widget = QListWidgetItem(t_item)
                widget.setData(Qt.UserRole, t_item)
                self.extra_lists[idx][contract_name].addItem(widget)

        self.ensure_empty_extra_item_row()
        self.refresh_scores()

    def refresh_scores(self):
        """Updates the visible text and TOOLTIPS to explicitly show the composite breakdown."""
        for contract_name in self.target_contracts.keys():
            contract_info = self.target_contracts[contract_name]
            ai_mapping = contract_info['ai']

            cat_list = self.cat_lists[contract_name]
            t_cat = cat_list.item(0).data(Qt.UserRole) if cat_list.count() > 0 else None

            # 1. Update Master Rows (Shows full composite math breakdown)
            for m_item in self.m_items:
                lst = self.item_lists[m_item][contract_name]
                if lst.count() > 0:
                    widget = lst.item(0)
                    t_item = widget.data(Qt.UserRole)

                    score_data = {}
                    if t_cat:
                        score_data = ai_mapping['items'].get(t_cat, {}).get(self.m_cat, {}).get(t_item, {}).get(
                            'scores', {}).get(m_item, {})

                    total = score_data.get('total', 0.0) if isinstance(score_data, dict) else float(
                        score_data if score_data else 0.0)
                    text_s = score_data.get('text', 0.0) if isinstance(score_data, dict) else total
                    unit_p = score_data.get('unit', 0.0) if isinstance(score_data, dict) else 0.0
                    qty_s = score_data.get('qty', 0.0) if isinstance(score_data, dict) else 0.0

                    tooltip_text = (
                        f"Vergeleken met Master: '{m_item}'\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"TOTAAL SCORE: {total:.2f}\n"
                        f"  • Tekst AI Score:  {text_s:.2f}\n"
                        f"  • Eenheid Penalty: {unit_p:.2f}\n"
                        f"  • Aantal Bonus:    +{qty_s:.2f}"
                    )

                    if total >= MATCH_THRESHOLD:
                        widget.setText(f"⭐ {t_item} ({total:.2f})")
                        widget.setToolTip(tooltip_text)
                    else:
                        widget.setText(f"⚠️ {t_item} ({total:.2f})")
                        widget.setToolTip(f"WAARSCHUWING: Zeer lage match!\n\n{tooltip_text}")

            # 2. Update Extra Rows (Target-to-Target Exact Matches)
            for i in range(len(self.extra_lists)):
                if not self.extra_row_widgets[i].isVisible(): continue
                lst = self.extra_lists[i][contract_name]
                if lst.count() > 0:
                    widget = lst.item(0)
                    t_item = widget.data(Qt.UserRole)
                    widget.setText(f"🔗 {t_item} (Exact)")
                    widget.setToolTip(
                        "Geen AI nodig: Dit item staat op deze rij omdat de tekst 100% identiek is aan een ander contract.")

    def get_mapping(self):
        block_mapping = {}
        for contract_name in self.target_contracts.keys():
            t_cat = None
            if self.cat_lists[contract_name].count() > 0:
                t_cat = self.cat_lists[contract_name].item(0).data(Qt.UserRole)

            item_mapping = {}
            for m_item in self.m_items:
                lst = self.item_lists[m_item][contract_name]
                if lst.count() > 0:
                    item_mapping[m_item] = lst.item(0).data(Qt.UserRole)

            for i in range(len(self.extra_lists)):
                if not self.extra_row_widgets[i].isVisible(): continue

                pseudo_master = None
                for c_name in self.target_contracts.keys():
                    if self.extra_lists[i][c_name].count() > 0:
                        pseudo_master = self.extra_lists[i][c_name].item(0).data(Qt.UserRole)
                        break

                if pseudo_master:
                    lst = self.extra_lists[i][contract_name]
                    if lst.count() > 0:
                        t_item = lst.item(0).data(Qt.UserRole)
                        item_mapping[pseudo_master] = t_item

            block_mapping[contract_name] = {
                'target_cat': t_cat,
                'items': item_mapping
            }
        return block_mapping


class MappingTab(QWidget):
    def __init__(self, master_dict, target_contracts):
        super().__init__()
        self.master_dict = master_dict
        self.target_contracts = target_contracts

        self.blocks = {}
        self.extra_cat_lists = {}
        self.extra_cat_widgets = []

        self.global_cat_groups = {}
        self.global_item_groups = {}

        self.build_global_groups()
        self.init_ui()
        self.populate_ai_data()

    def build_global_groups(self):
        """Pre-calculates exact Target-to-Target matches upfront."""
        for c_info in self.target_contracts.values():
            for cat, items in c_info['data'].items():
                self.global_cat_groups[cat] = str(cat).lower().strip()
                for item in items:
                    self.global_item_groups[item] = str(item).lower().strip()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        info = QLabel(
            "<b>Sleep de categorieën en items om ze te koppelen aan de Master.</b><br>"
            "De score tussen haakjes toont hoe goed het item past bij de Master rij waar het in zit. "
            "Items met een ⚠️ icoon hebben een erg lage AI score en horen mogelijk thuis in een Extra rij."
        )
        info.setFrameShape(QFrame.StyledPanel)
        info.setMargin(10)
        main_layout.addWidget(info)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(0)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 10)

        lbl_master = QLabel("Master (Contract 1)")
        lbl_master.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lbl_master.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(lbl_master, stretch=1)

        for contract_name in self.target_contracts.keys():
            lbl = QLabel(contract_name)
            lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            lbl.setStyleSheet("font-weight: bold; font-size: 14px;")
            header_layout.addWidget(lbl, stretch=1)

        scroll_layout.addLayout(header_layout)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("color: #aaa;")
        scroll_layout.addWidget(separator)

        for m_cat, m_items in self.master_dict.items():
            block = CategoryMappingBlock(m_cat, m_items, self.target_contracts, self.global_item_groups)
            self.blocks[m_cat] = block
            scroll_layout.addWidget(block)

        unmapped_widget = QWidget()
        self.unmapped_layout = QVBoxLayout(unmapped_widget)
        self.unmapped_layout.setContentsMargins(0, 20, 0, 0)

        lbl_unmapped_head = QLabel("🚫 Extra Categorieën (Niet in Master):")
        lbl_unmapped_head.setStyleSheet("font-weight: bold;")
        self.unmapped_layout.addWidget(lbl_unmapped_head)

        self.add_extra_cat_row()

        scroll_layout.addWidget(unmapped_widget)
        scroll_layout.addStretch()

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

    def add_extra_cat_row(self):
        i = len(self.extra_cat_lists)
        self.extra_cat_lists[i] = {}

        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)

        lbl_container = QWidget()
        lbl_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        l_layout = QHBoxLayout(lbl_container)
        l_layout.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel("Extra Categorie")
        lbl.setStyleSheet("color: #aaa;")
        l_layout.addWidget(lbl)
        row_layout.addWidget(lbl_container, stretch=1)

        for contract_name in self.target_contracts.keys():
            lst = ColumnRestrictedList(column_id=contract_name, is_unmapped=True, is_category=True)
            lst.itemsChanged.connect(lambda: QTimer.singleShot(0, self.ensure_empty_extra_cat_row))
            lst.itemsChanged.connect(lambda: QTimer.singleShot(0, self.refresh_cat_scores))
            self.extra_cat_lists[i][contract_name] = lst
            row_layout.addWidget(lst, stretch=1)

        self.unmapped_layout.addWidget(row_widget)
        self.extra_cat_widgets.append(row_widget)

    def ensure_empty_extra_cat_row(self):
        empty_indices = []
        for i in range(len(self.extra_cat_lists)):
            is_empty = all(self.extra_cat_lists[i][c].count() == 0 for c in self.target_contracts.keys())
            if is_empty:
                empty_indices.append(i)

        for idx in empty_indices:
            self.extra_cat_widgets[idx].setVisible(False)

        if empty_indices:
            idx_to_show = empty_indices[0]
            widget = self.extra_cat_widgets[idx_to_show]
            self.unmapped_layout.removeWidget(widget)
            self.unmapped_layout.addWidget(widget)
            widget.setVisible(True)
        else:
            self.add_extra_cat_row()

    def get_or_create_empty_cat_row(self):
        for i in range(len(self.extra_cat_lists)):
            is_empty = all(self.extra_cat_lists[i][c].count() == 0 for c in self.target_contracts.keys())
            if is_empty:
                if not self.extra_cat_widgets[i].isVisible():
                    self.unmapped_layout.removeWidget(self.extra_cat_widgets[i])
                    self.unmapped_layout.addWidget(self.extra_cat_widgets[i])
                    self.extra_cat_widgets[i].setVisible(True)
                return i

        self.add_extra_cat_row()
        return len(self.extra_cat_lists) - 1

    def populate_ai_data(self):
        unmapped_cats = []

        for contract_name, contract_info in self.target_contracts.items():
            target_dict = contract_info['data']
            ai_mapping = contract_info['ai']

            cat_candidates = []
            for t_cat in target_dict.keys():
                cat_match_info = ai_mapping['categories'].get(t_cat, {})
                best_m_cat = cat_match_info.get('best_match')
                score = cat_match_info.get('scores', {}).get(best_m_cat, 0.0) if best_m_cat else 0.0
                cat_candidates.append({'t_cat': t_cat, 'm_cat': best_m_cat, 'score': score})

            cat_candidates.sort(key=lambda x: x['score'], reverse=True)

            for candidate in cat_candidates:
                t_cat = candidate['t_cat']
                best_m_cat = candidate['m_cat']
                score = candidate['score']

                item_widget = QListWidgetItem(t_cat)
                item_widget.setData(Qt.UserRole, t_cat)

                # Use the new MATCH_THRESHOLD
                if best_m_cat and score >= MATCH_THRESHOLD and self.blocks[best_m_cat].cat_lists[
                    contract_name].count() == 0:
                    self.blocks[best_m_cat].cat_lists[contract_name].addItem(item_widget)
                else:
                    unmapped_cats.append((contract_name, t_cat))

            for block in self.blocks.values():
                block.update_items(contract_name)

        for contract_name, t_cat in unmapped_cats:
            group_id = self.global_cat_groups.get(t_cat)
            placed = False

            for i in range(len(self.extra_cat_lists)):
                if not self.extra_cat_widgets[i].isVisible(): continue
                row_belongs_to_group = False

                for other_contract in self.target_contracts.keys():
                    lst = self.extra_cat_lists[i][other_contract]
                    if lst.count() > 0:
                        existing_val = lst.item(0).data(Qt.UserRole)
                        if self.global_cat_groups.get(existing_val) == group_id:
                            row_belongs_to_group = True
                            break

                if row_belongs_to_group and self.extra_cat_lists[i][contract_name].count() == 0:
                    widget = QListWidgetItem(t_cat)
                    widget.setData(Qt.UserRole, t_cat)
                    self.extra_cat_lists[i][contract_name].addItem(widget)
                    placed = True
                    break

            if not placed:
                idx = self.get_or_create_empty_cat_row()
                widget = QListWidgetItem(t_cat)
                widget.setData(Qt.UserRole, t_cat)
                self.extra_cat_lists[idx][contract_name].addItem(widget)

        self.ensure_empty_extra_cat_row()
        self.refresh_cat_scores()

    def refresh_cat_scores(self):
        """Updates the visible text on the categories to show AI scores based on their row."""
        for contract_name in self.target_contracts.keys():
            ai_mapping = self.target_contracts[contract_name]['ai']

            # Master Categories
            for m_cat, block in self.blocks.items():
                lst = block.cat_lists[contract_name]
                if lst.count() > 0:
                    widget = lst.item(0)
                    t_cat = widget.data(Qt.UserRole)
                    score = ai_mapping['categories'].get(t_cat, {}).get('scores', {}).get(m_cat, 0.0)

                    if score >= MATCH_THRESHOLD:
                        widget.setText(f"⭐ {t_cat} ({score:.2f})")
                        widget.setToolTip(f"Good Match vs Master '{m_cat}'")
                    else:
                        widget.setText(f"⚠️ {t_cat} ({score:.2f})")
                        widget.setToolTip(f"Poor Match vs Master '{m_cat}'. Consider moving to Extra categorieën.")

            # Extra Categories
            for i in range(len(self.extra_cat_lists)):
                if not self.extra_cat_widgets[i].isVisible(): continue
                lst = self.extra_cat_lists[i][contract_name]
                if lst.count() > 0:
                    widget = lst.item(0)
                    t_cat = widget.data(Qt.UserRole)
                    widget.setText(f"🔗 {t_cat} (Exact)")
                    widget.setToolTip("Gegroepeerd via exacte naam overeenkomst met andere targets")

    def extract_final_mapping(self):
        final_mapping = {name: {} for name in self.target_contracts.keys()}

        for contract_name in self.target_contracts.keys():
            for m_cat, block in self.blocks.items():
                block_mapping = block.get_mapping()[contract_name]
                if block_mapping['target_cat'] or block_mapping['items']:
                    final_mapping[contract_name][m_cat] = block_mapping

        for i in range(len(self.extra_cat_lists)):
            if not self.extra_cat_widgets[i].isVisible(): continue

            pseudo_master_cat = None
            for c_name in self.target_contracts.keys():
                if self.extra_cat_lists[i][c_name].count() > 0:
                    pseudo_master_cat = self.extra_cat_lists[i][c_name].item(0).data(Qt.UserRole)
                    break

            if pseudo_master_cat:
                for c_name in self.target_contracts.keys():
                    if self.extra_cat_lists[i][c_name].count() > 0:
                        t_cat = self.extra_cat_lists[i][c_name].item(0).data(Qt.UserRole)
                        final_mapping[c_name][pseudo_master_cat] = {
                            'target_cat': t_cat,
                            'items': {}
                        }

        return final_mapping