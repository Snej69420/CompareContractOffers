from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
)
from PySide6.QtCore import Qt


class ClusterTooltip(QFrame):
    def __init__(self, contractor_names, parent=None):
        super().__init__(parent)

        self.contractor_names = contractor_names

        self.setWindowFlags(
            Qt.ToolTip |
            Qt.FramelessWindowHint
        )
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.setObjectName("ClusterTooltip")
        self.setStyleSheet("""
            #ClusterTooltip {
                background: white;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
            }

            QLabel {
                color: #1e293b;
                font-size: 12px;
            }

            .header {
                font-weight: bold;
                color: #64748b;
            }
        """)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(12, 10, 12, 10)
        self.layout.setSpacing(20)

    def populate(self, doc_keys, lists, target_width):
        self.clear()
        self.setFixedWidth(target_width)

        for key in doc_keys:
            column = QVBoxLayout()
            column.setSpacing(4)
            column.setContentsMargins(0, 0, 0, 0)

            header = QLabel(self.contractor_names.get(key, key))
            header.setProperty("class", "header")
            column.addWidget(header)

            items = lists[key].get_items()
            if items:
                for item in items:
                    label = QLabel(f"• {item.name}")
                    label.setWordWrap(True)
                    column.addWidget(label)
            else:
                empty = QLabel("-")
                empty.setStyleSheet("color: #94a3b8;")
                column.addWidget(empty)

            column.addStretch()
            self.layout.addLayout(column)

        self.adjustSize()

    def clear(self):
        clear_layout(self.layout)

def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)

        if widget := item.widget():
            widget.deleteLater()

        elif child_layout := item.layout():
            clear_layout(child_layout)
            child_layout.deleteLater()