import pandas as pd

class MatchItem:
    def __init__(self, raw_data: dict, original_id: int, doc_key: str):
        self.raw_data = raw_data
        name = raw_data.get('Naam', 'Onbekend')
        if pd.isna(name) or str(name).strip() == "":
            self.name = "Onbekend"
        else:
            self.name = str(name)

        # Clean quantities and units
        try:
            self.qty = float(raw_data.get('Aantal', 0))
        except (ValueError, TypeError):
            self.qty = 0.0

        self.unit = raw_data.get('unit', '')

        self.original_id = original_id
        self.doc_key = doc_key  # NEW: Tracks which document this belongs to
        self.current_score = 0.0
        self.best_match_name = ""

        self.is_qty_balanced = False
        self.is_unit_matched = False
        self.is_parked = False

    def display_text(self):
        return f"{self.name} ({self.qty} {self.unit})"