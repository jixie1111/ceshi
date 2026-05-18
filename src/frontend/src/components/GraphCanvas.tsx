import { useEffect, useMemo, useRef, useState } from 'react';
import * as d3 from 'd3';
import { IntegratedGraph, KnowledgeEdge, KnowledgeGraph, KnowledgeNode, Textbook } from '../api/client';
import { Filter, GitMerge, Layers3, Network, Search, Table2, TreePine } from 'lucide-react';

type GraphLike = KnowledgeGraph | IntegratedGraph | null;
type Props = {
  graph: GraphLike;
  books: Textbook[];
  selectedNode?: KnowledgeNode | null;
  onNode: (node: KnowledgeNode | null) => void;
};

type ViewMode = 'force' | 'tree' | 'matrix';
type Density = 'calm' | 'balanced' | 'rich';
type LabelMode = 'smart' | 'all';
type RenderNode = KnowledgeNode & { degree: number; score: number; x?: number; y?: number; fx?: number | null; fy?: number | null };
type RenderEdge = KnowledgeEdge & { source: string | RenderNode; target: string | RenderNode };
type D3Svg = d3.Selection<SVGSVGElement, unknown, null, undefined>;
type D3Group = d3.Selection<SVGGElement, unknown, null, undefined>;

const palette = ['#2563eb', '#0f766e', '#7c3aed', '#ea580c', '#be123c', '#0891b2', '#65a30d', '#475569'];
const relColor: Record<string, string> = {
  prerequisite: '#f97316',
  parallel: '#38bdf8',
  contains: '#8b5cf6',
  applies_to: '#22c55e',
};
const relLabel: Record<string, string> = {
  prerequisite: '前置依赖',
  parallel: '并列',
  contains: '包含',
  applies_to: '应用',
};
const densityConfig = {
  calm: {
    forceLimit: 70,
    treeLimit: 48,
    matrixLimit: 28,
    edgeFactor: 1.2,
    labelBudget: 34,
    nodePadding: 18,
    treeGap: 34,
    linkDistance: 170,
    charge: -520,
    edgeOpacity: 0.2,
  },
  balanced: {
    forceLimit: 135,
    treeLimit: 82,
    matrixLimit: 40,
    edgeFactor: 1.8,
    labelBudget: 48,
    nodePadding: 14,
    treeGap: 28,
    linkDistance: 145,
    charge: -430,
    edgeOpacity: 0.24,
  },
  rich: {
    forceLimit: 230,
    treeLimit: 120,
    matrixLimit: 54,
    edgeFactor: 2.4,
    labelBudget: 62,
    nodePadding: 11,
    treeGap: 24,
    linkDistance: 126,
    charge: -360,
    edgeOpacity: 0.18,
  },
} satisfies Record<Density, Record<string, number>>;

export default function GraphCanvas({ graph, books, selectedNode, onNode }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [query, setQuery] = useState('');
  const [view, setView] = useState<ViewMode>('force');
  const [density, setDensity] = useState<Density>('balanced');
  const [labelMode, setLabelMode] = useState<LabelMode>('smart');
  const [source, setSource] = useState('all');
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });

  const allNodes = useMemo(() => graph?.nodes ?? [], [graph]);
  const allEdges = useMemo(() => graph?.edges ?? [], [graph]);
  const sources = useMemo(() => buildSourceOptions(allNodes), [allNodes]);
  const visible = useMemo(
    () => buildVisibleGraph(allNodes, allEdges, query.trim(), source, density, view),
    [allNodes, allEdges, query, source, density, view],
  );

  useEffect(() => {
    if (source !== 'all' && !sources.some((item) => item.id === source)) setSource('all');
  }, [source, sources]);

  useEffect(() => {
    const el = svgRef.current;
    if (!el) return undefined;
    const update = () => setCanvasSize({ width: el.clientWidth || 900, height: el.clientHeight || 620 });
    update();
    const observer = new ResizeObserver(update);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    const w = canvasSize.width || svgRef.current.clientWidth || 900;
    const h = canvasSize.height || svgRef.current.clientHeight || 620;
    svg.attr('viewBox', `0 0 ${w} ${h}`);

    if (!allNodes.length) {
      drawEmpty(svg, w, h);
      return;
    }

    if (!visible.nodes.length) {
      drawNoResult(svg, w, h, query);
      return;
    }

    if (view === 'matrix') {
      drawMatrix(svg, w, h, visible.nodes, visible.edges, density, query, selectedNode, onNode);
      return;
    }
    if (view === 'tree') {
      drawTree(svg, w, h, visible.nodes, allNodes, books, source, density, query, selectedNode, onNode);
      return;
    }
    drawForce(svg, w, h, visible.nodes, visible.edges, density, query, selectedNode, onNode, labelMode);
  }, [allNodes.length, visible, books, source, query, view, density, labelMode, selectedNode, onNode, canvasSize]);

  return (
    <div className="graph-shell">
      <div className="graph-toolbar">
        <div className="metric strong"><Network size={14} /><b>{allNodes.length}</b><span>总节点</span></div>
        <div className="metric"><Layers3 size={14} /><b>{visible.nodes.length}</b><span>当前显示</span></div>
        <div className="metric"><GitMerge size={14} /><b>{visible.edges.length}</b><span>关系</span></div>
        <div className="search-box">
          <Search size={14} />
          <input placeholder="搜索知识点、章节、定义..." value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        <div className="select-box">
          <Filter size={14} />
          <select value={source} onChange={(e) => setSource(e.target.value)} aria-label="按教材筛选">
            <option value="all">全部教材</option>
            {sources.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
          </select>
        </div>
      </div>

      <div className="graph-subtoolbar">
        <div className="view-switch" aria-label="图谱视图">
          <button className={view === 'force' ? 'on' : ''} onClick={() => setView('force')}><Network size={13} /> 力导向</button>
          <button className={view === 'tree' ? 'on' : ''} onClick={() => setView('tree')}><TreePine size={13} /> 章节树</button>
          <button className={view === 'matrix' ? 'on' : ''} onClick={() => setView('matrix')}><Table2 size={13} /> 关系矩阵</button>
        </div>
        <div className="density-switch" aria-label="显示密度">
          <button className={density === 'calm' ? 'on' : ''} onClick={() => setDensity('calm')}>清爽</button>
          <button className={density === 'balanced' ? 'on' : ''} onClick={() => setDensity('balanced')}>均衡</button>
          <button className={density === 'rich' ? 'on' : ''} onClick={() => setDensity('rich')}>丰富</button>
        </div>
        <div className="label-switch" aria-label="节点标签">
          <button className={labelMode === 'smart' ? 'on' : ''} onClick={() => setLabelMode('smart')}>重点标注</button>
          <button className={labelMode === 'all' ? 'on' : ''} onClick={() => setLabelMode('all')}>全部标注</button>
        </div>
        <span className="graph-note">
          {graphNote(visible.hiddenNodes, labelMode)}
        </span>
      </div>

      <svg ref={svgRef} className="graph-svg" />
      <div className="legend">
        {Object.entries(relColor).map(([type, color]) => (
          <span key={type}><i style={{ background: color }} />{relLabel[type]}</span>
        ))}
      </div>
    </div>
  );
}

function graphNote(hiddenNodes: number, labelMode: LabelMode) {
  const labelHint = labelMode === 'all'
    ? '全部可见节点已常显名称，密集处可缩放或拖拽查看'
    : '默认常显重点名称，悬停任意节点可看完整信息';
  return hiddenNodes > 0
    ? `为避免堆叠，优先显示高频/高关联节点，隐藏 ${hiddenNodes} 个低权重节点；${labelHint}`
    : `已显示全部匹配节点；${labelHint}`;
}

function buildSourceOptions(nodes: KnowledgeNode[]) {
  const bySource = new Map<string, { id: string; title: string; count: number }>();
  for (const node of nodes) {
    const id = node.textbook_id || 'unknown';
    const title = node.textbook_title || id;
    const existing = bySource.get(id);
    if (existing) existing.count += 1;
    else bySource.set(id, { id, title, count: 1 });
  }
  return Array.from(bySource.values()).sort((a, b) => naturalCompare(a.title, b.title));
}

function buildVisibleGraph(
  nodes: KnowledgeNode[],
  edges: KnowledgeEdge[],
  query: string,
  source: string,
  density: Density,
  view: ViewMode,
) {
  const config = densityConfig[density];
  const sourceNodes = source === 'all' ? nodes : nodes.filter((node) => node.textbook_id === source);
  const sourceIds = new Set(sourceNodes.map((node) => node.id));
  const degree = new Map<string, number>();
  for (const edge of edges) {
    if (!sourceIds.has(edge.source) || !sourceIds.has(edge.target)) continue;
    degree.set(edge.source, (degree.get(edge.source) || 0) + 1);
    degree.set(edge.target, (degree.get(edge.target) || 0) + 1);
  }

  const queryText = query.toLowerCase();
  const directMatches = queryText ? sourceNodes.filter((node) => nodeMatches(node, queryText)) : [];
  let candidates = sourceNodes;

  if (queryText && directMatches.length) {
    const candidateIds = new Set(directMatches.map((node) => node.id));
    for (const edge of edges) {
      if (!sourceIds.has(edge.source) || !sourceIds.has(edge.target)) continue;
      if (candidateIds.has(edge.source)) candidateIds.add(edge.target);
      if (candidateIds.has(edge.target)) candidateIds.add(edge.source);
    }
    candidates = sourceNodes.filter((node) => candidateIds.has(node.id));
  } else if (queryText) {
    candidates = [];
  }

  const limit = view === 'matrix' ? config.matrixLimit : view === 'tree' ? config.treeLimit : config.forceLimit;
  const scored = candidates
    .map((node) => ({
      ...node,
      degree: degree.get(node.id) || 0,
      score: nodeScore(node, degree.get(node.id) || 0, queryText),
    }))
    .sort((a, b) => b.score - a.score);

  const visibleNodes = scored.slice(0, limit).sort(graphOrder);
  const visibleIds = new Set(visibleNodes.map((node) => node.id));
  const edgeLimit = view === 'matrix' ? limit * limit : Math.max(60, Math.round(limit * config.edgeFactor));
  const visibleEdges = edges
    .filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target))
    .sort((a, b) => (b.weight || 0) - (a.weight || 0))
    .slice(0, edgeLimit);

  return {
    nodes: visibleNodes,
    edges: visibleEdges,
    hiddenNodes: Math.max(0, candidates.length - visibleNodes.length),
    hiddenEdges: Math.max(0, edges.length - visibleEdges.length),
  };
}

function nodeScore(node: KnowledgeNode, degree: number, query: string) {
  const matchBoost = query && nodeMatches(node, query) ? 10000 : 0;
  return matchBoost + (node.frequency || 1) * 160 + (node.importance || 0.5) * 120 + degree * 18 + Math.min(40, (node.definition || '').length / 25);
}

function nodeMatches(node: KnowledgeNode, query: string) {
  const haystack = `${node.name} ${node.definition || ''} ${node.chapter || ''} ${node.category || ''} ${(node.aliases || []).join(' ')}`.toLowerCase();
  return haystack.includes(query);
}

function graphOrder(a: KnowledgeNode, b: KnowledgeNode) {
  return (
    naturalCompare(a.textbook_title || a.textbook_id, b.textbook_title || b.textbook_id) ||
    compareChapter(a.chapter, b.chapter) ||
    (a.page || 0) - (b.page || 0) ||
    naturalCompare(a.name, b.name)
  );
}

function naturalCompare(a = '', b = '') {
  return a.localeCompare(b, 'zh-Hans-CN', { numeric: true, sensitivity: 'base' });
}

function compareChapter(a = '', b = '') {
  return chapterNumber(a) - chapterNumber(b) || naturalCompare(a, b);
}

function chapterNumber(text = '') {
  const arabic = text.match(/第\s*(\d+)\s*[章节]/);
  if (arabic) return Number(arabic[1]);
  const cn = text.match(/第\s*([一二三四五六七八九十百千万零〇两]+)\s*[章节]/);
  if (cn) return chineseNumber(cn[1]);
  if (/^\s*(绪论|总论)\s*$/.test(text)) return 0;
  if (/未识别|未命名/.test(text)) return 9999;
  return 9998;
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

function nodeColor(node: KnowledgeNode) {
  return palette[Math.abs(hash(node.textbook_id || node.id)) % palette.length];
}

function hash(s: string) {
  return Array.from(s).reduce((a, c) => (a * 31 + c.charCodeAt(0)) | 0, 7);
}

function radius(node: RenderNode) {
  return 9 + Math.min(18, Math.sqrt((node.degree || 0) + 1) * 2.2 + (node.frequency || 1) * 2 + (node.importance || 0.5) * 4.5);
}

function shorten(text: string, max = 12) {
  const clean = (text || '').replace(/[\ufffd�\b]/g, '').trim();
  return clean.length > max ? `${clean.slice(0, max)}...` : clean;
}

function drawEmpty(svg: D3Svg, w: number, h: number) {
  svg.append('rect').attr('width', w).attr('height', h).attr('fill', '#f8fafc').attr('rx', 18);
  svg.append('text')
    .attr('x', w / 2).attr('y', h / 2 - 8).attr('text-anchor', 'middle')
    .attr('fill', '#64748b').attr('font-size', 16).attr('font-weight', 700).attr('font-family', 'inherit')
    .text('上传教材并构建图谱后，知识网络会在这里呈现');
  svg.append('text')
    .attr('x', w / 2).attr('y', h / 2 + 18).attr('text-anchor', 'middle')
    .attr('fill', '#94a3b8').attr('font-size', 12).attr('font-family', 'inherit')
    .text('支持缩放、拖拽、搜索、来源筛选和多视图切换');
}

function drawNoResult(svg: D3Svg, w: number, h: number, query: string) {
  svg.append('rect').attr('width', w).attr('height', h).attr('fill', '#f8fafc').attr('rx', 18);
  svg.append('text')
    .attr('x', w / 2).attr('y', h / 2).attr('text-anchor', 'middle')
    .attr('fill', '#64748b').attr('font-size', 14).attr('font-family', 'inherit')
    .text(`没有找到与“${query}”匹配的知识点`);
}

function addDefs(svg: D3Svg) {
  const defs = svg.append('defs');
  Object.entries(relColor).forEach(([type, color]) => {
    defs.append('marker')
      .attr('id', `arrow-${type}`)
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', color);
  });
  const filter = defs.append('filter').attr('id', 'soft-glow').attr('x', '-60%').attr('y', '-60%').attr('width', '220%').attr('height', '220%');
  filter.append('feGaussianBlur').attr('stdDeviation', '3.5').attr('result', 'blur');
  const merge = filter.append('feMerge');
  merge.append('feMergeNode').attr('in', 'blur');
  merge.append('feMergeNode').attr('in', 'SourceGraphic');
}

function setupZoom(svg: D3Svg, content: D3Group, min = 0.25, max = 4) {
  svg.call(
    d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([min, max])
      .on('zoom', (event) => content.attr('transform', event.transform)) as any,
  );
}

function drawForce(
  svg: D3Svg,
  w: number,
  h: number,
  rawNodes: RenderNode[],
  rawEdges: KnowledgeEdge[],
  density: Density,
  query: string,
  selectedNode: KnowledgeNode | null | undefined,
  onNode: (node: KnowledgeNode | null) => void,
  labelMode: LabelMode,
) {
  const config = densityConfig[density];
  addDefs(svg);
  svg.append('rect').attr('width', w).attr('height', h).attr('fill', '#fbfdff').attr('rx', 16);
  const content = svg.append('g');
  setupZoom(svg, content, 0.28, 3.4);

  const nodes = rawNodes.map((node, i) => {
    const angle = ((Math.abs(hash(node.id)) % 360) / 180) * Math.PI;
    const ring = 0.2 + (i % 7) * 0.045;
    return {
      ...node,
      x: w / 2 + Math.cos(angle) * w * ring,
      y: h / 2 + Math.sin(angle) * h * ring,
    };
  });
  const links: RenderEdge[] = rawEdges.map((edge) => ({ ...edge }));

  const sim = d3.forceSimulation(nodes as any)
    .force('link', d3.forceLink(links as any).id((d: any) => d.id).distance((d: any) => d.relation_type === 'contains' ? config.linkDistance * 0.78 : config.linkDistance).strength(0.42))
    .force('charge', d3.forceManyBody().strength(config.charge))
    .force('center', d3.forceCenter(w / 2, h / 2))
    .force('x', d3.forceX(w / 2).strength(0.045))
    .force('y', d3.forceY(h / 2).strength(0.045))
    .force('collide', d3.forceCollide<RenderNode>().radius((d) => radius(d) + config.nodePadding).strength(1).iterations(6))
    .stop();
  for (let i = 0; i < 190; i += 1) sim.tick();
  resolveCircleCollisions(nodes, w, h, (node) => radius(node) + config.nodePadding, 10);

  const link = content.append('g').attr('class', 'edge-layer').selectAll('path').data(links).join('path')
    .attr('fill', 'none')
    .attr('stroke', (d) => relColor[d.relation_type] || '#94a3b8')
    .attr('stroke-opacity', config.edgeOpacity)
    .attr('stroke-width', (d) => 0.7 + (d.weight || 0.5) * 1.5)
    .attr('marker-end', (d) => `url(#arrow-${d.relation_type})`);

  const node = content.append('g').attr('class', 'node-layer').selectAll('g').data(nodes).join('g')
    .attr('class', 'node')
    .style('cursor', 'grab')
    .on('click', (_, d) => onNode(d));

  node.append('circle')
    .attr('r', (d) => radius(d) + 6)
    .attr('fill', (d) => nodeColor(d))
    .attr('opacity', (d) => selectedNode?.id === d.id || (query && nodeMatches(d, query.toLowerCase())) ? 0.17 : 0.06);

  node.append('circle')
    .attr('r', radius)
    .attr('fill', nodeColor)
    .attr('fill-opacity', (d) => 0.64 + Math.min(0.26, (d.frequency || 1) * 0.04))
    .attr('stroke', (d) => selectedNode?.id === d.id ? '#0f172a' : '#ffffff')
    .attr('stroke-width', (d) => selectedNode?.id === d.id ? 3 : 1.8)
    .attr('filter', (d) => selectedNode?.id === d.id || (query && nodeMatches(d, query.toLowerCase())) ? 'url(#soft-glow)' : null);

  node.append('title').text((d) => `${d.name}\n${d.textbook_title || ''} · ${d.chapter || ''}\n${d.definition || ''}`);

  const labelLayer = content.append('g').attr('class', 'label-layer').style('pointer-events', 'none');
  const hoverLayer = content.append('g').attr('class', 'hover-layer').style('pointer-events', 'none');

  function pathFor(d: RenderEdge) {
    const s = d.source as RenderNode;
    const t = d.target as RenderNode;
    const dx = (t.x || 0) - (s.x || 0);
    const dy = (t.y || 0) - (s.y || 0);
    const dist = Math.max(1, Math.hypot(dx, dy));
    const curve = Math.min(42, dist * 0.14);
    const mx = ((s.x || 0) + (t.x || 0)) / 2 - (dy / dist) * curve;
    const my = ((s.y || 0) + (t.y || 0)) / 2 + (dx / dist) * curve;
    return `M${s.x},${s.y} Q${mx},${my} ${t.x},${t.y}`;
  }

  function renderLabels() {
    const labels = placeForceLabels(nodes, w, h, density, query, selectedNode, labelMode);
    const groups = labelLayer.selectAll<SVGGElement, LabelPlacement>('g.force-label').data(labels, (d: any) => d.id);
    const enter = groups.enter().append('g').attr('class', 'force-label');
    enter.append('rect').attr('rx', 6).attr('stroke', 'rgba(226,232,240,0.9)');
    enter.append('text')
      .attr('fill', '#172033')
      .attr('font-family', 'inherit')
      .attr('paint-order', 'stroke')
      .attr('stroke', 'rgba(255,255,255,0.92)')
      .attr('stroke-width', 2.5);
    const merged = enter.merge(groups as any);
    merged.attr('transform', (d) => `translate(${d.x},${d.y})`);
    merged.select('rect')
      .attr('x', -5)
      .attr('y', -dLabelPadY)
      .attr('width', (d) => d.width + 10)
      .attr('height', (d) => d.height + 4)
      .attr('fill', labelMode === 'all' ? 'rgba(255,255,255,0.72)' : 'rgba(255,255,255,0.88)');
    merged.select('text')
      .attr('y', 4)
      .attr('font-size', labelMode === 'all' ? 9.6 : 11)
      .attr('font-weight', labelMode === 'all' ? 700 : 800)
      .text((d) => d.text);
    groups.exit().remove();
  }

  function renderHover(nodeItem: RenderNode) {
    hoverLayer.selectAll('*').remove();
    const lines = hoverLines(nodeItem);
    const width = Math.min(320, Math.max(120, Math.max(...lines.map((line) => estimateTextWidth(line, 12))) + 22));
    const height = 18 + lines.length * 17;
    const r = radius(nodeItem);
    const x = clamp((nodeItem.x || 0) + r + 14, 8, w - width - 8);
    const y = clamp((nodeItem.y || 0) - height / 2, 8, h - height - 8);
    const group = hoverLayer.append('g').attr('transform', `translate(${x},${y})`);
    group.append('rect')
      .attr('width', width)
      .attr('height', height)
      .attr('rx', 8)
      .attr('fill', 'rgba(15,23,42,0.92)')
      .attr('stroke', 'rgba(255,255,255,0.72)')
      .attr('stroke-width', 1);
    group.selectAll('text')
      .data(lines)
      .join('text')
      .attr('x', 11)
      .attr('y', (_, i) => 17 + i * 17)
      .attr('fill', (_, i) => i === 0 ? '#ffffff' : '#cbd5e1')
      .attr('font-size', (_, i) => i === 0 ? 12 : 10.5)
      .attr('font-weight', (_, i) => i === 0 ? 800 : 600)
      .attr('font-family', 'inherit')
      .text((line) => line);
  }

  function update() {
    link.attr('d', pathFor);
    node.attr('transform', (d) => `translate(${d.x},${d.y})`);
    renderLabels();
  }
  update();

  node.call(d3.drag<SVGGElement, RenderNode>()
    .on('start', function () { d3.select(this).style('cursor', 'grabbing'); })
    .on('drag', function (event, d) {
      d.x = Math.max(radius(d) + 2, Math.min(w - radius(d) - 2, event.x));
      d.y = Math.max(radius(d) + 2, Math.min(h - radius(d) - 2, event.y));
      resolveCircleCollisions(nodes, w, h, (item) => radius(item) + config.nodePadding, 2);
      update();
    })
    .on('end', function () { d3.select(this).style('cursor', 'grab'); }) as any);

  node
    .on('mouseenter', (_, d) => renderHover(d))
    .on('mousemove', (_, d) => renderHover(d))
    .on('mouseleave', () => hoverLayer.selectAll('*').remove());
}

const dLabelPadY = 8;

type LabelPlacement = {
  id: string;
  text: string;
  x: number;
  y: number;
  width: number;
  height: number;
};

function placeForceLabels(
  nodes: RenderNode[],
  w: number,
  h: number,
  density: Density,
  query: string,
  selectedNode?: KnowledgeNode | null,
  labelMode: LabelMode = 'smart',
) {
  const config = densityConfig[density];
  const q = query.toLowerCase();
  const sorted = nodes
    .map((node, index) => ({
      node,
      index,
      priority: (selectedNode?.id === node.id ? 100000 : 0) + (q && nodeMatches(node, q) ? 50000 : 0) + node.score + node.degree * 10,
    }))
    .sort((a, b) => b.priority - a.priority)
    .slice(0, labelMode === 'all' ? nodes.length : config.labelBudget);
  const labels: LabelPlacement[] = [];
  const occupied: Rect[] = [];
  const nodeBoxes = nodes.map((node) => circleBox(node, radius(node) + 4));

  for (const item of sorted) {
    const node = item.node;
    const label = shorten(node.name, labelMode === 'all' ? (density === 'rich' ? 10 : 12) : density === 'rich' ? 9 : density === 'balanced' ? 11 : 14);
    if (!label) continue;
    const fontSize = labelMode === 'all' ? 9.6 : 11;
    const width = estimateTextWidth(label, fontSize);
    const height = labelMode === 'all' ? 14 : 16;
    const r = radius(node);
    const candidates = labelCandidates(node, width, height, r, labelMode);
    let placed = candidates.find((candidate) => {
      if (candidate.x < 8 || candidate.y < 12 || candidate.x + candidate.width > w - 8 || candidate.y + candidate.height > h - 8) return false;
      const padded = padRect(candidate, 4);
      if (occupied.some((rect) => rectsOverlap(padded, rect))) return false;
      return !nodeBoxes.some((box) => rectsOverlap(padded, box));
    });
    if (!placed && labelMode === 'all') {
      placed = candidates.find((candidate) => {
        if (candidate.x < 8 || candidate.y < 12 || candidate.x + candidate.width > w - 8 || candidate.y + candidate.height > h - 8) return false;
        return !occupied.some((rect) => rectsOverlap(padRect(candidate, 2), rect));
      });
    }
    if (!placed && labelMode === 'all') placed = clampRect(candidates[0], w, h);
    if (!placed) continue;
    occupied.push(padRect(placed, labelMode === 'all' ? 2 : 4));
    labels.push({ id: node.id, text: label, x: placed.x, y: placed.y + height / 2, width, height });
  }
  return labels;
}

function labelCandidates(node: RenderNode, width: number, height: number, r: number, labelMode: LabelMode): Rect[] {
  const cx = node.x || 0;
  const cy = node.y || 0;
  const basic: Rect[] = [
    { x: cx + r + 12, y: cy - height / 2, width, height },
    { x: cx - r - 12 - width, y: cy - height / 2, width, height },
    { x: cx - width / 2, y: cy - r - 20, width, height },
    { x: cx - width / 2, y: cy + r + 10, width, height },
  ];
  if (labelMode === 'smart') return basic;

  const candidates = [...basic];
  const angles = [0, Math.PI, -Math.PI / 2, Math.PI / 2, -Math.PI / 4, Math.PI / 4, -3 * Math.PI / 4, 3 * Math.PI / 4];
  const distances = [r + 18, r + 34, r + 52, r + 72];
  for (const distance of distances) {
    for (const angle of angles) {
      const ax = Math.cos(angle);
      const ay = Math.sin(angle);
      candidates.push({
        x: cx + ax * distance - (ax < -0.25 ? width : ax > 0.25 ? 0 : width / 2),
        y: cy + ay * distance - height / 2,
        width,
        height,
      });
    }
  }
  return candidates;
}

type Rect = { x: number; y: number; width: number; height: number };

function circleBox(node: RenderNode, r: number): Rect {
  return { x: (node.x || 0) - r, y: (node.y || 0) - r, width: r * 2, height: r * 2 };
}

function padRect(rect: Rect, pad: number): Rect {
  return { x: rect.x - pad, y: rect.y - pad, width: rect.width + pad * 2, height: rect.height + pad * 2 };
}

function rectsOverlap(a: Rect, b: Rect) {
  return a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y;
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function clampRect(rect: Rect, w: number, h: number): Rect {
  return {
    ...rect,
    x: clamp(rect.x, 8, Math.max(8, w - rect.width - 8)),
    y: clamp(rect.y, 12, Math.max(12, h - rect.height - 8)),
  };
}

function hoverLines(node: RenderNode) {
  const lines = splitLongText(node.name, 26, 2);
  const source = [node.textbook_title, node.chapter].filter(Boolean).join(' · ');
  if (source) lines.push(shorten(source, 34));
  lines.push('点击查看详情');
  return lines;
}

function splitLongText(text: string, max = 26, maxLines = 2) {
  const clean = (text || '').trim();
  if (!clean) return ['未命名知识点'];
  const lines: string[] = [];
  for (let start = 0; start < clean.length && lines.length < maxLines; start += max) {
    const next = clean.slice(start, start + max);
    const hasMore = start + max < clean.length;
    lines.push(hasMore && lines.length === maxLines - 1 ? `${next}...` : next);
  }
  return lines;
}

function estimateTextWidth(text: string, fontSize: number) {
  let width = 0;
  for (const char of text) width += /[\u4e00-\u9fa5]/.test(char) ? fontSize : fontSize * 0.62;
  return Math.ceil(width);
}

function resolveCircleCollisions(nodes: RenderNode[], w: number, h: number, rFor: (node: RenderNode) => number, iterations: number) {
  for (let iter = 0; iter < iterations; iter += 1) {
    for (let i = 0; i < nodes.length; i += 1) {
      const a = nodes[i];
      const ar = rFor(a);
      a.x = Math.max(ar, Math.min(w - ar, a.x || w / 2));
      a.y = Math.max(ar, Math.min(h - ar, a.y || h / 2));
      for (let j = i + 1; j < nodes.length; j += 1) {
        const b = nodes[j];
        const br = rFor(b);
        const ax: number = a.x ?? w / 2;
        const ay: number = a.y ?? h / 2;
        const bx: number = b.x ?? w / 2;
        const by: number = b.y ?? h / 2;
        const dx: number = bx - ax;
        const dy: number = by - ay;
        const dist: number = Math.max(0.01, Math.hypot(dx, dy));
        const minDist: number = ar + br + 1;
        if (dist >= minDist) continue;
        const push: number = (minDist - dist) / 2;
        const ux: number = dx / dist;
        const uy: number = dy / dist;
        a.x = (a.x || 0) - ux * push;
        a.y = (a.y || 0) - uy * push;
        b.x = (b.x || 0) + ux * push;
        b.y = (b.y || 0) + uy * push;
      }
    }
  }
  for (const node of nodes) {
    const r = rFor(node);
    node.x = Math.max(r, Math.min(w - r, node.x || w / 2));
    node.y = Math.max(r, Math.min(h - r, node.y || h / 2));
  }
}

function drawTree(
  svg: D3Svg,
  w: number,
  h: number,
  nodes: RenderNode[],
  graphNodes: KnowledgeNode[],
  books: Textbook[],
  source: string,
  density: Density,
  query: string,
  selectedNode: KnowledgeNode | null | undefined,
  onNode: (node: KnowledgeNode | null) => void,
) {
  addDefs(svg);
  svg.append('rect').attr('width', w).attr('height', h).attr('fill', '#fbfdff').attr('rx', 16);
  const content = svg.append('g');
  const root = buildTreeRoot(nodes, graphNodes, books, source);
  const hierarchy = d3.hierarchy(root);
  const treeGap = density === 'calm' ? 58 : density === 'balanced' ? 52 : 46;
  const levelGap = density === 'calm' ? 290 : density === 'balanced' ? 265 : 240;
  d3.tree<any>()
    .nodeSize([treeGap, levelGap])
    .separation((a, b) => {
      if (a.depth === 2 && b.depth === 2 && a.parent === b.parent) return 1.18;
      return a.parent === b.parent ? 1.08 : 1.55;
    })(hierarchy as any);

  const descendants = hierarchy.descendants() as any[];
  const xExtent = d3.extent(descendants, (d) => d.x) as [number, number];
  const yExtent = d3.extent(descendants, (d) => d.y) as [number, number];
  const contentWidth = Math.max(w - 80, yExtent[1] - yExtent[0] + 360);
  const contentHeight = Math.max(h - 80, xExtent[1] - xExtent[0] + 80);
  const fitScale = Math.max(0.62, Math.min(0.92, (h - 96) / Math.max(1, contentHeight)));
  const initialX = 64 - yExtent[0] * fitScale;
  const initialY = h / 2 - ((xExtent[0] + xExtent[1]) / 2) * fitScale;
  const treeZoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.45, 2.4])
      .on('zoom', (event) => content.attr('transform', event.transform));
  svg.call(treeZoom as any);
  svg.call((treeZoom as any).transform, d3.zoomIdentity.translate(initialX, initialY).scale(fitScale));

  content.append('rect')
    .attr('x', yExtent[0] - 36)
    .attr('y', xExtent[0] - 36)
    .attr('width', contentWidth + 72)
    .attr('height', contentHeight + 72)
    .attr('rx', 16)
    .attr('fill', 'rgba(255,255,255,0.72)');

  content.selectAll('path.tree-link').data(hierarchy.links()).join('path')
    .attr('class', 'tree-link')
    .attr('fill', 'none')
    .attr('stroke', (d: any) => d.target.depth === 1 ? '#2563eb' : d.target.depth === 2 ? '#0f766e' : '#cbd5e1')
    .attr('stroke-width', (d: any) => d.target.depth === 1 ? 2.4 : d.target.depth === 2 ? 1.6 : 1)
    .attr('stroke-opacity', 0.64)
    .attr('d', d3.linkHorizontal<any, any>().x((d: any) => d.y).y((d: any) => d.x));

  const item = content.selectAll('g.tree-node').data(descendants).join('g')
    .attr('class', 'tree-node')
    .attr('transform', (d: any) => `translate(${d.y},${d.x})`)
    .style('cursor', (d: any) => d.data.node ? 'pointer' : 'default')
    .on('click', (_, d: any) => d.data.node && onNode(d.data.node));

  item.each(function (d: any) {
    const el = d3.select(this);
    const node = d.data.node as RenderNode | undefined;
    const matched = Boolean(node && query && nodeMatches(node, query.toLowerCase()));
    const selected = Boolean(node && selectedNode?.id === node.id);
    if (d.depth === 0) {
      el.append('circle').attr('r', 19).attr('fill', '#0f172a');
      el.append('text').text('知').attr('text-anchor', 'middle').attr('dy', 5).attr('fill', '#fff').attr('font-size', 12).attr('font-weight', 800);
      return;
    }
    if (d.depth < 3) {
      const color = d.depth === 1 ? '#2563eb' : '#0f766e';
      const label = shorten(d.data.name, d.depth === 1 ? 16 : 22);
      const fontSize = d.depth === 1 ? 11.5 : 10.8;
      const height = d.depth === 1 ? 30 : 26;
      const width = Math.max(74, Math.min(d.depth === 1 ? 220 : 255, estimateTextWidth(label, fontSize) + 28));
      el.append('rect')
        .attr('x', -10)
        .attr('y', -height / 2)
        .attr('width', width)
        .attr('height', height)
        .attr('rx', 7)
        .attr('fill', color)
        .attr('opacity', d.depth === 1 ? 0.94 : 0.88);
      el.append('text')
        .text(label)
        .attr('x', 4)
        .attr('dy', 4)
        .attr('fill', '#fff')
        .attr('font-size', fontSize)
        .attr('font-weight', d.depth === 1 ? 800 : 760);
      return;
    }
    const r = node ? Math.max(5.5, Math.min(12, radius(node) * 0.5)) : 5.5;
    el.append('circle')
      .attr('r', r)
      .attr('fill', node ? nodeColor(node) : '#94a3b8')
      .attr('stroke', selected ? '#0f172a' : matched ? '#fff' : 'rgba(255,255,255,0.9)')
      .attr('stroke-width', selected ? 3 : matched ? 2.3 : 1.3)
      .attr('filter', selected || matched ? 'url(#soft-glow)' : null);
    el.append('text')
      .text(shorten(d.data.name, density === 'rich' ? 14 : 18))
      .attr('x', r + 9).attr('dy', 4)
      .attr('fill', selected || matched ? '#111827' : '#475569')
      .attr('font-size', 10.5)
      .attr('font-weight', selected || matched ? 800 : 650)
      .attr('paint-order', 'stroke')
      .attr('stroke', 'rgba(255,255,255,0.94)')
      .attr('stroke-width', 3);
  });
}

function buildTreeRoot(nodes: RenderNode[], graphNodes: KnowledgeNode[], books: Textbook[], source: string) {
  const root: any = { name: '知识体系', children: [] };
  const nodesByBookId = d3.group(nodes, (d) => d.textbook_id || 'unknown');
  const nodesByBookTitle = d3.group(nodes, (d) => d.textbook_title || d.textbook_id || '未知教材');
  const graphBookIds = new Set(graphNodes.map((node) => node.textbook_id).filter(Boolean));
  const bookList = books
    .filter((book) => (source === 'all' ? graphBookIds.has(book.textbook_id) : book.textbook_id === source))
    .sort((a, b) => naturalCompare(a.title, b.title));
  const renderedBooks = new Set<string>();

  for (const book of bookList) {
    const bookNodes = nodesByBookId.get(book.textbook_id) || nodesByBookTitle.get(book.title) || [];
    renderedBooks.add(book.textbook_id);
    const byChapter = d3.group(bookNodes.sort(graphOrder), (d) => d.chapter || '未识别章节');
    root.children.push({
      name: book.title,
      children: book.chapters
        .slice()
        .sort((a, b) => chapterNumber(a.title) - chapterNumber(b.title) || a.page_start - b.page_start || naturalCompare(a.title, b.title))
        .map((chapter) => {
          const chapterNodes = byChapter.get(chapter.title) || [];
          return {
            name: chapter.title,
            children: chapterNodes.sort(graphOrder).map((node) => ({ name: node.name, node })),
          };
        }),
    });
  }

  for (const [book, bookNodes] of Array.from(nodesByBookTitle.entries()).sort(([a], [b]) => naturalCompare(a, b))) {
    const first = bookNodes[0];
    if (!first || renderedBooks.has(first.textbook_id || '')) continue;
    const byChapter = d3.group(bookNodes.sort(graphOrder), (d) => d.chapter || '未识别章节');
    root.children.push({
      name: book,
      children: Array.from(byChapter.entries())
        .sort(([a], [b]) => compareChapter(a, b))
        .map(([chapter, chapterNodes]) => ({
          name: chapter,
          children: chapterNodes.sort(graphOrder).map((node) => ({ name: node.name, node })),
        })),
    });
  }
  return root;
}

function drawMatrix(
  svg: D3Svg,
  w: number,
  h: number,
  nodes: RenderNode[],
  edges: KnowledgeEdge[],
  density: Density,
  query: string,
  selectedNode: KnowledgeNode | null | undefined,
  onNode: (node: KnowledgeNode | null) => void,
) {
  svg.append('rect').attr('width', w).attr('height', h).attr('fill', '#fbfdff').attr('rx', 16);
  const maxBySpace = Math.max(12, Math.floor(Math.min(w - 260, h - 180) / 17));
  const sub = nodes.slice(0, Math.min(densityConfig[density].matrixLimit, maxBySpace));
  const idx = new Map(sub.map((node, i) => [node.id, i]));
  const gridSize = Math.min(w - 250, h - 150);
  const cell = Math.max(14, Math.min(22, gridSize / Math.max(1, sub.length)));
  const g = svg.append('g').attr('transform', 'translate(160,92)');
  g.append('rect').attr('x', -150).attr('y', -80).attr('width', cell * sub.length + 190).attr('height', cell * sub.length + 130).attr('rx', 16).attr('fill', 'rgba(255,255,255,0.74)');

  g.selectAll('rect.bg').data(d3.range(sub.length * sub.length)).join('rect')
    .attr('x', (d) => (d % sub.length) * cell)
    .attr('y', (d) => Math.floor(d / sub.length) * cell)
    .attr('width', cell - 1)
    .attr('height', cell - 1)
    .attr('rx', 2)
    .attr('fill', 'rgba(226,232,240,0.55)');

  const cells: { x: number; y: number; edge: KnowledgeEdge }[] = [];
  for (const edge of edges) {
    const x = idx.get(edge.source);
    const y = idx.get(edge.target);
    if (x !== undefined && y !== undefined) cells.push({ x, y, edge });
  }

  g.selectAll('rect.cell').data(cells).join('rect')
    .attr('x', (d) => d.x * cell)
    .attr('y', (d) => d.y * cell)
    .attr('width', cell - 1)
    .attr('height', cell - 1)
    .attr('rx', 2)
    .attr('fill', (d) => relColor[d.edge.relation_type] || '#64748b')
    .attr('opacity', 0.82)
    .append('title')
    .text((d) => `${sub[d.x]?.name} -> ${sub[d.y]?.name}\n${relLabel[d.edge.relation_type] || d.edge.relation_type}`);

  const matched = (node: RenderNode) => Boolean(query && nodeMatches(node, query.toLowerCase()));
  g.selectAll('text.row').data(sub).join('text')
    .attr('x', -10)
    .attr('y', (_, i) => i * cell + cell * 0.68)
    .attr('text-anchor', 'end')
    .attr('fill', (d) => selectedNode?.id === d.id || matched(d) ? '#111827' : '#64748b')
    .attr('font-size', 10)
    .attr('font-weight', (d) => selectedNode?.id === d.id || matched(d) ? 800 : 550)
    .text((d) => shorten(d.name, 12))
    .style('cursor', 'pointer')
    .on('click', (_, d) => onNode(d));

  g.selectAll('text.col').data(sub).join('text')
    .attr('transform', (_, i) => `translate(${i * cell + cell * 0.66},-10) rotate(-55)`)
    .attr('text-anchor', 'start')
    .attr('fill', (d) => selectedNode?.id === d.id || matched(d) ? '#111827' : '#64748b')
    .attr('font-size', 10)
    .attr('font-weight', (d) => selectedNode?.id === d.id || matched(d) ? 800 : 550)
    .text((d) => shorten(d.name, 12));
}
