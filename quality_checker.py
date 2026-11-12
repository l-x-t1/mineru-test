"""
MinerU PDF 解析质量检测
功能：
1. 对比原始 PDF 页数与 MinerU layout.json 页数
2. 检查每页文本量、乱码字符、异常重复
3. 检查疑似表格是否没有被结构化为 table + HTML
4. 检查 MinerU 引用的图片资源是否存在、是否为空
5. 输出统一 JSON 检测报告

依赖：
    pip install pymupdf

运行前修改下方 CONFIG 中的路径。
"""

import json
import re
from pathlib import Path
from collections import Counter
from typing import Any

import pymupdf


# ============================================================
# 1. 配置区：先修改这里
# ============================================================

CONFIG = {
    # 原始 PDF 文件
    "pdf_path": r"D:\shixi\mineru-text\input\1.pdf",

    # MinerU 输出的 layout.json
    "layout_json_path": r"D:\shixi\mineru-text\output\layout.json",

    # MinerU 生成图片的目录，通常是 images 文件夹
    "images_dir": r"D:\shixi\mineru-text\output\images",

    # 检测报告输出位置
    "report_path": r"D:\shixi\mineru-text\quality_report.json",
    # 每页最少字符数：低于该值只标记为“疑似”，不直接判失败
    "min_chars_per_page": 20,

    # 两页文本相似度达到该值时，标记为疑似重复页面
    "duplicate_similarity_threshold": 0.90,

    # 是否检查图片资源
    "check_images": True,

    # 是否检查疑似未结构化表格
    "check_tables": True,
}


# ============================================================
# 2. 通用工具函数
# ============================================================

def add_issue(
    issues: list,
    issue_id: str,
    category: str,
    rule_id: str,
    severity: str,
    description: str,
    evidence: str,
):
    """向当前页面的 issues 数组中添加一条问题记录。"""
    issues.append({
        "issue_id": issue_id,
        "category": category,
        "rule_id": rule_id,
        "severity": severity,
        "description": description,
        "evidence": evidence,
    })


def walk_dict(data: Any):
    """递归遍历 JSON 中所有字典节点。"""
    if isinstance(data, dict):
        yield data
        for value in data.values():
            yield from walk_dict(value)
    elif isinstance(data, list):
        for item in data:
            yield from walk_dict(item)


def collect_page_blocks(page_data: dict) -> list:
    """
    优先使用 para_blocks。
    如果没有 para_blocks，再使用 preproc_blocks。
    不同时合并两者，避免同一内容重复统计。
    """
    blocks = page_data.get("para_blocks")
    if isinstance(blocks, list):
        return blocks

    blocks = page_data.get("preproc_blocks")
    if isinstance(blocks, list):
        return blocks

    return []


def collect_text_from_blocks(blocks: list) -> str:
    """提取页面 block 中所有 span 的 content 文本。"""
    texts = []

    for block in blocks:
        for node in walk_dict(block):
            content = node.get("content")
            if isinstance(content, str) and content.strip():
                texts.append(content.strip())

    return "\n".join(texts)


def collect_table_info(blocks: list) -> tuple[int, int]:
    """
    返回：
    table_count：识别到的 table 类型数量
    html_table_count：包含非空 HTML 表格的数量
    """
    table_count = 0
    html_table_count = 0

    for block in blocks:
        for node in walk_dict(block):
            node_type = str(node.get("type", "")).lower()

            if node_type == "table":
                table_count += 1

                html = node.get("html")
                if isinstance(html, str) and html.strip():
                    if re.search(r"<table[\s>]", html, re.IGNORECASE):
                        html_table_count += 1

    return table_count, html_table_count


def collect_image_paths(blocks: list) -> list[str]:
    """提取页面中所有 image_path，去重后返回。"""
    paths = []

    for block in blocks:
        for node in walk_dict(block):
            image_path = node.get("image_path")
            if isinstance(image_path, str) and image_path.strip():
                paths.append(image_path.strip())

    return list(dict.fromkeys(paths))


def collect_large_visual_blocks(blocks: list, page_size: list) -> list:
    """
    找出面积占页面较大比例的 chart/image 类型 block。
    这里的面积比例只用于筛查，不代表它一定是表格。
    """
    result = []

    if not isinstance(page_size, list) or len(page_size) < 2:
        return result

    try:
        page_area = float(page_size[0]) * float(page_size[1])
    except (TypeError, ValueError):
        return result

    if page_area <= 0:
        return result

    for block in blocks:
        block_type = str(block.get("type", "")).lower()
        if block_type not in {"chart", "image_body", "image"}:
            continue

        bbox = block.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue

        try:
            x0, y0, x1, y1 = map(float, bbox)
            area_ratio = abs((x1 - x0) * (y1 - y0)) / page_area
        except (TypeError, ValueError):
            continue

        if area_ratio >= 0.15:
            result.append({
                "type": block_type,
                "area_ratio": round(area_ratio, 3),
            })

    return result


def has_table_like_text(text: str) -> tuple[bool, str]:
    """
    根据常见表格字段，初步判断页面是否具有表格特征。
    这是启发式规则，不是准确的表格识别算法。
    """
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    weekday_count = sum(1 for day in weekdays if day in text)

    if weekday_count >= 3:
        return True, f"检测到 {weekday_count} 个星期字段"

    table_keywords = [
        "姓名", "日期", "项目", "次数", "时间",
        "训练内容", "训练记录", "总计", "合计",
        "锻炼日志", "步数", "频率",
    ]

    matched = [word for word in table_keywords if word in text]

    if len(matched) >= 3:
        return True, "检测到多个疑似表格字段：" + "、".join(matched[:6])

    return False, ""


def resolve_image_path(image_path: str, images_dir: Path, output_dir: Path) -> Path:
    """
    兼容 MinerU 常见的相对图片路径：
    - images/xxx.jpg
    - xxx.jpg
    同时尝试 images_dir 和 layout.json 所在目录。
    """
    raw_path = Path(image_path)

    candidates = []

    if raw_path.is_absolute():
        candidates.append(raw_path)
    else:
        candidates.append(images_dir / raw_path.name)
        candidates.append(output_dir / raw_path)
        candidates.append(output_dir / raw_path.name)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]


def normalize_text(text: str) -> str:
    """用于重复页面比较：去掉空白和常见标点。"""
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[，。！？、；：,.!?;:'\"“”‘’（）()\[\]【】]", "", text)
    return text


def similarity(text_a: str, text_b: str) -> float:
    """计算两个页面文本的简单相似度。"""
    from difflib import SequenceMatcher

    a = normalize_text(text_a)
    b = normalize_text(text_b)

    if not a or not b:
        return 0.0

    return SequenceMatcher(None, a, b).ratio()


# ============================================================
# 3. 单页规则检测
# ============================================================

def check_page(
    page_number: int,
    page_data: dict,
    original_page_text: str,
    images_dir: Path,
    output_dir: Path,
) -> dict:

    issues = []
    blocks = collect_page_blocks(page_data)

    mineru_text = collect_text_from_blocks(blocks)
    char_count = len(re.sub(r"\s+", "", mineru_text))

    # ---------- 规则一：页面结构 ----------
    if not blocks:
        add_issue(
            issues,
            "ISSUE_001",
            "document_integrity",
            "DOC_002",
            "high",
            "页面没有检测到解析 block",
            "para_blocks 和 preproc_blocks 均为空或不存在",
        )

    # ---------- 规则二：文本量 ----------
    if char_count == 0:
        add_issue(
            issues,
            "ISSUE_002",
            "text_quality",
            "TEXT_001",
            "medium",
            "页面没有提取到文本",
            "MinerU 页面文本字符数为 0；图片页或纯图表页也可能出现这种情况",
        )
    elif char_count < CONFIG["min_chars_per_page"]:
        add_issue(
            issues,
            "ISSUE_003",
            "text_quality",
            "TEXT_002",
            "low",
            "页面文本量较少",
            f"当前页面提取到 {char_count} 个非空白字符，低于阈值 {CONFIG['min_chars_per_page']}",
        )

    # ---------- 规则三：明显乱码 ----------
    replacement_count = mineru_text.count("\ufffd")
    if replacement_count > 0:
        add_issue(
            issues,
            "ISSUE_004",
            "text_quality",
            "TEXT_003",
            "medium",
            "页面包含 Unicode 替换字符",
            f"检测到 {replacement_count} 个替换字符（�），建议人工或视觉复核",
        )

    # ---------- 规则四：疑似异常重复 ----------
    normalized = normalize_text(mineru_text)
    if len(normalized) >= 30:
        counts = Counter(normalized)
        most_common_char, most_common_count = counts.most_common(1)[0]
        repeated_ratio = most_common_count / len(normalized)

        if repeated_ratio >= 0.50:
            add_issue(
                issues,
                "ISSUE_005",
                "text_quality",
                "TEXT_004",
                "medium",
                "页面字符分布异常，疑似重复或乱码",
                f"字符“{most_common_char}”占页面有效字符的 {repeated_ratio:.1%}",
            )

    # ---------- 规则五：疑似表格未结构化 ----------
    if CONFIG["check_tables"]:
        table_count, html_table_count = collect_table_info(blocks)

        # 优先使用原始 PDF 页面文本辅助判断表格特征
        candidate_text = original_page_text or mineru_text
        looks_like_table, table_evidence = has_table_like_text(candidate_text)

        page_size = page_data.get("page_size", [])
        large_visual_blocks = collect_large_visual_blocks(blocks, page_size)

        if (
            table_count == 0
            and looks_like_table
            and large_visual_blocks
        ):
            visual_types = ", ".join(
                item["type"] for item in large_visual_blocks
            )

            add_issue(
                issues,
                "ISSUE_006",
                "table_quality",
                "TABLE_002",
                "medium",
                "疑似表格未被结构化识别",
                (
                    f"{table_evidence}；页面存在较大的 {visual_types} block，"
                    "但没有检测到 table 类型及 HTML 表格结构"
                ),
            )

        elif table_count > 0 and html_table_count == 0:
            add_issue(
                issues,
                "ISSUE_007",
                "table_quality",
                "TABLE_001",
                "medium",
                "检测到 table 类型，但没有有效 HTML 表格",
                f"检测到 {table_count} 个 table 节点，但没有发现非空 HTML table",
            )

    # ---------- 规则六：图片资源 ----------
    if CONFIG["check_images"]:
        image_paths = collect_image_paths(blocks)

        for image_path in image_paths:
            full_path = resolve_image_path(
                image_path,
                images_dir,
                output_dir,
            )

            if not full_path.exists():
                add_issue(
                    issues,
                    "ISSUE_008",
                    "image_quality",
                    "IMAGE_001",
                    "medium",
                    "图片资源文件不存在",
                    f"MinerU 引用了 {image_path}，但在配置的图片目录及输出目录中没有找到文件",
                )
                continue

            try:
                file_size = full_path.stat().st_size
            except OSError:
                file_size = 0

            if file_size == 0:
                add_issue(
                    issues,
                    "ISSUE_009",
                    "image_quality",
                    "IMAGE_002",
                    "medium",
                    "图片资源文件为空",
                    f"图片文件 {full_path.name} 的大小为 0 字节",
                )

    # ---------- 生成页面状态 ----------
    if any(issue["severity"] == "high" for issue in issues):
        status = "failed"
    elif issues:
        status = "needs_review"
    else:
        status = "passed"

    return {
        "page_number": page_number,
        "status": status,
        "text_char_count": char_count,
        "issues": issues,
    }


# ============================================================
# 4. 整份 PDF 检测
# ============================================================

def analyze_document() -> dict:
    pdf_path = Path(CONFIG["pdf_path"])
    layout_path = Path(CONFIG["layout_json_path"])
    images_dir = Path(CONFIG["images_dir"])
    report_path = Path(CONFIG["report_path"])

    # ---------- 检查输入文件 ----------
    if not pdf_path.exists():
        raise FileNotFoundError(f"找不到原始 PDF：{pdf_path}")

    if not layout_path.exists():
        raise FileNotFoundError(f"找不到 MinerU layout.json：{layout_path}")

    # ---------- 读取原始 PDF ----------
    pdf_doc = pymupdf.open(pdf_path)
    original_page_count = len(pdf_doc)

    original_page_texts = []
    for page in pdf_doc:
        original_page_texts.append(page.get_text("text").strip())

    # ---------- 读取 MinerU JSON ----------
    with layout_path.open("r", encoding="utf-8") as file:
        layout_data = json.load(file)

    pdf_info = layout_data.get("pdf_info")

    if not isinstance(pdf_info, list):
        raise ValueError(
            "layout.json 中没有找到有效的 pdf_info 数组，请检查 MinerU 输出格式"
        )

    mineru_page_count = len(pdf_info)

    # ---------- 逐页检测 ----------
    page_results = []

    for page_index in range(original_page_count):
        page_number = page_index + 1

        if page_index >= mineru_page_count:
            page_results.append({
                "page_number": page_number,
                "status": "failed",
                "text_char_count": 0,
                "issues": [{
                    "issue_id": "ISSUE_010",
                    "category": "document_integrity",
                    "rule_id": "DOC_001",
                    "severity": "high",
                    "description": "原始 PDF 页面没有对应的 MinerU 解析结果",
                    "evidence": (
                        f"原始 PDF 第 {page_number} 页存在，"
                        "但 pdf_info 中没有对应页面"
                    ),
                }],
            })
            continue

        page_data = pdf_info[page_index]
        original_text = original_page_texts[page_index]

        result = check_page(
            page_number=page_number,
            page_data=page_data,
            original_page_text=original_text,
            images_dir=images_dir,
            output_dir=layout_path.parent,
        )

        page_results.append(result)

    # ---------- 检查 MinerU 是否多出页面 ----------
    document_issues = []

    if original_page_count != mineru_page_count:
        document_issues.append({
            "issue_id": "DOC_ISSUE_001",
            "category": "document_integrity",
            "rule_id": "DOC_003",
            "severity": "high",
            "description": "原始 PDF 页数与 MinerU 解析页数不一致",
            "evidence": (
                f"原始 PDF 共 {original_page_count} 页，"
                f"MinerU 的 pdf_info 共 {mineru_page_count} 页"
            ),
        })

    # ---------- 检查相邻页面是否高度重复 ----------
    # 这里只检查相邻页面，避免误把内容相似但正常的不同页面判为重复。
    for index in range(1, len(page_results)):
        current_text = collect_text_from_blocks(
            collect_page_blocks(pdf_info[index])
        ) if index < mineru_page_count else ""

        previous_text = collect_text_from_blocks(
            collect_page_blocks(pdf_info[index - 1])
        ) if index - 1 < mineru_page_count else ""

        score = similarity(previous_text, current_text)

        if score >= CONFIG["duplicate_similarity_threshold"]:
            page_results[index]["issues"].append({
                "issue_id": "ISSUE_011",
                "category": "text_quality",
                "rule_id": "TEXT_005",
                "severity": "low",
                "description": "当前页面与上一页文本高度相似",
                "evidence": (
                    f"与第 {index} 页的文本相似度为 {score:.1%}，"
                    "请确认是否为正常重复页眉、模板页或异常重复解析"
                ),
            })

            if page_results[index]["status"] == "passed":
                page_results[index]["status"] = "needs_review"

    # ---------- 汇总统计 ----------
    issue_count = sum(
        len(page["issues"]) for page in page_results
    ) + len(document_issues)

    passed_pages = sum(
        1 for page in page_results if page["status"] == "passed"
    )

    review_pages = sum(
        1 for page in page_results if page["status"] == "needs_review"
    )

    failed_pages = sum(
        1 for page in page_results if page["status"] == "failed"
    )

    report = {
        "document_name": pdf_path.name,
        "summary": {
            "original_pdf_pages": original_page_count,
            "mineru_parsed_pages": mineru_page_count,
            "passed_pages": passed_pages,
            "needs_review_pages": review_pages,
            "failed_pages": failed_pages,
            "total_issue_count": issue_count,
        },
        "document_issues": document_issues,
        "pages": page_results,
    }

    # ---------- 保存 JSON 报告 ----------
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with report_path.open("w", encoding="utf-8") as file:
        json.dump(
            report,
            file,
            ensure_ascii=False,
            indent=2,
        )

    pdf_doc.close()

    return report


# ============================================================
# 5. 程序入口
# ============================================================

if __name__ == "__main__":
    try:
        report = analyze_document()

        print("=" * 55)
        print("MinerU PDF 质量检测完成")
        print("=" * 55)

        summary = report["summary"]

        print(f"原始 PDF 页数：{summary['original_pdf_pages']}")
        print(f"MinerU 解析页数：{summary['mineru_parsed_pages']}")
        print(f"通过页面：{summary['passed_pages']}")
        print(f"需要复核页面：{summary['needs_review_pages']}")
        print(f"解析异常页面：{summary['failed_pages']}")
        print(f"发现问题总数：{summary['total_issue_count']}")

        print(f"\n检测报告已保存到：{CONFIG['report_path']}")

        print("\n需要复核或解析异常的页面：")
        for page in report["pages"]:
            if page["status"] != "passed":
                print(
                    f"第 {page['page_number']} 页："
                    f"{page['status']}，"
                    f"{len(page['issues'])} 个问题"
                )

    except Exception as error:
        print(f"检测失败：{error}")
