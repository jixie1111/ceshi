from __future__ import annotations

import itertools
import re
from collections import Counter
from typing import List, Tuple

from ..core.config import get_settings
from ..models.schemas import KnowledgeEdge, KnowledgeGraph, KnowledgeNode, Textbook
from ..utils.text import STOPWORDS, best_definition, clean_line, clean_text, looks_like_toc_page, normalize_key, safe_id
from .llm_client import LLMClient

MEDICAL_HINTS = [
    "电位", "稳态", "反射", "调节", "转运", "受体", "递质", "激素", "血压", "血糖", "凝血", "通气", "换气", "代谢", "体温",
    "滤过", "重吸收", "分泌", "神经", "肌肉", "骨骼肌", "平滑肌", "心肌", "循环", "吸收", "免疫", "屏障", "微生态", "发育", "衰老", "炎症", "肿瘤",
    "缺氧", "水肿", "酸碱", "电解质", "坏死", "凋亡", "休克", "感染", "抗原", "抗体",
    "动脉", "静脉", "淋巴", "筋膜", "韧带", "关节", "神经丛",
]
MEDICAL_SHORT_TERMS = {
    "血压", "血糖", "凝血", "缺氧", "水肿", "炎症", "肿瘤", "坏死", "凋亡", "休克", "感染", "抗原", "抗体", "免疫",
    "通气", "换气", "吸收", "滤过", "分泌", "反射", "稳态", "血液", "循环", "代谢", "体温", "激素", "受体", "递质",
    "神经", "肌肉", "肌腱", "血管", "淋巴", "器官", "组织", "细菌", "病毒", "真菌", "损伤", "修复", "贫血",
}
BAD_TERMS = STOPWORDS | {
    "前言", "目录", "索引", "参考文献", "学习目标", "复习题", "思考题", "小结", "附录", "正文", "中国", "人民",
    "出版社", "编辑", "作者", "委员会", "专业委员会", "学会", "主任", "基础", "概述", "特点", "原因", "结果",
    "类型", "形式", "检测", "单位", "方面", "水平", "部分", "临床", "疾病", "病理", "生理", "解剖", "局部",
    "现象", "影响", "研究内容", "解剖学", "组织学", "胚胎学", "免疫学",
    "组织", "器官", "病理学", "生理学", "病理生理学", "局部解剖学", "感染病学", "文字记录", "总论",
    "主要症状", "主要表现", "主要内容", "主要功能", "主要成分", "临床表现", "诊断标准", "治疗原则",
    "防治原则", "病因学", "发病机制", "致病机制", "检查方法", "注意事项", "本章数字资源",
    "未识别章节", "未命名章节", "自动分段", "另一类", "医学教育", "临床医学", "医科大学", "高等学校",
    "教育部", "医学生", "第十轮", "五年制", "版教材",
}
PUBLISHING_MARKERS = {
    "国家卫生健康委员会", "十四五", "规划教材", "全国高等学校教材", "人民卫生出版社", "主编", "副主编",
    "编写修订", "医学教育家", "教材建设", "专业委员会", "学会", "供基础", "临床医学专业",
}
NON_TERM_MARKERS = {
    "请", "为什么", "怎样", "如何", "因为", "并不", "仅仅", "无论", "认为", "说明", "指出", "可知", "所具有",
    "没有", "只有", "通过", "按其", "分别", "同时", "主要功能", "基本功能", "主要任务", "本教材", "本书", "都",
    "也", "还可", "即可", "可用于", "常用", "有关", "相关", "一般", "正常", "异常",
}

PHRASE_MARKERS = {
    "主要症状", "主要表现", "主要原因", "主要任务", "主要内容", "主要成", "我国常被", "常被称为",
    "这种", "这些", "其主要", "并分泌", "并释放", "可分泌", "可分为", "可导致", "可引起", "可出现", "可发生",
    "易发生", "时易发生", "通过", "由于", "导致", "引起", "进入", "排出", "注入", "接受", "产生", "揭示",
    "提供", "关注", "从事", "研究", "观察", "修洁", "注意", "附着", "探查", "跨越", "深入",
    "包裹", "在机体", "的影响", "及其", "还",
    "位于", "分布于", "所致", "所形成", "所产生", "所引起", "由此", "从而", "因此", "以及",
    "利用", "适用于", "作为", "发现了", "成功地", "为主", "对于", "不仅", "已不再", "能够", "帮助", "决定",
    "增加了", "主要的", "提示", "显示", "诊断特征", "诊断方法", "表现形式", "震颤等",
    "尚不完善", "获得适应性", "就不会", "减弱而", "受体结合", "相应受体", "感染病人",
    "重要作用", "代谢途径", "严格落实", "巧克力酱样", "破坏人体", "认知障碍尤其",
    "症状", "后的", "的作用", "的方法", "的措施", "的机制", "的免疫", "较牢固", "持久的",
    "采用", "协助", "主要针对", "有效的", "既往", "称为", "又称", "存在异质性",
    "等机制达", "等共同形", "十分活跃", "明显增高", "多发生于", "阻止",
    "首次证明", "现多种", "到多种", "早期播散性", "起急性", "口咽部", "受体阴道",
    "最适酸碱度", "均为", "丧失神经支配",
    "本病例中", "病例中肿瘤", "重吸收水", "括弧内数据", "几乎全部",
    "扫描图片", "体验AR", "AR模型", "数字特色", "推荐阅读", "中英文名词", "本章数字资源",
}
SALVAGE_PREFIXES = (
    "根据", "依据", "按照", "按", "所谓", "即", "称为", "称作", "叫做", "又称", "分化为", "化为", "转化为", "发育为", "释放", "共同构成", "增厚形成", "加重",
)
BAD_START_PHRASES = (
    "它们", "他们", "她们", "这些", "那些", "此类", "前者", "后者", "其中", "中段", "每日", "开始",
    "部分",
    "周末", "体的", "落的", "科学为", "处仔细", "中肿瘤", "右侧自", "纵行切开", "胞分泌", "胞缺乏",
    "月开始", "首先", "部位", "体出现", "右侧至", "解剖", "人们", "利用", "能够", "帮助", "维护",
    "测试提示", "时启动", "断出现", "学感受性", "指体", "应诊断", "感染病不仅", "损伤机体",
    "体外细胞培养", "主要的", "等", "虽然", "初期", "验适用于", "期微循环",
    "骨表面供", "韧带等", "神经嵴细胞首先", "神经嵴细胞向", "后再", "别肺炎",
    "压力蒸汽灭菌器就", "破坏人体", "理神经", "病理神经反射阳", "保持了", "静脉血",
    "人在", "人体的", "素抗体", "性污染", "辅助受体", "采用", "直接免疫荧光法",
    "立有效", "疫主要靠", "生特异性", "伏于", "适应性免疫应答中", "供体移植入",
    "菌免疫的", "具体的", "据肿瘤", "构成了", "腹泻疫情就",
    "首次证明", "现多种", "到多种", "早期播散性", "起急性", "口咽部", "受体阴道",
    "最适酸碱度", "菌具有", "种病原", "均为", "组织学上", "认知障碍尤",
    "本病例", "病例中", "加快", "足长", "感染者几乎",
)
BAD_TRAILING_PHRASES = (
    "主要", "不断", "迅速", "通常", "一般", "明显", "较多", "较少", "附近", "平面", "后方", "清除", "作", "包", "仅", "进",
    "良好", "过多", "为主", "从开始", "前方", "深面", "上缘处", "既往", "尤其", "病人", "结果", "资料", "就",
)
TRIM_TRAILING_PHRASES = (
    "主要", "不断", "迅速", "通常", "一般", "明显", "较多", "较少", "附近", "平面", "清除", "作", "包", "仅", "进",
    "良好", "过多", "为主", "既往",
)
CLAUSE_MARKERS = (
    "发育为", "发育成", "分化为", "增厚为", "汇入", "分布到", "转运到", "分泌到", "不断", "逐渐",
    "主要包括", "主要接受", "是主要", "多为", "含有", "中含", "含水分", "含唾液", "正处于", "诊断为", "作用于", "起调节作用", "来调节",
    "调节腺", "缺如", "长入", "造成", "所致", "因", "常随", "发育阶段", "发育时期",
    "收集", "属于", "仔细", "寻认", "发育增大", "覆于", "穿环", "染血", "外包", "为人体", "借",
    "等细胞", "细胞分泌", "基本相同", "进一步发育", "排泄", "临床学科", "切开", "自右", "分泌物质",
    "经肋间", "偶见", "陆续", "衰老死亡", "转移至", "近腹股沟处", "之间无", "浅出",
    "腔面内皮", "发育完善", "较易观", "起自", "在胸锁关节", "在腹壁",
    "常需", "切断", "离断", "剖刀", "较伴行", "发育良好", "易受累", "不同组织", "表达的",
    "发现了", "成功地", "适用于", "结合决定", "显著增加", "主要侵犯", "中发挥",
    "诊断特征", "起源于", "吸收过多", "血压持续", "从开始", "已不再", "分离到", "不仅",
    "根据", "反应增强", "平衡失", "激机体", "供骨骼肌", "韧性结构", "管腔分泌",
    "首先分", "向两侧", "末梢释放", "体格发育程度", "许多", "逃避宿主", "尚不完善",
    "获得适应性", "再次增", "等检", "不会感染", "减弱而保留", "受体作用", "受体结合",
    "释放的大", "感染病人", "中起重要作用", "转运入", "不受", "保持其免疫原性",
    "压迫局部", "压迫髂", "某种激素", "缺氧发生", "落实计划", "巧克力酱样", "病史",
    "中枢神经系统新型隐球", "认知障碍尤其",
    "后的免疫", "天然免疫的作用", "较牢固的免疫力", "持久的免疫力", "抗原性稳定",
    "组织中高表达", "作凝集试", "促进补体", "对其感染", "从抑制性神经",
    "主要针对", "诱发免疫应答损伤", "放射免疫测定", "协助病毒包膜", "免疫组织化学方法",
    "共代谢", "共发育", "称为合成代谢", "称为分解代谢", "过度分泌", "中高表达",
    "移植入受体", "存在异质性",
    "等共同形", "十分活跃", "明显增高", "多发生于", "等机制达", "阻止支原体感染",
    "动物疾病", "多种特异性抗体", "急性肠道内感染", "定植菌吸入", "阴道微生物群",
    "病理改变均为", "丧失神经支配",
    "本病例中", "加快重吸收", "重吸收水", "括弧内数据", "感染者几乎全部", "几乎全部",
)
BAD_GENERIC_TERMS = {
    "主要作用", "主要特征", "总的作用", "形态特征", "超微结构特点", "本章目标测试", "供应范围", "发育",
    "调节", "分泌", "转运", "代谢", "吸收", "血液", "感染", "损伤",
    "脊肌", "本病例中肿瘤", "加快重吸收水", "足长括弧内数据", "感染者几乎全部",
}
BAD_DEFINITION_PHRASES = (
    "本病例中肿瘤", "加快重吸收水", "足长括弧内数据", "感染者几乎全部",
    "脊柱区的肌可", "脊肌可", "肛门括约肌可", "肌前内侧主要",
    "则应注意观测它", "则应注意观察它", "人体可",
    "上颌动脉以翼外肌为标志可", "嗜色细胞又",
)
TERMISH_SUFFIXES = (
    "症", "征", "病", "炎", "癌", "瘤", "菌", "毒", "体", "酶", "酸", "碱", "盐", "素", "蛋白", "因子",
    "细胞", "组织", "器官", "系统", "反应", "效应", "作用", "机制", "过程", "通路", "循环", "调节",
    "转运", "分泌", "吸收", "滤过", "重吸收", "代谢", "损伤", "坏死", "凋亡", "水肿", "休克", "感染",
    "发生",
    "免疫", "抗原", "抗体", "受体", "电位", "稳态", "反射", "血压", "血糖",
    "动脉", "静脉", "神经", "淋巴", "筋膜", "韧带", "关节", "肌", "肌肉", "骨骼肌", "平滑肌", "心肌",
    "网膜孔", "腹股沟管", "胸膜腔", "颅骨", "乳房",
)
ENGLISH_MEDICAL_TERMS = {
    "leukocyte", "lymphocyte", "monocyte", "neutrophil", "macrophage", "antigen", "antibody",
    "inflammation", "apoptosis", "necrosis", "shock", "homeostasis", "receptor", "cytokine",
    "virus", "bacteria", "fungus", "prion", "chlamydia", "mycoplasma", "rickettsia",
}


class KnowledgeExtractor:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm = LLMClient()

    def build_graph(self, textbook: Textbook) -> KnowledgeGraph:
        nodes: List[KnowledgeNode] = []
        edges: List[KnowledgeEdge] = []
        seen = set()
        for chapter in textbook.chapters:
            if not self._chapter_is_extractable(chapter.title, chapter.content):
                continue
            chapter_nodes, chapter_edges = self._extract_chapter(textbook, chapter)
            for n in chapter_nodes:
                clean_name = self._normalize_term(n.name)
                if not self._term_ok(clean_name):
                    continue
                n.name = clean_name
                key = (normalize_key(n.name), chapter.chapter_id)
                if key not in seen:
                    seen.add(key)
                    nodes.append(n)
            edges.extend(chapter_edges)
        # Global prerequisites: chapters follow book order.
        nodes_by_chapter = {}
        for n in nodes:
            nodes_by_chapter.setdefault(n.chapter, []).append(n)
        for chapter_nodes in nodes_by_chapter.values():
            important = sorted(chapter_nodes, key=lambda x: x.importance, reverse=True)[:4]
            for a, b in zip(important, important[1:]):
                edges.append(
                    KnowledgeEdge(
                        source=a.id,
                        target=b.id,
                        relation_type="prerequisite",
                        description=f"学习“{b.name}”通常需要先理解“{a.name}”。",
                        weight=0.65,
                    )
                )
        valid_ids = {n.id for n in nodes}
        edges = [e for e in edges if e.source in valid_ids and e.target in valid_ids]
        return KnowledgeGraph(textbook_id=textbook.textbook_id, nodes=nodes, edges=self._dedupe_edges(edges))

    def _extract_chapter(self, textbook: Textbook, chapter) -> Tuple[List[KnowledgeNode], List[KnowledgeEdge]]:
        if self.settings.enable_llm_extraction and self.llm.available:
            llm_result = self._extract_with_llm(textbook, chapter)
            if llm_result:
                return llm_result
        return self._extract_with_rules(textbook, chapter)

    def _extract_with_llm(self, textbook: Textbook, chapter) -> Tuple[List[KnowledgeNode], List[KnowledgeEdge]] | None:
        system = """你是医学教材知识图谱抽取专家。只输出 JSON，不要输出解释。
要求：nodes 中每个节点包含 name, definition, category, page；edges 中 relation_type 只能是 prerequisite/parallel/contains/applies_to。
定义不要编造，只能来自章节文本。"""
        user = f"""请从一个教材章节中抽取 8-14 个核心知识点及关系。
教材：{textbook.title}
章节：{chapter.title}，起始页：{chapter.page_start}
输出格式示例：{{"nodes":[{{"name":"动作电位","definition":"...","category":"核心概念","page":35}}],"edges":[{{"source":"动作电位","target":"静息电位","relation_type":"prerequisite","description":"..."}}]}}
章节正文：
{chapter.content[:8000]}"""
        raw = self.llm.json_chat(system, user)
        if not raw or "nodes" not in raw:
            return None
        nodes: List[KnowledgeNode] = []
        name_to_id = {}
        for item in raw.get("nodes", [])[:18]:
            name = self._normalize_term(str(item.get("name", "")))
            if not self._term_ok(name):
                continue
            nid = safe_id("node", f"{textbook.textbook_id}:{chapter.chapter_id}:{name}")
            name_to_id[name] = nid
            definition = self._clean_definition(name, str(item.get("definition") or best_definition(name, chapter.content)))
            nodes.append(
                KnowledgeNode(
                    id=nid,
                    name=name,
                    definition=definition,
                    category=clean_line(str(item.get("category") or "核心概念")),
                    chapter=clean_line(chapter.title),
                    page=int(item.get("page") or chapter.page_start),
                    textbook_id=textbook.textbook_id,
                    textbook_title=textbook.title,
                    source=f"{textbook.title}, {chapter.title}, 第 {chapter.page_start} 页",
                    importance=0.75,
                )
            )
        edges: List[KnowledgeEdge] = []
        for e in raw.get("edges", [])[:30]:
            s, t = str(e.get("source", "")), str(e.get("target", ""))
            if s in name_to_id and t in name_to_id and e.get("relation_type") in {"prerequisite", "parallel", "contains", "applies_to"}:
                edges.append(
                    KnowledgeEdge(
                        source=name_to_id[s],
                        target=name_to_id[t],
                        relation_type=e.get("relation_type"),
                        description=str(e.get("description") or ""),
                    )
                )
        return nodes, edges

    def _extract_with_rules(self, textbook: Textbook, chapter) -> Tuple[List[KnowledgeNode], List[KnowledgeEdge]]:
        text = clean_text(chapter.content)
        candidates = self._candidate_terms(chapter.title, text)
        nodes: List[KnowledgeNode] = []
        for rank, term in enumerate(candidates[:14], 1):
            definition = self._clean_definition(term, best_definition(term, text))
            category = self._category(term, definition)
            nid = safe_id("node", f"{textbook.textbook_id}:{chapter.chapter_id}:{term}")
            nodes.append(
                KnowledgeNode(
                    id=nid,
                    name=term,
                    definition=definition,
                    category=category,
                    chapter=clean_line(chapter.title),
                    page=chapter.page_start,
                    textbook_id=textbook.textbook_id,
                    textbook_title=textbook.title,
                    source=f"{textbook.title}, {chapter.title}, 第 {chapter.page_start} 页",
                    importance=max(0.2, 1 - rank / 20),
                )
            )
        edges = self._rule_edges(nodes, chapter.title, text)
        return nodes, edges

    def _candidate_terms(self, title: str, text: str) -> List[str]:
        terms: List[str] = []
        text = clean_text(text)
        title_terms = self._normalize_term(re.sub(r"^(第.+章|第.+节)\s*", "", clean_line(title)).strip())
        if self._term_ok(title_terms):
            terms.append(title_terms)
        # Definitions: XXX 是/是指/称为 YYY.
        patterns = [
            r"([\u4e00-\u9fa5A-Za-z0-9（）()]{2,18})\s*(?:是指|是|称为|定义为)",
            r"(?:所谓|即)\s*([\u4e00-\u9fa5A-Za-z0-9（）()]{2,18})",
            r"([\u4e00-\u9fa5A-Za-z0-9（）()]{2,18})\s*(?:包括|分为|表现为)",
        ]
        for pat in patterns:
            for m in re.finditer(pat, text):
                term = self._normalize_term(m.group(1))
                if self._term_ok(term):
                    terms.append(term)
        # TF keyword fallback with jieba.
        try:
            import jieba.analyse

            tags = jieba.analyse.extract_tags(text[:12000], topK=35, withWeight=False)
            terms.extend([self._normalize_term(t) for t in tags if self._term_ok(self._normalize_term(t))])
        except Exception:
            pass
        # Boost medical-looking terms.
        for hint in MEDICAL_HINTS:
            context = 6 if len(hint) >= 2 else 3
            for m in re.finditer(rf"[\u4e00-\u9fa5A-Za-z0-9]{{0,{context}}}{hint}[\u4e00-\u9fa5A-Za-z0-9]{{0,{context}}}", text):
                term = m.group(0).strip()
                term = self._normalize_term(term)
                if self._term_ok(term):
                    terms.append(term)
        counts = Counter([t for t in terms if self._term_ok(t)])
        ordered = sorted(counts, key=lambda t: self._term_score(t, text, counts[t]), reverse=True)
        # De-duplicate substrings while keeping semantic richness.
        result: List[str] = []
        for t in ordered:
            if not any(t in r or r in t for r in result):
                result.append(t)
        return result[:20]

    @staticmethod
    def _normalize_term(term: str) -> str:
        term = clean_line(term)
        term = re.sub(r"^第[一二三四五六七八九十百千万零〇两\d]+[章节篇]\s*", "", term)
        term = re.sub(r"^(?:[一二三四五六七八九十]+|\d+)[、.．]\s*", "", term)
        term = re.sub(r"^中(?=(?:人型|牛型|鸟型)结核分枝杆菌)", "", term)
        term = re.sub(r"^生(?=抗中肾旁管激素)", "", term)
        term = re.sub(r"^无(?=抗中肾旁管激素)", "", term)
        term = re.sub(r"^种(?=神经内分泌细胞)", "", term)
        term = re.sub(r"^系(?=垂体神经内分泌瘤)", "", term)
        term = re.sub(r"^[的地得一是在和与及或其此该]+", "", term)
        for prefix in SALVAGE_PREFIXES:
            if term.startswith(prefix) and len(term) > len(prefix) + 1:
                term = term[len(prefix):]
                break
        term = re.sub(r"^[的地得一是在和与及或其此该]+", "", term)
        if term.startswith("致") and not term.startswith(("致病", "致癌")) and len(term) > 4:
            term = term[1:]
        if "主要" in term[1:]:
            term = term[: term.find("主要", 1)]
        relation_cut = re.search(r"(?:以[\u4e00-\u9fa5A-Za-z0-9（）()]{1,12}为(?:标志|界|界限|依据)?|按|依照|依据)", term)
        if relation_cut and relation_cut.start() > 0:
            term = term[: relation_cut.start()]
        term = re.split(
            r"(?:是指|定义为|又称|称为|是|以|可|又|则|并|即|由|把|将|被|通过|由于|导致|引起|进入|排出|注入|附着|覆盖|组成|包括|分为|表现为|根据|对于|作为|适用于|发现|决定)",
            term,
            maxsplit=1,
        )[0]
        term = re.sub(r"^.*(?:表达的|分泌的|产生的|诱导的|介导的)(?=[\u4e00-\u9fa5A-Za-z0-9]{2,12}$)", "", term)
        if len(term) > 5:
            term = re.split(r"(?:和|与|及|或)", term, maxsplit=1)[0]
        changed = True
        while changed:
            changed = False
            for suffix in TRIM_TRAILING_PHRASES:
                if term.endswith(suffix) and len(term) > len(suffix) + 1:
                    term = term[: -len(suffix)]
                    changed = True
                    break
        if term.endswith("等") and len(term) > 3:
            term = term[:-1]
        if re.search(r"[\u4e00-\u9fa5]", term):
            term = re.sub(r"(?<=[\u4e00-\u9fa5])[A-Za-z]{3,}$", "", term)
        term = re.sub(r"^[的地得一是在和与及或其此该]+", "", term)
        term = re.sub(r"(?:可以|主要|可|又|则|和|与|及|或|并|亦|它|其)+$", "", term)
        term = re.sub(r"[，。；：:、,.()（）\[\]【】《》<>]+$", "", term)
        return term.strip()

    def _term_ok(self, term: str) -> bool:
        term = self._normalize_term(term)
        lower_term = term.lower()
        if len(term) < 2 or len(term) > 18:
            return False
        if term in BAD_TERMS:
            return False
        if term in BAD_GENERIC_TERMS:
            return False
        if lower_term in ENGLISH_MEDICAL_TERMS:
            return True
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9+\-]{2,12}", term):
            return bool(re.fullmatch(r"[A-Z]{2,6}\d{0,2}|[A-Z]{1,4}[a-z]?\d{0,2}", term))
        if term.count("（") != term.count("）") or term.count("(") != term.count(")"):
            return False
        if term.startswith(BAD_START_PHRASES):
            return False
        if term[0] in "个们者入向至再故示要时指应验帮维测断学数":
            return False
        if term.startswith("型"):
            return False
        if term.endswith("蛋"):
            return False
        if term.startswith("有") and re.match(r"^有(?:调节|促进|抑制|维持|保护|吸收|分泌|排泄|增加|减少)", term):
            return False
        if term.endswith(BAD_TRAILING_PHRASES):
            return False
        if any(marker in term for marker in CLAUSE_MARKERS):
            return False
        if re.search(r"\d", term) and re.search(r"[\u4e00-\u9fa5]", term):
            return False
        if any(marker in term for marker in PUBLISHING_MARKERS):
            return False
        if re.search(r"(大学|学校|教育部|出版社|教材|第十轮|五年制|主编|副主编|主任)$", term):
            return False
        if re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", term) and not any(h in term for h in MEDICAL_HINTS) and term not in MEDICAL_SHORT_TERMS and not term.endswith(TERMISH_SUFFIXES):
            return False
        if any(marker in term for marker in NON_TERM_MARKERS):
            return False
        if any(marker in term for marker in PHRASE_MARKERS):
            return False
        if self._looks_like_sentence_fragment(term):
            return False
        if re.search(r"第[一二三四五六七八九十百千万零〇两\d]+[章节篇]", term):
            return False
        if re.search(r"(图|表)\s*\d", term, flags=re.IGNORECASE):
            return False
        if "的" in term and len(term) > 4 and not any(h in term for h in ["血压", "体温", "稳态", "反射", "电位", "免疫", "凝血", "肌"]):
            return False
        if term.count("的") >= 2:
            return False
        if term.endswith(("特点", "特征", "诊断方法", "诊断特征", "表现形式")) and len(term) > 5:
            return False
        if len(term) >= 6 and term[-1] in "应治认操疾流膨失妥常只微着" and not term.endswith(TERMISH_SUFFIXES):
            return False
        if len(term) > 8 and not any(h in term for h in MEDICAL_HINTS) and not term.endswith(TERMISH_SUFFIXES):
            return False
        if len(term) > 6 and term.endswith("发育"):
            return False
        if any(ch in term for ch in "\ufffd�\x00\b"):
            return False
        if re.search(r"[^\u4e00-\u9fa5A-Za-z0-9α-ωΑ-Ω（）()+\-/%]", term):
            return False
        if re.fullmatch(r"\d+", term):
            return False
        if re.fullmatch(r"[A-Za-z]{1,2}\d?", term):
            return term in {"O2", "CO2", "Na", "Ca", "K"}
        if term[0] in "的不而和与及或其此该为在对以由绍" or term[-1] in "的了与及或为在对以可并亦":
            return False
        if re.search(r"[和与及或而并将把被]$", term):
            return False
        if term[-1] in "则又不上":
            return False
        if len(term) == 2 and not any(h in term for h in MEDICAL_HINTS) and term not in MEDICAL_SHORT_TERMS:
            return False
        return True

    @staticmethod
    def _clean_definition(term: str, definition: str) -> str:
        text = clean_text(definition)
        text = re.sub(r"另一类是", "", text)
        text = re.sub(r"另一类", "", text)
        if any(phrase in text for phrase in BAD_DEFINITION_PHRASES):
            parts = re.split(r"(?<=[。！？；;])\s*|\n+", text)
            kept = [part.strip() for part in parts if part.strip() and not any(phrase in part for phrase in BAD_DEFINITION_PHRASES)]
            text = " ".join(kept).strip() or text
            for phrase in BAD_DEFINITION_PHRASES:
                idx = text.find(phrase)
                if idx >= 0:
                    text = text[:idx].rstrip(" ，,；;。")
        text = re.sub(r"\s+", " ", text).strip()
        return text[:220] or clean_line(term)

    @staticmethod
    def _looks_like_sentence_fragment(term: str) -> bool:
        if not term:
            return True
        if term[0] in "的不而和与及或其此该这为在对以由从按将把被可并而但若如当使则都也还于绍因时指应等虽期验帮维测断学数":
            return True
        if term.startswith(BAD_START_PHRASES) or term[0] in "个们者入向至再故示要":
            return True
        if term[-1] in "的了与及或为在对以于中和或被将把成后前内外者时可并亦" and not term.endswith(TERMISH_SUFFIXES):
            return True
        verb_markers = ("导致", "引起", "进入", "排出", "注入", "分泌到", "作用于", "来源于", "发育为", "发育成", "分化为")
        if any(v in term for v in verb_markers):
            return True
        if any(v in term for v in ("形成", "发生", "出现", "进行")) and not term.endswith(TERMISH_SUFFIXES):
            return True
        if len(term) >= 6 and any(v in term for v in ("是", "有", "无", "能", "使", "被", "将")) and not term.endswith(TERMISH_SUFFIXES):
            return True
        return False

    @staticmethod
    def _chapter_is_extractable(title: str, content: str) -> bool:
        clean = clean_text(content)
        if len(clean) < 500:
            return False
        if looks_like_toc_page(content):
            return False
        head = clean[:1800]
        unknown_title = any(flag in title for flag in ["未识别", "未命名", "自动分段"])
        publishing_hits = sum(1 for marker in PUBLISHING_MARKERS if marker in head)
        if unknown_title and publishing_hits >= 2:
            return False
        if publishing_hits >= 4 and not any(h in head for h in MEDICAL_HINTS):
            return False
        if "本章数字资源" not in head and sum(marker in head for marker in ["推荐阅读", "中英文名词对照索引", "附录", "数字特色", "AR 模型"]) >= 2:
            return False
        return True

    @staticmethod
    def _term_score(term: str, text: str, count: int) -> tuple[float, int, int, int]:
        hint = int(any(h in term for h in MEDICAL_HINTS) or term in MEDICAL_SHORT_TERMS)
        definition_hit = int(bool(re.search(rf"{re.escape(term)}\s*(?:是指|是|称为|定义为|包括|分为)", text)))
        length_bonus = min(len(term), 8)
        return (count + hint * 2 + definition_hit * 3, hint, definition_hit, length_bonus)

    def _category(self, term: str, definition: str) -> str:
        s = term + definition
        if any(k in s for k in ["机制", "过程", "步骤", "通路", "反射"]):
            return "生理机制"
        if any(k in s for k in ["方法", "测定", "评价", "指标", "ECG", "心电图"]):
            return "方法/指标"
        if any(k in s for k in ["应用", "临床", "治疗", "诊断"]):
            return "应用场景"
        return "核心概念"

    def _rule_edges(self, nodes: List[KnowledgeNode], chapter_title: str, text: str) -> List[KnowledgeEdge]:
        edges: List[KnowledgeEdge] = []
        if not nodes:
            return edges
        root = nodes[0]
        for n in nodes[1:8]:
            edges.append(
                KnowledgeEdge(
                    source=root.id,
                    target=n.id,
                    relation_type="contains",
                    description=f"“{chapter_title}”中的核心主题“{root.name}”包含或统摄“{n.name}”。",
                    weight=0.8,
                )
            )
        for a, b in itertools.combinations(nodes[1:7], 2):
            if a.category == b.category:
                edges.append(
                    KnowledgeEdge(
                        source=a.id,
                        target=b.id,
                        relation_type="parallel",
                        description=f"“{a.name}”与“{b.name}”均属于{a.category}层级。",
                        weight=0.45,
                    )
                )
        for n in nodes:
            if any(k in n.definition for k in ["临床", "治疗", "诊断", "应用", "疾病"]):
                edges.append(
                    KnowledgeEdge(
                        source=n.id,
                        target=root.id,
                        relation_type="applies_to",
                        description=f"“{n.name}”可用于解释“{root.name}”相关临床或应用场景。",
                        weight=0.55,
                    )
                )
        return edges[:35]

    def _dedupe_edges(self, edges: List[KnowledgeEdge]) -> List[KnowledgeEdge]:
        out = []
        seen = set()
        for e in edges:
            key = (e.source, e.target, e.relation_type)
            if e.source != e.target and key not in seen:
                seen.add(key)
                out.append(e)
        return out
