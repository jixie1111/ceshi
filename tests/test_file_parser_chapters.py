from src.backend.app.models.schemas import Chapter
from src.backend.app.services.file_parser import TextbookParser


def test_infers_split_title_after_chapter_prefix():
    content = "\n".join(
        [
            "第七章 上",
            "肢",
            "本章数字资源",
            "第一节 | 概 述",
            "上肢upper limb 连于胸廓外上部。",
        ]
    )

    assert TextbookParser._infer_chapter_title_from_content(content) == "第七章 上肢"


def test_infers_title_when_resource_line_comes_first():
    content = "\n".join(
        [
            "本章数字资源",
            "第十三章  休",
            "克",
            "休克（shock）是指机体在严重失血、失液、感染、创伤等强烈致病因子的作用下。",
        ]
    )

    assert TextbookParser._infer_chapter_title_from_content(content) == "第十三章 休克"


def test_infers_multiline_titles_before_resource_marker():
    content = "\n".join(
        [
            "第八章",
            "细菌感染的检查方法与防治",
            "原则",
            "本章数字资源",
            "学习目标",
            "1. 描述病原学诊断的定义及其医学意义。",
        ]
    )

    assert TextbookParser._infer_chapter_title_from_content(content) == "第八章 细菌感染的检查方法与防治原则"


def test_does_not_treat_inline_chapter_reference_as_title():
    content = "\n".join(
        [
            "达到阻止病原体传播和扩散的目的。如针",
            "对肺鼠疫的严格隔离、",
            "2. 消毒 参见第三章。",
            "三",
            "保护易感人群",
        ]
    )

    assert TextbookParser._infer_chapter_title_from_content(content) is None


def test_keeps_full_body_title_instead_of_catalog_row():
    catalog = Chapter(
        chapter_id="ch_001",
        title="未识别章节",
        page_start=1,
        page_end=2,
        content="第八章 下肢 243\n推荐阅读 272\n中英文名词对照索引 273\nAR 模型1 颅骨 9",
        char_count=60,
    )
    real = Chapter(
        chapter_id="ch_002",
        title="第八章",
        page_start=243,
        page_end=270,
        content="第八章\n下\n肢\n本章数字资源\n第一节 | 概 述\n下肢lower limb 除具有行走和运动的功能外。",
        char_count=70,
    )

    parsed = TextbookParser._postprocess_chapters(TextbookParser.__new__(TextbookParser), [catalog, real])

    assert [chapter.title for chapter in parsed] == ["第八章 下肢"]
