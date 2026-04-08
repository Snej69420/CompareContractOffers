import re
import unicodedata
import pandas as pd

class TextNormalizer:
    UNIT_MAP = {
        'm2': 'm2', 'vkm': 'm2', 'sqm': 'm2', 'm²': 'm2',
        'm3': 'm3', 'kub': 'm3', 'kuub': 'm3', 'm³': 'm3',
        'lm': 'm', 'lopende meter': 'm', 'm1': 'm',
        'st': 'st', 'stuks': 'st', 'pce': 'st', 'pc': 'st',
        'ff': 'ff', 'sog': 'ff', "s.o.g.": 'ff',
        'kg': 'kg', 'kilogram': 'kg', 'ton': 't'
    }

    STOP_WORDS = {
        'leveren', 'plaatsen', 'voorzien', 'nodige', 'volgens', 'beschrijving', 'een'
        'type', 'inclusief', 'exclusief', 'met', 'van', 'voor', 'het', 'en', 'de', 'in',
    }

    @classmethod
    def normalize_unit(cls, unit_str):
        if not unit_str or pd.isna(unit_str): return ""
        u = str(unit_str).lower().strip().replace(" ", "")
        return cls.UNIT_MAP.get(u, u)

    @classmethod
    def clean_text(cls, text):
        if not text or str(text).lower() == 'nan': return ""

        # 1. Maak van hoofdletters kleine letters en verwijder accenten
        text = str(text).lower()
        text = "".join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))

        # 2. vervang ;,/: en dergelijke door een spatie
        text = re.sub(r'[/\\,\-_|]', ' ', text)

        # 3. Verwijder stop woorden
        words = text.split()
        cleaned_words = [w for w in words if w not in cls.STOP_WORDS]

        # 4. Verwijder onnodige witte ruimte
        return " ".join(cleaned_words).strip()