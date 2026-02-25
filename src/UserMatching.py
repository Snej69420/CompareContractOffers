import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame, QGridLayout,
    QListWidget, QAbstractItemView, QListWidgetItem, QGroupBox, QPushButton
)
from PySide6.QtCore import Qt


class ColumnRestrictedList(QListWidget):
    """A custom QListWidget that swaps items instead of stacking them."""

    def __init__(self, column_id, is_unmapped=False):
        super().__init__()
        self.column_id = column_id
        self.is_unmapped = is_unmapped

        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setAcceptDrops(True)

        # Sizing to make drop zones clear
        if self.is_unmapped:
            self.setMinimumHeight(100)
        else:
            self.setFixedHeight(45)  # Keep mapped slots small to visually enforce 1-item capacity

        # Use native frame styling that automatically respects Light/Dark OS modes
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Sunken)

    def dragEnterEvent(self, event):
        source = event.source()
        if isinstance(source, ColumnRestrictedList) and source.column_id == self.column_id:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        source = event.source()

        # Don't do anything if dropping in the exact same list
        if source == self:
            super().dropEvent(event)
            return

        if isinstance(source, ColumnRestrictedList) and source.column_id == self.column_id:
            item_to_swap_back = None

            # If we are dropping into a standard match slot that already has an item, prepare to swap
            if not self.is_unmapped and self.count() > 0:
                item_to_swap_back = self.takeItem(0)

            # Let Qt handle moving the dragged item into this list
            super().dropEvent(event)

            # If there was an item here, throw it back to wherever the new item came from
            if item_to_swap_back:
                source.addItem(item_to_swap_back)
        else:
            event.ignore()


class MappingTab(QWidget):
    def __init__(self, master_dict, target_contracts):
        super().__init__()
        self.master_dict = master_dict
        self.target_contracts = target_contracts

        self.cat_lists = {}
        self.cat_unmapped = {}

        self.item_lists = {}
        self.item_unmapped = {}

        self.init_ui()
        self.populate_ai_data()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        info = QLabel(
            "<b>Sleep de items om ze te koppelen.</b><br>"
            "Je kunt items alleen verticaal verplaatsen binnen hun eigen contractkolom. "
            "Plaats items in het 'Geen Match' vak onderaan als ze niet in de Master thuishoren.<br>"
            "<i>(Als je een item op een ander item sleept, wisselen ze automatisch van plek)</i>"
        )
        # Using a slight frame instead of hardcoded background colors for OS theme compatibility
        info.setFrameShape(QFrame.StyledPanel)
        info.setMargin(10)
        main_layout.addWidget(info)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # --- 1. CATEGORY BOARD ---
        cat_group = QGroupBox("1. Categorieën Koppelen")
        font = cat_group.font()
        font.setBold(True)
        cat_group.setFont(font)

        cat_layout = QGridLayout(cat_group)
        self.build_grid_headers(cat_layout)

        row_idx = 1
        for m_cat in self.master_dict.keys():
            lbl = QLabel(f"📁 {m_cat}")
            cat_layout.addWidget(lbl, row_idx, 0)

            self.cat_lists[m_cat] = {}
            for col_idx, contract_name in enumerate(self.target_contracts.keys(), start=1):
                lst = ColumnRestrictedList(column_id=contract_name)
                self.cat_lists[m_cat][contract_name] = lst
                cat_layout.addWidget(lst, row_idx, col_idx)
            row_idx += 1

        cat_layout.addWidget(self.create_unmapped_label(), row_idx, 0)
        for col_idx, contract_name in enumerate(self.target_contracts.keys(), start=1):
            lst = ColumnRestrictedList(column_id=contract_name, is_unmapped=True)
            self.cat_unmapped[contract_name] = lst
            cat_layout.addWidget(lst, row_idx, col_idx)

        scroll_layout.addWidget(cat_group)
        scroll_layout.addWidget(QLabel(" "))  # Spacer

        # --- 2. ITEM BOARD ---
        item_group = QGroupBox("2. Items Koppelen")
        item_group.setFont(font)
        item_layout = QGridLayout(item_group)
        self.build_grid_headers(item_layout)

        row_idx = 1
        for m_cat, m_items in self.master_dict.items():
            lbl_cat = QLabel(f"--- {m_cat} ---")
            cat_font = lbl_cat.font()
            cat_font.setItalic(True)
            lbl_cat.setFont(cat_font)
            item_layout.addWidget(lbl_cat, row_idx, 0)
            row_idx += 1

            for m_item in m_items:
                lbl = QLabel(f"↳ {m_item}")
                item_layout.addWidget(lbl, row_idx, 0)

                self.item_lists[m_item] = {}
                for col_idx, contract_name in enumerate(self.target_contracts.keys(), start=1):
                    lst = ColumnRestrictedList(column_id=contract_name)
                    self.item_lists[m_item][contract_name] = lst
                    item_layout.addWidget(lst, row_idx, col_idx)
                row_idx += 1

        item_layout.addWidget(self.create_unmapped_label(), row_idx, 0)
        for col_idx, contract_name in enumerate(self.target_contracts.keys(), start=1):
            lst = ColumnRestrictedList(column_id=contract_name, is_unmapped=True)
            self.item_unmapped[contract_name] = lst
            item_layout.addWidget(lst, row_idx, col_idx)

        scroll_layout.addWidget(item_group)
        scroll_layout.addStretch()

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

    def build_grid_headers(self, grid_layout):
        lbl_master = QLabel("Master (Contract 1)")
        f = lbl_master.font()
        f.setBold(True)
        lbl_master.setFont(f)
        grid_layout.addWidget(lbl_master, 0, 0)

        for col_idx, contract_name in enumerate(self.target_contracts.keys(), start=1):
            lbl = QLabel(contract_name)
            lbl.setFont(f)
            lbl.setAlignment(Qt.AlignCenter)
            grid_layout.addWidget(lbl, 0, col_idx)

    def create_unmapped_label(self):
        lbl = QLabel("🚫 Geen Match\n(Unmapped)")
        f = lbl.font()
        f.setBold(True)
        lbl.setFont(f)
        lbl.setAlignment(Qt.AlignCenter)
        return lbl

    def populate_ai_data(self):
        """Places items based on AI scores, ensuring 1-to-1 matching initially."""
        for contract_name, contract_info in self.target_contracts.items():
            target_dict = contract_info['data']
            ai_mapping = contract_info['ai']

            # 1. Populate Categories
            for t_cat in target_dict.keys():
                cat_match_info = ai_mapping['categories'].get(t_cat, {})
                best_m_cat = cat_match_info.get('best_match')
                score = cat_match_info.get('scores', {}).get(best_m_cat, 0.0) if best_m_cat else 0.0

                item_widget = QListWidgetItem(f"⭐ {t_cat}" if best_m_cat and score > 0.1 else t_cat)
                item_widget.setData(Qt.UserRole, t_cat)

                # Assign if good match AND the master slot is currently empty
                if best_m_cat and score > 0.1 and self.cat_lists[best_m_cat][contract_name].count() == 0:
                    self.cat_lists[best_m_cat][contract_name].addItem(item_widget)
                else:
                    # Otherwise throw to unmapped
                    self.cat_unmapped[contract_name].addItem(item_widget)

            # 2. Populate Items
            for t_cat, t_items in target_dict.items():
                for t_item in t_items:
                    best_m_item = None
                    best_score = -1

                    for m_cat in self.master_dict.keys():
                        ai_item_match = ai_mapping['items'].get(t_cat, {}).get(m_cat, {}).get(t_item, {})
                        scores = ai_item_match.get('scores', {})

                        for m_item, score in scores.items():
                            if score > best_score:
                                best_score = score
                                best_m_item = m_item

                    item_widget = QListWidgetItem(f"⭐ {t_item}" if best_m_item and best_score > 0.1 else t_item)
                    item_widget.setData(Qt.UserRole, t_item)

                    if best_m_item and best_score > 0.1 and self.item_lists[best_m_item][contract_name].count() == 0:
                        self.item_lists[best_m_item][contract_name].addItem(item_widget)
                    else:
                        self.item_unmapped[contract_name].addItem(item_widget)

    def extract_final_mapping(self):
        final_mapping = {name: {} for name in self.target_contracts.keys()}

        for contract_name in self.target_contracts.keys():
            for m_cat, m_items in self.master_dict.items():
                cat_list_widget = self.cat_lists[m_cat][contract_name]
                t_cat = None

                if cat_list_widget.count() > 0:
                    t_cat = cat_list_widget.item(0).data(Qt.UserRole)

                items_dict = {}
                for m_item in m_items:
                    item_list_widget = self.item_lists[m_item][contract_name]
                    if item_list_widget.count() > 0:
                        t_item = item_list_widget.item(0).data(Qt.UserRole)
                        items_dict[m_item] = t_item

                if t_cat or items_dict:
                    final_mapping[contract_name][m_cat] = {
                        'target_cat': t_cat,
                        'items': items_dict
                    }

        return final_mapping


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 1. Master Contract
    master_data = {
        'Grondwerken': ['Graven fundering', 'Afvoer aarde'],
        'Sanitair': ['Installatie toilet']
    }

    # 2. Target Contracts mapped into one dictionary (UPDATED TO NEW AI MATRIX FORMAT)
    target_contracts = {
        'Contract 2 (Janssens)': {
            'data': {
                'Graafwerken': ['Uitgraven sleuven'],
                'Loodgieterij': ['Plaatsen wc', 'Extra wasbak']
            },
            'ai': {
                'categories': {
                    'Graafwerken': {
                        'best_match': 'Grondwerken',
                        'scores': {'Grondwerken': 0.75, 'Sanitair': 0.22}
                    },
                    'Loodgieterij': {
                        'best_match': 'Sanitair',
                        'scores': {'Grondwerken': 0.45, 'Sanitair': 0.66}
                    }
                },
                'items': {
                    'Graafwerken': {
                        'Grondwerken': {
                            'Uitgraven sleuven': {
                                'best_match': 'Graven fundering',
                                'scores': {'Graven fundering': 0.80, 'Afvoer aarde': 0.52}
                            }
                        },
                        'Sanitair': {
                            'Uitgraven sleuven': {
                                'best_match': 'Installatie toilet',
                                'scores': {'Installatie toilet': 0.15}
                            }
                        }
                    },
                    'Loodgieterij': {
                        'Grondwerken': {
                            'Plaatsen wc': {'best_match': 'Graven fundering', 'scores': {'Graven fundering': 0.12, 'Afvoer aarde': 0.05}},
                            'Extra wasbak': {'best_match': 'Graven fundering', 'scores': {'Graven fundering': 0.10, 'Afvoer aarde': 0.08}}
                        },
                        'Sanitair': {
                            'Plaatsen wc': {
                                'best_match': 'Installatie toilet',
                                'scores': {'Installatie toilet': 0.71}
                            },
                            'Extra wasbak': {
                                'best_match': None,
                                'scores': {'Installatie toilet': 0.33}
                            }
                        }
                    }
                }
            }
        },
        'Contract 3 (Peeters)': {
            'data': {
                'Grondverzet': ['Fundering graven', 'Zand afvoeren'],
                'Badkamer': ['Toilet montage']
            },
            'ai': {
                'categories': {
                    'Grondverzet': {'best_match': 'Grondwerken', 'scores': {'Grondwerken': 0.82, 'Sanitair': 0.11}},
                    'Badkamer': {'best_match': 'Sanitair', 'scores': {'Grondwerken': 0.14, 'Sanitair': 0.78}}
                },
                'items': {
                    'Grondverzet': {
                        'Grondwerken': {
                            'Fundering graven': {'best_match': 'Graven fundering', 'scores': {'Graven fundering': 0.88, 'Afvoer aarde': 0.41}},
                            'Zand afvoeren': {'best_match': 'Afvoer aarde', 'scores': {'Graven fundering': 0.35, 'Afvoer aarde': 0.85}}
                        },
                        'Sanitair': {
                            'Fundering graven': {'best_match': 'Installatie toilet', 'scores': {'Installatie toilet': 0.10}},
                            'Zand afvoeren': {'best_match': 'Installatie toilet', 'scores': {'Installatie toilet': 0.12}}
                        }
                    },
                    'Badkamer': {
                        'Grondwerken': {
                            'Toilet montage': {'best_match': 'Graven fundering', 'scores': {'Graven fundering': 0.05, 'Afvoer aarde': 0.02}}
                        },
                        'Sanitair': {
                            'Toilet montage': {'best_match': 'Installatie toilet', 'scores': {'Installatie toilet': 0.81}}
                        }
                    }
                }
            }
        }
    }

    # 3. Launch UI
    window = MappingTab(master_data, target_contracts)
    window.resize(900, 500)  # Made it wider to accommodate 3 columns
    window.setWindowTitle("Meerdere Contracten Vergelijken")
    window.show()

    # Print Button
    btn_print = QPushButton("Print Final Mapping (Console)")
    btn_print.clicked.connect(lambda: print(window.extract_final_mapping()))
    window.layout().addWidget(btn_print)

    sys.exit(app.exec())