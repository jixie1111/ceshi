from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List

import numpy as np
try:
    from rank_bm25 import BM25Okapi
except Exception:  # fallback keeps demo runnable before pip install -r requirements.txt
    class BM25Okapi:  # type: ignore
        def __init__(self, corpus):
            from collections import Counter
            import math
            self.corpus = corpus
            self.df = Counter(t for doc in corpus for t in set(doc))
            self.N = len(corpus) or 1
            self.avgdl = sum(len(d) for d in corpus) / self.N
            self.idf = {t: math.log(1 + (self.N - df + 0.5) / (df + 0.5)) for t, df in self.df.items()}
        def get_scores(self, query):
            import numpy as _np
            scores = []
            for doc in self.corpus:
                dl = len(doc) or 1
                score = 0.0
                for t in query:
                    tf = doc.count(t)
                    if tf:
                        score += self.idf.get(t, 0.0) * tf * 2.5 / (tf + 1.5 * (0.25 + 0.75 * dl / (self.avgdl or 1)))
                scores.append(score)
            return _np.asarray(scores)
from sklearn.metrics.pairwise import cosine_similarity

from ..models.schemas import Citation, RagAnswer, RagStatus, Textbook
from ..utils.text import cn_tokenize, safe_id, sliding_window, split_sentences
from .embedding import EmbeddingService
from .llm_client import LLMClient


@dataclass
class Chunk:
    chunk_id: str
    text: str
    textbook_id: str
    textbook: str
    chapter: str
    page: int


class RAGEngine:
    def __init__(self) -> None:
        self.embedding = EmbeddingService()
        self.llm = LLMClient()
        self.chunks: List[Chunk] = []
        self.vectors: np.ndarray | None = None
        self.bm25: BM25Okapi | None = None
        self.status = RagStatus(embedding_backend=self.embedding.backend)

    def build_index(self, books: List[Textbook]) -> RagStatus:
        chunks: List[Chunk] = []
        for book in books:
            for chapter in book.chapters:
                for start, _end, text in sliding_window(chapter.content, size=700, overlap=80):
                    # Approximate page position within chapter.
                    page_span = max(1, chapter.page_end - chapter.page_start + 1)
                    page_offset = int((start / max(1, chapter.char_count)) * page_span)
                    page = chapter.page_start + page_offset
                    chunks.append(
                        Chunk(
                            chunk_id=safe_id("chunk", f"{book.textbook_id}:{chapter.chapter_id}:{start}"),
                            text=text,
                            textbook_id=book.textbook_id,
                            textbook=book.title,
                            chapter=chapter.title,
                            page=page,
                        )
                    )
        self.chunks = chunks
        texts = [c.text for c in chunks]
        self.vectors = self.embedding.encode_corpus(texts).vectors if texts else np.zeros((0, 0))
        tokenized = [cn_tokenize(t) for t in texts]
        self.bm25 = BM25Okapi(tokenized) if tokenized else None
        self.status = RagStatus(
            indexed_books=len(books),
            chunk_count=len(chunks),
            embedding_backend=self.embedding.backend,
            last_indexed_at=datetime.utcnow(),
        )
        return self.status

    def clear_index(self) -> RagStatus:
        self.chunks = []
        self.vectors = None
        self.bm25 = None
        self.status = RagStatus(embedding_backend=self.embedding.backend)
        return self.status

    def query(self, question: str, top_k: int = 5) -> RagAnswer:
        start = time.time()
        if not self.chunks or self.vectors is None or self.vectors.size == 0:
            return RagAnswer(answer="当前知识库尚未建立索引，请先点击“建立 RAG 索引”。", citations=[], source_chunks=[], latency_ms=0)
        q_vec = self.embedding.encode_queries([question])
        vector_scores = cosine_similarity(q_vec, self.vectors)[0]
        bm25_scores = np.zeros(len(self.chunks))
        if self.bm25 is not None:
            bm25_scores = np.asarray(self.bm25.get_scores(cn_tokenize(question)), dtype=float)
            if bm25_scores.max() > 0:
                bm25_scores = bm25_scores / bm25_scores.max()
        if vector_scores.max() > 0:
            vector_norm = vector_scores / vector_scores.max()
        else:
            vector_norm = vector_scores
        # Hybrid retrieval + lightweight rerank: exact keyword overlap rewards precise citations.
        q_terms = set(cn_tokenize(question))
        exact = np.asarray([len(q_terms & set(cn_tokenize(c.text))) / max(1, len(q_terms)) for c in self.chunks])
        scores = 0.62 * vector_norm + 0.28 * bm25_scores + 0.10 * exact
        idxs = np.argsort(scores)[::-1][: max(1, top_k)]
        selected = [(int(i), float(scores[i])) for i in idxs if scores[i] > 0]
        if not selected:
            return RagAnswer(answer="当前知识库中未找到相关信息。", citations=[], source_chunks=[], latency_ms=int((time.time() - start) * 1000))
        answer = self._generate_answer(question, selected)
        citations = [
            Citation(
                textbook=self.chunks[i].textbook,
                chapter=self.chunks[i].chapter,
                page=self.chunks[i].page,
                relevance_score=round(score, 4),
                chunk_id=self.chunks[i].chunk_id,
            )
            for i, score in selected
        ]
        source_chunks = [self._chunk_payload(self.chunks[i], score) for i, score in selected]
        return RagAnswer(answer=answer, citations=citations, source_chunks=source_chunks, latency_ms=int((time.time() - start) * 1000))

    def _generate_answer(self, question: str, selected: List[tuple[int, float]]) -> str:
        contexts = []
        for rank, (i, score) in enumerate(selected, 1):
            c = self.chunks[i]
            contexts.append(f"[{rank}] 来源：{c.textbook}, {c.chapter}, 第 {c.page} 页\n{c.text}")
        context_text = "\n\n".join(contexts)
        if self.llm.available:
            system = "你是教材 RAG 问答助手。只能基于提供的上下文回答。每个关键断言后附 [教材, 章节, 第 X 页]。找不到答案时回答：当前知识库中未找到相关信息。"
            ans = self.llm.answer_chat(system, f"问题：{question}\n\n上下文：\n{context_text[:10000]}")
            if ans:
                return ans
        # Offline extractive answer: pick sentences with the highest query overlap.
        q_terms = set(cn_tokenize(question))
        scored_sentences: List[tuple[float, str, Chunk]] = []
        for i, score in selected:
            c = self.chunks[i]
            for s in split_sentences(c.text):
                overlap = len(q_terms & set(cn_tokenize(s))) / max(1, len(q_terms))
                if overlap > 0:
                    scored_sentences.append((overlap + score * 0.2, s, c))
        scored_sentences.sort(reverse=True, key=lambda x: x[0])
        if not scored_sentences:
            c = self.chunks[selected[0][0]]
            return f"根据已检索到的教材片段，{c.text[:220]}…… [{c.textbook}, {c.chapter}, 第 {c.page} 页]"
        used = []
        seen = set()
        for _, s, c in scored_sentences[:5]:
            key = s[:30]
            if key in seen:
                continue
            seen.add(key)
            used.append(f"{s} [{c.textbook}, {c.chapter}, 第 {c.page} 页]")
        return "\n".join(used[:4])

    def _chunk_payload(self, chunk: Chunk, score: float) -> Dict[str, Any]:
        return {
            "chunk_id": chunk.chunk_id,
            "text": chunk.text,
            "textbook": chunk.textbook,
            "chapter": chunk.chapter,
            "page": chunk.page,
            "relevance_score": round(score, 4),
        }


rag_engine = RAGEngine()
