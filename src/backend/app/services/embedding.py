from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ..core.config import get_settings


@dataclass
class VectorResult:
    vectors: np.ndarray
    backend: str


class EmbeddingService:
    """Semantic embedding wrapper with graceful offline fallback.

    In competition networks, downloading models can fail. This class first tries
    sentence-transformers when configured, otherwise falls back to character-level
    TF-IDF, which is surprisingly robust for Chinese terminology and ensures the
    demo never breaks.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.model = None
        self.vectorizer: TfidfVectorizer | None = None
        self.backend = "tfidf"
        if self.settings.embedding_backend in {"auto", "sentence-transformers"}:
            try:
                from sentence_transformers import SentenceTransformer

                self.model = SentenceTransformer(self.settings.embedding_model)
                self.backend = "sentence-transformers"
            except Exception:
                self.model = None
                self.backend = "tfidf"

    def encode_corpus(self, texts: List[str]) -> VectorResult:
        if not texts:
            return VectorResult(np.zeros((0, 0)), self.backend)
        if self.model is not None:
            vectors = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            return VectorResult(np.asarray(vectors, dtype=np.float32), self.backend)
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1, max_features=16000)
        vectors = self.vectorizer.fit_transform(texts).toarray().astype(np.float32)
        return VectorResult(vectors, "tfidf")

    def encode_queries(self, texts: List[str]) -> np.ndarray:
        if self.model is not None:
            return np.asarray(self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False), dtype=np.float32)
        if self.vectorizer is None:
            raise RuntimeError("TF-IDF vectorizer has not been fitted. Call encode_corpus first.")
        return self.vectorizer.transform(texts).toarray().astype(np.float32)

    @staticmethod
    def cosine(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        if a.size == 0 or b.size == 0:
            return np.zeros((len(a), len(b)))
        return cosine_similarity(a, b)
