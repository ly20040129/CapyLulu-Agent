"""表格数据处理工具（批次10）：基于 pandas 的读取、清洗、过滤、转换。

覆盖：读取 xlsx/csv/json 并返回摘要、写入表格、去重/去空/去空格清洗、
按列条件过滤、xlsx<->csv 互转。清洗与过滤产物默认保存到 data/cleaned/。
"""
from __future__ import annotations

import datetime
import os

from ..config import config
from .registry import tool


def _cleaned_dir() -> str:
    d = os.path.join(config.data_dir, "cleaned")
    os.makedirs(d, exist_ok=True)
    return d


def _gen_name(src_path: str, tag: str, ext: str) -> str:
    base = os.path.splitext(os.path.basename(src_path or "data"))[0]
    now = datetime.datetime.now()
    return os.path.join(_cleaned_dir(), f"{base}_{tag}_{now.year}{now.month:02d}{now.day:02d}_{now.hour:02d}{now.minute:02d}{now.second:02d}.{ext}")


def _read_df(path: str):
    import pandas as pd
    p = os.path.abspath(path)
    if not os.path.exists(p):
        raise FileNotFoundError(f"文件不存在：{p}")
    ext = os.path.splitext(p)[1].lower()
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(p)
    if ext == ".csv":
        return pd.read_csv(p, encoding="utf-8-sig")
    if ext == ".json":
        return pd.read_json(p)
    if ext in (".tsv",):
        return pd.read_csv(p, sep="\t", encoding="utf-8-sig")
    raise ValueError(f"不支持的文件类型：{ext}，支持 xlsx/xls/csv/json/tsv")


def _save_df(df, out_path: str, to_ext: str = "") -> str:
    ext = (to_ext or os.path.splitext(out_path)[1]).lower().lstrip(".")
    if ext in ("xlsx", "xls"):
        df.to_excel(out_path, index=False)
    elif ext == "csv":
        df.to_csv(out_path, index=False, encoding="utf-8-sig")
    elif ext == "json":
        df.to_json(out_path, orient="records", force_ascii=False)
    else:
        raise ValueError(f"不支持输出类型：{ext}")
    return out_path


@tool(
    name="read_table",
    description="读取表格文件（xlsx/xls/csv/json/tsv），返回行数、列名与前几行数据摘要",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "表格文件绝对路径"},
            "max_rows": {"type": "integer", "description": "预览前几行，默认5"},
        },
        "required": ["path"],
    },
    risk="low",
)
def read_table(path: str, max_rows: int = 5) -> str:
    try:
        df = _read_df(path)
    except Exception as exc:  # noqa: BLE001
        return f"读取失败：{exc}"
    lines = [f"文件：{os.path.abspath(path)}", f"共 {len(df)} 行 × {len(df.columns)} 列", f"列名：{'、'.join(map(str, df.columns))}"]
    lines.append("前几行预览：")
    lines.append(df.head(max(1, int(max_rows))).to_string(index=False, max_colwidth=30))
    return "\n".join(lines)


@tool(
    name="write_table",
    description="把文本数据写入表格文件（按行转置；rows 传二维数组，首行作为列名），返回保存路径",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "输出文件绝对路径（.xlsx 或 .csv）"},
            "rows": {"type": "array", "description": "二维数组：第一行为列名，后续为数据行"},
        },
        "required": ["path", "rows"],
    },
    risk="medium",
)
def write_table(path: str, rows: list) -> str:
    import pandas as pd
    try:
        if not rows or not isinstance(rows, list):
            return "rows 必须是非空二维数组"
        headers = rows[0]
        data = [r for r in rows[1:] if isinstance(r, list)]
        df = pd.DataFrame(data, columns=headers)
        _save_df(df, path)
        return f"已写入表格：{os.path.abspath(path)}（{len(df)} 行 × {len(df.columns)} 列）"
    except Exception as exc:  # noqa: BLE001
        return f"写入失败：{exc}"


@tool(
    name="clean_table",
    description="清洗表格：去重、去全空行、去除单元格首尾空格（可指定保留列），返回保存路径",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "源表格文件绝对路径"},
            "dedup": {"type": "boolean", "description": "是否按整行去重，默认true"},
            "drop_empty_rows": {"type": "boolean", "description": "是否删除整行全空的记录，默认true"},
            "trim": {"type": "boolean", "description": "是否去除单元格文本首尾空格，默认true"},
            "subset": {"type": "array", "description": "可选，去重时依据的列名列表，默认整行"},
            "out_path": {"type": "string", "description": "可选，输出路径；默认 data/cleaned/ 下自动命名"},
        },
        "required": ["path"],
    },
    risk="medium",
)
def clean_table(path: str, dedup: bool = True, drop_empty_rows: bool = True, trim: bool = True, subset: list | None = None, out_path: str = "") -> str:
    try:
        df = _read_df(path)
        before = len(df)
        if trim:
            df = df.map(lambda v: v.strip() if isinstance(v, str) else v)
        if drop_empty_rows:
            df = df.dropna(how="all")
        if dedup:
            df = df.drop_duplicates(subset=subset or None)
        df = df.reset_index(drop=True)
        out = out_path or _gen_name(path, "cleaned", os.path.splitext(path)[1].lstrip(".").lower() or "xlsx")
        _save_df(df, out)
        return f"清洗完成：{before} 行 → {len(df)} 行；已保存 {out}"
    except Exception as exc:  # noqa: BLE001
        return f"清洗失败：{exc}"


@tool(
    name="filter_rows",
    description="按列条件过滤表格行（支持 eq/ne/gt/ge/lt/le 数值比较与 contains 文本包含），返回保存路径",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "源表格文件绝对路径"},
            "column": {"type": "string", "description": "用于过滤的列名"},
            "op": {"type": "string", "description": "比较操作：eq/ne/gt/ge/lt/le/contains"},
            "value": {"type": "string", "description": "比较值（字符串；数值比较时会自动转数字）"},
            "out_path": {"type": "string", "description": "可选，输出路径；默认 data/cleaned/ 下自动命名"},
        },
        "required": ["path", "column", "op", "value"],
    },
    risk="medium",
)
def filter_rows(path: str, column: str, op: str, value: str, out_path: str = "") -> str:
    try:
        df = _read_df(path)
        if column not in df.columns:
            return f"列不存在：{column}，可用列：{'、'.join(map(str, df.columns))}"
        col = df[column]
        ops = {
            "eq": lambda v: col.astype(str).str.strip() == str(v).strip(),
            "ne": lambda v: col.astype(str).str.strip() != str(v).strip(),
            "contains": lambda v: col.astype(str).str.contains(str(v), case=False, na=False, regex=False),
        }
        for k in ("gt", "ge", "lt", "le"):
            try:
                num = float(value)
            except ValueError:
                return f"操作 {k} 需要数值比较，但「{value}」不是数字"
            ops[k] = (lambda n, kk=k: {"gt": col.astype(float) > n, "ge": col.astype(float) >= n, "lt": col.astype(float) < n, "le": col.astype(float) <= n}[kk])(num)
        if op not in ops:
            return f"不支持的操作：{op}，支持 {'/'.join(ops.keys())}"
        mask = ops[op](value)
        out = df[mask].reset_index(drop=True)
        out_path = out_path or _gen_name(path, f"filter_{op}", os.path.splitext(path)[1].lstrip(".").lower() or "xlsx")
        _save_df(out, out_path)
        return f"过滤完成：{len(df)} 行 → {len(out)} 行（{column} {op} {value}）；已保存 {out_path}"
    except Exception as exc:  # noqa: BLE001
        return f"过滤失败：{exc}"


@tool(
    name="convert_table",
    description="表格格式转换（xlsx/csv/json 互转），返回转换后文件路径",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "源表格文件绝对路径"},
            "to_format": {"type": "string", "description": "目标格式：xlsx / csv / json"},
            "out_path": {"type": "string", "description": "可选，输出路径；默认 data/cleaned/ 下自动命名"},
        },
        "required": ["path", "to_format"],
    },
    risk="medium",
)
def convert_table(path: str, to_format: str, out_path: str = "") -> str:
    try:
        df = _read_df(path)
        fmt = (to_format or "").strip().lower().lstrip(".")
        if fmt not in ("xlsx", "csv", "json"):
            return f"不支持目标格式：{to_format}，支持 xlsx/csv/json"
        out = out_path or _gen_name(path, "conv", fmt)
        _save_df(df, out, fmt)
        return f"已转换：{os.path.abspath(path)} → {out}"
    except Exception as exc:  # noqa: BLE001
        return f"转换失败：{exc}"
