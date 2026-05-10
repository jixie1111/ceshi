import { useEffect, useState } from 'react';
import { Activity, Bot, Download, FileText, GitMerge, Loader2, MessageSquareText, Quote, SearchCheck, Sparkles } from 'lucide-react';
import { api, Decision, IntegratedGraph, RagAnswer, RagStatus } from '../api/client';

type Props = {
  integrated: IntegratedGraph | null;
  onIntegrated: (g: IntegratedGraph) => void;
};

export default function RightPanel({ integrated, onIntegrated }: Props) {
  const [tab, setTab] = useState<'integrate' | 'rag' | 'chat' | 'report' | 'bench'>('integrate');
  const [busy, setBusy] = useState(false);
  const [ragStatus, setRagStatus] = useState<RagStatus | null>(null);
  const [question, setQuestion] = useState('动作电位是什么？');
  const [answer, setAnswer] = useState<RagAnswer | null>(null);
  const [message, setMessage] = useState('为什么合并 动作电位？');
  const [chat, setChat] = useState<{ role: string; content: string }[]>([]);
  const [report, setReport] = useState('');
  const [bench, setBench] = useState<any>(null);

  useEffect(() => { api.ragStatus().then(setRagStatus).catch(() => null); api.history().then(setChat).catch(() => null); }, []);

  async function runIntegration() {
    setBusy(true);
    try { const g = await api.runIntegration(); onIntegrated(g); }
    finally { setBusy(false); }
  }
  async function buildIndex() { setBusy(true); try { setRagStatus(await api.ragIndex()); } finally { setBusy(false); } }
  async function ask() { setBusy(true); try { setAnswer(await api.ragQuery(question)); } finally { setBusy(false); } }
  async function send() { setBusy(true); try { const resp: any = await api.sendDialogue(message); setChat(await api.history()); if (resp.graph_changed) onIntegrated(await api.getIntegration()); } finally { setBusy(false); } }
  async function genReport() { setBusy(true); try { const r = await api.generateReport(); setReport(r.data.markdown); } finally { setBusy(false); } }
  async function runBench() { setBusy(true); try { setBench(await api.runBenchmark()); } finally { setBusy(false); } }

  return (
    <aside className="right-panel glass">
      <div className="tabs">
        <button className={tab === 'integrate' ? 'active' : ''} onClick={() => setTab('integrate')}><GitMerge size={16} />整合</button>
        <button className={tab === 'rag' ? 'active' : ''} onClick={() => setTab('rag')}><SearchCheck size={16} />RAG</button>
        <button className={tab === 'chat' ? 'active' : ''} onClick={() => setTab('chat')}><Bot size={16} />对话</button>
        <button className={tab === 'report' ? 'active' : ''} onClick={() => setTab('report')}><FileText size={16} />报告</button>
        <button className={tab === 'bench' ? 'active' : ''} onClick={() => setTab('bench')}><Activity size={16} />评测</button>
      </div>
      {busy && <div className="busy"><Loader2 className="spin" />处理中...</div>}

      {tab === 'integrate' && (
        <section className="tab-body">
          <button className="primary" onClick={runIntegration}><Sparkles size={16} /> 一键构建/整合图谱</button>
          <Stats g={integrated} />
          <h3>整合决策</h3>
          <div className="decision-list">
            {integrated?.decisions?.slice(0, 20).map((d) => <DecisionCard key={d.decision_id} d={d} />)}
            {!integrated?.decisions?.length && <p className="empty">运行整合后将显示 merge / keep / remove 决策及理由。</p>}
          </div>
        </section>
      )}

      {tab === 'rag' && (
        <section className="tab-body">
          <div className="rag-status">
            <b>索引状态</b><span>{ragStatus?.indexed_books ?? 0} 本教材 · {ragStatus?.chunk_count ?? 0} 个知识块 · {ragStatus?.embedding_backend ?? 'tfidf'}</span>
          </div>
          <button className="primary" onClick={buildIndex}><SearchCheck size={16} /> 建立 RAG 索引</button>
          <textarea className="question" value={question} onChange={(e) => setQuestion(e.target.value)} />
          <button className="primary ghost" onClick={ask}>提问并要求引用来源</button>
          {answer && <div className="answer"><h3>回答</h3><p>{answer.answer}</p><div className="latency">响应 {answer.latency_ms}ms</div><h3>引用来源</h3>{answer.citations.map((c) => <details key={c.chunk_id}><summary><Quote size={14} /> {c.textbook} · {c.chapter} · 第 {c.page} 页 · {Math.round(c.relevance_score * 100)}%</summary><p>{answer.source_chunks.find((s) => s.chunk_id === c.chunk_id)?.text}</p></details>)}</div>}
        </section>
      )}

      {tab === 'chat' && (
        <section className="tab-body">
          <div className="chat-box">
            {chat.map((m, i) => <div key={i} className={`bubble ${m.role}`}>{m.content}</div>)}
          </div>
          <textarea className="question" value={message} onChange={(e) => setMessage(e.target.value)} />
          <button className="primary" onClick={send}><MessageSquareText size={16} /> 发送教师反馈</button>
          <p className="hint">示例：保留 免疫应答 / 拆分 抗原 / 为什么合并 动作电位</p>
        </section>
      )}

      {tab === 'report' && (
        <section className="tab-body">
          <button className="primary" onClick={genReport}><FileText size={16} /> 生成 Markdown 报告</button>
          <div className="download-row">
            <a href="/api/report/download?format=md"><Download size={14} />下载 MD</a>
            <a href="/api/report/download?format=pdf"><Download size={14} />下载 PDF</a>
          </div>
          <pre className="report-preview">{report || '点击生成报告后预览；也可直接下载动态报告。'}</pre>
        </section>
      )}

      {tab === 'bench' && (
        <section className="tab-body">
          <button className="primary" onClick={runBench}><Activity size={16} /> 运行 RAG Benchmark</button>
          {bench && <div className="bench"><h2>{Math.round(bench.citation_hit_rate * 100)}%</h2><span>引用命中率 · {bench.question_count} 题</span>{bench.rows?.slice(0, 8).map((r: any, idx: number) => <div className="bench-row" key={idx}>{r.hit ? '✅' : '⚠️'} {r.question}</div>)}</div>}
        </section>
      )}
    </aside>
  );
}

function Stats({ g }: { g: IntegratedGraph | null }) {
  const s = g?.stats || {};
  return <div className="stats-grid">
    <div><b>{s.original_chars?.toLocaleString?.() ?? 0}</b><span>原始字数</span></div>
    <div><b>{s.integrated_chars?.toLocaleString?.() ?? 0}</b><span>精华字数</span></div>
    <div><b>{s.compression_ratio ?? 0}%</b><span>压缩比</span></div>
    <div><b>{s.nodes_before ?? 0}→{s.nodes_after ?? 0}</b><span>节点</span></div>
  </div>;
}

function DecisionCard({ d }: { d: Decision }) {
  return <div className={`decision ${d.action}`}>
    <div><strong>{d.action.toUpperCase()}</strong><em>{d.confidence.toFixed(2)} {d.teacher_locked ? '· 教师锁定' : ''}</em></div>
    <p>{d.reason}</p>
  </div>;
}
