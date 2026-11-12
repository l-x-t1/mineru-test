
import pymupdf

from validators import add_issue


def check_pdf(file_path, issues):

    doc = pymupdf.open(file_path)

    # PDF01：页面数量
    if len(doc) == 0:
        add_issue(
            issues, "PDF01", "页面为空", "high",
            "PDF 没有检测到有效页面。"
        )
        return

    for index, page in enumerate(doc):

        page_number = index + 1

        text = page.get_text("text").strip()
        images = page.get_images()

        # PDF02：疑似空白页
        if not text and not images:
            add_issue(
                issues, "PDF02", "疑似空白页", "medium",
                "页面没有提取到文本或图片。",
                {"page": page_number}
            )

        # PDF03：页面旋转
        if page.rotation != 0:
            add_issue(
                issues, "PDF03", "页面旋转", "low",
                f"页面旋转角度为 {page.rotation} 度。",
                {"page": page_number}
            )

    doc.close()