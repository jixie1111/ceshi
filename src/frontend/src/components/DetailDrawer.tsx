import { KnowledgeNode } from '../api/client';
import { MapPin, X } from 'lucide-react';

export default function DetailDrawer({ node, onClose }: { node?: KnowledgeNode | null; onClose: () => void }) {
  if (!node) return null;

  return (
    <div className="detail-drawer">
      <button className="close" onClick={onClose} aria-label="关闭">
        <X size={16} />
      </button>

      <div className="detail-header">
        <span className="pill">{node.category || '核心概念'}</span>
        <h2>{node.name}</h2>
      </div>

      {node.definition && (
        <div className="definition">{node.definition}</div>
      )}

      {node.aliases?.length ? (
        <div className="aliases">
          <strong>同义表述：</strong>{node.aliases.join('、')}
        </div>
      ) : null}

      <div className="source">
        <MapPin size={14} />
        <span>{node.source || `${node.textbook_title || ''} · ${node.chapter || ''} · 第 ${node.page || '?'} 页`}</span>
      </div>

      <div className="node-stats">
        <div>
          <b>{node.frequency || 1}</b>
          <span>出现频次</span>
        </div>
        <div>
          <b>{Math.round((node.importance || 0.5) * 100)}%</b>
          <span>重要度</span>
        </div>
      </div>

      {node.definition && (
        <div className="detail-section">
          <h4>完整定义</h4>
          <p className="definition-full">{node.definition}</p>
        </div>
      )}
    </div>
  );
}