from __future__ import annotations

import json
import shutil
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

OWNER = "\u738b\u7855"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backend.app.services.knowledge_extractor import KnowledgeExtractor

EXPORTS_DIR = PROJECT_ROOT / "exports"
RUNTIME_DIR = PROJECT_ROOT / "data" / "runtime"
DIST_DIR = PROJECT_ROOT / "src" / "frontend" / "dist"
REPORT_DIR = PROJECT_ROOT / "report"


def main() -> None:
    books = _read_json(RUNTIME_DIR / "books.json")
    graphs = _read_json(RUNTIME_DIR / "graphs.json")
    integration = _read_json(RUNTIME_DIR / "integration.json")
    graphs = _clean_graph_payload(graphs)
    integration = _clean_graph_payload(integration)
    generated_at = datetime.now().isoformat(timespec="seconds")

    if len(books) != 7:
        raise RuntimeError(f"Expected 7 books, found {len(books)}")
    if not isinstance(graphs, dict) or len(graphs) != 7:
        raise RuntimeError(f"Expected 7 book graphs, found {len(graphs) if isinstance(graphs, dict) else 'invalid'}")

    export_root = EXPORTS_DIR / OWNER
    zip_path = EXPORTS_DIR / f"{OWNER}.zip"
    _backup_existing(export_root, zip_path)

    (export_root / "单书知识图谱").mkdir(parents=True, exist_ok=True)
    (export_root / "整合成果").mkdir(parents=True, exist_ok=True)
    (export_root / "运行数据备份").mkdir(parents=True, exist_ok=True)
    (export_root / "可视化知识图谱").mkdir(parents=True, exist_ok=True)

    graph_by_book = {graph.get("textbook_id"): graph for graph in graphs.values() if isinstance(graph, dict)}

    for book in books:
        book_title = book["title"]
        book_dir = export_root / "单书知识图谱" / _safe_name(book_title)
        book_dir.mkdir(parents=True, exist_ok=True)
        graph = graph_by_book.get(book["textbook_id"], {"textbook_id": book["textbook_id"], "nodes": [], "edges": []})
        _write_json(book_dir / "knowledge_graph.json", graph)
        (book_dir / "knowledge_graph_summary.md").write_text(
            _book_summary(book, graph),
            encoding="utf-8",
        )

    backup_books = _books_for_export(books)
    _write_json(export_root / "运行数据备份" / "books.json", backup_books)
    _write_json(export_root / "运行数据备份" / "graphs.json", graphs)
    _write_json(export_root / "运行数据备份" / "integration.json", integration)

    _write_json(export_root / "整合成果" / "integrated_graph.json", integration)
    _write_json(export_root / "整合成果" / "integration_decisions.json", integration.get("decisions", []))
    (export_root / "整合成果" / "integration_decisions_summary.md").write_text(
        _decision_summary(integration),
        encoding="utf-8",
    )
    refined = _refined_book(books, integration)
    report = _report_markdown(books, graphs, integration, generated_at)
    (export_root / "整合成果" / "七本教材整合后精华版.md").write_text(refined, encoding="utf-8")
    (export_root / "整合成果" / "系统生成报告.md").write_text(report, encoding="utf-8")
    (export_root / "整合成果" / "整合报告.md").write_text(report, encoding="utf-8")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "整合报告.md").write_text(report, encoding="utf-8")

    summary = _export_summary(books, graphs, integration, generated_at)
    _write_json(export_root / "成果摘要.json", summary)
    (export_root / "README.md").write_text(_root_readme(summary), encoding="utf-8")
    (export_root / "打开说明.txt").write_text(_open_instructions(), encoding="utf-8")
    (export_root / "双击打开可视化图谱.cmd").write_text(_launcher_cmd(), encoding="utf-8-sig")
    _write_viewer(export_root / "可视化知识图谱", backup_books, graphs, integration, report)

    _zip_folder(export_root, zip_path)
    digest = _sha256(zip_path)
    (EXPORTS_DIR / f"{OWNER}.sha256.txt").write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")
    print(json.dumps({"export_root": str(export_root), "zip_path": str(zip_path), "sha256": digest, "summary": summary}, ensure_ascii=False, indent=2))


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _clean_graph_payload(payload: Any) -> Any:
    extractor = KnowledgeExtractor()

    def clean_graph(graph: dict[str, Any]) -> dict[str, Any]:
        graph = dict(graph)
        graph["nodes"] = [
            {**node, "definition": extractor._clean_definition(str(node.get("name", "")), str(node.get("definition", "")))}
            for node in graph.get("nodes", [])
        ]
        return graph

    if isinstance(payload, dict) and isinstance(payload.get("nodes"), list):
        return clean_graph(payload)
    if isinstance(payload, dict):
        return {key: clean_graph(value) if isinstance(value, dict) and isinstance(value.get("nodes"), list) else value for key, value in payload.items()}
    return payload


def _books_for_export(books: list[dict[str, Any]]) -> list[dict[str, Any]]:
    exported = []
    for book in books:
        clean_book = dict(book)
        clean_book["chapters"] = [
            {**chapter, "content": ""}
            for chapter in book.get("chapters", [])
        ]
        exported.append(clean_book)
    return exported


def _backup_existing(export_root: Path, zip_path: Path) -> None:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    if export_root.exists():
        target = EXPORTS_DIR / f"backup_{OWNER}_{stamp}"
        shutil.move(str(export_root), str(target))
    if zip_path.exists():
        target_zip = EXPORTS_DIR / f"backup_{OWNER}_{stamp}.zip"
        shutil.move(str(zip_path), str(target_zip))


def _safe_name(value: str) -> str:
    return "".join(ch if ch not in '<>:"/\\|?*' else "_" for ch in value).strip() or "未命名"


def _book_summary(book: dict[str, Any], graph: dict[str, Any]) -> str:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    chapter_counter = Counter(node.get("chapter") or "未标注章节" for node in nodes)
    lines = [
        f"# {book['title']} 知识图谱摘要",
        "",
        f"- 章节数：{len(book.get('chapters', []))}",
        f"- 知识点数：{len(nodes)}",
        f"- 关系数：{len(edges)}",
        "",
        "## 教材章节",
        "",
    ]
    for chapter in book.get("chapters", []):
        lines.append(
            f"- {chapter.get('title')}（第 {chapter.get('page_start')}–{chapter.get('page_end')} 页，{chapter.get('char_count')} 字）"
        )
    lines.extend(["", "## 章节节点分布", ""])
    for chapter, count in chapter_counter.most_common():
        lines.append(f"- {chapter}：{count} 个节点")
    lines.extend(["", "## 重要知识点示例", ""])
    for node in sorted(nodes, key=lambda item: (-float(item.get("importance", 0) or 0), item.get("name", "")))[:30]:
        lines.append(f"- {node.get('name')}（{node.get('chapter')}，{node.get('category')}，第 {node.get('page')} 页）")
    lines.append("")
    return "\n".join(lines)


def _decision_summary(integration: dict[str, Any]) -> str:
    decisions = integration.get("decisions", [])
    stats = integration.get("stats", {})
    counter = Counter(d.get("action", "unknown") for d in decisions)
    lines = [
        "# 跨教材整合决策摘要",
        "",
        f"- 决策总数：{len(decisions)}",
        f"- 合并：{counter.get('merge', stats.get('merge_count', 0))}",
        f"- 保留：{counter.get('keep', stats.get('keep_count', 0))}",
        f"- 删除：{counter.get('remove', stats.get('remove_count', 0))}",
        f"- 整合后节点：{len(integration.get('nodes', []))}",
        f"- 整合后关系：{len(integration.get('edges', []))}",
        "",
        "## 高置信度合并示例",
        "",
    ]
    for d in sorted((d for d in decisions if d.get("action") == "merge"), key=lambda item: (-float(item.get("confidence", 0) or 0), item.get("decision_id", "")))[:30]:
        affected = "、".join(d.get("affected_nodes", [])[:5])
        lines.append(f"- {d.get('decision_id')}：置信度 {float(d.get('confidence', 0) or 0):.2f}，结果节点 {d.get('result_node')}，来源 {affected}")
    lines.append("")
    return "\n".join(lines)


def _refined_book(books: list[dict[str, Any]], integration: dict[str, Any]) -> str:
    nodes_by_book_chapter: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for node in integration.get("nodes", []):
        nodes_by_book_chapter[(node.get("textbook_title", ""), node.get("chapter", ""))].append(node)

    lines = [
        "# 七本教材整合后精华版",
        "",
        "本文件按教材和章节组织整合后的核心知识点，保留名称、类型、页码、定义片段和来源，便于医学院单独复核。",
        "",
    ]
    for book in books:
        lines.extend([f"## {book['title']}", ""])
        for chapter in book.get("chapters", []):
            title = chapter.get("title", "")
            chapter_nodes = nodes_by_book_chapter.get((book["title"], title), [])
            lines.extend([f"### {title}", ""])
            if not chapter_nodes:
                lines.append("本章未保留独立核心节点，相关内容可能已并入跨教材同名或近义概念。")
                lines.append("")
                continue
            for node in sorted(chapter_nodes, key=lambda item: (-float(item.get("importance", 0) or 0), item.get("name", "")))[:20]:
                definition = " ".join(str(node.get("definition", "")).split())
                if len(definition) > 180:
                    definition = definition[:180] + "..."
                lines.append(f"- **{node.get('name')}**（{node.get('category')}，第 {node.get('page')} 页）：{definition}")
            lines.append("")
    return "\n".join(lines)


def _report_markdown(books: list[dict[str, Any]], graphs: dict[str, Any], integration: dict[str, Any], generated_at: str) -> str:
    stats = integration.get("stats", {})
    graph_by_book = {graph.get("textbook_id"): graph for graph in graphs.values() if isinstance(graph, dict)}
    lines = [
        "# 教材知识整合报告",
        "",
        f"> 本报告基于赛方七本教材的当前运行态数据生成。生成时间：{generated_at}",
        "",
        "## 1. 整合概览",
        "",
        f"- 原始教材数量：{stats.get('original_books', len(books))}",
        f"- 原始总字数：{stats.get('original_chars', 0):,}",
        f"- 整合后精华字数：{stats.get('integrated_chars', 0):,}",
        f"- 压缩比：{stats.get('compression_ratio', 0)}%",
        f"- 整合后节点数：{len(integration.get('nodes', []))}",
        f"- 整合后关系数：{len(integration.get('edges', []))}",
        f"- 向量/对齐后端：{stats.get('embedding_backend', 'unknown')}",
        "",
        "| 教材 | 章节数 | 原始字数 | 单书节点数 | 单书关系数 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for book in books:
        graph = graph_by_book.get(book["textbook_id"], {})
        lines.append(
            f"| {book['title']} | {len(book.get('chapters', []))} | {book.get('total_chars', 0):,} | "
            f"{len(graph.get('nodes', []))} | {len(graph.get('edges', []))} |"
        )
    lines.extend([
        "",
        "## 2. 可视化与交付说明",
        "",
        "离线可视化页面内置当前七本教材、单书图谱和整合图谱数据。页面左侧应显示 7 本教材，中间图谱支持力导向、章节树和关系矩阵三种视图切换。",
        "",
        "## 3. 复核建议",
        "",
        "本次导出已优先修正章节标题识别、目录页干扰、正文内章节引用误识别和短语截断类错误。自动抽取仍建议由教师重点复核高频泛化词、跨教材合并概念和少量 OCR 噪声。",
        "",
    ])
    return "\n".join(lines)


def _export_summary(books: list[dict[str, Any]], graphs: dict[str, Any], integration: dict[str, Any], generated_at: str) -> dict[str, Any]:
    graph_by_book = {graph.get("textbook_id"): graph for graph in graphs.values() if isinstance(graph, dict)}
    return {
        "owner": OWNER,
        "generated_at": generated_at,
        "book_count": len(books),
        "books": [
            {
                "title": book["title"],
                "chapters": len(book.get("chapters", [])),
                "chapter_titles": [chapter.get("title") for chapter in book.get("chapters", [])],
                "nodes": len(graph_by_book.get(book["textbook_id"], {}).get("nodes", [])),
                "edges": len(graph_by_book.get(book["textbook_id"], {}).get("edges", [])),
            }
            for book in books
        ],
        "integration_stats": integration.get("stats", {}),
        "integrated_nodes": len(integration.get("nodes", [])),
        "integrated_edges": len(integration.get("edges", [])),
    }


def _root_readme(summary: dict[str, Any]) -> str:
    lines = [
        f"# {OWNER} - AI 教材知识整合成果",
        "",
        "本压缩包包含七本教材的单书知识图谱、跨教材整合图谱、整合精华版、系统报告、运行数据备份和可双击打开的可视化知识图谱。",
        "",
        "## 内容清单",
        "",
        "- 单书知识图谱：每本教材的 JSON 图谱和 Markdown 摘要",
        "- 整合成果：跨教材整合图谱、整合决策、整合后精华版和报告",
        "- 可视化知识图谱：离线 HTML 页面，支持力导向、章节树、关系矩阵",
        "- 运行数据备份：books.json、graphs.json、integration.json",
        "",
        "## 教材章节数",
        "",
    ]
    for book in summary["books"]:
        lines.append(f"- {book['title']}：{book['chapters']} 章")
    lines.extend(["", "打开方式：双击“双击打开可视化图谱.cmd”，或进入“可视化知识图谱”文件夹打开 index.html。", ""])
    return "\n".join(lines)


def _open_instructions() -> str:
    return "\n".join(
        [
            "1. 双击“双击打开可视化图谱.cmd”。",
            "2. 如果浏览器安全策略拦截，请进入“可视化知识图谱”文件夹，双击 index.html。",
            "3. 页面左侧应显示 7 本教材。",
            "4. 中间图谱支持“力导向 / 章节树 / 关系矩阵”切换。",
            "",
        ]
    )


def _launcher_cmd() -> str:
    return "\n".join(
        [
            "@echo off",
            "setlocal",
            "set VIEWER=%~dp0可视化知识图谱\\index.html",
            'start "" "%VIEWER%"',
            "endlocal",
            "",
        ]
    )


def _write_viewer(target_dir: Path, books: list[dict[str, Any]], graphs: dict[str, Any], integration: dict[str, Any], report: str) -> None:
    index_html = (DIST_DIR / "index.html").read_text(encoding="utf-8")
    css_ref = _extract_between(index_html, 'href="/assets/', '"')
    js_ref = _extract_between(index_html, 'src="/assets/', '"')
    if not css_ref or not js_ref:
        raise RuntimeError("Could not locate frontend assets in dist/index.html")
    css = (DIST_DIR / "assets" / css_ref).read_text(encoding="utf-8")
    js = (DIST_DIR / "assets" / js_ref).read_text(encoding="utf-8")
    data = {"books": books, "graphs": graphs, "integration": integration, "report": report}
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    data_json = data_json.replace("</script", "<\\/script")
    html = f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{OWNER} - 可视化知识图谱</title>
    <style>{css}</style>
    <script>
window.__OFFLINE_DATA__={data_json};
(function(){{
  const data = window.__OFFLINE_DATA__;
  const ok = (payload) => Promise.resolve({{
    ok: true,
    status: 200,
    statusText: 'OK',
    json: () => Promise.resolve(payload),
    text: () => Promise.resolve(JSON.stringify(payload))
  }});
  window.fetch = function(input, init) {{
    const raw = String(typeof input === 'string' ? input : (input && input.url) || '');
    const path = raw.replace(/^https?:\\/\\/[^/]+/, '');
    if (path === '/api/textbooks' || path === '/api/textbooks/upload' || path === '/api/demo/load') return ok(data.books);
    if (path === '/api/integration' || path === '/api/integration/run') return ok(data.integration);
    const graphMatch = path.match(/^\\/api\\/graph\\/([^/]+)(?:\\/build)?$/);
    if (graphMatch) {{
      const id = decodeURIComponent(graphMatch[1]);
      return ok(data.graphs[id] || {{ textbook_id: id, nodes: [], edges: [] }});
    }}
    if (path === '/api/report/generate') return ok({{ message: 'offline', data: {{ markdown: data.report || '' }} }});
    if (path === '/api/rag/status' || path === '/api/rag/index') return ok({{ indexed_books: data.books.length, chunk_count: 0, embedding_backend: data.integration.stats && data.integration.stats.embedding_backend || 'offline' }});
    if (path === '/api/rag/query') return ok({{ answer: '离线导出包保留图谱与报告数据，问答索引需在系统运行时重新构建。', citations: [], source_chunks: [], latency_ms: 0 }});
    if (path === '/api/benchmark/run') return ok({{ score: 0, details: [] }});
    if (path === '/api/dialogue/history') return ok([]);
    if (path === '/api/dialogue/message') return ok({{ role: 'assistant', content: '离线导出包不支持实时对话。' }});
    return ok({{ message: '离线包不支持该接口', data: null }});
  }};
}})();
    </script>
  </head>
  <body>
    <div id="root"></div>
    <script type="module">{js}</script>
  </body>
</html>
"""
    for name in ["index.html", "viewer.html", "offline-index.html", "offline-viewer.html"]:
        (target_dir / name).write_text(html, encoding="utf-8")
    (target_dir / "README.md").write_text(
        "# 可视化知识图谱\n\n打开 index.html 即可查看离线图谱。页面内置七本教材、单书图谱和整合图谱，支持力导向、章节树、关系矩阵视图。\n",
        encoding="utf-8",
    )


def _extract_between(text: str, prefix: str, suffix: str) -> str:
    start = text.find(prefix)
    if start < 0:
        return ""
    start += len(prefix)
    end = text.find(suffix, start)
    return text[start:end] if end >= 0 else ""


def _zip_folder(folder: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                zf.write(path, (Path(OWNER) / path.relative_to(folder)).as_posix())


def _sha256(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


if __name__ == "__main__":
    main()
