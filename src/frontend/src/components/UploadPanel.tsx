import { useMemo, useRef, useState } from 'react';
import { AlertTriangle, BookOpen, CheckCircle2, FileUp, Loader2, Network, Trash2, Wand2, X } from 'lucide-react';
import { api, Textbook } from '../api/client';

type Props = {
  books: Textbook[];
  selectedId?: string;
  onBooks: (books: Textbook[]) => void;
  onSelect: (id: string | undefined) => void;
  onGraphBuilt: () => void | Promise<void>;
  onDeleted: (books: Textbook[]) => void;
};

export default function UploadPanel({ books, selectedId, onBooks, onSelect, onGraphBuilt, onDeleted }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [buildingId, setBuildingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<Textbook | null>(null);
  const [notice, setNotice] = useState<{ type: 'ok' | 'warn'; text: string } | null>(null);

  async function upload(files: FileList | File[]) {
    const list = Array.from(files);
    if (!list.length) return;
    setUploading(true);
    setNotice({ type: 'ok', text: `正在解析 ${list.length} 个文件，完成后会自动刷新教材列表。` });
    try {
      const result = await api.uploadBooks(list);
      const next = await api.listBooks();
      const failed = result.filter((book) => book.status === '失败');
      onBooks(next);
      if (!selectedId && next.length) onSelect(next[0].textbook_id);
      setNotice(
        failed.length
          ? { type: 'warn', text: `${failed.length} 个文件解析失败：${failed.map((book) => book.filename).join('、')}` }
          : { type: 'ok', text: `已完成 ${result.length} 个文件解析，可选择教材构建图谱。` },
      );
    } catch (err) {
      setNotice({ type: 'warn', text: err instanceof Error ? err.message : '上传失败，请检查文件格式或后端服务。' });
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  }

  async function build(id: string) {
    setBuildingId(id);
    setNotice({ type: 'ok', text: '正在构建单本教材知识图谱。大 PDF 会稍慢，请保持页面打开。' });
    try {
      await api.buildGraph(id);
      await onGraphBuilt();
      setNotice({ type: 'ok', text: '图谱已构建完成，点击节点可查看定义、章节和出处。' });
    } catch (err) {
      setNotice({ type: 'warn', text: err instanceof Error ? err.message : '图谱构建失败。' });
    } finally {
      setBuildingId(null);
    }
  }

  async function remove(book: Textbook) {
    setDeletingId(book.textbook_id);
    try {
      await api.deleteBook(book.textbook_id);
      const next = await api.listBooks();
      onBooks(next);
      onDeleted(next);
      if (selectedId === book.textbook_id) onSelect(next[0]?.textbook_id);
      setNotice({ type: 'ok', text: `已删除《${book.title}》，并清理过期图谱、整合结果和 RAG 索引。` });
    } catch (err) {
      setNotice({ type: 'warn', text: err instanceof Error ? err.message : '删除失败。' });
    } finally {
      setDeletingId(null);
      setConfirmDelete(null);
    }
  }

  async function demo() {
    setUploading(true);
    try {
      await api.loadDemo();
      const next = await api.listBooks();
      onBooks(next);
      if (!selectedId && next.length) onSelect(next[0].textbook_id);
      setNotice({ type: 'ok', text: '演示数据已加载，可直接体验图谱、整合与 RAG。' });
    } finally {
      setUploading(false);
    }
  }

  const selectedBook = books.find((book) => book.textbook_id === selectedId);
  const displayedChapters = useMemo(
    () => sortChapters(selectedBook?.chapters ?? []),
    [selectedBook],
  );

  return (
    <aside className="sidebar glass">
      <div className="brand">
        <div className="brand-mark">KF</div>
        <div className="brand-text">
          <h1>KnowledgeForge</h1>
          <p>学科知识整合智能体</p>
        </div>
      </div>

      <div
        className={`dropzone ${drag ? 'dragging' : ''} ${uploading ? 'busy-zone' : ''}`}
        onClick={() => !uploading && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files); }}
      >
        {uploading ? <Loader2 className="spin" /> : <FileUp />}
        <strong>{uploading ? '正在解析教材' : '拖拽 / 点击上传教材'}</strong>
        <span>支持 PDF、Markdown、TXT、DOCX、Excel，允许批量上传</span>
        <input ref={inputRef} hidden multiple type="file" accept=".pdf,.md,.markdown,.txt,.docx,.xlsx,.xlsm" onChange={(e) => e.target.files && upload(e.target.files)} />
      </div>

      {notice && (
        <div className={`upload-notice ${notice.type}`}>
          {notice.type === 'ok' ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
          <span>{notice.text}</span>
          <button onClick={() => setNotice(null)} aria-label="关闭提示"><X size={13} /></button>
        </div>
      )}

      <button className="demo-btn" onClick={demo} disabled={uploading}><Wand2 size={16} /> 加载演示数据</button>

      <div className="panel-title"><BookOpen size={16} /> 教材管理 <span>{books.length} 本</span></div>
      <div className="book-list">
        {books.map((book) => {
          const active = selectedId === book.textbook_id;
          const building = buildingId === book.textbook_id;
          const deleting = deletingId === book.textbook_id;
          return (
            <div key={book.textbook_id} className={`book-card ${active ? 'active' : ''}`} onClick={() => onSelect(book.textbook_id)}>
              <div className="book-main">
                <strong title={book.filename}>{book.title}</strong>
                <span>{book.format.toUpperCase()} · {formatBytes(book.file_size)} · {book.total_pages || 1} 页 · {book.total_chars.toLocaleString()} 字</span>
                <span className={`status ${book.status === '失败' ? 'failed' : ''}`}>{book.status}</span>
                {book.error && <span className="book-error">{book.error}</span>}
              </div>
              <div className="book-actions">
                <button title="构建图谱" disabled={Boolean(buildingId || deletingId)} onClick={(e) => { e.stopPropagation(); build(book.textbook_id); }}>
                  {building ? <Loader2 size={14} className="spin" /> : <Network size={14} />} <span className="action-label">图谱</span>
                </button>
                <button title="删除教材" disabled={Boolean(buildingId || deletingId)} onClick={(e) => { e.stopPropagation(); setConfirmDelete(book); }}>
                  {deleting ? <Loader2 size={14} className="spin" /> : <Trash2 size={14} />}
                </button>
              </div>
            </div>
          );
        })}
        {!books.length && <p className="empty">上传赛方教材后，章节结构和解析状态会显示在这里。</p>}
      </div>

      {confirmDelete && (
        <div className="confirm-box">
          <strong>删除《{confirmDelete.title}》？</strong>
          <p>会同步清理上传文件、单书图谱、整合结果和 RAG 索引，避免旧数据污染后续演示。</p>
          <div>
            <button onClick={() => setConfirmDelete(null)}>取消</button>
            <button className="danger" onClick={() => remove(confirmDelete)}>确认删除</button>
          </div>
        </div>
      )}

      <div className="chapter-preview">
        <h3>章节结构</h3>
        {displayedChapters.slice(0, 12).map((chapter) => (
          <div className="chapter" key={chapter.chapter_id}>
            <span title={chapter.title}>{chapter.title}</span><em>p.{chapter.page_start}-{chapter.page_end}</em>
          </div>
        ))}
        {selectedBook && displayedChapters.length > 12 && <div className="chapter more">还有 {displayedChapters.length - 12} 个章节</div>}
        {!selectedBook && <p className="empty small">选择一本教材后查看章节识别结果。</p>}
      </div>
    </aside>
  );
}

function formatBytes(bytes?: number) {
  if (!bytes) return '未知大小';
  const units = ['B', 'KB', 'MB', 'GB'];
  let value = bytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function sortChapters<T extends { title: string; page_start: number }>(chapters: T[]) {
  return [...chapters].sort((a, b) => chapterNumber(a.title) - chapterNumber(b.title) || a.page_start - b.page_start || naturalCompare(a.title, b.title));
}

function naturalCompare(a = '', b = '') {
  return a.localeCompare(b, 'zh-Hans-CN', { numeric: true, sensitivity: 'base' });
}

function chapterNumber(text = '') {
  if (/未识别|自动分段|未命名/.test(text)) return 9999;
  const arabic = text.match(/第\s*(\d+)\s*[章节]/);
  if (arabic) return Number(arabic[1]);
  const cn = text.match(/第\s*([一二三四五六七八九十百千万零〇两]+)\s*[章节]/);
  return cn ? chineseNumber(cn[1]) : 9998;
}

function chineseNumber(input: string) {
  const digit: Record<string, number> = { 零: 0, 〇: 0, 一: 1, 二: 2, 两: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9 };
  if (input === '十') return 10;
  const tenIndex = input.indexOf('十');
  if (tenIndex >= 0) {
    const left = input.slice(0, tenIndex);
    const right = input.slice(tenIndex + 1);
    return (left ? digit[left] || 0 : 1) * 10 + (right ? digit[right] || 0 : 0);
  }
  return Array.from(input).reduce((sum, char) => sum * 10 + (digit[char] || 0), 0);
}
