import os
import random
import torch
import pandas as pd
import numpy as np
from dataclasses import dataclass

from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer, util

from src.UI.Utils import get_asset_path
from src.Backend.loader import ContractLoader
from src.Backend.textprocessing import TextNormalizer

@dataclass
class GlobalItem:
    global_id: int
    doc_key: str
    local_idx: int
    raw_text: str
    clean_tokens: list[str]
    row_data: pd.Series


class ScoringEngine:
    def __init__(self, threshold: float = 0.45):
        self.threshold = threshold
        self.lump_sum_units = {'ff', ''}
        model_name = 'paraphrase-multilingual-MiniLM-L12-v2'
        local_model_path = get_asset_path(f"models/{model_name}")

        self.ai_model = SentenceTransformer(local_model_path)
        self.BM25_WEIGHT = 0.50
        self.SEMANTIC_WEIGHT = 0.50

    def _flatten_documents(self, documents: dict[str, pd.DataFrame]) -> list[GlobalItem]:
        """
        Flattens N documents into a single global pool.
        Why: Balances BM25 Inverse Document Frequency (IDF) evenly across all uploaded contracts.
        """
        global_pool = []
        global_counter = 0

        for doc_key, df in documents.items():
            for local_idx, row in df.iterrows():
                raw_text = f"{row.get('Categorie', '')} {row.get('Naam', '')}".strip()
                clean_tokens = TextNormalizer.get_clean_tokens(raw_text)

                item = GlobalItem(
                    global_id=global_counter,
                    doc_key=doc_key,
                    local_idx=local_idx,
                    raw_text=raw_text,
                    clean_tokens=clean_tokens,
                    row_data=row
                )
                global_pool.append(item)
                global_counter += 1

        return global_pool

    def match(self, documents: dict[str, pd.DataFrame]):
        global_pool = self._flatten_documents(documents)
        n_items = len(global_pool)

        all_raw_texts = [item.raw_text for item in global_pool]
        all_tokens = [item.clean_tokens for item in global_pool]

        bm25_global = BM25Okapi(all_tokens)
        embs_global = self.ai_model.encode(all_raw_texts, convert_to_tensor=True)

        semantic_matrix = util.cos_sim(embs_global, embs_global).cpu().numpy()

        bm25_matrix = [bm25_global.get_scores(q) for q in all_tokens]
        # Prevent matching items within the same document from boosting their BM25 scores
        for i in range(n_items):
            for j in range(n_items):
                if global_pool[i].doc_key == global_pool[j].doc_key:
                    bm25_matrix[i][j] = 0.0
        max_bm25 = max([max(scores) for scores in bm25_matrix if len(scores) > 0] + [1e-9])

        scoring_edges = []
        full_score_lookup = {}

        for i in range(n_items):
            for j in range(i + 1, n_items):

                item_a = global_pool[i]
                item_b = global_pool[j]

                if item_a.doc_key == item_b.doc_key:
                    continue

                # Symmetrical BM25 prevents length bias
                norm_ab = bm25_matrix[i][j] / max_bm25
                norm_ba = bm25_matrix[j][i] / max_bm25
                symmetric_bm25 = (norm_ab + norm_ba) / 2.0

                sem_score = semantic_matrix[i][j]
                hybrid_score = (symmetric_bm25 * self.BM25_WEIGHT) + (sem_score * self.SEMANTIC_WEIGHT)

                # Route through heuristic pruning
                final_score = self._apply_guardrails(hybrid_score, item_a, item_b)

                full_score_lookup[(item_a.global_id, item_b.global_id)] = final_score
                full_score_lookup[(item_b.global_id, item_a.global_id)] = final_score

                if final_score >= self.threshold:
                    scoring_edges.append({
                        "id_a": item_a.global_id,
                        "id_b": item_b.global_id,
                        "final_score": final_score
                    })

        scoring_edges.sort(key=lambda x: x["final_score"], reverse=True)
        clusters, unmatched = self._build_clusters(scoring_edges, global_pool)
        return clusters, full_score_lookup, unmatched

    def _apply_guardrails(self, base_score: float, item_a: GlobalItem, item_b: GlobalItem) -> float:
        # --- 1. DIMENSION CLASH (Kill Switch: 0.0) ---
        # Instantly severs matches with incompatible physical dimensions.
        dims_a = TextNormalizer.extract_dimensions(item_a.raw_text)
        dims_b = TextNormalizer.extract_dimensions(item_b.raw_text)
        if TextNormalizer.check_dimension_clash(dims_a, dims_b):
            return 0.0

        try:
            t_qty, m_qty = float(item_a.row_data.get('Aantal', 0)), float(item_b.row_data.get('Aantal', 0))
        except:
            t_qty, m_qty = 0.0, 0.0

        # --- 2. ANOMALY CHECK (Kill Switch: 0.0) ---
        # Forces unpriced/zero-quantity items into the Unmatched list.
        if t_qty == 0.0 or m_qty == 0.0:
            return 0.0

        t_unit = TextNormalizer.normalize_unit(item_a.row_data.get('Eenheid', ''))
        m_unit = TextNormalizer.normalize_unit(item_b.row_data.get('Eenheid', ''))

        is_lump_a = (t_unit in self.lump_sum_units)
        is_lump_b = (m_unit in self.lump_sum_units)

        # --- 3. LUMP SUM VS MEASUREMENT (Kill Switch: 0.0) ---
        # Prevents fixed fees (ff/sog) from bridging into continuous bulk materials.
        continuous_units = {'m²', 'm³', 'm', 'kg', 't'}
        if (is_lump_a and m_unit in continuous_units) or (is_lump_b and t_unit in continuous_units):
            return 0.0

        penalty, bonus = 0.0, 0.0

        # --- 4. STRICT MEASUREMENT PENALTY (-0.50) ---
        # Heavily penalizes incompatible continuous units (e.g. Area vs Length) sharing text keywords.
        if not is_lump_a and not is_lump_b and t_unit and m_unit and t_unit != m_unit:
            penalty -= 0.50

        # --- 5. EXACT QUANTITY BONUS (+0.20) ---
        # Rewards hyper-specific decimals (DNA fingerprints) to save matches suffering from typos/phrasing.
        if base_score > 0.20:
            if not is_lump_a and not is_lump_b and t_qty > 0 and m_qty > 0:
                max_q = max(t_qty, m_qty)
                if (abs(t_qty - m_qty) / max_q) < 0.01:
                    bonus += 0.20

        return max(0.0, min(base_score + penalty + bonus, 1.0))

    def _build_clusters(self, scoring_edges: list[dict], global_pool: list[GlobalItem]) -> tuple[list[dict], dict]:
        """Greedy Graph Clustering supporting 1-to-N aggregation."""

        # Tracks quantity fulfillment uniquely between pairs of specific documents.
        fulfilled_per_doc = {}
        node_to_cluster = {}
        clusters = {}
        cluster_counter = 0

        for edge in scoring_edges:
            id_a, id_b, score = edge['id_a'], edge['id_b'], edge['final_score']
            item_a, item_b = global_pool[id_a], global_pool[id_b]

            doc_a = item_a.doc_key
            doc_b = item_b.doc_key

            qty_a = float(item_a.row_data.get('Aantal', 0.0))
            qty_b = float(item_b.row_data.get('Aantal', 0.0))

            unit_a = TextNormalizer.normalize_unit(item_a.row_data.get('Eenheid', ''))
            unit_b = TextNormalizer.normalize_unit(item_b.row_data.get('Eenheid', ''))
            is_lump_a = (unit_a in self.lump_sum_units)
            is_lump_b = (unit_b in self.lump_sum_units)

            f_a = fulfilled_per_doc.get((id_a, doc_b), 0.0)
            f_b = fulfilled_per_doc.get((id_b, doc_a), 0.0)

            a_is_full = (f_a >= 1.0) if (is_lump_a or qty_a == 0) else (f_a >= (qty_a - 0.01))
            b_is_full = (f_b >= 1.0) if (is_lump_b or qty_b == 0) else (f_b >= (qty_b - 0.01))

            if a_is_full and b_is_full:
                continue

            fulfilled_per_doc[(id_a, doc_b)] = f_a + (1.0 if (is_lump_b or qty_b == 0) else qty_b)
            fulfilled_per_doc[(id_b, doc_a)] = f_b + (1.0 if (is_lump_a or qty_a == 0) else qty_a)

            c_a = node_to_cluster.get(id_a)
            c_b = node_to_cluster.get(id_b)

            # --- DOCUMENT CONFLICT BLOCKER ---
            # Prevents item internal snowballing (e.g. merging two identical items from the same contractor).
            def has_doc_conflict(cluster_id, doc_key):
                return any(global_pool[n].doc_key == doc_key for n in clusters[cluster_id]['nodes'])

            # --- 1-TO-N KNAPSACK BYPASS ---
            # Allows multiple smaller items to bypass the Conflict Blocker if they sum into a large anchor item.
            def can_merge_split_quantity(cluster_id, new_item):
                new_qty = float(new_item.row_data.get('Aantal', 0.0))
                if new_qty == 0: return False

                target_doc = new_item.doc_key
                current_doc_qty = 0.0
                max_anchor_qty = 0.0

                for n in clusters[cluster_id]['nodes']:
                    node = global_pool[n]
                    q = float(node.row_data.get('Aantal', 0.0))
                    if node.doc_key == target_doc:
                        current_doc_qty += q
                    else:
                        if q > max_anchor_qty:
                            max_anchor_qty = q

                if max_anchor_qty > 0 and (current_doc_qty + new_qty) <= (max_anchor_qty * 1.02):
                    return True
                return False

            if c_a is None and c_b is None:
                clusters[cluster_counter] = {'nodes': {id_a, id_b}, 'scores': [score]}
                node_to_cluster[id_a] = cluster_counter
                node_to_cluster[id_b] = cluster_counter
                cluster_counter += 1

            elif c_a is not None and c_b is None:
                if has_doc_conflict(c_a, item_b.doc_key):
                    if not can_merge_split_quantity(c_a, item_b):
                        if score < 0.8: continue
                clusters[c_a]['nodes'].add(id_b)
                clusters[c_a]['scores'].append(score)
                node_to_cluster[id_b] = c_a

            elif c_b is not None and c_a is None:
                if has_doc_conflict(c_b, item_a.doc_key):
                    if not can_merge_split_quantity(c_b, item_a):
                        if score < 0.8: continue
                clusters[c_b]['nodes'].add(id_a)
                clusters[c_b]['scores'].append(score)
                node_to_cluster[id_a] = c_b

            elif c_a != c_b:
                docs_a = {global_pool[n].doc_key for n in clusters[c_a]['nodes']}
                docs_b = {global_pool[n].doc_key for n in clusters[c_b]['nodes']}
                has_conflict = len(docs_a.intersection(docs_b)) > 0

                req_score = 0.8 if has_conflict else 0.70
                if score >= req_score:
                    clusters[c_a]['nodes'].update(clusters[c_b]['nodes'])
                    clusters[c_a]['scores'].extend(clusters[c_b]['scores'])
                    for n in clusters[c_b]['nodes']:
                        node_to_cluster[n] = c_a
                    del clusters[c_b]

        raw_clusters = []
        for c in clusters.values():
            avg_score = sum(c['scores']) / len(c['scores']) if c['scores'] else 0.0

            # --- RETROACTIVE QUANTITY BONUS ---
            # Awards the +0.20 DNA bonus post-clustering if a 1-to-N aggregated sum perfectly matches.
            doc_sums = {}
            for n in c['nodes']:
                item = global_pool[n]
                u = TextNormalizer.normalize_unit(item.row_data.get('Eenheid', ''))
                if u not in self.lump_sum_units:
                    doc_sums[item.doc_key] = doc_sums.get(item.doc_key, 0.0) + float(item.row_data.get('Aantal', 0.0))

            if len(doc_sums) > 1:
                sums = list(doc_sums.values())
                if max(sums) > 0 and (max(sums) - min(sums)) / max(sums) < 0.02:
                    avg_score = min(1.0, avg_score + 0.20)

            raw_clusters.append({"nodes": list(c['nodes']), "avg_score": avg_score})

        return self._format_results(raw_clusters, global_pool)

    def _format_results(self, raw_clusters: list[dict], global_pool: list[GlobalItem]) -> tuple[list[dict], dict]:
        """Formats the graph data dynamically so the UI can handle N-Documents."""
        formatted_clusters = []
        matched_ids = set()

        for rc in raw_clusters:
            cluster_dict = {}
            for node_id in rc["nodes"]:
                matched_ids.add(node_id)
                item = global_pool[node_id]
                doc_key = item.doc_key

                if doc_key not in cluster_dict:
                    cluster_dict[doc_key] = []

                item_dict = {
                    "id": item.local_idx,
                    "global_id": item.global_id,
                    "unit": TextNormalizer.normalize_unit(item.row_data.get('Eenheid', '')),
                    **item.row_data.to_dict()
                }
                cluster_dict[doc_key].append(item_dict)

            cluster_dict["cluster_score"] = round(rc["avg_score"], 2)
            formatted_clusters.append(cluster_dict)

        unmatched_dict = {}
        for item in global_pool:
            if item.global_id not in matched_ids:
                if item.doc_key not in unmatched_dict:
                    unmatched_dict[item.doc_key] = []

                item_dict = {
                    "id": item.local_idx,
                    "unit": TextNormalizer.normalize_unit(item.row_data.get('Eenheid', '')),
                    **item.row_data.to_dict()
                }
                unmatched_dict[item.doc_key].append(item_dict)

        return formatted_clusters, unmatched_dict


if __name__ == "__main__":
    from pathlib import Path

    base_dir = Path(r"C:\Users\jensv\Documents\Steen Vastgoed\Offertes Vergelijken\Pre-Made Templates")
    loader = ContractLoader()
    decock = "JV-Offerte_Template_DeCock.xlsx"
    michielse = "JV-Offerte_Template_Michielse.xlsx"
    vnt = "JV-Offerte_Template_VNT.xlsx"

    try:
        documents = {
            decock: loader.load_excel(base_dir / decock),
            michielse: loader.load_excel(base_dir / michielse),
            vnt: loader.load_excel(base_dir / vnt)
        }

        matcher = ScoringEngine(threshold=0.4)
        mapping_results, score_lookup, unmatched_dict = matcher.match(documents)

        print(f"\nTotal Clusters Formed: {len(mapping_results)}")
        for doc_key, items in unmatched_dict.items():
            print(f"Unmatched in {doc_key}: {len(items)}")
        print("=" * 80)

        for idx, cluster in enumerate(mapping_results, 1):
            score = cluster.get('cluster_score', 0.0)
            print(f"📦 CLUSTER {idx} | Average Confidence: [{score:.2f}]")

            for doc_key, items in cluster.items():
                if doc_key == "cluster_score": continue

                print(f"  [{doc_key}]:")
                for item in items:
                    name = item.get('Naam', 'N/A')
                    qty = item.get('Aantal', 'N/A')
                    unit = item.get('Eenheid', '')
                    print(f"    - {name} ({qty} {unit})")

            print("-" * 80)

        for doc_key, items in unmatched_dict.items():
            if items:
                print(f"\n❌ UNMATCHED IN {doc_key}:")
                for item in items:
                    print(f"    - {item.get('Naam', 'N/A')} ({item.get('Aantal', 0)} {item.get('Eenheid', '')})")

    except Exception as e:
        import traceback
        print(f"Error: {e}")
        traceback.print_exc()