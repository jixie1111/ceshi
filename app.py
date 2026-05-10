from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import gradio as gr

from src.backend.app.core.config import get_settings
from src.backend.app.services.dialogue_agent import DialogueAgent
from src.backend.app.services.file_parser import TextbookParser
from src.backend.app.services.graph_integrator import GraphIntegrator
from src.backend.app.services.knowledge_extractor import KnowledgeExtractor
from src.backend.app.services.rag_engine import rag_engine
from src.backend.app.services.report_service import ReportService
from src.backend.app.storage import store


settings = get_settings()
parser = TextbookParser(settings.upload_dir)
extractor = KnowledgeExtractor()
integrator = GraphIntegrator()
dialogue_agent = DialogueAgent()
reporter = ReportService()


def _summary() -> str:
    books = store.list_books()
    integrated = store.get_integration()
    stats = integrated.stats or {}
    return "\n".join(
        [
            f"已加载教材：{len(books)} 本",
            f"整合节点：{len(integrated.nodes)}",
            f"整合关系：{len(integrated.edges)}",
            f"整合决策：{len(integrated.decisions)}",
            f"压缩比：{stats.get('compression_ratio', 0)}%",
            f"RAG 索引：{rag_engine.status.chunk_count} 个知识块",
        ]
    )


def load_demo() -> str:
    from src.backend.app.main import load_demo as _load_demo

    books = _load_demo()
    return f"已加载演示教材 {len(books)} 本。\n\n{_summary()}"


def upload_textbooks(files: list[str] | None) -> str:
    if not files:
        return "请先选择 PDF / Markdown / TXT / DOCX / Excel 教材文件。"
    rows = []
    for file_path in files:
        source = Path(file_path)
        target = settings.upload_dir / f"{int(time.time() * 1000)}_{source.name}"
        shutil.copyfile(source, target)
        book = parser.parse(target, source.name)
        store.upsert_book(book)
        rows.append(f"- {book.title}：{len(book.chapters)} 章，{book.total_chars} 字")
    return "上传解析完成：\n" + "\n".join(rows) + "\n\n" + _summary()


def build_graphs_and_integrate() -> str:
    books = store.list_books()
    if not books:
        return "请先上传教材，或点击加载演示数据。"
    graphs = store.list_graphs()
    for book in books:
        if book.textbook_id not in graphs:
            graph = extractor.build_graph(book)
            store.save_graph(graph)
            graphs[book.textbook_id] = graph
    integrated = integrator.integrate(books, graphs)
    store.save_integration(integrated)
    stats = integrated.stats
    return "\n".join(
        [
            "跨教材整合完成。",
            f"- 教材数：{stats.get('original_books', len(books))}",
            f"- 节点：{stats.get('nodes_before', 0)} -> {stats.get('nodes_after', 0)}",
            f"- 关系：{stats.get('edges_before', 0)} -> {stats.get('edges_after', 0)}",
            f"- 合并：{stats.get('merge_count', 0)} 项",
            f"- 保留：{stats.get('keep_count', 0)} 项",
            f"- 压缩比：{stats.get('compression_ratio', 0)}%",
        ]
    )


def build_rag() -> str:
    books = store.list_books()
    if not books:
        return "请先上传教材，或点击加载演示数据。"
    status = rag_engine.build_index(books)
    return f"RAG 索引完成：{status.indexed_books} 本教材，{status.chunk_count} 个知识块，后端 {status.embedding_backend}。"


def ask(question: str) -> str:
    if not question.strip():
        return "请输入问题。"
    if rag_engine.status.chunk_count == 0:
        rag_engine.build_index(store.list_books())
    answer = rag_engine.query(question, top_k=5)
    cites = "\n".join(
        f"- [{c.textbook}, {c.chapter}, 第 {c.page} 页] 相关度 {c.relevance_score:.2f}"
        for c in answer.citations
    )
    return f"{answer.answer}\n\n### 引用来源\n{cites or '当前知识库中未找到相关信息'}"


def chat(message: str) -> str:
    if not message.strip():
        return "请输入反馈，例如：保留 抗原 / 拆分 抗原 / 为什么合并 感染。"
    graph = store.get_integration()
    resp = dialogue_agent.handle(message, graph)
    if resp.graph_changed:
        store.save_integration(graph)
    return resp.reply + "\n\n" + _summary()


def generate_report() -> str:
    content = reporter.generate_markdown(store.list_books(), store.get_integration())
    reporter.save_markdown(content)
    return content


with gr.Blocks(title="KnowledgeForge") as demo:
    gr.Markdown(
        """
        # KnowledgeForge · 学科知识整合智能体
        面向 AI 全栈极速黑客松：教材解析、知识图谱、跨教材整合、RAG 带引用问答、教师反馈和整合报告。
        """
    )
    status = gr.Textbox(label="运行状态", value=_summary(), lines=6)
    with gr.Row():
        demo_btn = gr.Button("加载演示数据")
        integrate_btn = gr.Button("构建图谱并整合")
        rag_btn = gr.Button("建立 RAG 索引")
    with gr.Tab("教材上传"):
        files = gr.File(label="上传教材", file_count="multiple", type="filepath")
        upload_btn = gr.Button("上传并解析")
        upload_out = gr.Textbox(label="解析结果", lines=10)
    with gr.Tab("RAG 问答"):
        question = gr.Textbox(label="问题", placeholder="例如：炎症是什么？请引用来源。")
        ask_btn = gr.Button("提问")
        answer = gr.Markdown()
    with gr.Tab("教师反馈"):
        message = gr.Textbox(label="反馈", placeholder="例如：保留 抗原；为什么合并 感染？")
        chat_btn = gr.Button("提交反馈")
        chat_out = gr.Textbox(label="反馈结果", lines=8)
    with gr.Tab("整合报告"):
        report_btn = gr.Button("生成报告")
        report = gr.Markdown()
    with gr.Tab("项目链接"):
        gr.Markdown(
            """
            - GitHub 仓库：<https://github.com/jixie1111/ceshi>
            - 创空间链接：<https://modelscope.cn/studios/jixie1111/knowledgeforge>
            - 说明：教材 PDF 不随仓库上传，评审时可在本页面上传教材并重新生成图谱、索引和报告。
            """
        )

    demo_btn.click(load_demo, outputs=status)
    integrate_btn.click(build_graphs_and_integrate, outputs=status)
    rag_btn.click(build_rag, outputs=status)
    upload_btn.click(upload_textbooks, inputs=files, outputs=upload_out)
    ask_btn.click(ask, inputs=question, outputs=answer)
    chat_btn.click(chat, inputs=message, outputs=chat_out)
    report_btn.click(generate_report, outputs=report)


if __name__ == "__main__":
    port = int(os.environ.get("PORT") or os.environ.get("GRADIO_SERVER_PORT") or "7860")
    demo.launch(server_name="0.0.0.0", server_port=port)
