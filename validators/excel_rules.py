
from openpyxl import load_workbook

from validators import add_issue


def check_excel(file_path, issues):

    workbook = load_workbook(
        file_path,
        data_only=False,
        read_only=False
    )

    # EXCEL01：工作表检测
    if not workbook.worksheets:
        add_issue(
            issues, "EXCEL01", "工作表缺失", "high",
            "Excel 中没有工作表。"
        )
        return

    for sheet in workbook.worksheets:

        if sheet.sheet_state != "visible":
            add_issue(
                issues, "EXCEL01", "隐藏工作表", "low",
                f"工作表 {sheet.title} 当前处于隐藏状态。",
                {"sheet": sheet.title}
            )

        # EXCEL02：空工作表
        has_data = False

        # EXCEL03：公式引用错误
        for row in sheet.iter_rows():

            for cell in row:

                if cell.value is not None:
                    has_data = True

                if (
                    isinstance(cell.value, str)
                    and cell.value.startswith("=")
                    and "#REF!" in cell.value
                ):
                    add_issue(
                        issues, "EXCEL03", "公式引用异常", "high",
                        f"单元格 {cell.coordinate} 存在 #REF! 引用。",
                        {
                            "sheet": sheet.title,
                            "cell": cell.coordinate
                        }
                    )

        if not has_data:
            add_issue(
                issues, "EXCEL02", "空工作表", "medium",
                f"工作表 {sheet.title} 没有数据。",
                {"sheet": sheet.title}
            )

    workbook.close()