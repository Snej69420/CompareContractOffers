from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal
from src.UI.DragDropList import DragDropList

class MatchBucket(QWidget):
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
            lst = DragDropList(column_id=c_name)
            lst.itemsChanged.connect(self.bucketChanged.emit)
            self.lists[c_name] = lst
            row_layout.addWidget(lst, stretch=1)

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "MatchBucketWidget { background-color: rgba(128, 128, 128, 0.1); border: 1px solid rgba(128, 128, 128, 0.4); border-radius: 6px; margin-bottom: 5px; }"
        )

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