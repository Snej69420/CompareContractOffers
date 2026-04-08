import os

# 1. Force Hugging Face into strict offline mode to prevent startup timeouts
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import torch
import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder, util


class ScoringEngine:
    def __init__(self,
                 bi_model='intfloat/multilingual-e5-large',
                 cross_model='cross-encoder/mmarco-mMiniLMv2-L12-H384-v1'):

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Initializing ScoringEngine on {self.device} (Offline Mode)...")

        self.bi_model = SentenceTransformer(bi_model, device=self.device, local_files_only=True)
        self.cross_model = CrossEncoder(cross_model, device=self.device, local_files_only=True)

    def get_top_k_candidates(self, target_text, master_list, top_k=15):
        """Finds the best potential matches using fast vector similarity."""
        if not master_list:
            return []

        # We use 'query: ' and 'passage: ' prefixes because the E5 model requires them
        query = f"query: {target_text}"
        passages = [f"passage: {m}" for m in master_list]

        # Encode and compute cosine similarity
        query_emb = self.bi_model.encode(query, convert_to_tensor=True)
        passage_embs = self.bi_model.encode(passages, convert_to_tensor=True)

        hits = util.semantic_search(query_emb, passage_embs, top_k=top_k)[0]

        # Return indices and their initial scores
        return hits

    def rerank_candidates(self, target_text, candidate_texts):
        """Uses the Cross-Encoder to give a high-fidelity score to the shortlist."""
        if not candidate_texts:
            return []

        # The Cross-Encoder takes pairs of sentences
        pairs = [[target_text, cand] for cand in candidate_texts]

        # Cross-encoders return raw logits; we use sigmoid to map them to 0-1
        scores = self.cross_model.predict(pairs)
        scores = 1 / (1 + np.exp(-scores))  # Sigmoid function

        return scores.tolist()

    def get_hybrid_score(self, target_text, master_list, top_k=10):
        """The main entry point: combines both models for the final result."""
        # Step 1: Broad search (Bi-Encoder)
        hits = self.get_top_k_candidates(target_text, master_list, top_k=top_k)

        if not hits:
            return []

        candidate_indices = [h['corpus_id'] for h in hits]
        candidate_strings = [master_list[i] for i in candidate_indices]

        # Step 2: Deep Analysis (Cross-Encoder)
        refined_scores = self.rerank_candidates(target_text, candidate_strings)

        # Step 3: Combine into a list of results
        final_results = []
        for i in range(len(candidate_indices)):
            final_results.append({
                'master_index': candidate_indices[i],
                'master_text': candidate_strings[i],
                'bi_score': round(float(hits[i]['score']), 4),
                'cross_score': round(float(refined_scores[i]), 4)
            })

        # Sort by the more accurate cross_score
        return sorted(final_results, key=lambda x: x['cross_score'], reverse=True)