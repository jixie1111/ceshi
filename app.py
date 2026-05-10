"""
KnowledgeForge - 学科知识整合智能体
ModelScope Gradio 完整可运行应用
"""

import gradio as gr
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from src.backend.app.main import (
    app as fastapi_app,
    parser,
    extractor,
    integrator,
    dialogue_agent,
    reporter,
    store,
    rag_engine,
)
from src.backend.app.models.schemas import ApiMessage


class KnowledgeForgeApp:
    def __init__(self):
        self.current_books = []
        self.current_graph = None
        self.current_integration = None

    def upload_textbooks(self, files):
        if not files:
            return "请上传教材文件", self.list_textbooks()
        results = []
        for file in files:
            try:
                path = parser.save_upload(file)
                book = parser.parse(path, file.name)
                store.upsert_book(book)
                results.append(f"✓ {book.title}")
            except Exception as e:
                results.append(f"✗ {file.name}: {str(e)}")
        self.current_books = store.list_books()
        return "\n".join(results) if results else "上传失败", self.list_textbooks()

    def list_textbooks(self):
        books = store.list_books()
        if not books:
            return "暂无教材，请上传或加载演示数据"
        lines = []
        for b in books:
            lines.append(f"📚 {b.title} ({b.format}) - {b.total_chars}字")
            for ch in b.chapters[:3]:
                lines.append(f"   • {ch.title}")
            if len(b.chapters) > 3:
                lines.append(f"   ... 共{len(b.chapters)}章")
        return "\n".join(lines)

    def load_demo(self):
        try:
            from src.backend.app.main import load_demo
            books = load_demo()
            self.current_books = store.list_books()
            return f"✓ 已加载 {len(books)} 本演示教材", self.list_textbooks()
        except Exception as e:
            return f"加载失败: {str(e)}", self.list_textbooks()

    def build_graph(self, textbook_id):
        if not textbook_id:
            return "请先选择或上传教材", ""
        try:
            graph = extractor.build_graph(store.get_book(textbook_id))
            store.save_graph(graph)
            self.current_graph = graph
            return f"✓ 图谱构建完成", self.format_graph_info(graph)
        except Exception as e:
            return f"构建失败: {str(e)}", ""

    def format_graph_info(self, graph):
        if not graph or not graph.nodes:
            return "图谱为空"
        lines = [f"📊 节点数: {len(graph.nodes)}", f"🔗 关系数: {len(graph.edges)}", "", "知识点:"]
        for i, node in enumerate(graph.nodes[:15]):
            lines.append(f"  • {node.name} ({node.category})")
        if len(graph.nodes) > 15:
            lines.append(f"  ... 还有 {len(graph.nodes) - 15} 个节点")
        return "\n".join(lines)

    def run_integration(self):
        try:
            books = store.list_books()
            if not books:
                return "请先上传教材或加载演示数据"
            integrated = integrator.integrate(books, store.list_graphs())
            store.save_integration(integrated)
            self.current_integration = integrated
            lines = [f"✓ 整合完成", f"📚 涉及 {len(integrated.nodes)} 个知识点", f"🔗 包含 {len(integrated.edges)} 条关系"]
            decisions = [d for d in integrated.decisions if d.action == "merge"]
            keeps = [d for d in integrated.decisions if d.action == "keep"]
            if decisions:
                lines.append(f"✅ 合并决策: {len(decisions)} 项")
            if keeps:
                lines.append(f"📌 保留决策: {len(keeps)} 项")
            return "\n".join(lines)
        except Exception as e:
            return f"整合失败: {str(e)}"

    def rag_query(self, question, top_k=3):
        if not question.strip():
            return "请输入问题"
        try:
            books = store.list_books()
            if not books:
                return "请先上传教材或加载演示数据"
            if rag_engine.status.chunk_count == 0:
                rag_engine.build_index(books)
            answer = rag_engine.query(question, top_k=top_k)
            lines = [answer.answer, "", "📖 引用来源:"]
            for cite in answer.citations:
                lines.append(f"  • [{cite.book}, {cite.chapter}, 第{cite.page}页] (相关度: {cite.score:.2f})")
            lines.append(f"\n⏱️ 响应时间: {answer.latency_ms}ms")
            return "\n".join(lines)
        except Exception as e:
            return f"查询失败: {str(e)}"

    def dialogue(self, message, history):
        if not message.strip():
            return history, ""
        try:
            graph = store.get_integration()
            if not graph or not graph.nodes:
                return history + [(message, "请先构建整合图谱")], ""
            resp = dialogue_agent.handle(message, graph)
            if resp.graph_changed:
                store.save_integration(graph)
            history = history + [(message, resp.reply)]
            return history, ""
        except Exception as e:
            return history + [(message, f"对话失败: {str(e)}")], ""

    def generate_report(self):
        try:
            content = reporter.generate_markdown(store.list_books(), store.get_integration())
            path = reporter.save_markdown(content)
            return content, str(path)
        except Exception as e:
            return f"报告生成失败: {str(e)}", ""


app_instance = KnowledgeForgeApp()


def upload_interface(files):
    result, book_list = app_instance.upload_textbooks(files)
    return result, book_list


def demo_interface():
    result, book_list = app_instance.load_demo()
    return result, book_list


def list_interface():
    return app_instance.list_textbooks()


def graph_interface(textbook_id):
    result, info = app_instance.build_graph(textbook_id)
    return result, info


def integration_interface():
    return app_instance.run_integration()


def rag_interface(question, top_k):
    return app_instance.rag_query(question, top_k)


def dialogue_interface(message, history):
    return app_instance.dialogue(message, history)


def report_interface():
    return app_instance.generate_report()


def get_textbook_choices():
    books = store.list_books()
    return [b.textbook_id for b in books], [(b.title, b.textbook_id) for b in books]


def refresh_textbook_list():
    books = store.list_books()
    choices = [b.textbook_id for b in books]
    return gr.update(choices=choices)


css = """
.gradio-container {max-width: 1400px !important; margin: auto !important;}
.header {text-align: center; padding: 20px; background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 10px; margin-bottom: 20px;}
.section {padding: 15px; border: 1px solid #ddd; border-radius: 8px; margin: 10px 0;}
"""


with gr.Blocks(css=css, title="KnowledgeForge · 学科知识整合智能体") as demo:
    gr.Markdown("""
    <div class="header">
        <h1>📚 KnowledgeForge · 学科知识整合智能体</h1>
        <p>多格式教材解析 · 知识图谱构建 · RAG 智能问答 · 跨教材整合</p>
    </div>
    """)

    with gr.Tabs():
        with gr.Tab(label="📤 教材管理"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### 上传教材")
                    file_upload = gr.File(
                        file_count="multiple",
                        file_types=[".pdf", ".txt", ".md", ".docx", ".xlsx"],
                        label="支持 PDF/TXT/MD/DOCX/Excel"
                    )
                    upload_btn = gr.Button("📤 上传", variant="primary")
                    upload_status = gr.Textbox(label="上传状态", lines=2, interactive=False)
                    demo_btn = gr.Button("📋 加载演示数据", variant="secondary")
                with gr.Column(scale=1):
                    gr.Markdown("### 教材列表")
                    book_list = gr.Textbox(label="已加载教材", lines=15, interactive=False)
                    refresh_btn = gr.Button("🔄 刷新")

            upload_btn.click(upload_interface, inputs=file_upload, outputs=[upload_status, book_list])
            demo_btn.click(demo_interface, outputs=[upload_status, book_list])
            refresh_btn.click(list_interface, outputs=book_list)

        with gr.Tab(label="🕸️ 知识图谱"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### 选择教材")
                    textbook_dropdown = gr.Dropdown(choices=[], label="选择教材")
                    refresh_btn2 = gr.Button("🔄 刷新列表")
                    build_btn = gr.Button("🔨 构建图谱", variant="primary")
                    graph_status = gr.Textbox(label="构建状态", lines=2, interactive=False)
                with gr.Column(scale=1):
                    gr.Markdown("### 图谱信息")
                    graph_output = gr.Textbox(label="图谱详情", lines=20, interactive=False)

            refresh_btn2.click(
                fn=lambda: ([b.textbook_id for b in store.list_books()], [(b.title, b.textbook_id) for b in store.list_books()]),
                outputs=textbook_dropdown
            )
            build_btn.click(graph_interface, inputs=textbook_dropdown, outputs=[graph_status, graph_output])

        with gr.Tab(label="🔗 跨书整合"):
            with gr.Column():
                gr.Markdown("### 跨教材知识整合")
                gr.Markdown("将多本教材的知识点进行去重、合并，生成统一的整合知识图谱")
                integrate_btn = gr.Button("🚀 一键整合全部教材", variant="primary", size="lg")
                integration_output = gr.Textbox(label="整合结果", lines=15, interactive=False)
            integrate_btn.click(integration_interface, outputs=integration_output)

        with gr.Tab(label="💬 RAG 问答"):
            with gr.Column():
                gr.Markdown("### 精准问答（带引用）")
                question_input = gr.Textbox(label="输入问题", placeholder="例如：炎症的机制是什么？", lines=2)
                with gr.Row():
                    top_k_slider = gr.Slider(1, 10, value=3, step=1, label="返回引用数")
                    rag_btn = gr.Button("🔍 提问", variant="primary")
                answer_output = gr.Textbox(label="回答", lines=12, interactive=False)
            rag_btn.click(rag_interface, inputs=[question_input, top_k_slider], outputs=answer_output)

        with gr.Tab(label="🤖 智能对话"):
            gr.Markdown("### 教师反馈对话")
            gr.Markdown("输入指令如：保留 X / 删除 X / 拆分 X / 为什么合并 X")
            chatbot = gr.Chatbot(height=400)
            msg_input = gr.Textbox(label="输入指令", placeholder="例如：保留'细胞凋亡'这个知识点", lines=2)
            with gr.Row():
                send_btn = gr.Button("📤 发送", variant="primary")
                clear_btn = gr.Button("🗑️ 清空")
            send_btn.click(dialogue_interface, inputs=[msg_input, chatbot], outputs=[chatbot, msg_input])
            clear_btn.click(fn=lambda: ([], ""), outputs=[chatbot, msg_input])

        with gr.Tab(label="📄 报告导出"):
            with gr.Column():
                gr.Markdown("### 生成整合报告")
                report_btn = gr.Button("📄 生成 Markdown 报告", variant="primary")
                report_output = gr.Textbox(label="报告内容", lines=25, interactive=False)
            report_btn.click(report_interface, outputs=report_output)

    gr.Markdown("""
    <div style="text-align: center; padding: 20px; color: #666;">
        <p>KnowledgeForge · 学科知识整合智能体 | AI 全栈极速黑客松参赛作品</p>
        <p>支持无 API Key 运行（使用 TF-IDF + BM25 检索）</p>
    </div>
    """)


if __name__ == "__main__":
    demo.launch()
