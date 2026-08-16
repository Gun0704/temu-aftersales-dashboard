from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from marketing_dashboard.analytics.metrics import safe_divide


def _num(series: pd.Series | None) -> pd.Series:
    """把可选字段安全转成数字，缺失时返回空数字序列。"""
    if series is None:
        return pd.Series(dtype=float)
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _first(row: dict[str, Any], *keys: str, default: Any = "") -> Any:
    """兼容 TEMU 不同接口的字段命名。"""
    lower_map = {str(k).lower(): v for k, v in row.items()}
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
        value = lower_map.get(key.lower())
        if value is not None:
            return value
    return default


def extra_rows_to_df(rows: list[dict], source_name: str = "TEMU_API") -> pd.DataFrame:
    """把更多 TEMU 接口结果标准化成可选高级指标表。

    这个函数不是绑定某一个固定接口，而是做宽松字段映射：只要接口返回里出现
    加购、支付、退货、库存、价格、成本等常见字段，就会进入高级分析模块。
    """
    data: list[dict[str, Any]] = []
    for r in rows:
        data.append({
            "date": _first(r, "date", "statDate", "bizDate", "orderDate", "payTime", "createTime"),
            "goods_id": _first(r, "goodsId", "goods_id", "productId", "product_id"),
            "sku": _first(r, "sku", "skuId", "sku_id", "extCode"),
            "store": _first(r, "storeName", "mallName", "shopName", "store", default=source_name),
            "add_to_cart": _first(r, "addToCartCnt", "cartCnt", "cartCount", "addToCart", default=0),
            "visitors": _first(r, "visitorCnt", "visitors", "uv", "uniqueVisitors", default=0),
            "paid_orders": _first(r, "paidOrderCnt", "payOrderCnt", "paidOrders", default=0),
            "paid_units": _first(r, "paidUnitCnt", "payQty", "paidQty", default=0),
            "refund_orders": _first(r, "refundOrderCnt", "refundOrders", "returnOrderCnt", default=0),
            "refund_units": _first(r, "refundUnitCnt", "returnQty", "refundQty", default=0),
            "refund_amount": _first(r, "refundAmount", "refundAmt", "returnAmount", default=0),
            "inventory_qty": _first(r, "inventory", "stock", "availableQty", "quantity", default=0),
            "front_price": _first(r, "frontPrice", "retailPrice", "salePrice", "price", default=0),
            "supply_price": _first(r, "supplyPrice", "cost", "costPrice", default=0),
        })
    df = pd.DataFrame(data)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.floor("D")
    df["goods_id"] = df["goods_id"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    df = df[df["goods_id"].notna() & (df["goods_id"] != "") & (df["goods_id"].str.lower() != "nan")].copy()
    for col in ["add_to_cart", "visitors", "paid_orders", "paid_units", "refund_orders", "refund_units", "refund_amount", "inventory_qty", "front_price", "supply_price"]:
        df[col] = _num(df[col])
    return df


def merge_extra_metrics(detail_df: pd.DataFrame, extra_df: pd.DataFrame) -> pd.DataFrame:
    """把高级 API 指标合并到当前看板明细。"""
    if detail_df.empty:
        return pd.DataFrame()
    base = detail_df.copy()
    base["date"] = pd.to_datetime(base["date"], errors="coerce").dt.floor("D")
    if extra_df.empty:
        for col in ["add_to_cart", "visitors", "paid_orders", "paid_units", "refund_orders", "refund_units", "refund_amount", "front_price", "supply_price"]:
            base[col] = 0
        base["inventory_qty_api"] = base.get("inventory_qty", 0)
        return _attach_advanced_rates(base)

    ext = extra_df.copy()
    ext["date"] = pd.to_datetime(ext["date"], errors="coerce").dt.floor("D")
    group_cols = ["date", "goods_id"]
    ext_grouped = ext.groupby(group_cols, as_index=False).agg(
        add_to_cart=("add_to_cart", "sum"),
        visitors=("visitors", "sum"),
        paid_orders=("paid_orders", "sum"),
        paid_units=("paid_units", "sum"),
        refund_orders=("refund_orders", "sum"),
        refund_units=("refund_units", "sum"),
        refund_amount=("refund_amount", "sum"),
        inventory_qty_api=("inventory_qty", "max"),
        front_price=("front_price", "max"),
        supply_price=("supply_price", "max"),
    )
    merged = base.merge(ext_grouped, on=["date", "goods_id"], how="left")
    for col in ["add_to_cart", "visitors", "paid_orders", "paid_units", "refund_orders", "refund_units", "refund_amount", "inventory_qty_api", "front_price", "supply_price"]:
        merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0)
    merged["inventory_qty_api"] = np.where(merged["inventory_qty_api"] > 0, merged["inventory_qty_api"], merged.get("inventory_qty", 0))
    return _attach_advanced_rates(merged)


def _attach_advanced_rates(df: pd.DataFrame) -> pd.DataFrame:
    """补充漏斗、退货、利润和库存派生指标。"""
    out = df.copy()
    out["visit_click_rate"] = safe_divide(out["clicks"], out["visitors"].replace(0, np.nan)) if "visitors" in out else 0
    out["cart_rate"] = safe_divide(out["add_to_cart"], out["clicks"].replace(0, np.nan)) if "add_to_cart" in out else 0
    out["cart_to_order_rate"] = safe_divide(out["orders"], out["add_to_cart"].replace(0, np.nan)) if "add_to_cart" in out else 0
    out["pay_rate"] = safe_divide(out["paid_orders"], out["orders"].replace(0, np.nan)) if "paid_orders" in out else 0
    out["refund_order_rate"] = safe_divide(out["refund_orders"], out["signed_orders"].replace(0, np.nan)) if "refund_orders" in out else 0
    out["refund_unit_rate"] = safe_divide(out["refund_units"], out["signed_units_ordered"].replace(0, np.nan)) if "refund_units" in out else 0
    out["gross_profit"] = np.where(out.get("supply_price", 0) > 0, out["sales_amount"] - out["supply_price"] * out["units_ordered"], 0)
    out["gross_margin"] = safe_divide(out["gross_profit"], out["sales_amount"].replace(0, np.nan))
    avg_daily_units = out.groupby("goods_id")["units_ordered"].transform("mean").replace(0, np.nan)
    out["sellable_days"] = safe_divide(out["inventory_qty_api"], avg_daily_units)
    return out


def build_dimension_summary(advanced_df: pd.DataFrame) -> pd.DataFrame:
    """按店铺 / SKU / Goods ID 汇总更多维度指标。"""
    if advanced_df.empty:
        return pd.DataFrame()
    grouped = advanced_df.groupby(["store", "goods_id", "display_sku"], as_index=False).agg(
        product_name=("product_name", "first"),
        impressions=("impressions", "sum"),
        clicks=("clicks", "sum"),
        visitors=("visitors", "sum"),
        add_to_cart=("add_to_cart", "sum"),
        orders=("orders", "sum"),
        paid_orders=("paid_orders", "sum"),
        sales_amount=("sales_amount", "sum"),
        units_ordered=("units_ordered", "sum"),
        refund_orders=("refund_orders", "sum"),
        refund_units=("refund_units", "sum"),
        refund_amount=("refund_amount", "sum"),
        inventory_qty=("inventory_qty_api", "max"),
        gross_profit=("gross_profit", "sum"),
    )
    grouped["ctr"] = safe_divide(grouped["clicks"], grouped["impressions"])
    grouped["cart_rate"] = safe_divide(grouped["add_to_cart"], grouped["clicks"])
    grouped["conversion_rate"] = safe_divide(grouped["orders"], grouped["clicks"])
    grouped["refund_order_rate"] = safe_divide(grouped["refund_orders"], grouped["orders"])
    grouped["gross_margin"] = safe_divide(grouped["gross_profit"], grouped["sales_amount"])
    grouped["sellable_days"] = safe_divide(grouped["inventory_qty"], grouped["units_ordered"] / max(advanced_df["date"].nunique(), 1))
    return grouped.sort_values(["sales_amount", "orders", "impressions"], ascending=[False, False, False])


def build_diagnostic_actions(summary_df: pd.DataFrame) -> pd.DataFrame:
    """生成商品级诊断和动作建议。"""
    if summary_df.empty:
        return pd.DataFrame(columns=["优先级", "诊断类型", "SKU", "Goods ID", "关键指标", "建议动作"])
    rows: list[dict[str, Any]] = []
    for _, r in summary_df.iterrows():
        sku = str(r.get("display_sku", ""))
        gid = str(r.get("goods_id", ""))
        if r["impressions"] >= 5000 and r["ctr"] < 0.015:
            rows.append({"优先级": "高", "诊断类型": "高曝光低点击", "SKU": sku, "Goods ID": gid, "关键指标": f"曝光{r['impressions']:.0f}，CTR {r['ctr']:.2%}", "建议动作": "优先检查主图、标题、价格锚点和活动标识。"})
        if r["clicks"] >= 300 and r["conversion_rate"] < 0.015:
            rows.append({"优先级": "高", "诊断类型": "高点击低转化", "SKU": sku, "Goods ID": gid, "关键指标": f"点击{r['clicks']:.0f}，转化{r['conversion_rate']:.2%}", "建议动作": "排查详情页承接、评价、尺码/规格表达、竞品价格。"})
        if r["conversion_rate"] >= 0.04 and r["impressions"] < 1000:
            rows.append({"优先级": "中", "诊断类型": "低曝光高转化", "SKU": sku, "Goods ID": gid, "关键指标": f"曝光{r['impressions']:.0f}，转化{r['conversion_rate']:.2%}", "建议动作": "适合争取更多资源位或活动流量，先检查库存是否充足。"})
        if r["refund_order_rate"] >= 0.08 and r["orders"] >= 20:
            rows.append({"优先级": "高", "诊断类型": "退货率偏高", "SKU": sku, "Goods ID": gid, "关键指标": f"订单{r['orders']:.0f}，退货率{r['refund_order_rate']:.2%}", "建议动作": "重点复盘质量、尺码、描述一致性和物流破损问题。"})
        if 0 < r["sellable_days"] <= 7:
            rows.append({"优先级": "高", "诊断类型": "库存风险", "SKU": sku, "Goods ID": gid, "关键指标": f"库存{r['inventory_qty']:.0f}，可售{r['sellable_days']:.1f}天", "建议动作": "尽快补货或降低投流，避免爆款断货。"})
        if r["sellable_days"] >= 45 and r["units_ordered"] < 10:
            rows.append({"优先级": "中", "诊断类型": "库存滞销", "SKU": sku, "Goods ID": gid, "关键指标": f"库存{r['inventory_qty']:.0f}，销量{r['units_ordered']:.0f}", "建议动作": "考虑降价、清仓活动或暂停补货。"})
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    priority_order = {"高": 0, "中": 1, "低": 2}
    return result.sort_values(["优先级", "诊断类型"], key=lambda s: s.map(priority_order).fillna(9) if s.name == "优先级" else s).head(100)
