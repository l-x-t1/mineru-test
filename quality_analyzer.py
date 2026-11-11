
import pymupdf

def analyze_pdf(file_path: str) -> dict:
    """
    分析 PDF 文档的基础质量信息。
    """

    with pymupdf.open(file_path) as doc:

        total_pages = len(doc)
        total_chars = 0
        empty_pages = 0
        image_pages = 0

        for page in doc:
            # 提取当前页面的文本
            text = page.get_text("text").strip()

            # 统计文本字符数
            char_count = len(text)
            total_chars += char_count

            # 判断是否为空白页或文本极少
            if char_count < 20:
                empty_pages += 1

            # 判断页面是否包含图片
            if page.get_images():
                image_pages += 1

        # 计算平均每页字符数
        avg_chars = total_chars / total_pages if total_pages else 0

        # 计算空白页比例
        empty_ratio = empty_pages / total_pages if total_pages else 0

        # 计算图片页面比例
        image_ratio = image_pages / total_pages if total_pages else 0

        return {
            "total_pages": total_pages,
            "total_chars": total_chars,
            "avg_chars": round(avg_chars, 2),
            "empty_pages": empty_pages,
            "empty_ratio": round(empty_ratio, 2),
            "image_pages": image_pages,
            "image_ratio": round(image_ratio, 2)
        }
if __name__ == "__main__":
    result = analyze_pdf("sample.pdf")

    print("PDF 质量检测结果：")

    for key, value in result.items():
        print(f"{key}: {value}")