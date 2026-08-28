"""
Pro-Versed National Plagiarism & Originality Audit Engine
Implements TF-IDF vectorization, N-Gram Cosine Similarity, and Jaccard Containment
to audit student project abstracts and documentation against national repositories.
"""

import re
import math
from typing import List, Dict, Tuple, Any, Optional

# Comprehensive stop words list
STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by",
    "can", "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't", "doing",
    "don't", "down", "during", "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers", "herself",
    "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is",
    "isn't", "it", "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself", "no",
    "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves",
    "out", "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so",
    "some", "such", "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then", "there",
    "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this", "those", "through", "to",
    "too", "under", "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which", "while", "who", "who's",
    "whom", "why", "why's", "with", "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've",
    "your", "yours", "yourself", "yourselves", "system", "project", "using", "based", "proposed", "paper",
    "designed", "developed", "implementation", "results", "analysis"
}

def tokenize(text: str) -> List[str]:
    """Tokenizes string into lowercase alphanumeric words, filtering out short tokens and stop words."""
    if not text:
        return []
    words = re.findall(r'[a-zA-Z0-9]+', text.lower())
    return [w for w in words if len(w) > 2 and w not in STOP_WORDS]

def get_ngrams(tokens: List[str], n: int = 2) -> List[str]:
    """Generates contiguous n-grams from a list of tokens."""
    if len(tokens) < n:
        return []
    return [" ".join(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]

def compute_tf(tokens: List[str]) -> Dict[str, float]:
    """Computes sublinear term frequency for token list."""
    tf_counts: Dict[str, int] = {}
    for token in tokens:
        tf_counts[token] = tf_counts.get(token, 0) + 1
    
    tf: Dict[str, float] = {}
    for token, count in tf_counts.items():
        tf[token] = 1.0 + math.log(count)
    return tf

class PlagiarismEngine:
    def __init__(self):
        self.corpus_docs: List[Dict[str, Any]] = []

    def set_corpus(self, projects: List[Dict[str, Any]]):
        """Sets the reference corpus of existing national projects."""
        self.corpus_docs = []
        for p in projects:
            combined_text = f"{p.get('title', '')} {p.get('abstract', '')} {p.get('description', '')}"
            tokens = tokenize(combined_text)
            bigrams = get_ngrams(tokens, 2)
            trigrams = get_ngrams(tokens, 3)
            self.corpus_docs.append({
                "id": p.get("id"),
                "title": p.get("title", "Untitled Project"),
                "college": p.get("college_name", "Academic Institute"),
                "text": combined_text,
                "tokens": tokens,
                "token_set": set(tokens),
                "bigram_set": set(bigrams),
                "trigram_set": set(trigrams),
                "tf": compute_tf(tokens)
            })

    def check_originality(self, query_text: str, exclude_id: Optional[Any] = None) -> Dict[str, Any]:
        """
        Audits a query text (abstract + description) against the corpus.
        Returns similarity score, originality percentage, status, and highest matching document.
        """
        query_tokens = tokenize(query_text)
        if not query_tokens:
            return {
                "similarity_score": 0.0,
                "originality_score": 100.0,
                "plagiarism_status": "PASSED",
                "highest_match_project_id": None,
                "highest_match_title": "None (No significant text)",
                "matched_college": None,
                "top_overlapping_keywords": [],
                "audit_summary": "Insufficient textual content for comprehensive plagiarism audit. Marked as unique."
            }

        query_bigrams = set(get_ngrams(query_tokens, 2))
        query_trigrams = set(get_ngrams(query_tokens, 3))
        query_set = set(query_tokens)
        query_tf = compute_tf(query_tokens)

        # Filter active corpus excluding self
        active_corpus = [d for d in self.corpus_docs if str(d["id"]) != str(exclude_id)]
        
        if not active_corpus:
            return {
                "similarity_score": 0.0,
                "originality_score": 100.0,
                "plagiarism_status": "PASSED",
                "highest_match_project_id": None,
                "highest_match_title": "First Project in Domain Repository",
                "matched_college": None,
                "top_overlapping_keywords": list(query_set)[:5],
                "audit_summary": "No historical corpus records to compare against. High novelty index verified."
            }

        # Calculate IDF across corpus + query
        total_docs = len(active_corpus) + 1
        doc_freq: Dict[str, int] = {}
        for token in query_set:
            doc_freq[token] = 1 # query itself
        for doc in active_corpus:
            for token in doc["token_set"]:
                doc_freq[token] = doc_freq.get(token, 0) + 1

        idf: Dict[str, float] = {}
        for token, df in doc_freq.items():
            idf[token] = math.log((1.0 + total_docs) / (1.0 + df)) + 1.0

        # Vectorize query
        query_vec: Dict[str, float] = {}
        query_norm_sq = 0.0
        for token, tf_val in query_tf.items():
            val = tf_val * idf.get(token, 1.0)
            query_vec[token] = val
            query_norm_sq += val * val
        query_norm = math.sqrt(query_norm_sq) if query_norm_sq > 0 else 1.0

        highest_sim = 0.0
        best_match_doc = None
        best_overlapping_words: List[str] = []

        for doc in active_corpus:
            # 1. Cosine similarity of TF-IDF
            dot_product = 0.0
            doc_norm_sq = 0.0
            doc_tf = doc["tf"]
            for token, tf_val in doc_tf.items():
                val = tf_val * idf.get(token, 1.0)
                doc_norm_sq += val * val
                if token in query_vec:
                    dot_product += query_vec[token] * val
            doc_norm = math.sqrt(doc_norm_sq) if doc_norm_sq > 0 else 1.0
            cosine_sim = dot_product / (query_norm * doc_norm) if (query_norm * doc_norm) > 0 else 0.0

            # 2. N-gram Overlap (Jaccard & Containment)
            bigram_overlap = len(query_bigrams.intersection(doc["bigram_set"])) / max(1, len(query_bigrams)) if query_bigrams else 0.0
            trigram_overlap = len(query_trigrams.intersection(doc["trigram_set"])) / max(1, len(query_trigrams)) if query_trigrams else 0.0
            ngram_sim = (bigram_overlap * 0.6) + (trigram_overlap * 0.4)

            # 3. Weighted composite score
            composite_sim = (cosine_sim * 0.65) + (ngram_sim * 0.35)

            if composite_sim > highest_sim:
                highest_sim = composite_sim
                best_match_doc = doc
                best_overlapping_words = list(query_set.intersection(doc["token_set"]))

        # Convert to percentage
        sim_percentage = round(min(100.0, max(0.0, highest_sim * 100.0)), 1)
        orig_percentage = round(max(0.0, 100.0 - sim_percentage), 1)

        # Classification
        if sim_percentage <= 15.0:
            status = "PASSED"
            summary = f"Originality verified ({orig_percentage}%). Textual overlap is within acceptable academic thresholds."
        elif sim_percentage <= 25.0:
            status = "NEEDS REVIEW"
            summary = f"Moderate similarity ({sim_percentage}%) detected against national repository. Faculty review advised."
        else:
            status = "FLAGGED"
            summary = f"High similarity ({sim_percentage}%) flagged against existing work '{best_match_doc['title'] if best_match_doc else 'National Project'}'. Requires SPOC investigation."

        return {
            "similarity_score": sim_percentage,
            "originality_score": orig_percentage,
            "plagiarism_status": status,
            "highest_match_project_id": best_match_doc["id"] if best_match_doc else None,
            "highest_match_title": best_match_doc["title"] if best_match_doc else "None",
            "matched_college": best_match_doc["college"] if best_match_doc else None,
            "top_overlapping_keywords": best_overlapping_words[:6],
            "audit_summary": summary
        }

# Global singleton instance
plagiarism_engine = PlagiarismEngine()
