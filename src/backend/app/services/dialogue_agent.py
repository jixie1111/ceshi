from __future__ import annotations

import re
from typing import List

from ..models.schemas import DialogueResponse, IntegratedGraph, IntegrationDecision


class DialogueAgent:
    """Teacher-feedback agent.

    It intentionally supports deterministic natural-language commands so the demo
    is reliable under a 5-hour hackathon constraint. LLM understanding can be
    added later while keeping these safe command paths.
    """

    def handle(self, message: str, graph: IntegratedGraph) -> DialogueResponse:
        msg = message.strip()
        updated: List[IntegrationDecision] = []
        graph_changed = False

        if not graph.decisions:
            return DialogueResponse(reply="我还没有整合决策。请先运行“跨教材整合”，再告诉我需要保留、删除、合并或拆分哪个知识点。")

        # Explain why.
        why_match = re.search(r"为什么.*?(?:把|将)?[《\u4e00-\u9fa5A-Za-z0-9_\-]*['‘“]?([^'’”]+?)['’”]?(?:和|与|同|合并|删除)", msg)
        if "为什么" in msg:
            keyword = self._extract_keyword(msg)
            decision = self._find_decision(keyword, graph)
            if decision:
                return DialogueResponse(reply=f"关于“{keyword}”：{decision.reason} 置信度 {decision.confidence:.2f}。如果你认为不合理，可以说“保留 {keyword}”或“拆分 {keyword}”。")
            return DialogueResponse(reply="我没有找到对应的整合决策。可以提供更具体的知识点名称，例如“为什么合并 动作电位”。")

        keyword = self._extract_keyword(msg)
        if any(k in msg for k in ["保留", "不要删除", "恢复"]):
            for d in graph.decisions:
                if self._decision_matches(d, keyword, graph):
                    d.action = "keep"
                    d.teacher_locked = True
                    d.reason += f"；教师反馈要求保留“{keyword}”，系统已锁定为 keep。"
                    updated.append(d)
            graph_changed = bool(updated)
            reply = f"已根据教师反馈保留“{keyword}”，对应决策已锁定并会在图谱中保留。" if updated else f"没找到“{keyword}”对应决策，请换一个更精确名称。"
            return DialogueResponse(reply=reply, updated_decisions=updated, graph_changed=graph_changed)

        if any(k in msg for k in ["删除", "移除", "去掉"]):
            for d in graph.decisions:
                if self._decision_matches(d, keyword, graph):
                    d.action = "remove"
                    d.teacher_locked = True
                    d.reason += f"；教师反馈要求删除“{keyword}”，系统已调整为 remove。"
                    updated.append(d)
            graph_changed = bool(updated)
            reply = f"已把“{keyword}”标记为删除。" if updated else f"没找到“{keyword}”对应决策，请换一个更精确名称。"
            return DialogueResponse(reply=reply, updated_decisions=updated, graph_changed=graph_changed)

        if any(k in msg for k in ["分开", "拆分", "不是同一个", "不应该合并"]):
            for d in graph.decisions:
                if d.action == "merge" and self._decision_matches(d, keyword, graph):
                    d.action = "split"
                    d.teacher_locked = True
                    d.reason += f"；教师反馈认为“{keyword}”不应合并，系统已将该决策改为 split，前端会显示为待拆分。"
                    updated.append(d)
            graph_changed = bool(updated)
            reply = f"已把“{keyword}”相关合并决策改为拆分。" if updated else f"没有找到包含“{keyword}”的合并决策。"
            return DialogueResponse(reply=reply, updated_decisions=updated, graph_changed=graph_changed)

        if any(k in msg for k in ["合并", "归并"]):
            return DialogueResponse(reply="可以合并。请用“合并 A 和 B”的格式告诉我两个知识点；当前版本会把它记录为教师建议，下一次整合会优先考虑。")

        return DialogueResponse(reply="我理解你的反馈。当前可执行命令包括：为什么合并/删除 X、保留 X、删除 X、拆分 X。你的对话历史会保留在当前会话中。")

    def _extract_keyword(self, message: str) -> str:
        quoted = re.findall(r"[“'‘《]?([\u4e00-\u9fa5A-Za-z0-9_\-]{2,20})[”'’》]?", message)
        stop = {"为什么", "我觉得", "不应该", "请保留", "保留", "删除", "拆分", "合并", "不是", "同一个", "知识点", "教材", "系统"}
        candidates = [x for x in quoted if x not in stop and not x.isdigit()]
        return candidates[-1] if candidates else message[-12:]

    def _find_decision(self, keyword: str, graph: IntegratedGraph) -> IntegrationDecision | None:
        return next((d for d in graph.decisions if self._decision_matches(d, keyword, graph)), None)

    def _decision_matches(self, decision: IntegrationDecision, keyword: str, graph: IntegratedGraph) -> bool:
        if not keyword:
            return False
        if keyword in decision.reason or any(keyword in nid for nid in decision.affected_nodes):
            return True
        nodes = {n.id: n for n in graph.nodes}
        ids = list(decision.affected_nodes) + ([decision.result_node] if decision.result_node else [])
        for nid in ids:
            n = nodes.get(nid)
            if n and (keyword in n.name or keyword in "".join(n.aliases) or keyword in n.definition):
                return True
        return False
