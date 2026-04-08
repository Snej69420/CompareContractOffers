from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt

class ProductLabel(QLabel):
    def __init__(self, text, *args, **kwargs):
        super().__init__(text, *args, **kwargs)
        self.full_text = text

    def resizeEvent(self, event):
        fm = self.fontMetrics()
        elided_text = fm.elidedText(self.full_text, Qt.ElideRight, self.width() - 5)
        self.setText(elided_text)
        super().resizeEvent(event)