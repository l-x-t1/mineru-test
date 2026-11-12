
from pathlib import Path
from bs4 import BeautifulSoup

from validators import add_issue


def check_html(file_path, issues):

    raw = Path(file_path).read_text(encoding="utf-8")

    soup = BeautifulSoup(raw, "html.parser")

    # HTML01：body 检测
    if soup.body is None:
        add_issue(
            issues, "HTML01", "缺少 body", "medium",
            "没有检测到 body 标签。"
        )

    # HTML02：title 检测
    if soup.title is None or not soup.title.get_text(strip=True):
        add_issue(
            issues, "HTML02", "标题缺失", "low",
            "没有有效的网页标题。"
        )

    # HTML03：正文检测
    if soup.body and not soup.body.get_text(strip=True):
        add_issue(
            issues, "HTML03", "正文为空", "high",
            "网页正文没有提取到文本。"
        )