from __future__ import annotations

from pathlib import Path
from typing import List

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .core.config import get_settings
from .models.schemas import ApiMessage, DialogueRequest, DialogueResponse, IntegratedGraph, KnowledgeGraph, RagAnswer, RagQuery, RagStatus, Textbook
from .services.dialogue_agent import DialogueAgent
from .services.file_parser import TextbookParser
from .services.graph_integrator import GraphIntegrator
from .services.knowledge_extractor import KnowledgeExtractor
from .services.rag_engine import rag_engine
from .services.report_service import ReportService
from .storage import store
from .utils.text import safe_id

settings = get_settings()
app = FastAPI(title="KnowledgeForge 学科知识整合智能体", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

parser = TextbookParser(settings.upload_dir)
extractor = KnowledgeExtractor()
integrator = GraphIntegrator()
dialogue_agent = DialogueAgent()
reporter = ReportService()


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "app": "KnowledgeForge", "env": settings.app_env}


@app.post("/api/textbooks/upload", response_model=List[Textbook])
async def upload_textbooks(files: List[UploadFile] = File(...)) -> List[Textbook]:
    results: List[Textbook] = []
    for file in files:
        try:
            path = await parser.save_upload(file)
            book = parser.parse(path, file.filename)
            store.upsert_book(book)
            results.append(book)
        except Exception as exc:  # noqa: BLE001 - useful for hackathon UI
            failed = Textbook(
                textbook_id=f"failed_{len(results)}",
                filename=file.filename or "unknown",
                title=Path(file.filename or "unknown").stem,
                format=Path(file.filename or "").suffix.lower().lstrip("."),
                file_size=getattr(file, "size", 0) or 0,
                status="失败",
                error=str(exc),
            )
            results.append(failed)
    return results


@app.get("/api/textbooks", response_model=List[Textbook])
def list_textbooks() -> List[Textbook]:
    return store.list_books()


@app.get("/api/textbooks/{textbook_id}", response_model=Textbook)
def get_textbook(textbook_id: str) -> Textbook:
    book = store.get_book(textbook_id)
    if not book:
        raise HTTPException(404, "教材不存在")
    return book


@app.delete("/api/textbooks/{textbook_id}", response_model=ApiMessage)
def delete_textbook(textbook_id: str) -> ApiMessage:
    book = store.get_book(textbook_id)
    if not book:
        raise HTTPException(404, "教材不存在")

    books = [b for b in store.list_books() if b.textbook_id != textbook_id]
    store.save_books(books)

    graphs = store.list_graphs()
    if textbook_id in graphs:
        del graphs[textbook_id]
        store.write_json("graphs.json", {k: v.model_dump(mode="json") for k, v in graphs.items()})

    suffix = Path(book.filename).suffix.lower()
    upload_path = settings.upload_dir / f"{safe_id('file', Path(book.filename).stem + suffix)}{suffix}"
    if upload_path.exists():
        upload_path.unlink()

    # Any cross-book integration or in-memory RAG index becomes stale once a
    # source book disappears. Keep remaining single-book graphs, but force the
    # user to rebuild integration/RAG from the new corpus.
    store.save_integration(IntegratedGraph())
    rag_engine.clear_index()
    return ApiMessage(message="已删除教材、上传文件、单书图谱，并清理过期整合结果与 RAG 索引")


@app.post("/api/graph/{textbook_id}/build", response_model=KnowledgeGraph)
def build_graph(textbook_id: str) -> KnowledgeGraph:
    book = store.get_book(textbook_id)
    if not book:
        raise HTTPException(404, "教材不存在")
    graph = extractor.build_graph(book)
    store.save_graph(graph)
    return graph


@app.get("/api/graph/{textbook_id}", response_model=KnowledgeGraph)
def get_graph(textbook_id: str) -> KnowledgeGraph:
    graph = store.get_graph(textbook_id)
    if not graph:
        raise HTTPException(404, "图谱尚未生成")
    return graph


@app.post("/api/integration/run", response_model=IntegratedGraph)
def run_integration() -> IntegratedGraph:
    books = store.list_books()
    graphs = store.list_graphs()
    # Auto-build missing graphs to reduce click friction during judging.
    for book in books:
        if book.textbook_id not in graphs:
            graph = extractor.build_graph(book)
            store.save_graph(graph)
            graphs[book.textbook_id] = graph
    integrated = integrator.integrate(books, graphs)
    store.save_integration(integrated)
    return integrated


@app.get("/api/integration", response_model=IntegratedGraph)
def get_integration() -> IntegratedGraph:
    return store.get_integration()


@app.post("/api/rag/index", response_model=RagStatus)
def rag_index() -> RagStatus:
    books = store.list_books()
    status = rag_engine.build_index(books)
    return status


@app.get("/api/rag/status", response_model=RagStatus)
def rag_status() -> RagStatus:
    return rag_engine.status


@app.post("/api/rag/query", response_model=RagAnswer)
def rag_query(query: RagQuery) -> RagAnswer:
    return rag_engine.query(query.question, top_k=query.top_k)


@app.get("/api/dialogue/history")
def dialogue_history():
    return store.chat_history()


@app.post("/api/dialogue/message", response_model=DialogueResponse)
def dialogue_message(req: DialogueRequest) -> DialogueResponse:
    store.append_chat("user", req.message)
    graph = store.get_integration()
    resp = dialogue_agent.handle(req.message, graph)
    if resp.graph_changed:
        store.save_integration(graph)
    store.append_chat("assistant", resp.reply)
    return resp


@app.post("/api/report/generate", response_model=ApiMessage)
def report_generate() -> ApiMessage:
    content = reporter.generate_markdown(store.list_books(), store.get_integration())
    path = reporter.save_markdown(content)
    return ApiMessage(message="报告已生成", data={"path": str(path), "markdown": content})


@app.get("/api/report/download")
def report_download(format: str = "md"):
    content = reporter.generate_markdown(store.list_books(), store.get_integration())
    md_path = reporter.save_markdown(content)
    if format == "pdf":
        pdf_path = reporter.markdown_to_pdf(content)
        return FileResponse(str(pdf_path), filename="整合报告.pdf", media_type="application/pdf")
    return FileResponse(str(md_path), filename="整合报告.md", media_type="text/markdown")


@app.post("/api/benchmark/run")
def benchmark_run():
    # Lightweight, reproducible self-check: generate questions from chapter titles and test retrieval hit.
    books = store.list_books()
    if rag_engine.status.chunk_count == 0:
        rag_engine.build_index(books)
    questions = []
    for book in books:
        for ch in book.chapters[:4]:
            questions.append({"question": f"{ch.title}的核心内容是什么？", "expected_chapter": ch.title, "book": book.title})
    questions = questions[:24]
    rows = []
    hits = 0
    for q in questions:
        ans = rag_engine.query(q["question"], top_k=3)
        hit = any(c.chapter == q["expected_chapter"] for c in ans.citations)
        hits += int(hit)
        rows.append({**q, "hit": hit, "latency_ms": ans.latency_ms, "top_citation": ans.citations[0].model_dump() if ans.citations else None})
    accuracy = round(hits / len(questions), 3) if questions else 0
    return {"question_count": len(questions), "citation_hit_rate": accuracy, "rows": rows}


@app.post("/api/demo/load", response_model=List[Textbook])
def load_demo() -> List[Textbook]:
    """Load a tiny synthetic demo so reviewers can click through without PDFs."""
    demo_books = [
        Textbook(
            textbook_id="book_demo_physiology",
            filename="demo_生理学.txt",
            title="Demo 生理学",
            format="txt",
            total_pages=3,
            total_chars=1800,
            chapters=[
                {
                    "chapter_id": "ch_001",
                    "title": "第二章 细胞的基本功能",
                    "page_start": 13,
                    "page_end": 52,
                    "content": "静息电位是细胞在安静状态下膜内外存在的电位差。动作电位是可兴奋细胞受到有效刺激后产生的一次快速、可逆的膜电位变化。动作电位依赖静息电位、离子通道和跨膜离子流。钠通道开放导致去极化，钾通道开放参与复极化。临床上神经肌肉兴奋异常可与膜电位改变有关。",
                    "char_count": 140,
                },
                {
                    "chapter_id": "ch_002",
                    "title": "第四章 血液循环",
                    "page_start": 79,
                    "page_end": 134,
                    "content": "心输出量是每分钟一侧心室射出的血量，是评价心脏泵血功能的重要指标。动脉血压是血液对单位面积动脉管壁的侧压力，受心输出量、外周阻力和循环血量影响。压力感受性反射参与短期血压调节。",
                    "char_count": 110,
                },
            ],
        ),
        Textbook(
            textbook_id="book_demo_pathology",
            filename="demo_病理生理学.txt",
            title="Demo 病理生理学",
            format="txt",
            total_pages=2,
            total_chars=1300,
            chapters=[
                {
                    "chapter_id": "ch_001",
                    "title": "第一章 疾病概论",
                    "page_start": 1,
                    "page_end": 12,
                    "content": "内环境稳态是机体维持细胞外液理化性质相对稳定的状态。稳态破坏可导致疾病发生。白细胞又称 leukocyte，是参与免疫防御和炎症反应的重要血细胞。炎症反应是机体对损伤因子的防御性反应。",
                    "char_count": 100,
                }
            ],
        ),
    ]
    for b in demo_books:
        store.upsert_book(b)
    return demo_books
