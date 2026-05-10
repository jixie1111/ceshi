from __future__ import annotations

import re
from typing import Iterable, List

CN_NUM = "一二三四五六七八九十百千万零〇两"

REPLACEMENT_RE = re.compile(r"[\ufffd�]+")
CONTROL_RE = re.compile(r"[\x01-\x08\x0b\x0e-\x1f\x7f]")
TOC_LEADER_RE = re.compile(r"((?:[.\u2026·•\-—_]\s*){4,}|[\ufffd�]{3,})")
TOC_LINE_RE = re.compile(r"^\s*(第[一二三四五六七八九十百千万零〇两\d]+[章节部篇].*|[一二三四五六七八九十]+[、.].*)\s+\d+\s*$")

STOPWORDS = {
    "以及", "进行", "可以", "通过", "由于", "因此", "主要", "包括", "具有", "作用", "功能", "过程",
    "细胞", "系统", "而不", "而非", "不同", "但是", "如果", "或者", "因为", "所以", "其中", "本章",
    "本节", "教材", "医学", "教学", "修订", "本次", "尤其", "可能", "发现", "形成", "研究", "患者",
    "正常", "异常", "有关", "相关", "一种", "一个", "这些", "这种", "同时", "一般", "发生", "发展",
}


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ").replace("\ufeff", "")
    text = CONTROL_RE.sub(" ", text)
    text = REPLACEMENT_RE.sub(" ", text)
    text = re.sub(r"[\t\r\f]+", " ", text)
    text = re.sub(r"[ \u3000]{2,}", " ", text)
    # Remove common page footer patterns produced by textbooks/PDFs.
    text = re.sub(r"第\s*\d+\s*页\s*/\s*共\s*\d+\s*页", "", text)
    lines = []
    for line in text.splitlines():
        line = clean_line(line)
        if line and not is_noise_line(line):
            lines.append(line)
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_line(line: str) -> str:
    line = line.replace("\x00", " ").replace("\ufeff", "")
    line = CONTROL_RE.sub(" ", line)
    line = REPLACEMENT_RE.sub(" ", line)
    line = TOC_LEADER_RE.sub(" ", line)
    line = re.sub(r"[ \u3000]{2,}", " ", line)
    return line.strip()


def is_noise_line(line: str) -> bool:
    line = clean_line(line)
    if not line:
        return True
    if len(line) <= 2 and not re.search(r"[\u4e00-\u9fa5A-Za-z]", line):
        return True
    if TOC_LINE_RE.match(line):
        return True
    if len(re.findall(r"\d", line)) > 10 and len(line) < 40:
        return True
    return False


def looks_like_toc_page(text: str) -> bool:
    raw_lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not raw_lines:
        return False
    leader_lines = sum(1 for line in raw_lines if TOC_LEADER_RE.search(line) or TOC_LINE_RE.match(clean_line(line)))
    chapter_lines = sum(1 for line in raw_lines if re.match(r"^\s*第[一二三四五六七八九十百千万零〇两\d]+[章部篇]", clean_line(line)))
    section_lines = sum(1 for line in raw_lines if re.match(r"^\s*第[一二三四五六七八九十百千万零〇两\d]+节", clean_line(line)))
    has_toc_word = any("目录" in clean_line(line) for line in raw_lines[:8])
    has_back_matter = any(any(word in clean_line(line) for word in ["推荐阅读", "中英文名词对照索引", "附录", "数字特色"]) for line in raw_lines[:14])
    punctuation_count = len(re.findall(r"[，。；：、]", text))
    if len(text) > 1200 and punctuation_count > 18 and not has_toc_word and leader_lines < 4:
        return False
    return (
        has_toc_word
        or leader_lines >= 4
        or chapter_lines >= 3
        or (chapter_lines >= 2 and has_back_matter)
        or (chapter_lines + section_lines >= 5 and leader_lines >= 1)
    )


def normalize_key(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[\s\-_/（）()《》〈〉\[\]【】,:：;；。,.，·•]+", "", text)
    synonyms = {
        "leukocyte": "白细胞",
        "whitebloodcell": "白细胞",
        "whitebloodcells": "白细胞",
        "炎症反应": "炎症",
        "actionpotential": "动作电位",
        "restingpotential": "静息电位",
        "内环境稳态": "稳态",
    }
    return synonyms.get(text, text)


def split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[。！？!?；;])\s*", text)
    return [p.strip() for p in parts if len(p.strip()) > 8]


def cn_tokenize(text: str) -> List[str]:
    try:
        import jieba

        tokens = [t.strip() for t in jieba.lcut(text) if len(t.strip()) > 1]
    except Exception:
        tokens = re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]{2,}", text)
    return [t for t in tokens if t not in STOPWORDS]


def best_definition(term: str, text: str, fallback_len: int = 140) -> str:
    text = clean_text(text)
    sentences = [s for s in split_sentences(text) if not is_noise_line(s)]
    for s in sentences:
        if term in s and any(k in s for k in ["是", "是指", "称为", "定义为", "表现为", "包括"]):
            return s[:220]
    for s in sentences:
        if term in s:
            return s[:220]
    return text[:fallback_len]


def safe_id(prefix: str, value: str, length: int = 12) -> str:
    import hashlib

    digest = hashlib.sha1(value.encode("utf-8", errors="ignore")).hexdigest()[:length]
    return f"{prefix}_{digest}"


def sliding_window(text: str, size: int = 700, overlap: int = 80) -> Iterable[tuple[int, int, str]]:
    clean = clean_text(text)
    if not clean:
        return
    start = 0
    n = len(clean)
    while start < n:
        end = min(start + size, n)
        # Move to punctuation where possible to avoid chopping definitions.
        if end < n:
            punct = max(clean.rfind("。", start, end), clean.rfind("；", start, end), clean.rfind("\n", start, end))
            if punct > start + int(size * 0.65):
                end = punct + 1
        yield start, end, clean[start:end]
        if end >= n:
            break
        start = max(0, end - overlap)
