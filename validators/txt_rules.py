from pathlib import Path

from validators import add_issue


def check_txt(file_path, issues):

    try:
        Path(file_path).read_text(encoding="utf-8-sig")

    except UnicodeDecodeError:
        add_issue(
            issues, "TXT01", "编码异常", "medium",
            "文件无法使用 UTF-8 编码正常解码。"
        )