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
        "型神经元主要",
        "中段发育为气管",
        "它们不断分泌基质",
        "有调节体温",
        "细胞是主要的免疫细胞",
        "本章目标测试",
        "前者发育为舌根",
        "者分化为中枢神经系统",
        "椎外静脉丛收集椎体",
        "碱性颗粒属于分泌颗粒",
        "处仔细寻认右淋巴导管",
        "间隙借镰状韧带",
        "周末开始血液循环",
        "胸腰筋膜后层覆于竖脊",
        "声门下腔淋巴管穿环甲膜",
        "牙蕾发育增大",
        "染色法染血涂片",
        "神经上皮外包一层",
        "落的新陈代谢过程",
        "科学为人体发育学",
        "噬细胞等细胞分泌",
        "胞分泌雄激素",
        "右侧自右胸锁关节",
        "肾旁管进一步发育",
        "纵行切开胸腰筋膜后层",
        "分泌物质基本相同",
        "排泄机体代谢产物",
        "肿瘤学等临床学科",
        "胸背区静脉经肋间",
        "淋巴中偶见单核细",
        "环甲关节后方进",
        "月开始行使内分泌",
        "血细胞陆续衰老死亡",
        "首先转移至该淋巴",
        "浅筋膜近腹股沟处",
    ]

    for term in rejected:
        assert extractor._term_ok(term) is False


def test_reject_round2_surviving_fragments():
    extractor = KnowledgeExtractor()

    rejected = [
        "骨表面供骨骼肌",
        "韧带等韧性结构",
        "神经嵴细胞首先分",
        "神经嵴细胞向两侧",
        "运动神经末梢释放",
        "儿童体格发育程度",
        "调节许多神经肽",
        "原体逃避宿主免疫反应的机制",
        "幼儿免疫系统发育尚不完善",
        "刻获得适应性免疫的措施",
        "脾等非神经组织中再次增",
        "胶体金免疫层析技术等检",
        "后再穿就不会感染疾病",
        "力减弱而保留免疫原性",
        "肠道神经细胞受体作用",
        "黏膜上皮细胞受体结合",
        "各种免疫细胞释放的大",
        "别肺炎支原体感染病人",
        "物质转运中起重要作用",
        "蛋白质转运入宿主胞质",
        "细胞表面相应受体结合",
        "细胞不受相应受体限制",
        "子宫压迫髂总静脉",
        "某种激素分泌",
        "缺氧发生坏死",
        "严格落实计划免疫",
        "量巧克力酱样坏死物质",
        "破坏人体微生态就",
        "理神经反射阳性",
        "病理神经反射阳",
        "保持了酸碱的稳态",
        "静脉血氧含量差减",
        "静脉血分流入动脉",
        "静脉血氧含量差小",
        "认知障碍尤其",
    ]

    for term in rejected:
        assert extractor._term_ok(extractor._normalize_term(term)) is False


def test_repair_leading_relation_fragments():
    extractor = KnowledgeExtractor()

    repaired = {
        "根据抗原": "抗原",
        "根据神经胶质细胞": "神经胶质细胞",
        "称为神经内分泌细胞": "神经内分泌细胞",
        "化为成神经细胞": "成神经细胞",
        "分化为骨骼肌": "骨骼肌",
        "生抗中肾旁管激素": "抗中肾旁管激素",
        "释放顶体酶": "顶体酶",
        "又称腰方肌筋膜quadra": "腰方肌筋膜",
        "共同构成咽淋巴环": "咽淋巴环",
        "类固醇激素分泌细胞仅": "类固醇激素分泌细胞",
        "增厚形成腰肋韧带": "腰肋韧带",
        "种神经内分泌细胞": "神经内分泌细胞",
        "加重微循环灌流障碍": "微循环灌流障碍",
    }

    for raw, normalized in repaired.items():
        assert extractor._normalize_term(raw) == normalized
        assert extractor._term_ok(normalized) is True


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
        "神经胶质细胞",
        "神经内分泌细胞",
        "成神经细胞",
        "顶体酶",
        "抗中肾旁管激素",
        "leukocyte",
    ]

    for term in accepted:
        assert extractor._term_ok(term) is True


def test_reject_round1_sampled_sentence_fragments():
    extractor = KnowledgeExtractor()

    rejected = [
        "左膈结肠韧带发育良好",
        "管径较伴行静脉小",
        "肿瘤转移时易受累",
        "消化管腔分泌免疫球蛋白作为应",
        "几种不同组织发育分化",
        "神经管头端迅速膨",
        "测试提示双耳分泌性中耳炎",
        "时启动体温调节机制",
        "断出现双下肢水肿",
        "支配肾动脉（尤其",
        "Ivanovski）发现了烟草花叶病",
        "抗毒素的动物免疫血清成功地治",
        "验适用于人群免疫情况的调查",
        "靶细胞表面受体结合决定病毒",
        "震颤等中枢神经系统症状为主",
        "激机体的体液免疫",
        "胃肠道间质瘤的免疫组织化学的诊断特征",
        "数起源于外周型神经纤维瘤（尤其",
        "时毛细淋巴管吸收过多",
        "指体循环动脉血压持续",
        "宫平滑肌肉瘤从开始",
        "器官伤残已不再只",
        "体外细胞培养分离到无形体",
        "主要的血清免疫学诊断方法",
        "机械通气等侵袭性操",
        "损伤机体的免疫系统",
        "感染病不仅威胁着",
        "呼吸衰竭根据动脉血气特点",
        "等抑制性神经递质增多",
        "虽然酸碱平衡紊乱常",
        "初期肺通气反应增强",
        "脑内神经递质平衡失",
    ]

    for term in rejected:
        assert extractor._term_ok(term) is False


def test_keep_round1_sampled_real_terms():
    extractor = KnowledgeExtractor()

    accepted = [
        "左锁骨下动脉",
        "膝上内侧动脉",
        "内在光敏感视神经节细胞",
        "胸腺基质淋巴细胞生成素",
        "弥散神经内分泌系统",
        "雄激素不敏感综合征",
        "绒毛膜促性腺激素",
        "肺泡通气血流比例失调",
        "活化部分凝血活酶时间",
        "弥散性血管内凝血",
        "幽门螺杆菌粪便抗原检测",
        "半乳甘露聚糖（GM）抗原",
    ]

    for term in accepted:
        assert extractor._term_ok(term) is True


def test_reject_round3_high_precision_noise():
    extractor = KnowledgeExtractor()

    rejected = [
        "性污染的放射免疫测定",
        "辅助受体协助病毒包膜",
        "采用免疫组织化学方法",
        "直接免疫荧光法检测",
        "人体的抗感染免疫机制",
        "素抗体主要针对霍乱",
        "人在出生时胃肠道",
        "共代谢",
        "共发育",
        "诱发免疫应答损伤机体",
        "合成称为合成代谢",
        "过程称为分解代谢",
        "调节免疫等机制达",
        "供体移植入受体阴道",
        "疾病存在异质性",
        "具体的反射途径",
        "感染",
        "损伤",
        "调节",
        "分泌",
        "转运",
        "代谢",
        "吸收",
        "血液",
        "首次证明动物疾病",
        "现多种特异性抗体",
        "到多种特异性抗体",
        "早期播散性感染多",
        "起急性肠道内感染",
        "口咽部定植菌吸入",
        "受体阴道微生物群",
        "最适酸碱度为pH",
        "病理改变均为炎症",
        "肌肉丧失神经支配",
    ]

    for term in rejected:
        assert extractor._term_ok(term) is False


def test_keep_round3_high_precision_medical_terms():
    extractor = KnowledgeExtractor()

    accepted = [
        "幽门螺杆菌粪便抗原检测",
        "血清特异性抗体检测",
        "人类免疫缺陷病毒",
        "大细胞神经内分泌癌",
        "垂体神经内分泌瘤",
        "人工主动免疫",
        "适应性免疫",
        "链球菌毒性休克综合征",
        "花生四烯酸代谢产物",
        "糖皮质激素分泌不足",
        "肾小球滤过面积减少",
        "肾小球滤过膜通透性改变",
        "甲型肝炎灭活疫苗",
        "洋葱伯克霍尔德菌",
        "中枢神经系统感染",
        "神经氨酸酶抑制剂",
        "免疫病理损伤机制",
    ]

    for term in accepted:
        assert extractor._term_ok(extractor._normalize_term(term)) is True


def test_repair_user_reported_trailing_fragments():
    extractor = KnowledgeExtractor()

    repaired = {
        "脊柱区的肌可": "脊柱区的肌",
        "肛门括约肌可": "肛门括约肌",
        "上颌动脉以翼外肌为标志可": "上颌动脉",
        "嗜色细胞又": "嗜色细胞",
        "外分泌腺按形态可": "外分泌腺",
        "肌组织又可": "肌组织",
        "细胞黏附分子又": "细胞黏附分子",
    }

    for raw, normalized in repaired.items():
        assert extractor._normalize_term(raw) == normalized
        assert extractor._term_ok(normalized) is True


def test_reject_user_reported_sentence_residue():
    extractor = KnowledgeExtractor()

    rejected = [
        "肌前内侧主要",
        "脊肌可",
        "则应注意观测它",
        "则应注意观察它",
        "另一类",
        "人体可",
        "组织学上皮肤可",
        "按排列方式可",
        "功能主要",
        "受精的过程可",
        "先天畸形主要",
        "儿童体格发育程度则",
        "防主要",
        "疫主要",
        "大致可",
        "用的主要",
        "等基因序列可",
        "这种稳态主要",
        "机制主要",
    ]

    for term in rejected:
        assert extractor._term_ok(extractor._normalize_term(term)) is False


def test_reject_user_reported_round4_fragments():
    extractor = KnowledgeExtractor()

    rejected = [
        "本病例中肿瘤",
        "加快重吸收水",
        "足长括弧内数据",
        "感染者几乎全部",
    ]

    for term in rejected:
        assert extractor._term_ok(extractor._normalize_term(term)) is False


def test_keep_round4_nearby_real_terms():
    extractor = KnowledgeExtractor()

    accepted = [
        "肿瘤",
        "重吸收",
        "水重吸收",
        "肾小管重吸收",
        "中枢神经系统感染",
    ]

    for term in accepted:
        assert extractor._term_ok(extractor._normalize_term(term)) is True
