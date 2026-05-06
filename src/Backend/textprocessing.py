import re
import unicodedata
from typing import Any
import pandas as pd
from nltk.stem.snowball import SnowballStemmer

class TextNormalizer:
    """
    Handles deep NLP cleaning, stemming, and unit standardization.
    Strips action verbs (leveren, plaatsen) to prevent BM25 score inflation.
    """

    UNIT_MAP = {
        'm2': 'm²', 'vkm': 'm²', 'sqm': 'm²', 'm²': 'm²',
        'm3': 'm³', 'kub': 'm³', 'kuub': 'm³', 'm³': 'm³',
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
        Extracts measurements.
        Dual-Regex: Catches prefix (Ø 40) AND suffix (40mm).
        Normalizes all length units (cm, Ø, dia) to 'mm' for unified baseline.
        """
        if pd.isna(text):
            return set()

        text = str(text).lower()
        raw_dimensions = set()

        # Suffix catch (e.g., "142mm", "2,6 cm", "100 dia")
        suffix_pattern = r'(\d+(?:[.,]\d+)?)\s*(mm|cm|ø|dia|diameter)'
        for val, raw_unit in re.findall(suffix_pattern, text):
            raw_dimensions.add((val, raw_unit))

        # Prefix catch (e.g., "Ø 40", "dia 100")
        prefix_pattern = r'(ø|diameter|dia)\s*(\d+(?:[.,]\d+)?)'
        for raw_unit, val in re.findall(prefix_pattern, text):
            raw_dimensions.add((val, raw_unit))

        cleaned_dims = set()
        for val_str, raw_unit in raw_dimensions:
            clean_val = float(val_str.replace(',', '.'))
            u = raw_unit.strip()

            # Normalize to mm
            if u == 'cm':
                clean_val *= 10.0
                u = 'mm'
            elif u in ['ø', 'dia', 'diameter']:
                u = 'mm'

            cleaned_dims.add((clean_val, u))

        return cleaned_dims

    @staticmethod
    def check_dimension_clash(dims_a: set[tuple[float, str]], dims_b: set[tuple[float, str]]) -> bool:
        """
        Checks for numeric clashes.
        Magnitude Classification: Prevents 'Thickness' (<10mm) clashing with 'Width' (>10mm).
        E.g., Stops 1.5mm aluminum plate from destroying match with 50mm profile.
        """
        if not dims_a or not dims_b:
            return False

        if dims_a.intersection(dims_b):
            return False

        units_a = {u for v, u in dims_a}
        units_b = {u for v, u in dims_b}
        shared_units = units_a.intersection(units_b)

        if not shared_units:
            return False

        for unit in shared_units:
            vals_a = [v for v, u in dims_a if u == unit]
            vals_b = [v for v, u in dims_b if u == unit]

            # Separate into Large (>10) and Small (<10)
            a_large = [v for v in vals_a if v >= 10.0]
            a_small = [v for v in vals_a if v < 10.0]
            b_large = [v for v in vals_b if v >= 10.0]
            b_small = [v for v in vals_b if v < 10.0]

            # Backend Large vs Large
            if a_large and b_large:
                has_close = False
                for va in a_large:
                    for vb in b_large:
                        # Tolerance: 30mm or 25% (Allows standard pipe jumps 75->100)
                        tolerance = max(30.0, 0.25 * max(va, vb))
                        if abs(va - vb) <= tolerance:
                            has_close = True
                            break
                    if has_close: break
                if not has_close: return True # CLASH

            # Backend Small vs Small
            if a_small and b_small:
                has_close = False
                for va in a_small:
                    for vb in b_small:
                        # Tolerance: 1.0mm or 15% (Strict on sheet metal / foil)
                        tolerance = max(1.0, 0.15 * max(va, vb))
                        if abs(va - vb) <= tolerance:
                            has_close = True
                            break
                    if has_close: break
                if not has_close: return True # CLASH

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