from __future__ import annotations

import pandas as pd
from marketing_dashboard.core.cache import cache_data

from marketing_dashboard.data.cleaners import parse_numeric_series
from marketing_dashboard.data.pipeline import load_table_from_bytes


@cache_data(show_spinner=False)
def load_frontend_order_df(file_name: str, file_bytes: bytes) -> pd.DataFrame:
    """Load and normalize exported frontend order data for price-sales charts."""
    df = load_table_from_bytes(file_name, file_bytes)
    df.columns = [str(c).strip().lower() for c in df.columns]
    required_cols = ["purchase date", "retail price (tax excl.)", "quantity purchased"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"前端价订单表缺少字段：{', '.join(missing)}")

    cleaned = df.copy()
    purchase_text = (
        cleaned["purchase date"].astype(str).str.strip()
        .str.replace(r"\s+[A-Z]{2,5}\(UTC[+-]\d+\)$", "", regex=True)
        .str.replace(r"\s+UTC[+-]?\d+$", "", regex=True)
    )
    purchase_dt = pd.to_datetime(purchase_text, errors="coerce")
    if purchase_dt.isna().any():
        fallback_dt = pd.to_datetime(purchase_text, format="%b %d, %Y, %I:%M %p", errors="coerce")
        purchase_dt = purchase_dt.fillna(fallback_dt)
    cleaned["purchase_dt"] = purchase_dt
    cleaned["date"] = cleaned["purchase_dt"].dt.normalize()
    cleaned["retail price (tax excl.)"] = parse_numeric_series(cleaned["retail price (tax excl.)"])
    cleaned["quantity purchased"] = parse_numeric_series(cleaned["quantity purchased"])

    for status_col in ["order status", "order item status"]:
        if status_col in cleaned.columns:
            cleaned[status_col] = cleaned[status_col].astype(str).str.strip()
    if "contribution sku" in cleaned.columns:
        cleaned["contribution sku"] = cleaned["contribution sku"].astype(str).str.strip()
        cleaned["contribution sku"] = cleaned["contribution sku"].replace({"nan": "", "None": ""})

    invalid_status_mask = pd.Series(False, index=cleaned.index)
    for status_col in ["order status", "order item status"]:
        if status_col in cleaned.columns:
            invalid_status_mask = invalid_status_mask | cleaned[status_col].str.contains(
                r"cancel|closed|void", case=False, na=False
            )

    cleaned = cleaned.dropna(subset=["date"]).copy()
    cleaned = cleaned[cleaned["retail price (tax excl.)"] > 0].copy()
    cleaned = cleaned[cleaned["quantity purchased"] > 0].copy()
    cleaned = cleaned[~invalid_status_mask.loc[cleaned.index]].copy()

    if cleaned.empty:
        raise ValueError("前端价订单表清洗后无有效数据")
    return cleaned


@cache_data(show_spinner=False)
def build_frontend_daily_dataset(order_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate frontend price and purchased quantity by day."""
    def _agg(group: pd.DataFrame) -> pd.Series:
        total_qty = pd.to_numeric(group["quantity purchased"], errors="coerce").fillna(0).sum()
        total_retail = pd.to_numeric(group["retail price (tax excl.)"], errors="coerce").fillna(0).sum()
        unit_price_tax_excl = total_retail / total_qty if total_qty else 0
        return pd.Series({
            "frontend_price": unit_price_tax_excl * 1.16,
            "frontend_price_tax_excl": unit_price_tax_excl,
            "quantity_purchased": total_qty,
            "retail_price_tax_excl_total": total_retail,
        })

    daily = order_df.groupby("date").apply(_agg).reset_index()
    return daily.sort_values("date")


def normalize_text_key(series: pd.Series | None) -> pd.Series:
    if series is None:
        return pd.Series(dtype=str)
    return (
        series.astype(str)
        .str.strip()
        .replace({"": pd.NA, "nan": pd.NA, "None": pd.NA, "<NA>": pd.NA})
        .fillna("")
    )


@cache_data(show_spinner=False)
def enrich_frontend_order_df(
    frontend_order_df: pd.DataFrame,
    sales_df: pd.DataFrame,
    traffic_df: pd.DataFrame,
    mapping_df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    """Map frontend orders back to Goods ID/SKU using SKU and product names."""
    if frontend_order_df.empty:
        return frontend_order_df.copy(), {"total_rows": 0, "mapped_rows": 0, "mapped_ratio": 0.0, "sku_hit_rows": 0, "name_hit_rows": 0}

    enriched = frontend_order_df.copy()
    enriched["product_name_key"] = normalize_text_key(enriched.get("product name"))
    enriched["frontend_sku"] = normalize_text_key(enriched.get("contribution sku"))
    enriched["variation_key"] = normalize_text_key(enriched.get("variation"))

    name_parts: list[pd.DataFrame] = []
    if not sales_df.empty and {"product_name", "goods_id"}.issubset(sales_df.columns):
        name_parts.append(sales_df[["product_name", "goods_id"]].copy())
    if not traffic_df.empty and {"product_name", "goods_id"}.issubset(traffic_df.columns):
        name_parts.append(traffic_df[["product_name", "goods_id"]].copy())
    if not mapping_df.empty and {"product_name", "goods_id"}.issubset(mapping_df.columns):
        name_parts.append(mapping_df[["product_name", "goods_id"]].copy())
    if name_parts:
        name_map = pd.concat(name_parts, ignore_index=True)
        name_map["product_name_key"] = normalize_text_key(name_map["product_name"])
        name_map = name_map[name_map["product_name_key"] != ""].drop_duplicates("product_name_key")
        enriched = enriched.merge(name_map[["product_name_key", "goods_id"]].rename(columns={"goods_id": "goods_id_by_name"}), on="product_name_key", how="left")
    else:
        enriched["goods_id_by_name"] = ""

    sku_map_parts: list[pd.DataFrame] = []
    if not mapping_df.empty and {"sku", "goods_id"}.issubset(mapping_df.columns):
        sku_map = mapping_df[["sku", "goods_id"]].copy()
        sku_map["sku_key"] = normalize_text_key(sku_map["sku"])
        sku_map_parts.append(sku_map[["sku_key", "goods_id"]])
    if not sales_df.empty and {"sku", "goods_id"}.issubset(sales_df.columns):
        sku_map = sales_df[["sku", "goods_id"]].copy()
        sku_map["sku_key"] = normalize_text_key(sku_map["sku"])
        sku_map_parts.append(sku_map[["sku_key", "goods_id"]])

    if sku_map_parts:
        sku_map = pd.concat(sku_map_parts, ignore_index=True)
        sku_map = sku_map[sku_map["sku_key"] != ""].drop_duplicates("sku_key")
        enriched = enriched.merge(sku_map.rename(columns={"goods_id": "goods_id_by_sku"}), left_on="frontend_sku", right_on="sku_key", how="left")
    else:
        enriched["goods_id_by_sku"] = ""

    enriched["goods_id"] = normalize_text_key(enriched.get("goods_id_by_sku")).where(
        normalize_text_key(enriched.get("goods_id_by_sku")) != "",
        normalize_text_key(enriched.get("goods_id_by_name")),
    )
    enriched["display_sku"] = enriched["frontend_sku"].where(enriched["frontend_sku"] != "", enriched["goods_id"])

    stats = {
        "total_rows": int(len(enriched)),
        "mapped_rows": int((enriched["goods_id"] != "").sum()),
        "mapped_ratio": float((enriched["goods_id"] != "").mean()) if len(enriched) else 0.0,
        "sku_hit_rows": int((normalize_text_key(enriched.get("goods_id_by_sku")) != "").sum()),
        "name_hit_rows": int((normalize_text_key(enriched.get("goods_id_by_name")) != "").sum()),
    }
    return enriched, stats
