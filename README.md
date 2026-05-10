---
title: KnowledgeForge
emoji: 📚
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
app_file: app.py
pinned: false
license: mit
short_description: 学科知识整合智能体
---

# KnowledgeForge · 学科知识整合智能体

> Python 3.10 + Node 18/20 全栈项目。面向“AI 全栈极速黑客松·学科知识整合智能体开发”赛题，覆盖多格式教材解析、单书知识图谱、跨教材去重整合、RAG 精准问答、多轮教师反馈、报告导出和 Benchmark。

## 亮点

- **P0 全链路可跑通**：上传教材 → 自动解析章节 → 构建知识图谱 → 跨书合并去重 → 建立 RAG 索引 → 带引用问答 → 教师反馈修改决策 → 生成整合报告。
- **漂亮的 Web 单页应用**：左侧教材管理，中间 D3 交互知识图谱，右侧整合 / RAG / 对话 / 报告 / 评测 Tab。
- **混合检索**：TF-IDF / sentence-transformers 向量检索 + BM25 + 关键词 overlap rerank，回答附教材、章节、页码、相关度。
- **稳健降级**：无 API Key、无本地模型时仍能用规则抽取与抽取式 RAG 答案；配置 OpenAI 兼容接口后可升级为 LLM 抽取与生成。
- **P1/P2 加分准备**：多视图图谱（力导向 / 章节树 / 关系矩阵）、PDF 报告导出、Docker、Benchmark、Agent 架构文档、创新点说明。

## 环境要求

- Python **3.10**
- Node.js **18–20**
- 推荐：8GB+ 内存；如启用 sentence-transformers 首次会下载模型。

## 本地运行

```bash
# 1. 克隆项目后进入目录
cd ai_textbook_agent_champion

# 2. Python 后端
python3.10 -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
python -m uvicorn src.backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# 3. 新开终端启动前端
npm --prefix src/frontend install
npm --prefix src/frontend run dev
```

浏览器打开：<http://localhost:5173>

## Docker 一键运行

```bash
cp .env.example .env
docker compose up --build
```

前端：<http://localhost:5173>，后端 API：<http://localhost:8000/docs>

## 配置说明

`.env` 关键项：

```env
EMBEDDING_BACKEND=auto             # auto / tfidf / sentence-transformers
EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
ENABLE_LLM_EXTRACTION=false        # true 后会尝试调用 OpenAI 兼容接口做知识抽取
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

未配置 API Key 时，系统自动使用本地规则抽取、TF-IDF/BM25 检索与抽取式回答，保证评审环境可复现。

## 使用流程

1. 在左侧上传 PDF / Markdown / TXT / DOCX / Excel 教材；若暂时没有教材，可点击“加载演示数据”。
2. 选择教材，点击“图谱”构建单本教材知识图谱。
3. 点击右侧“整合”里的“一键构建/整合图谱”，生成跨教材合并决策与压缩比。
4. 切换到 RAG，点击“建立 RAG 索引”，输入问题，查看带原文引用的回答。
5. 切换到“对话”，输入“保留 X / 删除 X / 拆分 X / 为什么合并 X”，图谱与决策会实时更新。
6. 切换到“报告”，导出 Markdown 或 PDF 整合报告。
7. 切换到“评测”，运行自动 Benchmark，记录引用命中率与响应时间。

## 仓库结构

```text
.
├── README.md
├── requirements.txt
├── package.json
├── docker-compose.yml
├── src/
│   ├── backend/app/              # FastAPI + Agent / RAG / 图谱整合服务
│   └── frontend/                 # Vite + React + D3 单页应用
├── docs/
│   ├── 需求分析.md
│   ├── 系统设计.md
│   ├── Agent架构说明.md
│   └── 接口文档.md
├── report/
│   └── 整合报告.md
└── data/                         # runtime 与 upload 默认被 .gitignore 排除
```

## 注意：不要提交教材 PDF

赛题要求 GitHub 仓库中不要包含教材 PDF，本项目 `.gitignore` 已排除：

```gitignore
data/textbooks/*.pdf
*.pdf
*.docx
*.xlsx
```

评审时从前端上传教材即可，不依赖仓库内固定教材。
