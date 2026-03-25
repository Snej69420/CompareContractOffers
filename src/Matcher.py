import torch
import pandas as pd
from sentence_transformers import SentenceTransformer, util


class ContractMatcher:
    def __init__(self, model_name='distiluse-base-multilingual-cased-v2'):
        print(f"Loading semantic embedding model: {model_name}...")
        self.model = SentenceTransformer(model_name)

    def clean_text(self, text_list):
        cleaned = []
        for text in text_list:
            if pd.isna(text):
                cleaned.append("")
            else:
                cleaned.append(str(text).strip())
        return cleaned

    def get_all_matches(self, master_list, target_list):
        """Returns the score of EVERY target against EVERY master."""
        if not master_list or not target_list:
            return {t: {'scores': {}, 'best_match': None} for t in target_list}

        clean_master = self.clean_text(master_list)
        clean_target = self.clean_text(target_list)

        master_embeddings = self.model.encode(clean_master, convert_to_tensor=True)
        target_embeddings = self.model.encode(clean_target, convert_to_tensor=True)

        cosine_scores = util.cos_sim(target_embeddings, master_embeddings)

        matches = {}
        for i, target in enumerate(target_list):
            target_scores = {}
            for j, master in enumerate(master_list):
                target_scores[master] = round(cosine_scores[i][j].item(), 3)

            # Keep track of the absolute best match to auto-select it later
            best_idx = torch.argmax(cosine_scores[i]).item()
            matches[target] = {
                'scores': target_scores,
                'best_match': master_list[best_idx]
            }
        return matches

    def get_composite_matches(self, m_df_subset, t_df_subset):
        """Calculates AI Text Score and applies penalties for mismatched units."""
        m_items = m_df_subset.drop_duplicates(subset=['Naam'])
        t_items = t_df_subset.drop_duplicates(subset=['Naam'])

        m_names = m_items['Naam'].dropna().astype(str).tolist()
        t_names = t_items['Naam'].dropna().astype(str).tolist()

        text_matches = self.get_all_matches(m_names, t_names)

        for t_idx, t_row in t_items.iterrows():
            t_name = str(t_row['Naam']).strip()
            t_unit = str(t_row.get('Eenheid', '')).strip().lower()
            try:
                t_qty = float(t_row.get('Aantal', 0))
            except:
                t_qty = 0.0

            best_m_name = None
            best_composite_score = -1

            for m_idx, m_row in m_items.iterrows():
                m_name = str(m_row['Naam']).strip()
                m_unit = str(m_row.get('Eenheid', '')).strip().lower()
                try:
                    m_qty = float(m_row.get('Aantal', 0))
                except:
                    m_qty = 0.0

                # Base Text Score (Weighted at 100% now)
                base_score = float(text_matches[t_name]['scores'][m_name])

                # UNIT PENALTY: Massive drop if units explicitly do not match
                unit_penalty = 0.0
                if t_unit not in ["", "nan", "none"] and m_unit not in ["", "nan", "none"]:
                    if t_unit != m_unit:
                        unit_penalty = -0.40  # Heavy penalty for m² vs lm

                # Quantity Bonus: Small tie-breaker bump if quantities match perfectly
                qty_bonus = 0.0
                if m_qty > 0 and t_qty > 0:
                    margin = abs(m_qty - t_qty) / max(m_qty, t_qty)
                    if margin <= 0.05:
                        qty_bonus = 0.10

                # Calculate final score (Clamp between 0.0 and 1.0)
                composite_score = max(0.0, min(round(base_score + unit_penalty + qty_bonus, 3), 1.0))

                text_matches[t_name]['scores'][m_name] = {
                    'total': composite_score,
                    'text': round(base_score, 3),
                    'unit': unit_penalty,  # Now stores the penalty
                    'qty': qty_bonus
                }

                if composite_score > best_composite_score:
                    best_composite_score = composite_score
                    best_m_name = m_name

            text_matches[t_name]['best_match'] = best_m_name

        return text_matches

    def match_contracts(self, master_df, target_df):
        master_cats = master_df['Categorie'].dropna().astype(str).unique().tolist()
        target_cats = target_df['Categorie'].dropna().astype(str).unique().tolist()

        # 1. Full Matrix of Categories (Still uses pure text matching)
        category_mapping = self.get_all_matches(master_cats, target_cats)

        # 2. Full Matrix of Items per Category combination (NOW USES COMPOSITE SCORING)
        item_mapping = {}
        for t_cat in target_cats:
            item_mapping[t_cat] = {}
            t_subset = target_df[target_df['Categorie'] == t_cat]

            for m_cat in master_cats:
                m_subset = master_df[master_df['Categorie'] == m_cat]

                # Compute composite scores (AI Text + Unit + Qty) for this specific category combination
                item_mapping[t_cat][m_cat] = self.get_composite_matches(m_subset, t_subset)

        return {
            'categories': category_mapping,
            'items': item_mapping
        }