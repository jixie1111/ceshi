from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, List

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from ..core.config import get_settings
from ..models.schemas import IntegratedGraph, Textbook


class ReportService:
    def __init__(self) -> None:
        settings = get_settings()
        self.report_dir = settings.data_dir.parent / "generated_reports"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def generate_markdown(self, books: List[Textbook], integrated: IntegratedGraph) -> str:
        stats = integrated.stats or {}
        graph_stats = self._load_book_graph_stats()
        top_decisions = self._select_case_decisions(integrated)
        nodes_by_id = {node.id: node for node in integrated.nodes}
        compression_ratio = float(stats.get("compression_ratio", 0) or 0)
        target_exceeded = bool(stats.get("target_exceeded", False))
        compression_note = "满足不超过 30% 的赛题约束" if compression_ratio <= 30 and not target_exceeded else "超过 30%，需要继续压缩"
        lines = [
            "# 教材知识整合报告",
            "",
            f"> 本报告基于赛方提供的 {len(books)} 本教材运行态数据生成，数据来自本地 Web 系统完成上传、解析、单书图谱构建与跨教材整合后的结果。生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 1. 整合概览",
            "",
            f"- 原始教材数量：{_fmt_int(stats.get('original_books', len(books)))}",
            f"- 原始总字数：{_fmt_int(stats.get('original_chars', sum(b.total_chars for b in books)))}",
            f"- 整合后精华字数：{_fmt_int(stats.get('integrated_chars', 0))}",
            f"- 30% 目标字数：{_fmt_int(stats.get('target_chars', int((stats.get('original_chars', 0) or 0) * 0.3)))}",
            f"- 压缩比：{stats.get('compression_ratio', 0)}%（{compression_note}）",
            f"- 向量/对齐后端：{self._backend_label(str(stats.get('embedding_backend', 'tfidf')))}",
            "",
            "| 教材 | 章节数 | 原始字数 | 单书节点数 | 单书关系数 |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
        for book in books:
            book_graph = graph_stats.get(book.textbook_id, {})
            lines.append(
                f"| {book.title} | {len(book.chapters)} | {_fmt_int(book.total_chars)} | "
                f"{_fmt_int(book_graph.get('nodes', 0))} | {_fmt_int(book_graph.get('edges', 0))} |"
            )
        lines.extend([
            "",
            "## 2. 整合决策摘要",
            "",
            f"- 整合决策总数：{_fmt_int(len(integrated.decisions))} 项",
            f"- 合并：{_fmt_int(stats.get('merge_count', 0))} 项",
            f"- 保留：{_fmt_int(stats.get('keep_count', 0))} 项",
            f"- 删除：{_fmt_int(stats.get('remove_count', 0))} 项",
            f"- 整合前节点数：{_fmt_int(stats.get('nodes_before', 0))}",
            f"- 整合后节点数：{_fmt_int(stats.get('nodes_after', 0))}",
            f"- 整合前关系数：{_fmt_int(stats.get('edges_before', 0))}",
            f"- 整合后关系数：{_fmt_int(stats.get('edges_after', 0))}",
            "",
            "系统优先合并跨教材重复概念，对具有独立教学意义的节点执行 keep；当前未执行硬删除，以避免在自动评审和教师复核前误删关键知识点。压缩主要通过节点合并、别名聚合、章节摘要和 RAG 精华片段控制实现。",
            "",
            "## 3. 知识图谱统计",
            "",
            "系统先为每本教材构建单书知识图谱，再进行跨教材对齐。节点保留教材、章节、页码、定义、频次、别名与重要度；关系覆盖 prerequisite、parallel、contains、applies_to 四类。",
            "",
            f"整合后图谱包含 {_fmt_int(len(integrated.nodes))} 个核心节点和 {_fmt_int(len(integrated.edges))} 条关系。前端默认展示高频/高关联核心子图，并支持搜索邻域、教材筛选、力导向图、章节树和关系矩阵，避免大图一次性渲染造成卡顿。",
            "",
            "## 4. 重点整合案例",
            "",
        ])
        if top_decisions:
            for d in top_decisions:
                node = nodes_by_id.get(d.result_node or "")
                title = node.name if node else d.result_node or d.decision_id
                lines.extend([
                    f"### 案例：{title}",
                    f"- 决策类型：{d.action}",
                    f"- 影响范围：{len(d.affected_nodes)} 个节点",
                    f"- 结果节点：{d.result_node or '无'}",
                    f"- 置信度：{d.confidence:.2f}",
                    f"- 理由：{d.reason}",
                    "",
                ])
        else:
            lines.append("当前尚未运行整合。上传教材并点击“跨教材整合”后，本报告会自动填充真实数据。")
        lines.extend([
            "## 5. 教学完整性说明",
            "",
            "系统采用“章节主线 + 关键概念 + 关系约束”的方式保证压缩后教学逻辑不断裂：",
            "",
            "1. 前置依赖边保留学习顺序，避免先学应用后学基础。",
            "2. contains 边保留上位概念到下位概念的覆盖关系。",
            "3. parallel 边保留同层概念对比学习所需的结构。",
            "4. applies_to 边保留基础知识与临床/实践场景之间的桥接。",
            "5. aliases 和引用来源保留不同教材的表达差异，RAG 回答仍能回溯到教材、章节和页码。",
            "6. 教师反馈可以锁定 keep / split / remove 决策，防止算法误合并或误删关键知识点。",
            "",
            "## 6. 当前风险与复核建议",
            "",
            "- 高频泛化词可能存在过合并风险，建议教师在最终演示前重点复核。",
            "- 当前默认部署使用 TF-IDF + BM25，优点是无需下载大模型、部署稳定；如果评审环境允许，可启用 sentence-transformers 或 OpenAI Embedding 提升跨表述语义对齐质量。",
            "- 7 本教材 PDF 不进入 GitHub 仓库，评审时通过前端上传教材重新生成图谱、索引和报告。",
        ])
        return "\n".join(lines)

    def _load_book_graph_stats(self) -> Dict[str, Dict[str, int]]:
        graph_path = get_settings().data_dir / "graphs.json"
        if not graph_path.exists():
            return {}
        try:
            raw = json.loads(graph_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return {
            book_id: {"nodes": len(payload.get("nodes", [])), "edges": len(payload.get("edges", []))}
            for book_id, payload in raw.items()
            if isinstance(payload, dict)
        }

    @staticmethod
    def _select_case_decisions(integrated: IntegratedGraph) -> List[Any]:
        nodes_by_id = {node.id: node for node in integrated.nodes}
        merges = [d for d in integrated.decisions if d.action == "merge"]
        preferred = ["感染", "抗原", "受体", "抗体", "炎症"]
        selected = []
        for name in preferred:
            match = next((d for d in merges if nodes_by_id.get(d.result_node or "") and nodes_by_id[d.result_node or ""].name == name), None)
            if match and match not in selected:
                selected.append(match)
        for decision in sorted(merges, key=lambda d: (-len(d.affected_nodes), -d.confidence, d.decision_id)):
            if decision not in selected:
                selected.append(decision)
            if len(selected) >= 5:
                break
        return selected[:5]

    @staticmethod
    def _backend_label(backend: str) -> str:
        if backend == "tfidf":
            return "TF-IDF 字符 n-gram + BM25 + RapidFuzz 名称约束"
        return backend

    def save_markdown(self, content: str) -> Path:
        target = self.report_dir / "整合报告.md"
        target.write_text(content, encoding="utf-8")
        return target

    def markdown_to_pdf(self, markdown_text: str) -> Path:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        target = self.report_dir / "整合报告.pdf"
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="Chinese", fontName="STSong-Light", fontSize=10, leading=16))
        styles.add(ParagraphStyle(name="ChineseTitle", fontName="STSong-Light", fontSize=18, leading=24, spaceAfter=12))
        doc = SimpleDocTemplate(str(target), pagesize=A4)
        story = []
        for line in markdown_text.splitlines():
            if not line.strip():
                story.append(Spacer(1, 8))
                continue
            if line.startswith("# "):
                story.append(Paragraph(line[2:], styles["ChineseTitle"]))
            elif line.startswith("## "):
                story.append(Paragraph(f"<b>{line[3:]}</b>", styles["Chinese"]))
            elif line.startswith("### "):
                story.append(Paragraph(f"<b>{line[4:]}</b>", styles["Chinese"]))
            else:
                story.append(Paragraph(line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), styles["Chinese"]))
        doc.build(story)
        return target


def _fmt_int(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except Exception:
        return str(value)
