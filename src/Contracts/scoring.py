import os
import random
import torch
import pandas as pd
import numpy as np

from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer, util

from src.Contracts.loader import ContractLoader
from src.Contracts.textprocessing import TextNormalizer

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

    def match(self, df_a: pd.DataFrame, df_b: pd.DataFrame)-> tuple[list[dict], dict, list[dict], list[dict]]:
        docs_a_raw = (df_a['Categorie'].astype(str) + " " + df_a['Naam'].astype(str)).tolist()
        docs_b_raw = (df_b['Categorie'].astype(str) + " " + df_b['Naam'].astype(str)).tolist()

        tokens_a = [TextNormalizer.get_clean_tokens(doc) for doc in docs_a_raw]
        tokens_b = [TextNormalizer.get_clean_tokens(doc) for doc in docs_b_raw]

        bm25 = BM25Okapi(tokens_b)

        embs_a = self.ai_model.encode(docs_a_raw, convert_to_tensor=True)
        embs_b = self.ai_model.encode(docs_b_raw, convert_to_tensor=True)
        semantic_matrix = util.cos_sim(embs_a, embs_b).cpu().numpy()

        scoring_matrix = []
        full_score_lookup = {}
        global_max_bm25 = max([max(bm25.get_scores(q)) for q in tokens_a if len(bm25.get_scores(q)) > 0] + [1.0])

        for i, query_tokens in enumerate(tokens_a):
            raw_bm25_scores = bm25.get_scores(query_tokens)
            for j, bm25_score in enumerate(raw_bm25_scores):
                norm_bm25 = bm25_score / global_max_bm25
                sem_score = semantic_matrix[i][j]
                hybrid_score = (norm_bm25 * self.BM25_WEIGHT) + (sem_score * self.SEMANTIC_WEIGHT)

                row_a, row_b = df_a.iloc[i], df_b.iloc[j]
                final_score = self._apply_guardrails(hybrid_score, row_a, row_b)
                full_score_lookup[(i, j)] = final_score

                if final_score >= self.threshold:
                    scoring_matrix.append({"id_a": i, "id_b": j, "final_score": final_score})

        scoring_matrix.sort(key=lambda x: (x["final_score"], x["id_a"], x["id_b"]), reverse=True)
        clusters, unmatched_a, unmatched_b = self._build_clusters(scoring_matrix, df_a, df_b)
        return clusters, full_score_lookup, unmatched_a, unmatched_b

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

    def _build_clusters(self, sorted_matrix: list[dict], df_a: pd.DataFrame, df_b: pd.DataFrame) -> tuple[
        list[dict], list[dict], list[dict]]:
        """Main orchestrator for graph generation and data formatting."""
        clusters = self._generate_graph_clusters(sorted_matrix, df_a, df_b)
        return self._format_results(clusters, df_a, df_b)

    def _generate_graph_clusters(self, sorted_matrix: list[dict], df_a: pd.DataFrame, df_b: pd.DataFrame) -> dict:
        """Handles the core algorithmic logic of building matched sets based on fulfillment."""
        node_to_cluster = {}
        clusters = {}
        cluster_counter = 0

        fulfilled_a = {i: 0.0 for i in range(len(df_a))}
        fulfilled_b = {j: 0.0 for j in range(len(df_b))}
        best_scores_a = {}

        for match in sorted_matrix:
            i, j, score = match["id_a"], match["id_b"], match["final_score"]
            qty_a = float(df_a.iloc[i].get('Aantal', 0.0))
            qty_b = float(df_b.iloc[j].get('Aantal', 0.0))

            unit_a = TextNormalizer.normalize_unit(df_a.iloc[i].get('Eenheid', ''))
            is_lump_a = (unit_a in self.lump_sum_units)

            a_is_full = False if is_lump_a else (fulfilled_a[i] >= (qty_a - 0.01))
            b_is_full = (fulfilled_b[j] >= (qty_b - 0.01)) if qty_b > 0 else (fulfilled_b[j] >= 1.0)

            # --- COMPANION ITEM EXCEPTION ---
            is_companion = False
            if qty_a > 0 and abs(qty_a - qty_b) < 0.01:
                is_signature_qty = (qty_a > 10.0) and (qty_a % 1 != 0)
                score_ratio_required = 0.50 if is_signature_qty else (0.90 if qty_a <= 2.5 else 0.80)

                if i in best_scores_a and score >= (best_scores_a[i] * score_ratio_required):
                    if a_is_full and not b_is_full:
                        is_companion = True
                    elif b_is_full and not a_is_full:
                        is_companion = True

            # --- FULFILLMENT CHECK ---
            if (not a_is_full and not b_is_full) or is_companion:
                if i not in best_scores_a:
                    best_scores_a[i] = score

                if score < (best_scores_a[i] * 0.50):
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

                # --- CLUSTER ASSIGNMENT ---
                node_a, node_b = f"A_{i}", f"B_{j}"
                cluster_a, cluster_b = node_to_cluster.get(node_a), node_to_cluster.get(node_b)

                if cluster_a is None and cluster_b is None:
                    clusters[cluster_counter] = {'a_nodes': {i}, 'b_nodes': {j}, 'scores': [score]}
                    node_to_cluster[node_a] = cluster_counter
                    node_to_cluster[node_b] = cluster_counter
                    cluster_counter += 1
                elif cluster_a is not None and cluster_b is None:
                    clusters[cluster_a]['b_nodes'].add(j)
                    clusters[cluster_a]['scores'].append(score)
                    node_to_cluster[node_b] = cluster_a
                elif cluster_b is not None and cluster_a is None:
                    clusters[cluster_b]['a_nodes'].add(i)
                    clusters[cluster_b]['scores'].append(score)
                    node_to_cluster[node_a] = cluster_b

        return clusters

    def _format_results(self, clusters: dict, df_a: pd.DataFrame, df_b: pd.DataFrame) -> tuple[
        list[dict], list[dict], list[dict]]:
        """Handles transforming the clusters and raw dataframes into the structured dictionaries required by the UI."""
        matched_a = {a for c in clusters.values() for a in c['a_nodes']}
        matched_b = {b for c in clusters.values() for b in c['b_nodes']}

        formatted_clusters = []
        for c in clusters.values():
            # FIXED: Ensuring "Norm_Eenheid" is universally used for both matched items
            formatted_clusters.append({
                "contract_a_items": [
                    {"id": a, "unit": TextNormalizer.normalize_unit(df_a.iloc[a].get('Eenheid', '')),
                     **df_a.iloc[a].to_dict()} for a in c['a_nodes']],
                "contract_b_items": [
                    {"id": b, "unit": TextNormalizer.normalize_unit(df_b.iloc[b].get('Eenheid', '')),
                     **df_b.iloc[b].to_dict()} for b in c['b_nodes']],
                "cluster_score": round(sum(c['scores']) / len(c['scores']), 2)
            })

        unmatched_a = [{"id": i, "unit": TextNormalizer.normalize_unit(df_a.iloc[i].get('Eenheid', '')),
                        **df_a.iloc[i].to_dict()}
                       for i in range(len(df_a)) if i not in matched_a]

        unmatched_b = [{"id": j, "unit": TextNormalizer.normalize_unit(df_b.iloc[j].get('Eenheid', '')),
                        **df_b.iloc[j].to_dict()}
                       for j in range(len(df_b)) if j not in matched_b]

        return formatted_clusters, unmatched_a, unmatched_b

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