from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List

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
        top_decisions = integrated.decisions[:5]
        lines = [
            "# 教材知识整合报告",
            "",
            f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 1. 整合概览",
            "",
            f"- 原始教材数量：{stats.get('original_books', len(books))}",
            f"- 原始总字数：{stats.get('original_chars', sum(b.total_chars for b in books))}",
            f"- 整合后精华字数：{stats.get('integrated_chars', 0)}",
            f"- 压缩比：{stats.get('compression_ratio', 0)}%（目标 ≤ 30%）",
            f"- 向量/对齐后端：{stats.get('embedding_backend', 'tfidf')}",
            "",
            "## 2. 整合决策摘要",
            "",
            f"- 合并：{stats.get('merge_count', 0)} 项",
            f"- 保留：{stats.get('keep_count', 0)} 项",
            f"- 删除：{stats.get('remove_count', 0)} 项",
            f"- 节点：{stats.get('nodes_before', 0)} → {stats.get('nodes_after', 0)}",
            f"- 关系：{stats.get('edges_before', 0)} → {stats.get('edges_after', 0)}",
            "",
            "## 3. 重点整合案例",
            "",
        ]
        if top_decisions:
            for d in top_decisions:
                lines.extend([
                    f"### {d.decision_id} · {d.action}",
                    f"- 影响节点：{', '.join(d.affected_nodes[:8])}",
                    f"- 结果节点：{d.result_node or '无'}",
                    f"- 置信度：{d.confidence:.2f}",
                    f"- 理由：{d.reason}",
                    "",
                ])
        else:
            lines.append("当前尚未运行整合。上传教材并点击“跨教材整合”后，本报告会自动填充真实数据。")
        lines.extend([
            "## 4. 教学完整性说明",
            "",
            "系统采用“章节主线 + 关键概念 + 关系约束”的方式保证压缩后教学逻辑不断裂：",
            "",
            "1. 前置依赖边保留学习顺序，避免先学应用后学基础。",
            "2. contains 边保留上位概念到下位概念的覆盖关系。",
            "3. parallel 边保留同层概念对比学习所需的结构。",
            "4. applies_to 边保留基础知识与临床/实践场景之间的桥接。",
            "5. 教师反馈可锁定 keep/split/remove 决策，防止算法误删关键知识点。",
            "",
            "## 5. 后续优化建议",
            "",
            "- 若有 7 本完整教材，建议上传全部教材后重新生成本报告，使统计与实际运行结果完全一致。",
            "- 对低置信度 merge 决策进行教师复核，可显著提高教学完整性。",
            "- 使用本地 BGE-small-zh 或 OpenAI Embedding 后端可提升跨表述语义对齐质量。",
        ])
        return "\n".join(lines)

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
