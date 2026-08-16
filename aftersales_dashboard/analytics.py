from __future__ import annotations

import io
import re
from typing import Iterable

import pandas as pd

COLUMN_RENAME = {
    "store": "店铺",
    "return_id": "售后单ID",
    "order_id": "订单ID",
    "return_status": "售后单状态",
    "sku_id": "SKU ID",
    "reason_for_request": "申请理由",
    "return_quantity": "退货数量",
    "amount_request_to_refund": "申请退款金额",
    "amount_refund_to_buyer": "退还给买家的金额",
    "order_date": "下单日期",
    "requested_date": "申请日期",
    "service_type": "售后类型",
    "first_reason": "一级原因",
    "order_return_rate": "订单维度退货率",
    "unit_return_rate": "产品件数退货率",
    "refund_amount_metric": "退款金额",
    "return_order_count_metric": "退货退款订单数",
    "return_unit_count_metric": "退货退款件数",
}


def filter_return_df(
    return_df: pd.DataFrame,
    store: str = "全部店铺",
    sku_ids: Iterable[str] | None = None,
    statuses: Iterable[str] | None = None,
    reasons: Iterable[str] | None = None,
    first_reasons: Iterable[str] | None = None,
    service_types: Iterable[str] | None = None,
    start_date=None,
    end_date=None,
    search_text: str = "",
) -> pd.DataFrame:
    df = return_df.copy()
    if df.empty:
        return df
    if store and store != "全部店铺":
        df = df[df["store"].astype(str) == str(store)]
    if start_date is not None and end_date is not None:
        df = df[(df["requested_date"].dt.date >= start_date) & (df["requested_date"].dt.date <= end_date)]

    for col, vals in [
        ("sku_id", sku_ids),
        ("return_status", statuses),
        ("reason_for_request", reasons),
        ("first_reason", first_reasons),
        ("service_type", service_types),
    ]:
        selected = [str(x) for x in (vals or []) if str(x).strip() and str(x) != "全部"]
        if selected:
            df = df[df[col].astype(str).isin(selected)]

    keyword = str(search_text or "").strip().casefold()
    if keyword:
        mask = pd.Series(False, index=df.index)
        for col in ["return_id", "order_id", "sku_id", "reason_for_request", "tracking_number"]:
            if col in df.columns:
                mask = mask | df[col].astype(str).str.casefold().str.contains(re.escape(keyword), na=False)
        df = df[mask]
    return df.copy()


def _denominator_sales(detail_df: pd.DataFrame, return_scope: pd.DataFrame, start_date, end_date, store: str) -> tuple[float, float, bool]:
    denominator_skus = None
    if return_scope is not None and not return_scope.empty:
        denominator_skus = set(return_scope["sku_id"].astype(str).dropna().unique().tolist())
    return _denominator_sales_for_skus(detail_df, denominator_skus, start_date, end_date, store)


def _denominator_sales_for_skus(detail_df: pd.DataFrame, sku_ids: Iterable[str] | None, start_date, end_date, store: str) -> tuple[float, float, bool]:
    if detail_df is None or detail_df.empty:
        return 0.0, 0.0, False

    base = detail_df.copy()
    if start_date is not None and end_date is not None:
        base = base[(base["date"].dt.date >= start_date) & (base["date"].dt.date <= end_date)]
    if store and store != "全部店铺" and "store" in base.columns:
        base = base[base["store"].astype(str) == str(store)]
    selected_skus = {str(x) for x in (sku_ids or []) if str(x).strip()}
    if selected_skus and "display_sku" in base.columns:
        matched = base[base["display_sku"].astype(str).isin(selected_skus)]
        if not matched.empty:
            base = matched

    signed_units_col = "signed_units_ordered" if "signed_units_ordered" in base.columns else "units_ordered"
    if "signed_order_ids" in base.columns:
        order_ids = set()
        for value in base["signed_order_ids"]:
            if isinstance(value, set):
                order_ids.update(str(x) for x in value if str(x).strip())
            elif isinstance(value, (list, tuple)):
                order_ids.update(str(x) for x in value if str(x).strip())
        orders = float(len(order_ids))
    else:
        signed_orders_col = "signed_orders" if "signed_orders" in base.columns else "orders"
        orders = float(pd.to_numeric(base.get(signed_orders_col, 0), errors="coerce").fillna(0).sum())
    units = float(pd.to_numeric(base.get(signed_units_col, 0), errors="coerce").fillna(0).sum())
    signed_status_available = bool(pd.to_numeric(base.get("status_available_count", 0), errors="coerce").fillna(0).sum() > 0) if not base.empty else False
    return orders, units, signed_status_available


def build_return_summary(return_scope: pd.DataFrame, detail_df: pd.DataFrame, start_date=None, end_date=None, store: str = "全部店铺", denominator_skus: Iterable[str] | None = None) -> dict:
    sales_orders, sales_units, signed_status_available = _denominator_sales_for_skus(detail_df, denominator_skus, start_date, end_date, store)
    if return_scope.empty:
        return {
            "refund_amount": 0.0,
            "return_order_count": 0,
            "return_unit_count": 0.0,
            "sales_order_count": sales_orders,
            "sales_unit_count": sales_units,
            "signed_status_available": signed_status_available,
            "order_return_rate": 0.0,
            "unit_return_rate": 0.0,
        }

    effective = return_scope[return_scope["return_status"] != "已拒绝"].copy()
    refund_amount = float(pd.to_numeric(return_scope["amount_refund_to_buyer"], errors="coerce").fillna(0).sum())
    return_order_count = int(effective["order_id"].nunique())
    return_unit_count = float(pd.to_numeric(effective["return_quantity"], errors="coerce").fillna(0).sum())
    return {
        "refund_amount": refund_amount,
        "return_order_count": return_order_count,
        "return_unit_count": return_unit_count,
        "sales_order_count": sales_orders,
        "sales_unit_count": sales_units,
        "signed_status_available": signed_status_available,
        "order_return_rate": return_order_count / sales_orders if sales_orders else 0.0,
        "unit_return_rate": return_unit_count / sales_units if sales_units else 0.0,
    }


def build_sku_summary(return_scope: pd.DataFrame, sales_detail_df: pd.DataFrame, start_date=None, end_date=None, store: str = "全部店铺") -> pd.DataFrame:
    if return_scope.empty:
        return pd.DataFrame(columns=["sku_id", "refund_amount", "return_order_count", "return_unit_count", "order_return_rate", "unit_return_rate"])

    effective = return_scope[return_scope["return_status"] != "已拒绝"].copy()
    base = effective.groupby("sku_id", as_index=False).agg(
        return_order_count=("order_id", "nunique"),
        return_unit_count=("return_quantity", "sum"),
    )
    refund = return_scope.groupby("sku_id", as_index=False).agg(refund_amount=("amount_refund_to_buyer", "sum"))
    summary = base.merge(refund, on="sku_id", how="outer").fillna(0)

    denominators = []
    for sku in summary["sku_id"].astype(str):
        scope = return_scope[return_scope["sku_id"].astype(str) == sku]
        orders, units, _ = _denominator_sales(sales_detail_df, scope, start_date, end_date, store)
        denominators.append((sku, orders, units))
    denom_df = pd.DataFrame(denominators, columns=["sku_id", "sales_order_count", "sales_unit_count"])
    summary = summary.merge(denom_df, on="sku_id", how="left")
    if sales_detail_df is not None and not sales_detail_df.empty:
        info_cols = [c for c in ["display_sku", "seller_sku", "product_name", "sku_spec"] if c in sales_detail_df.columns]
        if info_cols:
            sku_info = (
                sales_detail_df[info_cols]
                .rename(columns={"display_sku": "sku_id"})
                .drop_duplicates("sku_id")
            )
            summary = summary.merge(sku_info, on="sku_id", how="left")
    order_denominator = summary["sales_order_count"].where(summary["sales_order_count"] != 0)
    unit_denominator = summary["sales_unit_count"].where(summary["sales_unit_count"] != 0)
    summary["order_return_rate"] = summary["return_order_count"] / order_denominator
    summary["unit_return_rate"] = summary["return_unit_count"] / unit_denominator
    return summary.fillna(0).sort_values(["refund_amount", "return_order_count"], ascending=[False, False])


def build_reason_summary(return_scope: pd.DataFrame) -> pd.DataFrame:
    if return_scope.empty:
        return pd.DataFrame(columns=["first_reason", "return_order_count", "return_unit_count", "refund_amount"])
    effective = return_scope[return_scope["return_status"] != "已拒绝"].copy()
    base = effective.groupby("first_reason", as_index=False).agg(
        return_order_count=("order_id", "nunique"),
        return_unit_count=("return_quantity", "sum"),
    )
    refund = return_scope.groupby("first_reason", as_index=False).agg(refund_amount=("amount_refund_to_buyer", "sum"))
    return base.merge(refund, on="first_reason", how="outer").fillna(0).sort_values("return_order_count", ascending=False)


def build_daily_summary(return_scope: pd.DataFrame) -> pd.DataFrame:
    if return_scope.empty:
        return pd.DataFrame(columns=["requested_date", "return_order_count", "return_unit_count", "refund_amount"])
    effective = return_scope[return_scope["return_status"] != "已拒绝"].copy()
    base = effective.groupby("requested_date", as_index=False).agg(
        return_order_count=("order_id", "nunique"),
        return_unit_count=("return_quantity", "sum"),
    )
    refund = return_scope.groupby("requested_date", as_index=False).agg(refund_amount=("amount_refund_to_buyer", "sum"))
    return base.merge(refund, on="requested_date", how="outer").fillna(0).sort_values("requested_date")


def format_pct(value: float) -> str:
    return f"{float(value) * 100:.2f}%"


def format_return_display_df(return_scope: pd.DataFrame, summary: dict) -> pd.DataFrame:
    if return_scope.empty:
        return pd.DataFrame(columns=list(COLUMN_RENAME.values()))

    show = return_scope.copy()
    show["order_return_rate"] = summary.get("order_return_rate", 0.0)
    show["unit_return_rate"] = summary.get("unit_return_rate", 0.0)
    show["refund_amount_metric"] = summary.get("refund_amount", 0.0)
    show["return_order_count_metric"] = summary.get("return_order_count", 0)
    show["return_unit_count_metric"] = summary.get("return_unit_count", 0.0)
    cols = [
        "store", "return_id", "order_id", "return_status", "sku_id", "reason_for_request",
        "return_quantity", "amount_request_to_refund", "amount_refund_to_buyer",
        "order_date", "requested_date", "service_type", "first_reason",
        "order_return_rate", "unit_return_rate", "refund_amount_metric",
        "return_order_count_metric", "return_unit_count_metric",
    ]
    show = show[[c for c in cols if c in show.columns]].rename(columns=COLUMN_RENAME)
    for date_col in ["下单日期", "申请日期"]:
        if date_col in show.columns:
            show[date_col] = pd.to_datetime(show[date_col], errors="coerce").dt.strftime("%Y-%m-%d")
    for money_col in ["申请退款金额", "退还给买家的金额", "退款金额"]:
        if money_col in show.columns:
            show[money_col] = pd.to_numeric(show[money_col], errors="coerce").fillna(0).map(lambda x: f"MX${x:,.2f}")
    for qty_col in ["退货数量", "退货退款件数"]:
        if qty_col in show.columns:
            show[qty_col] = pd.to_numeric(show[qty_col], errors="coerce").fillna(0).map(lambda x: f"{x:,.0f}")
    for pct_col in ["订单维度退货率", "产品件数退货率"]:
        if pct_col in show.columns:
            show[pct_col] = pd.to_numeric(show[pct_col], errors="coerce").fillna(0).map(format_pct)
    return show


def build_return_export_file(display_df: pd.DataFrame, sku_summary: pd.DataFrame, reason_summary: pd.DataFrame, daily_summary: pd.DataFrame) -> bytes:
    desc_df = pd.DataFrame({
        "字段": ["退款金额", "退货退款订单数", "退货退款件数", "订单维度退货率", "产品件数退货率"],
        "说明": ["退还给买家的金额总和", "筛选范围内非拒绝售后订单去重计数", "筛选范围内非拒绝售后退货数量求和", "退货退款订单数 / 已签收订单数", "退货退款件数 / 已签收销售件数"],
    })
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        display_df.to_excel(writer, index=False, sheet_name="售后明细")
        sku_summary.to_excel(writer, index=False, sheet_name="SKU汇总")
        reason_summary.to_excel(writer, index=False, sheet_name="原因汇总")
        daily_summary.to_excel(writer, index=False, sheet_name="每日趋势")
        desc_df.to_excel(writer, index=False, sheet_name="字段说明")

        workbook = writer.book
        header_fmt = workbook.add_format({"bold": True, "bg_color": "#D9EAF7", "border": 1, "align": "center", "valign": "vcenter"})
        wrap_fmt = workbook.add_format({"text_wrap": True, "valign": "top"})
        for sheet_name, df in [
            ("售后明细", display_df),
            ("SKU汇总", sku_summary),
            ("原因汇总", reason_summary),
            ("每日趋势", daily_summary),
            ("字段说明", desc_df),
        ]:
            ws = writer.sheets[sheet_name]
            for idx, col in enumerate(df.columns):
                ws.write(0, idx, col, header_fmt)
                col_data = df.iloc[:, idx] if idx < len(df.columns) else pd.Series(dtype="object")
                width_quantile = pd.to_numeric(col_data.astype(str).str.len(), errors="coerce").dropna().quantile(0.9) if not df.empty else pd.NA
                content_width = int(width_quantile) if pd.notna(width_quantile) else 12
                ws.set_column(idx, idx, max(12, min(36, max(len(str(col)) + 2, content_width))), wrap_fmt if col in {"申请理由", "说明"} else None)
            ws.autofilter(0, 0, len(df), max(len(df.columns) - 1, 0))
            ws.freeze_panes(1, 0)
    return output.getvalue()
