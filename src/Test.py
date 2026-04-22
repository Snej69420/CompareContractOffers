import os
import random
import re
import unicodedata
from pathlib import Path
from typing import Any


import torch
import pandas as pd
import numpy as np

from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer, util
from nltk.stem.snowball import SnowballStemmer


class ContractLoader:
    """Handles reading and initial formatting of the contract templates."""

    @staticmethod
    def load_excel(file_path: Path, skiprows: int = 9) -> pd.DataFrame:
        df = pd.read_excel(file_path, skiprows=skiprows)
        df = df.dropna(subset=['Categorie', 'Naam']).reset_index(drop=True)
        # Ensure numeric columns are clean
        df['Aantal'] = pd.to_numeric(df['Aantal'], errors='coerce').fillna(0.0)
        return df


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


seed = 42
os.environ['PYTHONHASHSEED'] = str(seed)
random.seed(seed)
np.random.seed(seed)
torch.manual_seed(seed)
if torch.cuda.is_available():
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


class ScoringEngine:
    def __init__(self, threshold: float = 0.45):
        self.threshold = threshold
        self.lump_sum_units = {'ff', ''}
        print("Loading Semantic AI Model...")
        self.ai_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        self.BM25_WEIGHT = 0.50
        self.SEMANTIC_WEIGHT = 0.50

    def match(self, df_a: pd.DataFrame, df_b: pd.DataFrame) -> list[dict]:
        docs_a_raw = (df_a['Categorie'].astype(str) + " " + df_a['Naam'].astype(str)).tolist()
        docs_b_raw = (df_b['Categorie'].astype(str) + " " + df_b['Naam'].astype(str)).tolist()

        tokens_a = [TextNormalizer.get_clean_tokens(doc) for doc in docs_a_raw]
        tokens_b = [TextNormalizer.get_clean_tokens(doc) for doc in docs_b_raw]

        bm25 = BM25Okapi(tokens_b)

        embs_a = self.ai_model.encode(docs_a_raw, convert_to_tensor=True)
        embs_b = self.ai_model.encode(docs_b_raw, convert_to_tensor=True)
        semantic_matrix = util.cos_sim(embs_a, embs_b).cpu().numpy()

        scoring_matrix = []
        global_max_bm25 = max([max(bm25.get_scores(q)) for q in tokens_a if len(bm25.get_scores(q)) > 0] + [1.0])

        for i, query_tokens in enumerate(tokens_a):
            raw_bm25_scores = bm25.get_scores(query_tokens)
            for j, bm25_score in enumerate(raw_bm25_scores):
                norm_bm25 = bm25_score / global_max_bm25
                sem_score = semantic_matrix[i][j]
                hybrid_score = (norm_bm25 * self.BM25_WEIGHT) + (sem_score * self.SEMANTIC_WEIGHT)

                row_a, row_b = df_a.iloc[i], df_b.iloc[j]
                final_score = self._apply_guardrails(hybrid_score, row_a, row_b)

                if final_score >= self.threshold:
                    scoring_matrix.append({"id_a": i, "id_b": j, "final_score": final_score})

        scoring_matrix.sort(key=lambda x: (x["final_score"], x["id_a"], x["id_b"]), reverse=True)
        return self._build_clusters(scoring_matrix, df_a, df_b)

    def _apply_guardrails(self, base_score: float, row_a: pd.Series, row_b: pd.Series) -> float:
        t_unit = TextNormalizer.normalize_unit(row_a.get('Eenheid', ''))
        m_unit = TextNormalizer.normalize_unit(row_b.get('Eenheid', ''))
        is_lump_sum = (t_unit in self.lump_sum_units) or (m_unit in self.lump_sum_units)

        try:
            t_qty, m_qty = float(row_a.get('Aantal', 0)), float(row_b.get('Aantal', 0))
        except:
            t_qty, m_qty = 0, 0

        penalty, bonus = 0.0, 0.0

        # 1. UNIT PENALTY
        if not is_lump_sum and t_unit and m_unit and t_unit != m_unit:
            penalty -= 0.30

        # 2. EXACT QUANTITY BONUS (NERFED & STRICTER)
        # Raised the semantic gate to 0.40 and lowered the bonus to +0.10.
        # This prevents "3.0 st" from overpowering actual text matches.
        if base_score > 0.40:
            if not is_lump_sum and t_qty > 2.5 and m_qty > 2.5:
                max_q = max(t_qty, m_qty)
                if (abs(t_qty - m_qty) / max_q) < 0.01:
                    bonus += 0.10

        return max(0.0, min(base_score + penalty + bonus, 1.0))


    def _build_clusters(self, sorted_matrix: list[dict], df_a: pd.DataFrame, df_b: pd.DataFrame) -> list[dict]:
        node_to_cluster = {}
        clusters = {}
        cluster_counter = 0

        fulfilled_a = {i: 0.0 for i in range(len(df_a))}
        fulfilled_b = {j: 0.0 for j in range(len(df_b))}
        best_scores_a = {}

        for match in sorted_matrix:
            i, j = match["id_a"], match["id_b"]
            score = match["final_score"]
            qty_a = float(df_a.iloc[i].get('Aantal', 0.0))
            qty_b = float(df_b.iloc[j].get('Aantal', 0.0))

            unit_a = TextNormalizer.normalize_unit(df_a.iloc[i].get('Eenheid', ''))
            is_lump_a = (unit_a in self.lump_sum_units)

            a_is_full = False if is_lump_a else (fulfilled_a[i] >= (qty_a - 0.01))
            b_is_full = (fulfilled_b[j] >= (qty_b - 0.01)) if qty_b > 0 else (fulfilled_b[j] >= 1.0)

            # --- COMPANION ITEM EXCEPTION ---
            # If items share the exact same quantity, they might be parallel operations
            # (e.g., placing the roof edge AND sealing the roof edge).
            # We allow an empty item to pair with a full item so they cluster together.
            is_companion = False
            if qty_a > 0 and abs(qty_a - qty_b) < 0.01:
                # If the quantity is a highly specific decimal (e.g., 104.93), it's a signature.
                # We can trust the number more than the semantics.
                is_signature_qty = (qty_a > 10.0) and (qty_a % 1 != 0)

                # Lower the required semantic ratio to 50% for signatures,
                # keep it strict (90%/80%) for generic integers.
                score_ratio_required = 0.50 if is_signature_qty else (0.90 if qty_a <= 2.5 else 0.80)

                if i in best_scores_a and score >= (best_scores_a[i] * score_ratio_required):
                    if a_is_full and not b_is_full:
                        is_companion = True
                    elif b_is_full and not a_is_full:
                        is_companion = True

            if (not a_is_full and not b_is_full) or is_companion:
                if i not in best_scores_a:
                    best_scores_a[i] = score

                v_limit = 0.50
                if score < (best_scores_a[i] * v_limit):
                    continue

                # Add to fulfillment
                if not is_companion:
                    if is_lump_a:
                        fulfilled_a[i] = 0.5
                    else:
                        fulfilled_a[i] += qty_b

                if not is_companion or (is_companion and not b_is_full):
                    if qty_b == 0:
                        fulfilled_b[j] += 1
                    else:
                        fulfilled_b[j] += qty_a

                # --- NEW GRAPH LOGIC (NO SNOWBALLING) ---
                node_a = f"A_{i}"
                node_b = f"B_{j}"

                cluster_a = node_to_cluster.get(node_a)
                cluster_b = node_to_cluster.get(node_b)

                if cluster_a is None and cluster_b is None:
                    # Create new independent cluster
                    clusters[cluster_counter] = {'a_nodes': {i}, 'b_nodes': {j}, 'scores': [score]}
                    node_to_cluster[node_a] = cluster_counter
                    node_to_cluster[node_b] = cluster_counter
                    cluster_counter += 1
                elif cluster_a is not None and cluster_b is None:
                    # Add B directly to A's group
                    clusters[cluster_a]['b_nodes'].add(j)
                    clusters[cluster_a]['scores'].append(score)
                    node_to_cluster[node_b] = cluster_a
                elif cluster_b is not None and cluster_a is None:
                    # Add A directly to B's group
                    clusters[cluster_b]['a_nodes'].add(i)
                    clusters[cluster_b]['scores'].append(score)
                    node_to_cluster[node_a] = cluster_b
                else:
                    # BOTH items already belong to different clusters.
                    # Instead of merging the clusters (which causes the mess), we safely ignore the link.
                    pass

        return [{
            "contract_a_items": [df_a.iloc[a].to_dict() for a in c['a_nodes']],
            "contract_b_items": [df_b.iloc[b].to_dict() for b in c['b_nodes']],
            "cluster_score": round(sum(c['scores']) / len(c['scores']), 2)
        } for c in clusters.values()]


if __name__ == "__main__":
    from pathlib import Path

    base_dir = Path(r"C:\Users\jensv\Documents\Steen Vastgoed\Offertes Vergelijken\Pre-Made Templates")
    loader = ContractLoader()
    decock = "JV-Offerte_Template_DeCock.xlsx"
    michielse = "JV-Offerte_Template_Michielse.xlsx"
    vnt = "JV-Offerte_Template_VNT.xlsx"
    try:
        contract_a = loader.load_excel(base_dir / decock)
        contract_b = loader.load_excel(base_dir / vnt)

        matcher = ScoringEngine(threshold=0.4)
        mapping_results = matcher.match(contract_a, contract_b)

        # --- 1. Identify Unmatched Items ---
        # Extract names of matched items
        matched_a_names = {item.get('Naam') for cluster in mapping_results for item in cluster['contract_a_items']}
        matched_b_names = {item.get('Naam') for cluster in mapping_results for item in cluster['contract_b_items']}

        # Filter the original dataframes for items NOT in the matched sets
        unmatched_a = contract_a[~contract_a['Naam'].isin(matched_a_names)]
        unmatched_b = contract_b[~contract_b['Naam'].isin(matched_b_names)]

        # --- 2. Print Summary & Clusters ---
        print(f"\nTotal Clusters Formed: {len(mapping_results)}")
        print(f"Unmatched Items: {len(unmatched_a)} in Contract A | {len(unmatched_b)} in Contract B")
        print("=" * 80)

        for idx, cluster in enumerate(mapping_results, 1):
            score = cluster['cluster_score']
            print(f"📦 CLUSTER {idx} | Average Confidence: [{score:.2f}]")

            print("  [Contract A Items]:")
            for item in cluster['contract_a_items']:
                name = item.get('Naam', 'N/A')
                qty = item.get('Aantal', 'N/A')
                unit = item.get('Eenheid', '')
                print(f"    - {name} ({qty} {unit})")

            print("  [Contract B Items]:")
            for item in cluster['contract_b_items']:
                name = item.get('Naam', 'N/A')
                qty = item.get('Aantal', 'N/A')
                unit = item.get('Eenheid', '')
                print(f"    - {name} ({qty} {unit})")

            print("-" * 80)

        # --- 3. Print Unmatched Items Lists ---
        if not unmatched_a.empty:
            print("\n❌ UNMATCHED IN CONTRACT A:")
            for _, row in unmatched_a.iterrows():
                print(f"    - {row['Naam']} ({row.get('Aantal', 0)} {row.get('Eenheid', '')})")

        if not unmatched_b.empty:
            print("\n❌ UNMATCHED IN CONTRACT B:")
            for _, row in unmatched_b.iterrows():
                print(f"    - {row['Naam']} ({row.get('Aantal', 0)} {row.get('Eenheid', '')})")

    except FileNotFoundError as e:
        print(f"Error loading files: Ensure the paths are correct. Details: {e}")