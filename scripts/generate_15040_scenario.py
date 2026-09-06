# -*- coding: utf-8 -*-
"""Generate importable scenario gold set for course 15040 from local PDFs."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from pypdf import PdfReader

SRC = Path(r"d:\Download\15040习近平新时代")
OUT_DIR = Path(r"d:\projects\RAG\data\scenarios")
OUT_DIR.mkdir(parents=True, exist_ok=True)

DOCS = {
    "速记宝典": "15040速记宝典.pdf",
    "精讲": "15040精讲.pdf",
    "课件": "15040课件.pdf",
}


def lab_pdf_text(path: Path) -> str:
    """Match backend engine.doc_extract._pdf_text joining."""
    reader = PdfReader(str(path))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n\n".join(part for part in pages if part)


corpus = {key: lab_pdf_text(SRC / name) for key, name in DOCS.items()}
for key, text in corpus.items():
    print(f"{key}: {len(text)} chars")


def _collapse_map(text: str) -> tuple[str, list[int]]:
    """Return whitespace-stripped text and index map back into original."""
    collapsed: list[str] = []
    index_map: list[int] = []
    for i, ch in enumerate(text):
        if ch.isspace():
            continue
        collapsed.append(ch)
        index_map.append(i)
    return "".join(collapsed), index_map


_collapsed_cache = {key: _collapse_map(text) for key, text in corpus.items()}


def find_quote(
    preferred: list[str],
    *needles: str,
    min_len: int = 8,
    max_len: int = 120,
) -> tuple[str, str] | None:
    """Find a gold quote; tolerate PDF mid-sentence newlines via collapsed match."""
    for key in preferred:
        text = corpus[key]
        collapsed, index_map = _collapsed_cache[key]
        for needle in needles:
            needle = needle.strip()
            if not needle:
                continue
            compact = "".join(ch for ch in needle if not ch.isspace())
            if len(compact) < min_len:
                continue
            # Prefer exact substring when PDF already has continuous text.
            if needle in text and len(needle) <= max_len:
                return DOCS[key], needle
            pos = collapsed.find(compact)
            if pos < 0:
                # Try progressive compact prefixes (longest first).
                found = None
                for n in range(min(len(compact), max_len), min_len - 1, -1):
                    frag = compact[:n]
                    p = collapsed.find(frag)
                    if p >= 0:
                        found = (p, n)
                        break
                if not found:
                    continue
                pos, n = found
                compact = compact[:n]
            start = index_map[pos]
            end = index_map[pos + len(compact) - 1] + 1
            quote = text[start:end]
            # Trim to max_len on original (may include newlines); keep readable.
            if len(quote) > max_len:
                # Cut on collapsed length instead.
                end = index_map[pos + min(len(compact), max_len) - 1] + 1
                quote = text[start:end]
            quote = quote.strip()
            if len("".join(ch for ch in quote if not ch.isspace())) >= min_len and quote in text:
                return DOCS[key], quote
    return None


raw_items: list[dict] = [
    {
        "question": "中国特色社会主义最本质的特征是什么？",
        "expected": "中国共产党领导。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": ["中国特色社会主义最本质的特征是中国共产党领导"],
        "chapter": "导论/第三章",
        "type": "选择/识记",
    },
    {
        "question": "中国特色社会主义制度的最大优势是什么？",
        "expected": "中国共产党领导。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": ["中国特色社会主义制度的最大优势是中国共产党领导"],
        "chapter": "导论/第三章",
        "type": "选择/识记",
    },
    {
        "question": "中国共产党在党和国家事业中处于什么地位？",
        "expected": "中国共产党是最高政治领导力量。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": ["中国共产党是最高政治领导力量"],
        "chapter": "导论",
        "type": "选择/识记",
    },
    {
        "question": "新时代我国社会主要矛盾是什么？",
        "expected": "人民日益增长的美好生活需要和不平衡不充分的发展之间的矛盾。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "人民日益增长的美好生活需要和不平衡不充分的发展之",
            "人民日益增长的美好生活需要和不平衡不充分的发展之间的矛盾",
        ],
        "chapter": "第一章",
        "type": "选择/识记",
    },
    {
        "question": "中国特色社会主义事业的总体布局和战略布局分别是什么？",
        "expected": "总体布局是五位一体；战略布局是四个全面（全面建设社会主义现代化国家、全面深化改革、全面依法治国、全面从严治党）。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "经济建设、政治建设、文化建设、社会建设、生态",
            "全面建设社会主义现代化国家、全面深化改革、全面依法治",
        ],
        "chapter": "导论",
        "type": "简答",
    },
    {
        "question": "全面深化改革的总目标是什么？",
        "expected": "完善和发展中国特色社会主义制度、推进国家治理体系和治理能力现代化。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "全面深化改革总目标是完善和发展中国特色社会主义制度、推进国家治理体系和治理",
            "完善和发展中国特色社会主义制度、推进国家治理体系和治理能力现代化",
        ],
        "chapter": "第五章",
        "type": "选择/识记",
    },
    {
        "question": "全面推进依法治国的总目标是什么？",
        "expected": "建设中国特色社会主义法治体系、建设社会主义法治国家。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "全面推进依法治国总目标是建设中国特色社会主义法治体系、建设社会主义法治国家",
            "建设中国特色社会主义法治体系、建设社会主义法治国家",
        ],
        "chapter": "第九章",
        "type": "选择/识记",
    },
    {
        "question": "党在新时代的强军目标是什么？",
        "expected": "建设一支听党指挥、能打胜仗、作风优良的人民军队，把人民军队建设成为世界一流军队。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "听党指挥、能打胜仗、作风优良的人民军队，把人",
            "建设一支听党指挥、能打胜仗、作风优良的人民军队",
            "把人民军队建设成为世界一流军队",
        ],
        "chapter": "第十四章",
        "type": "简答",
    },
    {
        "question": "在强军目标中，听党指挥、能打胜仗、作风优良分别对应什么定位？",
        "expected": "听党指挥是灵魂，能打胜仗是核心，作风优良是保证。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "听党指挥是灵魂，决定军队建设的政治方向",
            "能打胜仗是核心，反映军队的根本职能",
            "作风优良是保证，关系军队的性质、宗旨、本色",
        ],
        "chapter": "第十四章",
        "type": "选择/识记",
    },
    {
        "question": "构建新发展格局的基本内涵是什么？",
        "expected": "以国内大循环为主体、国内国际双循环相互促进。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "以国内大循环为主体、国内国际双循环相互促进的新发展格局",
            "构建以国内大循环为主体、国内国际双循环相互促进",
        ],
        "chapter": "第六章",
        "type": "选择/识记",
    },
    {
        "question": "为什么说构建新发展格局是“先手棋”而不是被迫之举？",
        "expected": "是把握未来发展主动权的先手棋，不是被迫之举和权宜之计；是开放的国内国际双循环，不是封闭的国内单循环；是以全国统一大市场基础上的国内大循环为主体。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "构建新发展格局是把握未来发展主动权的先手棋，不是被迫之举和权宜之计",
            "构建新发展格局是开放的国内国际双循环，不是封闭的国内单循环",
            "以全国统一大市场基础上的国内大循环为主体",
        ],
        "chapter": "第六章",
        "type": "简答",
    },
    {
        "question": "中国梦的本质是什么？",
        "expected": "国家富强、民族振兴、人民幸福。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "实现中华民族伟大复兴中国梦的本质是国家富强、民族振兴、人民幸福",
            "国家富强、民族振兴、人民幸福",
        ],
        "chapter": "第二章",
        "type": "选择/识记",
    },
    {
        "question": "习近平何时首次提出“中国梦”？",
        "expected": "2012年11月参观《复兴之路》展览时。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "习近平在 2012 年 11 月参观《复兴之路》展览时首次提出“中国梦”",
            "参观《复兴之路》展览时首次提出“中国梦”",
        ],
        "chapter": "第二章",
        "type": "选择/识记",
    },
    {
        "question": "中国式现代化有哪些中国特色？",
        "expected": "人口规模巨大；全体人民共同富裕；物质文明和精神文明相协调；人与自然和谐共生；走和平发展道路。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "中国式现代化是人口规模巨大的现代化",
            "中国式现代化是全体人民共同富裕的现代化",
            "中国式现代化是物质文明和精神文明相协调的现代化",
            "中国式现代化是人与自然和谐共生的现代化",
            "中国式现代化是走和平发展道路的现代化",
        ],
        "chapter": "第二章",
        "type": "论述/简答",
    },
    {
        "question": "全面建成社会主义现代化强国总的战略安排（两步走）是什么？",
        "expected": "2020—2035年基本实现社会主义现代化；2035年到本世纪中叶建成社会主义现代化强国。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "2020 年到 2035 年基本实现社会主义现代化",
            "2035 年到本世纪中叶把我国建成富强",
        ],
        "chapter": "第二章",
        "type": "简答",
    },
    {
        "question": "人民立场为什么重要？",
        "expected": "人民立场是中国共产党的根本政治立场，是我们党区别于其他政党的显著标志。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "人民立场是中国共产党的根本政治立场，是我们党区别于其他政党的显著标志",
            "人民立场是中国共产党的根本政治立场",
        ],
        "chapter": "第四章",
        "type": "选择/识记",
    },
    {
        "question": "我们党的最大政治优势是什么？执政后的最大危险是什么？",
        "expected": "最大政治优势是密切联系群众；最大危险是脱离群众。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "我们党的最大政治优势是密",
            "党执政后的最大危险是脱离群众",
        ],
        "chapter": "第四章",
        "type": "选择/易混",
    },
    {
        "question": "党的群众路线的内涵是什么？它在党的工作中处于什么地位？",
        "expected": "群众路线是党的生命线和根本工作路线；坚持一切为了群众、一切依靠群众，从群众中来、到群众中去。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "群众路线是我们党的生命线和根本工作路线",
            "坚持一切为了群众、一切依靠群众，从群众中来到群众中去",
            "没有调查就没有发言权，就没有决策权",
        ],
        "chapter": "第四章",
        "type": "简答",
    },
    {
        "question": "为什么说共同富裕既是本质要求也是重大政治问题？",
        "expected": "共同富裕是中国特色社会主义的本质要求、中国式现代化的重要特征；实现共同富裕不仅是经济问题，而且是关系党的执政基础的重大政治问题。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "共同富裕是中国特色社会主义的本质要求，是中国式现代化的重要特征",
            "实现共同富裕不仅是经济问题，而且是关系党的执政基础的重大政治问题",
        ],
        "chapter": "第四章",
        "type": "简答",
    },
    {
        "question": "高质量发展在全面建设社会主义现代化国家中处于什么地位？",
        "expected": "是新时代经济社会发展的鲜明主题，是全面建设社会主义现代化国家的首要任务。",
        "preferred": ["速记宝典", "精讲"],
            "quotes": [
            "高质量发展是新时代我国经济社会发展的鲜明主题，是全面建设社会主义现代化国家",
            "全面建设社会主义现代化国家的首要任务",
            "鲜明主题",
        ],
        "chapter": "第六章",
        "type": "选择/识记",
    },
    {
        "question": "新发展理念中，创新、协调、绿色、开放、共享分别解决什么问题？",
        "expected": "创新→动力；协调→不平衡；绿色→人与自然和谐共生；开放→内外联动；共享→社会公平正义。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "解决发展动力问题",
            "解决发展不平衡问题",
            "解决社会公平正义问题",
            "创新 、协调、绿色、开放、共享的新发展理念",
            "创新、协调、绿色、开放、共享的新发展理念",
        ],
        "chapter": "第六章",
        "type": "简答",
    },
    {
        "question": "创新在我国现代化建设全局中处于什么地位？",
        "expected": "必须坚持创新在我国现代化建设全局中的核心地位；创新是引领发展的第一动力。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "引领发展的第一动力",
            "创新在我国现代化建设全局中的核心地位",
            "必须坚持创新在我国现代化建",
        ],
        "chapter": "第六章",
        "type": "选择/识记",
    },
    {
        "question": "教育、科技、人才三者分别坚持什么方针？",
        "expected": "教育优先发展、科技自立自强、人才引领驱动。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "坚持教育优先发展、科技自立自强、人才引领驱动",
            "教育优先发展、科技自立自强、人才引领驱动",
        ],
        "chapter": "第七章",
        "type": "选择/识记",
    },
    {
        "question": "走中国特色社会主义政治发展道路必须坚持哪三者有机统一？最根本的是什么？",
        "expected": "党的领导、人民当家作主、依法治国有机统一；最根本的是坚持党的领导。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "必须坚持党的领导、人民当家作主、依法治国有",
            "党的领导是人民当家作主和依法治国的根本保证",
            "最根本的是坚持党的领导",
        ],
        "chapter": "第八章",
        "type": "简答",
    },
    {
        "question": "中国特色社会主义法治之魂是什么？",
        "expected": "党的领导是中国特色社会主义法治之魂，也是同西方法治最大的区别。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "党的领导是中国特色社会主义法治之魂，是我们的法治同西",
            "中国特色社会主义法治之魂",
        ],
        "chapter": "第九章",
        "type": "选择/识记",
    },
    {
        "question": "建设社会主义文化强国在“举旗帜、聚民心、育新人、兴文化、展形象”方面有哪些要求？",
        "expected": "举旗帜、聚民心、育新人、兴文化、展形象；坚持二为方向与双百方针。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "坚持举旗帜、聚民心、育新人、兴文化、展形象",
            "高举马克思主义、中国特色社会主义的旗帜",
            "讲好中国故事、传播好中国声音",
        ],
        "chapter": "第十章",
        "type": "简答",
    },
    {
        "question": "社会主义文化事业必须坚持的“二为”方向和“双百”方针分别是什么？",
        "expected": "二为：为人民服务、为社会主义服务；双百：百花齐放、百家争鸣。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "坚持为人民服务、为社会主义服务的根本方向",
            "坚持百花齐放、百家争鸣",
        ],
        "chapter": "第十章",
        "type": "选择/识记",
    },
    {
        "question": "总体国家安全观中，宗旨、根本、基础、保障、依托分别是什么？",
        "expected": "宗旨人民安全；根本政治安全；基础经济安全；保障军事、科技、文化、社会安全；依托促进国际安全。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "总体国家安全观以人民安全为宗旨",
            "以政治安全为根本",
            "以经济安全为基础",
            "以军事、科技、文化、社会安全为保障",
            "以促进国际安全为依托",
        ],
        "chapter": "第十三章",
        "type": "简答",
    },
    {
        "question": "如何准确把握“一国两制”中全面管治权与高度自治权的关系？",
        "expected": "坚持中央全面管治权和保障特别行政区高度自治权相统一；高度自治不是完全自治，也不是分权。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "坚持中央全面管治权和保障特别行政区高度自治权相统一",
            "高度自治不是完全自治",
            "全面管治权是授权特别行政区高度自治的前提和基础",
        ],
        "chapter": "第十五章",
        "type": "简答",
    },
    {
        "question": "“爱国者治港”“爱国者治澳”为什么不能动摇？",
        "expected": "要把特别行政区管治权牢牢掌握在爱国者手中，事关国家主权、安全、发展利益和港澳长期繁荣稳定。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "把特别行政区管治权牢牢掌握在爱国者手中",
        ],
        "chapter": "第十五章",
        "type": "选择/识记",
    },
    {
        "question": "特别行政区的宪制基础是什么？",
        "expected": "宪法和基本法共同构成特别行政区的宪制基础。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "宪法和基本法共同构成特别行政区的宪制基础",
            "宪法和基本法共同构成、共同实施",
        ],
        "chapter": "第十五章",
        "type": "选择/识记",
    },
    {
        "question": "构建人类命运共同体要建设一个怎样的世界？",
        "expected": "持久和平、普遍安全、共同繁荣、开放包容、清洁美丽的世界。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "共同建设持久和平、普遍安全、共同繁",
            "持久和平、普遍安全、共同繁荣、开放包容、清洁美丽的世界",
        ],
        "chapter": "第十六章",
        "type": "简答/论述",
    },
    {
        "question": "新型国际关系的基本内涵是什么？",
        "expected": "相互尊重、公平正义、合作共赢；对话不对抗、结伴不结盟。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "相互尊重、公平正义、合作共赢的新型国际关系",
            "对话不对抗、结伴不结盟的伙伴关系",
        ],
        "chapter": "第十六章",
        "type": "选择/识记",
    },
    {
        "question": "“十个明确”在习近平新时代中国特色社会主义思想体系中处于什么地位？",
        "expected": "是主体内容，构成思想体系的四梁八柱，发挥统摄作用。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "是习近平新时代中国特色社会主义思想的主体内容",
            "构成了这一思想体系的四梁八柱",
        ],
        "chapter": "导论",
        "type": "选择/识记",
    },
    {
        "question": "坚定“四个自信”分别指什么？",
        "expected": "道路自信、理论自信、制度自信、文化自信。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "必须坚定道路自信、 理论自信、 制度自信、 文化自信",
            "道路自信、理论自信、制度自信、文化自信",
        ],
        "chapter": "导论/第一章",
        "type": "选择/识记",
    },
    {
        "question": "进入新时代的重大意义（三个“意味着”）是什么？",
        "expected": "迎来从站起来、富起来到强起来的伟大飞跃；科学社会主义在21世纪中国焕发强大生机活力；拓展发展中国家走向现代化途径，贡献中国智慧和中国方案。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "科学社会主义在 21 世纪的中国焕发出强大生机活力",
            "拓展了发展中国家走向现代化的途径",
            "中国智慧和中国方案",
        ],
        "chapter": "第一章",
        "type": "简答",
    },
    {
        "question": "新时代的科学内涵主要包括哪些方面？",
        "expected": "承前启后、继往开来继续夺取伟大胜利；决胜全面建成小康社会、进而全面建设社会主义现代化强国；团结奋斗创造美好生活、逐步实现共同富裕；同心实现中国梦、不断为人类作出更大贡献。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "承前启后、继往开来、在新的历史条件下继续夺取中国",
            "决胜全面建成小康社会、进而全面建设社会主义现代化强",
            "不断为人类作出更大贡献的时代",
        ],
        "chapter": "第一章",
        "type": "简答",
    },
    {
        "question": "绿水青山与金山银山的关系应如何理解？",
        "expected": "牢固树立和践行绿水青山就是金山银山的理念，坚持节约优先、保护优先、自然恢复为主。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "绿水青山就是金山银山的理念",
            "须牢固树立和践行绿水青山就是金山银山的理念",
        ],
        "chapter": "第十二章",
        "type": "选择/识记",
    },
    {
        "question": "全面从严治党战略方针中，如何概括以自我革命引领社会革命？",
        "expected": "以伟大自我革命引领伟大社会革命。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "以伟大自我革命引领伟大社会革命",
            "伟大自我革命引领伟大社会革命",
        ],
        "chapter": "第十七章",
        "type": "选择/识记",
    },
    {
        "question": "坚持和发展中国特色社会主义的总任务是什么？",
        "expected": "实现社会主义现代化和中华民族伟大复兴，以中国式现代化推进中华民族伟大复兴。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "总任务是实现社会主义现代化和中华民族伟大复兴",
            "以中国式现代化推进中华民族伟大复兴",
        ],
        "chapter": "导论",
        "type": "选择/识记",
    },
    {
        "question": "市场在资源配置中应起什么作用？政府应如何定位？",
        "expected": "使市场在资源配置中起决定性作用，更好发挥政府作用。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "使市场在资源配置中起决定性作用，更好发",
            "市场在资源配置中起决定性作用，更好发挥政府作用",
        ],
        "chapter": "第六章",
        "type": "选择/识记",
    },
    {
        "question": "“六个紧紧围绕”中，经济体制改革紧紧围绕什么？",
        "expected": "使市场在资源配置中起决定性作用和更好发挥政府作用。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "紧紧围绕使市场在资源配置中起决定性作用和更好发挥政府作用，深化经济体",
            "使市场在资源配置中起决定性作用和更好发挥政府作用",
        ],
        "chapter": "第五章",
        "type": "选择/识记",
    },
    {
        "question": "中国式现代化区别于西方现代化的显著标志是什么？",
        "expected": "全体人民共同富裕的现代化。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "这是中国式现代化区别于西方现代化的显著标",
            "中国式现代化是全体人民共同富裕的现代化",
        ],
        "chapter": "第二章",
        "type": "选择/识记",
    },
    {
        "question": "一百年来党团结带领人民一切奋斗、牺牲、创造，归结起来是什么主题？",
        "expected": "实现中华民族伟大复兴。",
        "preferred": ["速记宝典", "精讲"],
        "quotes": [
            "就是一个主题：实现中华民族伟大复兴",
        ],
        "chapter": "第二章",
        "type": "选择/识记",
    },
    {
        "question": "人民代表大会制度在我国政治制度体系中属于什么层次？",
        "expected": "根本政治制度。",
        "preferred": ["精讲", "课件", "速记宝典"],
        "quotes": [
            "人民代表大会制度是我国的根本政治制度",
            "人民代表大会制度",
        ],
        "chapter": "第八章",
        "type": "选择/识记",
    },
    {
        "question": "“两个确立”的内涵是什么？",
        "expected": "确立习近平同志党中央的核心、全党的核心地位；确立习近平新时代中国特色社会主义思想的指导地位。",
        "preferred": ["精讲", "课件", "速记宝典"],
        "quotes": [
            "深刻领悟“两个确立”的决定性意义",
            "“两个确立”的内涵",
            "习近平同志党中央的核心、全党的核心地位",
            "最大确定性、最大底气、最大保证",
        ],
        "chapter": "导论",
        "type": "简答",
    },
    {
        "question": "社会主义基本经济制度包括哪三个方面？",
        "expected": "公有制为主体、多种所有制经济共同发展；按劳分配为主体、多种分配方式并存；社会主义市场经济体制。",
        "preferred": ["精讲", "速记宝典", "课件"],
        "quotes": [
            "公有制为主体、多种所有制经济共同发展",
            "按劳分配为主体、多种分配方式并存",
            "社会主义市场经济体制",
            "社会主义基本经济制度",
        ],
        "chapter": "第六章",
        "type": "简答",
    },
    {
        "question": "跳出治乱兴衰历史周期率的第二个答案是什么？",
        "expected": "自我革命（第一个答案是人民监督）。",
        "preferred": ["精讲", "课件", "速记宝典"],
        "quotes": [
            "党的自我革命是跳出历史周期率的第二个答案",
            "跳出历史周期率的第二个答案",
            "以伟大自我革命引领伟大社会革命",
        ],
        "chapter": "第十七章",
        "type": "选择/识记",
    },
]


def build() -> None:
    items: list[dict] = []
    warnings: list[str] = []
    for i, raw in enumerate(raw_items, 1):
        spans: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for q in raw["quotes"]:
            hit = find_quote(raw["preferred"], q) or find_quote(
                ["速记宝典", "精讲", "课件"], q
            )
            if not hit:
                warnings.append(f"Q{i} missing quote: {q[:48]}")
                continue
            doc, quote = hit
            key = (doc, quote)
            if key in seen:
                continue
            spans.append({"document": doc, "quote": quote})
            seen.add(key)
        if not spans:
            warnings.append(f"Q{i} NO SPANS: {raw['question']}")
            continue
        items.append(
            {
                "question": raw["question"],
                "expected": raw["expected"],
                "metadata": {
                    "course": "15040",
                    "chapter": raw["chapter"],
                    "type": raw["type"],
                    "source": "15040精讲/课件/速记宝典",
                },
                "spans": spans,
            }
        )

    payload = {"items": items}
    json_path = OUT_DIR / "15040-scenario-items.json"
    csv_path = OUT_DIR / "15040-scenario-items.csv"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["question", "expected", "document", "quote", "chapter", "type"]
        )
        writer.writeheader()
        for row in items:
            for j, span in enumerate(row["spans"]):
                writer.writerow(
                    {
                        "question": row["question"] if j == 0 else "",
                        "expected": row["expected"] if j == 0 else "",
                        "document": span["document"],
                        "quote": span["quote"],
                        "chapter": row["metadata"]["chapter"] if j == 0 else "",
                        "type": row["metadata"]["type"] if j == 0 else "",
                    }
                )

    readme = OUT_DIR / "README-15040-import.md"
    readme.write_text(
        """# 15040 场景题库导入说明

## 文件

- `15040-scenario-items.json` — 推荐：场景页「导入文件」直接上传
- `15040-scenario-items.csv` — 同等内容（UTF-8 BOM，Excel 可开）

## 导入步骤

1. 知识库先上传：`15040精讲.pdf`、`15040速记宝典.pdf`（可选 `15040课件.pdf`）
2. 新建场景，绑定该知识库
3. 场景详情 → 导入文件 → 选择上述 JSON 或 CSV
4. `document` 字段按文件名匹配；请保持上传文件名与题库一致

## 说明

- `quote` 已按本仓库 PDF 抽取逻辑（pypdf 按页拼接）校验为原文子串，便于 `recall_at_k` / `mrr` 评测
- 课件多为幻灯片，题库依据主要落在精讲与速记宝典
- 题目覆盖导论至第十七章高频考点
""",
        encoding="utf-8",
    )

    print(f"items={len(items)} spans={sum(len(i['spans']) for i in items)}")
    print(f"wrote {json_path}")
    print(f"wrote {csv_path}")
    if warnings:
        print("WARNINGS:")
        for w in warnings:
            print(" ", w)


if __name__ == "__main__":
    build()
