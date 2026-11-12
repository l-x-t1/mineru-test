
from quality_analyzer import analyze_pdf


def route_document(file_path: str) -> dict:
    """
    根据 PDF 质量检测结果，选择文档解析路径。
    """

    # 1. 获取 PDF 质量检测结果
    quality = analyze_pdf(file_path)

    avg_chars = quality["avg_chars"]
    empty_ratio = quality["empty_ratio"]

    # 2. 根据检测指标选择解析路径
    if avg_chars < 50 or empty_ratio > 0.5:
        route = "mineru"
        reason = "文本量较少或空白页面比例较高，疑似扫描版 PDF"

    else:
        route = "pymupdf"
        reason = "文本提取情况正常，优先使用 PyMuPDF"

    # 3. 返回路由结果
    return {
        "file_path": file_path,
        "route": route,
        "reason": reason,
        "quality": quality
    }


if __name__ == "__main__":
    result = route_document("sample.pdf")

    print("Document Router 路由结果：")
    print(f"解析路径：{result['route']}")
    print(f"判断原因：{result['reason']}")
    print(f"质量指标：{result['quality']}")
