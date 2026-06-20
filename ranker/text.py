"""
Text handling: prose extraction + TF-IDF semantic similarity.

We read each candidate's *prose* — headline, summary, every role title and
description — because prose is far harder to keyword-stuff than the skills[]
array. TF-IDF cosine vs the JD is the semantic signal: CPU-only, deterministic,
no network, fits the 5-minute / 100K budget. An optional sentence-transformers
booster (precompute_embeddings.py) can be blended in when present.
"""
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

_WS = re.compile(r"\s+")


def candidate_text(cand):
    """The prose we trust: headline, summary, every role title + description."""
    p = cand.get("profile", {}) or {}
    parts = [p.get("headline", ""), p.get("summary", ""),
             p.get("current_title", ""), p.get("current_industry", "")]
    for r in cand.get("career_history", []) or []:
        parts.append(r.get("title", ""))
        parts.append(r.get("description", ""))
        parts.append(r.get("industry", ""))
    for e in cand.get("education", []) or []:
        parts.append(e.get("field_of_study", ""))
    return _WS.sub(" ", " ".join(x for x in parts if x)).strip().lower()


class SemanticIndex:
    """Fits TF-IDF over the candidate corpus, scores cosine vs the JD."""

    def __init__(self, jd_text, max_features=40000):
        self.jd_text = jd_text.lower()
        self.vectorizer = TfidfVectorizer(
            max_features=max_features, ngram_range=(1, 2),
            min_df=2, stop_words="english", sublinear_tf=True)
        self._matrix = None
        self._jd_vec = None

    def fit(self, corpus):
        m = self.vectorizer.fit_transform(corpus + [self.jd_text])
        self._jd_vec = m[-1]
        self._matrix = m[:-1]
        return self

    def similarities(self):
        return linear_kernel(self._jd_vec, self._matrix).ravel()
