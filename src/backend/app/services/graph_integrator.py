from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Dict, List

import numpy as np
from rapidfuzz import fuzz

from ..models.schemas import IntegratedGraph, IntegrationDecision, KnowledgeEdge, KnowledgeGraph, KnowledgeNode, Textbook
from ..utils.text import normalize_key, safe_id
from .embedding import EmbeddingService


class GraphIntegrator:
    def __init__(self) -> None:
        self.embedding = EmbeddingService()

    def integrate(self, books: List[Textbook], graphs: Dict[str, KnowledgeGraph], threshold: float = 0.82) -> IntegratedGraph:
        all_nodes: List[KnowledgeNode] = []
        all_edges: List[KnowledgeEdge] = []
        for g in graphs.values():
            all_nodes.extend(g.nodes)
            all_edges.extend(g.edges)
        if not all_nodes:
            return IntegratedGraph(stats={"message": "尚未构建知识图谱"})

        clusters = self._cluster_nodes(all_nodes, threshold=threshold)
        merged_nodes: List[KnowledgeNode] = []
        decisions: List[IntegrationDecision] = []
        node_map: Dict[str, str] = {}

        for idx, cluster in enumerate(clusters, 1):
            cluster_nodes = [all_nodes[i] for i in cluster]
            if len(cluster_nodes) > 1:
                result = self._merge_cluster(cluster_nodes, idx)
                merged_nodes.append(result)
                for n in cluster_nodes:
                    node_map[n.id] = result.id
                decisions.append(
                    IntegrationDecision(
                        decision_id=f"merge_{idx:03d}",
                        action="merge",
                        affected_nodes=[n.id for n in cluster_nodes],
                        result_node=result.id,
                        reason=self._merge_reason(cluster_nodes, result),
                        confidence=self._cluster_confidence(cluster_nodes),
                    )
                )
            else:
                n = cluster_nodes[0]
                kept = n.model_copy(deep=True)
                kept.frequency = 1
                merged_nodes.append(kept)
                node_map[n.id] = kept.id
                decisions.append(
                    IntegrationDecision(
                        decision_id=f"keep_{idx:03d}",
                        action="keep",
                        affected_nodes=[n.id],
                        result_node=n.id,
                        reason=f"“{n.name}”在当前教材集合中没有发现高相似重复概念，保留作为互补知识点。",
                        confidence=0.78,
                    )
                )

        remapped_edges: List[KnowledgeEdge] = []
        seen_edges = set()
        for e in all_edges:
            s, t = node_map.get(e.source), node_map.get(e.target)
            if not s or not t or s == t:
                continue
            key = (s, t, e.relation_type)
            if key in seen_edges:
                continue
            seen_edges.add(key)
            remapped_edges.append(e.model_copy(update={"source": s, "target": t}))

        # Compression: definitions + relation descriptions as the essence text.
        original_chars = sum(b.total_chars for b in books)
        raw_integrated_chars = sum(len(n.definition) for n in merged_nodes) + sum(len(e.description) for e in remapped_edges)
        target_chars = int(original_chars * 0.30) if original_chars else raw_integrated_chars
        # Report the actual essence size instead of clipping the statistic to
        # the target. The graph essence is already compact in normal seven-book
        # runs; if a future corpus exceeds the target, surface that honestly.
        integrated_chars = raw_integrated_chars
        compression_ratio = round((integrated_chars / original_chars * 100), 2) if original_chars else 0

        stats = {
            "original_books": len(books),
            "original_chars": original_chars,
            "integrated_chars": integrated_chars,
            "raw_integrated_chars": raw_integrated_chars,
            "compression_ratio": compression_ratio,
            "target_ratio": 30,
            "target_chars": target_chars,
            "target_exceeded": bool(original_chars and integrated_chars > target_chars),
            "nodes_before": len(all_nodes),
            "nodes_after": len(merged_nodes),
            "edges_before": len(all_edges),
            "edges_after": len(remapped_edges),
            "merge_count": sum(1 for d in decisions if d.action == "merge"),
            "keep_count": sum(1 for d in decisions if d.action == "keep"),
            "remove_count": sum(1 for d in decisions if d.action == "remove"),
            "embedding_backend": self.embedding.backend,
            "updated_at": datetime.utcnow().isoformat(),
        }
        return IntegratedGraph(nodes=merged_nodes, edges=remapped_edges, decisions=decisions, stats=stats)

    def _cluster_nodes(self, nodes: List[KnowledgeNode], threshold: float) -> List[List[int]]:
        n = len(nodes)
        parent = list(range(n))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        names = [normalize_key(node.name) for node in nodes]
        texts = [f"{node.name}。{node.definition}" for node in nodes]
        vectors = self.embedding.encode_corpus(texts).vectors

        # Exact-name buckets are cheap and precise. Avoid section labels such as
        # "第一节" because they otherwise become giant transitive clusters.
        exact_buckets: Dict[str, List[int]] = defaultdict(list)
        for idx, name in enumerate(names):
            if self._mergeable_name(name):
                exact_buckets[name].append(idx)
        for bucket in exact_buckets.values():
            for idx in bucket[1:]:
                union(bucket[0], idx)

        # Semantic alignment is restricted to nearest neighbors instead of all
        # O(n^2) pairs, which keeps 7-book runs responsive and prevents one weak
        # similarity bridge from collapsing unrelated concepts into a mega-cluster.
        if getattr(vectors, "size", 0):
            neighbor_count = min(10, n)
            similarities = self.embedding.cosine(vectors, vectors)
            for i in range(n):
                if neighbor_count <= 1:
                    continue
                row = similarities[i].copy()
                row[i] = -1.0
                candidates = np.argpartition(row, -neighbor_count)[-neighbor_count:]
                candidates = candidates[np.argsort(row[candidates])[::-1]]
                for j in candidates:
                    if j <= i:
                        continue
                    semantic = float(row[j])
                    if self._should_merge_pair(nodes, names, i, int(j), semantic, threshold):
                        union(i, int(j))

        buckets: Dict[int, List[int]] = defaultdict(list)
        for i in range(n):
            buckets[find(i)].append(i)
        return sorted(buckets.values(), key=lambda c: (-len(c), min(c)))

    def _should_merge_pair(self, nodes: List[KnowledgeNode], names: List[str], i: int, j: int, semantic: float, threshold: float) -> bool:
        left_name = names[i]
        right_name = names[j]
        if not self._mergeable_name(left_name) or not self._mergeable_name(right_name):
            return False
        fuzzy = fuzz.token_sort_ratio(left_name, right_name) / 100
        overlap = self._char_overlap(left_name, right_name)
        same_book = nodes[i].textbook_id == nodes[j].textbook_id
        if fuzzy >= 0.94:
            return True
        if same_book:
            return False
        return (semantic >= threshold and (fuzzy >= 0.72 or overlap >= 0.58)) or (semantic >= 0.90 and fuzzy >= 0.55)

    @staticmethod
    def _mergeable_name(name: str) -> bool:
        if len(name) < 2:
            return False
        generic = {"第一节", "第二节", "第三节", "第四节", "第五节", "第六节", "第七节", "第八节", "第九节", "第十节", "目录", "索引", "概述", "绪论"}
        return name not in generic and not name.isdigit()

    @staticmethod
    def _char_overlap(left: str, right: str) -> float:
        left_set = {c for c in left if c.strip()}
        right_set = {c for c in right if c.strip()}
        if not left_set or not right_set:
            return 0.0
        return len(left_set & right_set) / max(1, min(len(left_set), len(right_set)))

    def _merge_cluster(self, nodes: List[KnowledgeNode], idx: int) -> KnowledgeNode:
        # Pick the most complete definition as canonical, but retain aliases and provenance.
        best = sorted(nodes, key=lambda n: (len(n.definition), n.importance), reverse=True)[0]
        aliases = sorted({n.name for n in nodes if n.name != best.name})
        textbook_titles = sorted({n.textbook_title for n in nodes})
        merged_definition = best.definition
        if aliases:
            merged_definition += f"（同义/近义表述：{'、'.join(aliases[:6])}。）"
        return best.model_copy(
            update={
                "id": f"merged_node_{idx:03d}",
                "aliases": aliases,
                "frequency": len(textbook_titles),
                "source": "；".join([n.source for n in nodes[:5]]),
                "definition": merged_definition[:500],
                "importance": min(1.0, max(n.importance for n in nodes) + 0.08 * (len(textbook_titles) - 1)),
            }
        )

    def _merge_reason(self, nodes: List[KnowledgeNode], result: KnowledgeNode) -> str:
        sources = "、".join(sorted({n.textbook_title for n in nodes}))
        names = "、".join(sorted({n.name for n in nodes}))
        return f"{len(nodes)} 个节点（{names}）在名称、定义或语义向量上高度相似，来自 {sources}；保留“{result.name}”作为最完整表述，并把其他表述写入 aliases。"

    def _cluster_confidence(self, nodes: List[KnowledgeNode]) -> float:
        if len(nodes) <= 1:
            return 0.75
        names = [normalize_key(n.name) for n in nodes]
        exact_bonus = 0.08 if len(set(names)) == 1 else 0
        return min(0.98, 0.82 + exact_bonus + 0.02 * len(nodes))
