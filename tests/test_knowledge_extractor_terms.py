from src.backend.app.services.knowledge_extractor import KnowledgeExtractor


def test_reject_sentence_fragments_and_section_labels():
    extractor = KnowledgeExtractor()

    rejected = [
        "主要症状",
        "我国常被",
        "并分泌到血液循环中",
        "这种高度变异引起的免疫逃逸作用",
        "组织细胞接受刺激后产生动作电位的现象",
        "炎症时易发生水肿",
        "可分泌雄激素",
        "成果揭示了雌激素抑制心血管损",
        "解剖学",
        "医学教育",
        "医科大学",
        "第十轮",
        "部分肌可附着于筋膜",
        "解剖肌要注意修洁出",
        "探查浆膜腔",
        "中肿瘤组织芯片又",
        "这部分内容",
        "原位杂交则",
        "开皮肤和切断肌",
        "未识别章节",
        "扫描图片",
        "推荐阅读",
        "第八章",
    ]

    for term in rejected:
        assert extractor._term_ok(term) is False


def test_keep_real_medical_concepts():
    extractor = KnowledgeExtractor()

    accepted = [
        "动作电位",
        "静息电位",
        "压力感受性反射",
        "抗原",
        "抗体",
        "休克",
        "炎症反应",
        "肾小球滤过率",
        "精子发生",
        "外分泌腺",
        "网膜孔",
        "leukocyte",
    ]

    for term in accepted:
        assert extractor._term_ok(term) is True
