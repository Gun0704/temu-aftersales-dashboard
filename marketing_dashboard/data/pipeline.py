from __future__ import annotations

from io import BytesIO

import pandas as pd
from marketing_dashboard.core.cache import cache_data

from marketing_dashboard.analytics.matching import build_detail_dataset, build_match_check
from marketing_dashboard.data.cleaners import (
    clean_mapping_df,
    clean_sales_df,
    clean_traffic_df,
    is_sales_file,
    is_traffic_file,
)


@cache_data(show_spinner=False)
def load_table_from_bytes(file_name: str, file_bytes: bytes) -> pd.DataFrame:
    """Read CSV/Excel bytes with a small encoding fallback for CSV files."""
    suffix = file_name.lower().split(".")[-1]
    bio = BytesIO(file_bytes)
    if suffix == "csv":
        last_error: Exception | None = None
        for encoding in ("utf-8", "utf-8-sig", "latin1", "cp1252"):
            try:
                bio.seek(0)
                return pd.read_csv(bio, encoding=encoding)
            except Exception as exc:  # pragma: no cover - surfaced to Streamlit UI
                last_error = exc
        raise ValueError(f"CSV 读取失败：{last_error}")
    return pd.read_excel(bio)


@cache_data(show_spinner=False)
def process_inputs(
    sales_inputs: list[tuple[str, bytes]],
    traffic_inputs: list[tuple[str, bytes]],
    mapping_inputs: list[tuple[str, bytes]],
    mixed_inputs: list[tuple[str, bytes]],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], list[str]]:
    """Clean and merge uploaded/local sales, traffic and mapping files."""
    sales_df = pd.DataFrame()
    traffic_df = pd.DataFrame()
    mapping_df = pd.DataFrame()
    messages: list[str] = []
    unknown_files: list[str] = []
    sales_parts, traffic_parts, mapping_parts = [], [], []

    if sales_inputs:
        for name, content in sales_inputs:
            sales_parts.append(clean_sales_df(load_table_from_bytes(name, content), name))
        sales_df = pd.concat(sales_parts, ignore_index=True) if sales_parts else pd.DataFrame()
        messages.append(f"销售表载入 {len(sales_inputs)} 个文件，共 {len(sales_df):,} 行")
    if traffic_inputs:
        for name, content in traffic_inputs:
            traffic_parts.append(clean_traffic_df(load_table_from_bytes(name, content), name))
        traffic_df = pd.concat(traffic_parts, ignore_index=True) if traffic_parts else pd.DataFrame()
        messages.append(f"流量表载入 {len(traffic_inputs)} 个文件，共 {len(traffic_df):,} 行")
    if mapping_inputs:
        for name, content in mapping_inputs:
            mapping_parts.append(clean_mapping_df(load_table_from_bytes(name, content), name))
        mapping_df = pd.concat(mapping_parts, ignore_index=True) if mapping_parts else pd.DataFrame()
        if not mapping_df.empty:
            mapping_df = mapping_df.sort_values(["goods_id", "inventory_qty"], ascending=[True, False]).drop_duplicates("goods_id")
        messages.append(f"商品信息表载入 {len(mapping_inputs)} 个文件，共 {len(mapping_df):,} 个 Goods ID")
    if mixed_inputs:
        mixed_sales_parts, mixed_traffic_parts = [], []
        for name, content in mixed_inputs:
            raw_df = load_table_from_bytes(name, content)
            if is_sales_file(raw_df):
                mixed_sales_parts.append(clean_sales_df(raw_df, name))
            elif is_traffic_file(raw_df):
                mixed_traffic_parts.append(clean_traffic_df(raw_df, name))
            else:
                unknown_files.append(name)
        if mixed_sales_parts:
            mixed_sales_df = pd.concat(mixed_sales_parts, ignore_index=True)
            sales_df = pd.concat([sales_df, mixed_sales_df], ignore_index=True) if not sales_df.empty else mixed_sales_df
        if mixed_traffic_parts:
            mixed_traffic_df = pd.concat(mixed_traffic_parts, ignore_index=True)
            traffic_df = pd.concat([traffic_df, mixed_traffic_df], ignore_index=True) if not traffic_df.empty else mixed_traffic_df
        messages.append(f"混合上传自动识别：销售文件 {len(mixed_sales_parts)} 个，流量文件 {len(mixed_traffic_parts)} 个")

    return sales_df, traffic_df, mapping_df, messages, unknown_files


@cache_data(show_spinner=False)
def compute_base_datasets(
    sales_df: pd.DataFrame,
    traffic_df: pd.DataFrame,
    mapping_df: pd.DataFrame,
    conversion_basis: str,
) -> tuple[pd.DataFrame, dict, dict]:
    """Build merged detail data and matching diagnostics."""
    detail_df = build_detail_dataset(sales_df, traffic_df, mapping_df, conversion_basis)
    match_summary, match_details = build_match_check(sales_df, traffic_df, mapping_df)
    return detail_df, match_summary, match_details
