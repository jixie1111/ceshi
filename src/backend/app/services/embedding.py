from __future__ import annotations

from dataclasses import dataclass
from typing import List
import zlib

import numpy as np
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
except Exception:  # sklearn/scipy can be unavailable or NumPy-incompatible on judge machines.
    TfidfVectorizer = None  # type: ignore[assignment]

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
        self.vectorizer = None
        self.hash_dim = 4096
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
        if TfidfVectorizer is not None:
            try:
                self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1, max_features=16000)
                vectors = self.vectorizer.fit_transform(texts).toarray().astype(np.float32)
                return VectorResult(self._l2_normalize(vectors), "tfidf")
            except Exception:
                self.vectorizer = None
        self.backend = "hash-char"
        return VectorResult(self._hash_char_vectors(texts), self.backend)

    def encode_queries(self, texts: List[str]) -> np.ndarray:
        if self.model is not None:
            return np.asarray(self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False), dtype=np.float32)
        if self.vectorizer is not None:
            try:
                return self._l2_normalize(self.vectorizer.transform(texts).toarray().astype(np.float32))
            except Exception:
                pass
        return self._hash_char_vectors(texts)

    @staticmethod
    def cosine(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        if a.size == 0 or b.size == 0:
            return np.zeros((len(a), len(b)))
        a_norm = EmbeddingService._l2_normalize(a)
        b_norm = EmbeddingService._l2_normalize(b)
        return a_norm @ b_norm.T

    @staticmethod
    def _l2_normalize(vectors: np.ndarray) -> np.ndarray:
        if vectors.size == 0:
            return vectors
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return (vectors / norms).astype(np.float32)

    def _hash_char_vectors(self, texts: List[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), self.hash_dim), dtype=np.float32)
        for row, text in enumerate(texts):
            compact = "".join(str(text).split())
            if not compact:
                continue
            padded = f" {compact} "
            for ngram_size in (2, 3, 4):
                if len(padded) < ngram_size:
                    continue
                for idx in range(0, len(padded) - ngram_size + 1):
                    gram = padded[idx: idx + ngram_size]
                    slot = zlib.crc32(gram.encode("utf-8")) % self.hash_dim
                    vectors[row, slot] += 1.0
        return self._l2_normalize(vectors)
