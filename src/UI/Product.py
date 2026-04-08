from PySide6.QtWidgets import QListWidgetItem
from PySide6.QtCore import Qt

class Product(QListWidgetItem):
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
                f"Originele Categorie: {self.orig_cat}\nVolledige naam:\n{self.orig_name}\n\n🧑‍🔧 Handmatig geplaatst."
            )
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