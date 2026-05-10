from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class Chapter(BaseModel):
    chapter_id: str
    title: str
    page_start: int = 1
    page_end: int = 1
    content: str
    char_count: int = 0


class Textbook(BaseModel):
    textbook_id: str
    filename: str
    title: str
    format: str
    file_size: int = 0
    total_pages: int = 0
    total_chars: int = 0
    status: Literal["解析中", "已完成", "失败"] = "已完成"
    error: Optional[str] = None
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    chapters: List[Chapter] = Field(default_factory=list)


class KnowledgeNode(BaseModel):
    id: str
    name: str
    definition: str
    category: str = "核心概念"
    chapter: str
    page: int = 1
    textbook_id: str
    textbook_title: str
    source: str = ""
    frequency: int = 1
    aliases: List[str] = Field(default_factory=list)
    importance: float = 0.5


class KnowledgeEdge(BaseModel):
    source: str
    target: str
    relation_type: Literal["prerequisite", "parallel", "contains", "applies_to"]
    description: str = ""
    weight: float = 1.0


class KnowledgeGraph(BaseModel):
    textbook_id: str
    nodes: List[KnowledgeNode] = Field(default_factory=list)
    edges: List[KnowledgeEdge] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class IntegrationDecision(BaseModel):
    decision_id: str
    action: Literal["merge", "keep", "remove", "split"]
    affected_nodes: List[str]
    result_node: Optional[str] = None
    reason: str
    confidence: float = 0.0
    teacher_locked: bool = False


class IntegratedGraph(BaseModel):
    nodes: List[KnowledgeNode] = Field(default_factory=list)
    edges: List[KnowledgeEdge] = Field(default_factory=list)
    decisions: List[IntegrationDecision] = Field(default_factory=list)
    stats: Dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RagStatus(BaseModel):
    indexed_books: int = 0
    chunk_count: int = 0
    embedding_backend: str = "tfidf"
    last_indexed_at: Optional[datetime] = None


class RagQuery(BaseModel):
    question: str
    top_k: int = 5


class Citation(BaseModel):
    textbook: str
    chapter: str
    page: int
    relevance_score: float
    chunk_id: str


class RagAnswer(BaseModel):
    answer: str
    citations: List[Citation]
    source_chunks: List[Dict[str, Any]]
    latency_ms: int


class DialogueRequest(BaseModel):
    message: str


class DialogueResponse(BaseModel):
    reply: str
    updated_decisions: List[IntegrationDecision] = Field(default_factory=list)
    graph_changed: bool = False


class ApiMessage(BaseModel):
    message: str
    data: Optional[Any] = None
