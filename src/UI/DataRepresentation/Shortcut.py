from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QPushButton, QDialog, QLabel
from PySide6.QtCore import Qt

class ShortcutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sneltoetsen Overzicht")
        # Increased height from 320 to 420 to fit the new shortcuts
        self.setFixedSize(460, 420)

        # Removes the native Windows '?' help button from the title bar
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setStyleSheet("QDialog { background-color: #ffffff; }")

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # --- CSS for the Keyboard Keys ---
        k_style = (
            "background-color: #f5f5f5; color: #333333; border: 1px solid #cccccc; "
            "border-bottom: 2px solid #aaaaaa; border-radius: 4px; padding: 2px 6px; "
            "font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: bold;"
        )

        info_text = f"""
        <h3 style='color: #222; margin-bottom: 5px; font-size: 16px;'>Toetsenbord Navigatie & Selectie</h3>
        <p style='color: #555; font-size: 13px; margin-bottom: 15px;'>
            Je hoeft je muis nauwelijks te gebruiken. Focus op een lijst en gebruik deze sneltoetsen:
        </p>
        <table style='font-size: 13px;' cellspacing='10'>
            <tr>
                <td align='right'>
                    <span style='{k_style}'>&larr;</span> <span style='{k_style}'>&uarr;</span> <span style='{k_style}'>&darr;</span> <span style='{k_style}'>&rarr;</span>
                </td>
                <td style='padding-left: 10px; color: #444;'>Navigeer vrij door items en clusters</td>
            </tr>
            <tr>
                <td align='right'><span style='{k_style}'>Shift</span> + <span style='{k_style}'>&uarr;</span> / <span style='{k_style}'>&darr;</span></td>
                <td style='padding-left: 10px; color: #444;'>Selecteer een reeks items</td>
            </tr>
            <tr>
                <td align='right'><span style='{k_style}'>Ctrl</span> + <span style='{k_style}'>Spatie</span></td>
                <td style='padding-left: 10px; color: #444;'>Selecteer of deselecteer losse items</td>
            </tr>
            <tr>
                <td align='right'><span style='{k_style}'>Alt</span> + <span style='{k_style}'>&uarr;</span> / <span style='{k_style}'>&darr;</span></td>
                <td style='padding-left: 10px; color: #444;'>Verplaats geselecteerde item(s)</td>
            </tr>
            <tr>
                <td align='right'><span style='{k_style}'>Del</span> of <span style='{k_style}'>Back</span></td>
                <td style='padding-left: 10px; color: #444;'>Verwijder item(s) (naar ongekoppeld)</td>
            </tr>
            <tr>
                <td align='right'><span style='{k_style}'>Ctrl</span> + <span style='{k_style}'>N</span></td>
                <td style='padding-left: 10px; color: #444;'>Nieuwe cluster toevoegen</td>
            </tr>
            <tr>
                <td align='right'><span style='{k_style}'>Shift</span> + <span style='{k_style}'>Del</span></td>
                <td style='padding-left: 10px; color: #444;'>Huidige cluster verwijderen</td>
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