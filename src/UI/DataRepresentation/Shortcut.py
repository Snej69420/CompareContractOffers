from PySide6.QtWidgets import  QVBoxLayout, QHBoxLayout, QPushButton, QDialog, QLabel
from PySide6.QtCore import Qt

class ShortcutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sneltoetsen Overzicht")
        self.setFixedSize(450, 320)

        # Removes the native Windows '?' help button from the title bar
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setStyleSheet("QDialog { background-color: #ffffff; }")

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # --- CSS for the Keyboard Keys ---
        # This creates a grey box with a border, rounded corners, and a slight shadow effect
        k_style = (
            "background-color: #f5f5f5; color: #333333; border: 1px solid #cccccc; "
            "border-bottom: 2px solid #aaaaaa; border-radius: 4px; padding: 2px 6px; "
            "font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: bold;"
        )

        # We use clean HTML entities (&uarr; &darr;) instead of emojis!
        info_text = f"""
        <h3 style='color: #222; margin-bottom: 5px; font-size: 16px;'>Toetsenbord Navigatie</h3>
        <p style='color: #555; font-size: 13px; margin-bottom: 15px;'>
            Je hoeft je muis nauwelijks te gebruiken. Focus op een lijst en gebruik de pijltjestoetsen om overal te komen.
        </p>
        <table style='font-size: 13px;' cellspacing='10'>
            <tr>
                <td align='right'><span style='{k_style}'>Ctrl</span> + <span style='{k_style}'>N</span></td>
                <td style='padding-left: 10px; color: #444;'>Nieuwe cluster toevoegen</td>
            </tr>
            <tr>
                <td align='right'><span style='{k_style}'>Shift</span> + <span style='{k_style}'>Del</span></td>
                <td style='padding-left: 10px; color: #444;'>Huidige cluster verwijderen</td>
            </tr>
            <tr>
                <td align='right'><span style='{k_style}'>Ctrl</span> + <span style='{k_style}'>&uarr;</span> / <span style='{k_style}'>&darr;</span></td>
                <td style='padding-left: 10px; color: #444;'>Verplaats item naar boven/onder</td>
            </tr>
            <tr>
                <td align='right'><span style='{k_style}'>Del</span></td>
                <td style='padding-left: 10px; color: #444;'>Verwijder item (naar ongekoppeld)</td>
            </tr>
            <tr>
                <td align='right'>
                    <span style='{k_style}'>&larr;</span> <span style='{k_style}'>&uarr;</span> <span style='{k_style}'>&darr;</span> <span style='{k_style}'>&rarr;</span>
                </td>
                <td style='padding-left: 10px; color: #444;'>Navigeer vrij door items en clusters</td>
            </tr>
        </table>
        """

        label = QLabel(info_text)
        label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(label)

        # A clean close button
        close_btn = QPushButton("Begrepen")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff; color: white; font-weight: bold;
                border-radius: 5px; padding: 8px 20px;
            }
            QPushButton:hover { background-color: #0069d9; }
        """)
        close_btn.clicked.connect(self.accept)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)