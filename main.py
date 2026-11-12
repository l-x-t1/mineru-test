
import json
from pathlib import Path
from bs4 import BeautifulSoup

# ==================================================
# 1. 导入已有的规则检测模块
# ==================================================

from validators import create_result

from validators.common_rules import check_common_rules
from validators.pdf_rules import check_pdf
from validators.word_rules import check_word
from validators.excel_rules import check_excel
from validators.html_rules import check_html
from validators.markdown_rules import check_markdown
from validators.txt_rules import check_txt


# ==================================================
# 2. 项目路径配置
# ==================================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
REPORT_DIR = BASE_DIR / "reports"


# 文件夹名称与文件后缀对应关系
TYPE_MAPPING = {
    "pdf": [".pdf"],
    "word": [".docx"],
    "excel": [".xlsx"],
    "html": [".html", ".htm"],
    "markdown": [".md"],
    "txt": [".txt"]
}


# ==================================================
# 3. 读取 MinerU JSON
# ==================================================

def load_parsed_data(json_path: Path) -> dict:
    """
    读取 MinerU 解析生成的 JSON 文件。
    """

    if not json_path.is_file():
        raise FileNotFoundError(
            f"解析结果不存在：{json_path}"
        )

    try:
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

    except json.JSONDecodeError as e:
        raise ValueError(
            f"JSON 文件格式错误：{e}"
        )

    if not isinstance(data, dict):
        raise ValueError("JSON 最外层必须是对象")

    return data


# ==================================================
# 4. 提取 PDF 的 MinerU 文本
# ==================================================

def extract_pdf_text(parsed_data: dict) -> str:
    """
    适配已经确认的 MinerU PDF layout.json 结构。
    """

    pdf_info = parsed_data.get("pdf_info")

    if not isinstance(pdf_info, list):
        raise ValueError(
            "PDF JSON 中没有有效的 pdf_info"
        )

    pages_text = []

    for page in pdf_info:

        if not isinstance(page, dict):
            continue

        page_idx = page.get("page_idx", 0)
        page_texts = []

        def walk_blocks(blocks):

            if not isinstance(blocks, list):
                return

            for block in blocks:

                if not isinstance(block, dict):
                    continue

                # 提取普通文本
                for line in block.get("lines", []):

                    if not isinstance(line, dict):
                        continue

                    for span in line.get("spans", []):

                        if not isinstance(span, dict):
                            continue

                        content = span.get("content")

                        if isinstance(content, str) and content.strip():
                            page_texts.append(content.strip())

                # 提取表格 HTML
                html = block.get("html")

                if isinstance(html, str) and html.strip():

                    soup = BeautifulSoup(
                        html,
                        "html.parser"
                    )

                    table_text = soup.get_text(
                        separator=" ",
                        strip=True
                    )

                    if table_text:
                        page_texts.append(table_text)

                # 递归提取嵌套内容块
                walk_blocks(block.get("blocks", []))

        # 正式解析内容
        walk_blocks(page.get("para_blocks", []))

        pages_text.append(
            f"第 {page_idx + 1} 页\n"
            + "\n".join(page_texts)
        )

    return "\n\n".join(pages_text)


# ==================================================
# 5. 其他格式的 JSON 文本提取
# ==================================================

def extract_general_text(parsed_data: dict) -> str:
    """
    通用 JSON 文本提取。

    查找常见字段：
    content、text、html

    其他格式后续可以根据真实 JSON 结构
    增加专用提取适配器。
    """

    texts = []

    def walk(obj):

        if isinstance(obj, dict):

            for key, value in obj.items():

                key = str(key).lower()

                if key in ("content", "text"):

                    if isinstance(value, str) and value.strip():
                        texts.append(value.strip())

                elif key == "html":

                    if isinstance(value, str) and value.strip():

                        soup = BeautifulSoup(
                            value,
                            "html.parser"
                        )

                        html_text = soup.get_text(
                            separator=" ",
                            strip=True
                        )

                        if html_text:
                            texts.append(html_text)

                else:
                    walk(value)

        elif isinstance(obj, list):

            for item in obj:
                walk(item)

    walk(parsed_data)

    # 去除完全重复的文本片段
    unique_texts = list(dict.fromkeys(texts))

    return "\n".join(unique_texts)


# ==================================================
# 6. 统一解析结果提取入口
# ==================================================

def extract_parsed_text(
    parsed_data: dict,
    file_type: str
) -> str:
    """
    根据文档类型选择对应的文本提取方式。
    """

    if file_type == "pdf":
        return extract_pdf_text(parsed_data)

    return extract_general_text(parsed_data)


# ==================================================
# 7. 查找对应的 MinerU 解析结果
# ==================================================

def find_parsed_files(
    file_path: Path,
    folder_type: str
):
    """
    根据文件类型和文件名查找对应的 JSON 和图片目录。

    约定：
    output/文件类型/原文件名/layout.json
    output/文件类型/原文件名/images/
    """

    document_dir = (
        OUTPUT_DIR
        / folder_type
        / file_path.stem
    )

    json_path = document_dir / "layout.json"

    if not json_path.is_file():

        raise FileNotFoundError(
            f"没有找到 {file_path.name} 对应的 JSON："
            f"{json_path}"
        )

    image_dir = document_dir / "images"

    return json_path, image_dir


# ==================================================
# 8. 单个文档的 Python 规则检测
# ==================================================

def validate_document(
    file_path: Path,
    json_path: Path,
    image_dir: Path,
    file_type: str
) -> dict:
    """
    单个文档检测流程：

    1. 读取 MinerU JSON
    2. 提取解析文本
    3. 通用规则检测
    4. 专项规则检测
    5. 生成统一报告
    """

    # 读取解析结果
    parsed_data = load_parsed_data(json_path)

    # 提取文本
    parsed_text = extract_parsed_text(
        parsed_data,
        file_type
    )

    # 初始化问题列表
    issues = []

    # ------------------------------
    # 第一步：通用规则
    # ------------------------------

    print("    执行通用规则检测...")

    check_common_rules(
        file_path,
        parsed_text,
        issues
    )

    # ------------------------------
    # 第二步：专项规则
    # ------------------------------

    print("    执行专项规则检测...")

    if file_type == "pdf":

        check_pdf(file_path, issues)

    elif file_type == "docx":

        check_word(file_path, issues)

    elif file_type == "xlsx":

        check_excel(file_path, issues)

    elif file_type in ("html", "htm"):

        check_html(file_path, issues)

    elif file_type == "md":

        check_markdown(file_path, issues)

    elif file_type == "txt":

        check_txt(file_path, issues)

    # ------------------------------
    # 第三步：统一生成检测结果
    # ------------------------------

    result = create_result(
        str(file_path),
        file_type,
        issues
    )

    return result


# ==================================================
# 9. 保存单个文档检测报告
# ==================================================

def save_report(
    result: dict,
    file_path: Path
) -> Path:

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    report_name = (
        f"{file_path.stem}_"
        f"{file_path.suffix.lstrip('.').lower()}_report.json"
    )

    report_path = REPORT_DIR / report_name

    report_path.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=4
        ),
        encoding="utf-8"
    )

    return report_path


# ==================================================
# 10. 批量扫描和检测
# ==================================================

def batch_validate():
    """
    扫描 input 下不同类型的文件夹，
    自动寻找原始文档及其 MinerU JSON，
    执行对应的 Python 规则检测。
    """

    if not INPUT_DIR.is_dir():
        raise FileNotFoundError(
            f"input 目录不存在：{INPUT_DIR}"
        )

    total_count = 0
    success_count = 0
    failed_count = 0

    batch_results = []

    print("=" * 60)
    print("          Python 文档质量批量检测")
    print("=" * 60)

    # 按照文件类型扫描
    for folder_type, extensions in TYPE_MAPPING.items():

        type_input_dir = INPUT_DIR / folder_type

        # 文件夹不存在则跳过
        if not type_input_dir.is_dir():
            continue

        print(f"\n正在扫描：{folder_type}")

        # 获取该类型文件夹下所有文档
        files = [
            p for p in type_input_dir.rglob("*")
            if p.is_file()
            and p.suffix.lower() in extensions
        ]

        for file_path in files:

            total_count += 1

            file_type = file_path.suffix.lower().lstrip(".")

            print("\n" + "-" * 50)
            print(
                f"[{total_count}] "
                f"正在检测：{file_path.name}"
            )

            try:

                # 查找对应 JSON 和图片目录
                json_path, image_dir = find_parsed_files(
                    file_path,
                    folder_type
                )

                print(f"    JSON：{json_path}")

                # 执行检测
                result = validate_document(
                    file_path=file_path,
                    json_path=json_path,
                    image_dir=image_dir,
                    file_type=file_type
                )

                # 保存报告
                report_path = save_report(
                    result,
                    file_path
                )

                success_count += 1

                batch_results.append({
                    "file_name": file_path.name,
                    "file_type": file_type,
                    "status": "success",
                    "report_path": str(report_path)
                })

                print(f"    检测完成：{report_path.name}")

            except Exception as e:

                failed_count += 1

                batch_results.append({
                    "file_name": file_path.name,
                    "file_type": file_type,
                    "status": "failed",
                    "error": str(e)
                })

                print(f"    检测失败：{e}")

    # ==================================================
    # 11. 保存批量汇总报告
    # ==================================================

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    summary = {
        "total": total_count,
        "success": success_count,
        "failed": failed_count,
        "results": batch_results
    }

    summary_path = REPORT_DIR / "batch_summary.json"

    summary_path.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=4
        ),
        encoding="utf-8"
    )

    # 打印最终统计
    print("\n" + "=" * 60)
    print("          批量检测结束")
    print("=" * 60)

    print(f"文档总数：{total_count}")
    print(f"检测成功：{success_count}")
    print(f"检测失败：{failed_count}")
    print(f"汇总报告：{summary_path}")


# ==================================================
# 12. 程序入口
# ==================================================

if __name__ == "__main__":

    batch_validate()
