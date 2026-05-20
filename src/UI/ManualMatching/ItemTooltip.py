from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
)
from PySide6.QtCore import Qt

class ProductTooltip(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
        self.setObjectName("ProductTooltip")
        self.setStyleSheet("""
            #ProductTooltip {
                background: white;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(2)
        self.layout.setContentsMargins(10, 8, 10, 8)
        self.setLayout(self.layout)

        self.name_label = QLabel()
        self.name_label.setWordWrap(True)
        self.name_label.setStyleSheet("font-weight: bold; color: #1e293b;")

        self.score_label = QLabel()

        self.hint_label = QLabel("<i>Sleep of gebruik Alt+pijltjes om te verplaatsen.</i>")
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet("color: #94a3b8; font-size: 11px;")

        self.layout.addWidget(self.name_label)
        self.layout.addWidget(self.score_label)
        self.layout.addWidget(self.hint_label)
        self.layout.addStretch()

    def update_content(self, name, score, target_width):
        self.setFixedWidth(target_width)
        self.name_label.setText(name)

        score_color = "#28a745" if score >= 0.70 else "#d39e00" if score >= 0.40 else "#dc3545"
        self.score_label.setText(f"Zekerheid: <b style='color: {score_color};'>{score:.0%}</b>")
        self.adjustSize()
