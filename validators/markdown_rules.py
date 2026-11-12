import re
from pathlib import Path

from validators import add_issue


def check_markdown(file_path, issues):

    content = Path(file_path).read_text(encoding="utf-8")

    # MD01：代码块闭合
    fences = re.findall(
        r"(?m)^\s*(`{3,}|~{3,})",
        content
    )

    if len(fences) % 2 != 0:
        add_issue(
            issues, "MD01", "代码块未闭合", "medium",
            "代码块起始和结束标记数量不匹配。"
        )

    # MD02：标题层级
    previous_level = 0

    for line_number, line in enumerate(content.splitlines(), 1):

        match = re.match(r"^\s{0,3}(#{1,6})\s+", line)

        if match:
            level = len(match.group(1))

            if previous_level and level > previous_level + 1:
                add_issue(
                    issues, "MD02", "标题层级跳级", "low",
                    f"标题从 {previous_level} 级跳到 {level} 级。",
                    {"line": line_number}
                )

            previous_level = level