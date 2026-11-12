import re
from pathlib import Path

from validators import add_issue


def check_common_rules(file_path, parsed_text, issues):

    path = Path(file_path)

    # G01：文件完整性
    if not path.exists():
        add_issue(
            issues, "G01", "文件不存在", "critical",
            "指定路径下没有找到文件。"
        )
        return

    if not path.is_file():
        add_issue(
            issues, "G01", "文件类型异常", "critical",
            "指定路径不是普通文件。"
        )
        return

    try:
        with path.open("rb") as f:
            f.read(1)
    except OSError as e:
        add_issue(
            issues, "G01", "文件无法读取", "critical",
            f"文件无法读取：{e}"
        )
        return

    # G02：内容完整性
    if not parsed_text.strip():
        add_issue(
            issues, "G02", "解析内容为空", "high",
            "解析结果没有提取到有效文本。"
        )
        return

    # G03：乱码检测
    replacement_count = parsed_text.count("\ufffd")
    null_count = parsed_text.count("\x00")

    if replacement_count > 0 or null_count > 0:
        add_issue(
            issues, "G03", "疑似乱码", "medium",
            f"发现替换字符 {replacement_count} 个，"
            f"空字符 {null_count} 个。"
        )

    # G04：重复内容
    paragraphs = [
        re.sub(r"\s+", "", p)
        for p in re.split(r"[\n\r]+", parsed_text)
        if len(re.sub(r"\s+", "", p)) >= 20
    ]

    if len(paragraphs) >= 4:
        duplicate_count = len(paragraphs) - len(set(paragraphs))
        ratio = duplicate_count / len(paragraphs)

        if ratio >= 0.3:
            add_issue(
                issues, "G04", "重复内容", "medium",
                f"检测到 {ratio:.1%} 的段落为重复内容。"
            )

    # G05：异常空白
    if len(parsed_text) >= 100:
        whitespace_count = sum(
            1 for char in parsed_text if char.isspace()
        )

        ratio = whitespace_count / len(parsed_text)

        if ratio > 0.8:
            add_issue(
                issues, "G05", "空白比例异常", "medium",
                f"空白字符占比为 {ratio:.1%}。"
            )

    # G06：解析完整性
    # 仅检查原始文本和解析文本长度的明显差异。
    # 原始文本提取由各格式适配器提供。
    """
    这里的 G06 暂时不直接写死在通用模块中，因为 PDF、Word、Excel 的原文提取方式不同。
    后续应该通过各格式解析适配器提供原始文本和结构信息，再做对比，避免错误地把扫描版 PDF 判定为解析失败。
    """