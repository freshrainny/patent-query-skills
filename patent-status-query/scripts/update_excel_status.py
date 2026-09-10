#!/usr/bin/env python3
"""将专利案件状态写入 Excel 表格的指定列（默认 F 列/法律状态）。

用法:
    python3 update_excel_status.py --file 表格.xlsx --mapping status_map.json [--column 6] [--check-column 3] [--no-backup]

参数:
    --file         要更新的 xlsx 路径（必填）
    --mapping      JSON 文件，行号(字符串) -> 状态文本，如 {"2": "等待实审提案"}（必填）
    --column       要写入的状态列号，默认 6（F 列）
    --check-column 校验用的申请号列号（默认 3/C 列）；校验失败则拒绝写入该行
    --no-backup    不创建备份（默认自动备份到同目录 <原名>_备份_<日期>.xlsx）
"""
import argparse
import datetime
import json
import shutil
import sys

import openpyxl


def main():
    ap = argparse.ArgumentParser(description="更新 Excel 专利法律状态列")
    ap.add_argument("--file", required=True)
    ap.add_argument("--mapping", required=True)
    ap.add_argument("--column", type=int, default=6)
    ap.add_argument("--check-column", type=int, default=3)
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    with open(args.mapping, encoding="utf-8") as f:
        mapping = json.load(f)  # {"行号": "状态", ...}

    if not args.no_backup:
        bak = f"{args.file.rsplit('.', 1)[0]}_备份_{datetime.date.today():%Y%m%d}.xlsx"
        shutil.copy2(args.file, bak)
        print(f"已备份: {bak}")

    wb = openpyxl.load_workbook(args.file)
    ws = wb.active

    for row_str, status in mapping.items():
        row = int(row_str)
        # 校验行内申请号非空，防止错行写入
        check_val = ws.cell(row=row, column=args.check_column).value
        if check_val is None or str(check_val).strip() == "":
            print(f"警告: 第 {row} 行申请号列为空，跳过写入", file=sys.stderr)
            continue
        ws.cell(row=row, column=args.column).value = status
    wb.save(args.file)
    print(f"已写入 {len(mapping)} 行 -> {args.file}")

    # 回读验证（不同路径：重新加载文件）
    wb2 = openpyxl.load_workbook(args.file, data_only=True)
    ws2 = wb2.active
    for row_str in sorted(mapping, key=int):
        row = int(row_str)
        got = ws2.cell(row=row, column=args.column).value
        print(f"第 {row} 行 [{ws2.cell(row=row, column=args.check_column).value}] -> {got}")


if __name__ == "__main__":
    main()
