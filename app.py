import gradio as gr


REPORT = """
# KnowledgeForge · 学科知识整合智能体

这是“AI 全栈极速黑客松·学科知识整合智能体开发”项目的公网展示页。

## 项目入口

- GitHub 仓库：https://github.com/jixie1111/ceshi
- 创空间页面：https://modelscope.cn/studios/jixie1111/knowledgeforge

## 已实现能力

- 多格式教材解析：PDF / Markdown / TXT / DOCX / Excel
- 单本教材知识图谱构建与可视化
- 跨教材知识点去重、合并与整合决策
- RAG 精准问答，回答附教材、章节、页码引用
- 教师多轮反馈：保留、拆分、删除、解释合并理由
- Markdown / PDF 整合报告导出
- Docker 与本地部署配置

## 7 本教材整合报告摘要

- 原始教材数量：7
- 原始总字数：3,159,547
- 整合后精华字数：193,292
- 压缩比：6.12%
- 整合前节点数：1,806
- 整合后节点数：1,505
- 整合前关系数：2,860
- 整合后关系数：2,825
- 合并决策：110 项
- 保留决策：1,395 项
- 删除决策：0 项

## 说明

教材 PDF 按赛题要求没有上传到 GitHub。评审可 clone GitHub 仓库后本地运行完整 Web 版，
也可以参考仓库中的 `README.md`、`docs/` 和 `report/整合报告.md` 查看完整功能与文档。
"""


def rag_demo(question):
    if not question:
        return "请输入一个问题。"
    return (
        "这是公网轻量展示页。完整 RAG 服务和源码已提交在 GitHub 仓库中。\n\n"
        "示例回答格式：\n"
        "炎症是机体对损伤因子的防御性反应，涉及血管反应、细胞渗出和组织修复等过程。\n\n"
        "引用来源示例：\n"
        "- [病理学, 炎症章节, 第 78 页]\n"
        "- [病理生理学, 组织损伤章节, 第 42 页]\n\n"
        f"你的问题：{question}"
    )


with gr.Blocks(title="KnowledgeForge") as demo:
    gr.Markdown(REPORT)
    gr.Markdown("## RAG 问答展示")
    question = gr.Textbox(label="输入问题", placeholder="例如：炎症是什么？")
    answer = gr.Textbox(label="回答", lines=8)
    gr.Button("提问").click(rag_demo, inputs=question, outputs=answer)


if __name__ == "__main__":
    demo.launch()
