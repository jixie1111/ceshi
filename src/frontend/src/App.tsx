import { useCallback, useEffect, useMemo, useState } from 'react';
import { api, IntegratedGraph, KnowledgeGraph, KnowledgeNode, Textbook } from './api/client';
import UploadPanel from './components/UploadPanel';
import GraphCanvas from './components/GraphCanvas';
import RightPanel from './components/RightPanel';
import DetailDrawer from './components/DetailDrawer';

export default function App() {
  const [books, setBooks] = useState<Textbook[]>([]);
  const [selected, setSelected] = useState<string | undefined>();
  const [graph, setGraph] = useState<KnowledgeGraph | null>(null);
  const [integrated, setIntegrated] = useState<IntegratedGraph | null>(null);
  const [node, setNode] = useState<KnowledgeNode | null>(null);
  const [scope, setScope] = useState<'single' | 'integrated'>('single');

  async function refreshBooks() {
    const b = await api.listBooks();
    setBooks(b);
    if (!selected && b.length) setSelected(b[0].textbook_id);
  }

  useEffect(() => {
    refreshBooks();
    api.getIntegration().then((g) => {
      if (g.nodes?.length) {
        setIntegrated(g);
        setScope('integrated');
      }
    }).catch(() => null);
  }, []);

  useEffect(() => {
    if (selected) api.getGraph(selected).then(setGraph).catch(() => setGraph(null));
  }, [selected]);

  const activeGraph = useMemo(() => (scope === 'integrated' && integrated?.nodes?.length ? integrated : graph), [scope, integrated, graph]);
  const onGraphBuilt = useCallback(async () => {
    if (selected) {
      setGraph(await api.getGraph(selected));
      setScope('single');
    }
  }, [selected]);
  const handleBooks = useCallback((nextBooks: Textbook[]) => {
    setBooks(nextBooks);
    if (selected && !nextBooks.some((book) => book.textbook_id === selected)) {
      setSelected(nextBooks[0]?.textbook_id);
    }
  }, [selected]);
  const handleSelect = useCallback((id: string | undefined) => {
    setSelected(id);
    setNode(null);
    setScope('single');
  }, []);
  const handleDeleted = useCallback((nextBooks: Textbook[]) => {
    setNode(null);
    setIntegrated(null);
    if (!nextBooks.length) setGraph(null);
    setScope('single');
  }, []);
  const handleIntegrated = useCallback((g: IntegratedGraph) => {
    setIntegrated(g);
    setNode(null);
    setScope('integrated');
  }, []);

  return (
    <div className="app-layout">
      <UploadPanel books={books} selectedId={selected} onBooks={handleBooks} onSelect={handleSelect} onGraphBuilt={onGraphBuilt} onDeleted={handleDeleted} />
      <div className="center">
        <div className="hero">
          <div className="hero-left">
            <span className="eyebrow">AI Full-Stack Hackathon</span>
            <h2>学科知识整合智能体</h2>
          </div>
          <div className="scope-switch">
            <button className={scope === 'single' ? 'active' : ''} onClick={() => setScope('single')} disabled={!graph?.nodes?.length}>单本图谱</button>
            <button className={scope === 'integrated' ? 'active' : ''} onClick={() => setScope('integrated')} disabled={!integrated?.nodes?.length}>整合图谱</button>
          </div>
          <div className="hero-stats">
            <span><b>{books.length}</b><em>教材</em></span>
            <span><b>{activeGraph?.nodes?.length ?? 0}</b><em>知识点</em></span>
            <span><b>{activeGraph?.edges?.length ?? 0}</b><em>关系</em></span>
          </div>
        </div>
        <GraphCanvas graph={activeGraph} selectedNode={node} onNode={setNode} />
      </div>
      <RightPanel integrated={integrated} onIntegrated={handleIntegrated} />
      <DetailDrawer node={node} onClose={() => setNode(null)} />
    </div>
  );
}
