import re
import unicodedata
from typing import Any
import pandas as pd
from nltk.stem.snowball import SnowballStemmer

class TextNormalizer:
    """Handles deep NLP cleaning, stemming, and unit standardization."""

    UNIT_MAP = {
        'm2': 'm2', 'vkm': 'm2', 'sqm': 'm2', 'm²': 'm2',
        'm3': 'm3', 'kub': 'm3', 'kuub': 'm3', 'm³': 'm3',
        'lm': 'm', 'lopende meter': 'm', 'm1': 'm',
        'st': 'st', 'stuks': 'st', 'pce': 'st', 'pc': 'st',
        'ff': 'ff', 'sog': 'ff', "s.o.g.": 'ff',
        'kg': 'kg', 'kilogram': 'kg', 'ton': 't'
    }

    STOP_WORDS = {
        'leveren', 'plaatsen', 'voorzien', 'nodige', 'volgens', 'beschrijving', 'een',
        'type', 'inclusief', 'exclusief', 'met', 'van', 'voor', 'het', 'en', 'de', 'in',
        'bestaande', 'uit', 'wordt', 'geleverd', 'geplaatst'
    }

    stemmer = SnowballStemmer("dutch")

    @classmethod
    def normalize_unit(cls, unit_str: Any) -> str:
        if pd.isna(unit_str):
            return ""
        u = str(unit_str).lower().strip().replace(" ", "")
        return cls.UNIT_MAP.get(u, u)

    @staticmethod
    def extract_dimensions(text: str) -> set[tuple[float, str]]:
        """
        Finds explicit measurements like '142 mm', '2,6mm', 'Ø 100'.
        Returns a set of tuples, e.g., {(142.0, 'mm'), (2.6, 'mm')}
        """
        if pd.isna(text):
            return set()

        text = str(text).lower()
        dimensions = set()

        # Regex explanation:
        # (\d+(?:[.,]\d+)?) catches numbers like 142, 2.6, or 2,6
        # \s* catches optional spaces
        # (mm|cm|ø|diameter) catches the dimension unit
        pattern = r'(?:ø|diameter\s*)?(\d+(?:[.,]\d+)?)\s*(mm|cm|ø)'

        matches = re.findall(pattern, text)
        for val, unit in matches:
            # Clean comma decimals to dots for Python floats
            clean_val = float(val.replace(',', '.'))
            dimensions.add((clean_val, unit))

        return dimensions

    @staticmethod
    def check_dimension_clash(dims_a: set[tuple[float, str]], dims_b: set[tuple[float, str]]) -> bool:
        """
        Returns True if the items have conflicting physical dimensions.
        """
        if not dims_a or not dims_b:
            return False  # Not enough info to force a clash

        # If they share the exact same dimension (e.g., both are 100mm), no clash
        if dims_a.intersection(dims_b):
            return False

        # If they use the same unit (e.g., both use 'mm') but the values didn't match, it's a clash!
        units_a = {u for v, u in dims_a}
        units_b = {u for v, u in dims_b}
        shared_units = units_a.intersection(units_b)

        if shared_units:
            return True

        return False

    @classmethod
    def get_clean_tokens(cls, text: str) -> list[str]:
        if pd.isna(text):
            return []

        text = str(text).lower()
        # Remove accents
        text = "".join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))
        # Replace structural punctuation with spaces
        text = re.sub(r'[/\\,\-_|]', ' ', text)
        # Separate numbers from letters (e.g., 10m -> 10 m)
        text = re.sub(r'(\d+)([a-zA-Z]+)', r'\1 \2', text)
        text = re.sub(r'([a-zA-Z]+)(\d+)', r'\1 \2', text)

        words = text.split()
        return [cls.stemmer.stem(w) for w in words if w not in cls.STOP_WORDS]
