import re
from docx import Document

from validators import add_issue


def check_word(file_path, issues):

    doc = Document(file_path)

    # WORD01：标题层级
    previous_level = 0

    for index, paragraph in enumerate(doc.paragraphs):

        match = re.match(
            r"Heading\s+(\d+)",
            paragraph.style.name,
            re.I
        )

        if match:
            level = int(match.group(1))

            if previous_level and level > previous_level + 1:
                add_issue(
                    issues, "WORD01", "标题层级跳级", "low",
                    f"标题从 {previous_level} 级跳到 {level} 级。",
                    {"paragraph": index + 1}
                )

            previous_level = level

    # WORD02：空表格
    for index, table in enumerate(doc.tables):

        has_content = any(
            cell.text.strip()
            for row in table.rows
            for cell in row.cells
        )

        if not has_content:
            add_issue(
                issues, "WORD02", "空表格", "medium",
                "检测到空表格。",
                {"table": index + 1}
            )