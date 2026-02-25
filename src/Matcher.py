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

    def match_contracts(self, master_df, target_df):
        master_cats = master_df['Categorie'].dropna().astype(str).unique().tolist()
        target_cats = target_df['Categorie'].dropna().astype(str).unique().tolist()

        # 1. Full Matrix of Categories
        category_mapping = self.get_all_matches(master_cats, target_cats)

        # 2. Full Matrix of Items per Category combination
        item_mapping = {}
        for t_cat in target_cats:
            item_mapping[t_cat] = {}
            t_items = target_df[target_df['Categorie'] == t_cat]['Naam'].dropna().astype(str).unique().tolist()

            for m_cat in master_cats:
                m_items = master_df[master_df['Categorie'] == m_cat]['Naam'].dropna().astype(str).unique().tolist()
                # Compute scores between target items and master items FOR THIS SPECIFIC CATEGORY
                item_mapping[t_cat][m_cat] = self.get_all_matches(m_items, t_items)

        return {
            'categories': category_mapping,
            'items': item_mapping
        }