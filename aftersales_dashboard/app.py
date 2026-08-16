from __future__ import annotations

from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import plotly.express as px
import streamlit as st

from aftersales_dashboard.analytics import (
    build_daily_summary,
    build_reason_summary,
    build_return_export_file,
    build_return_summary,
    build_sku_summary,
    filter_return_df,
    format_pct,
    format_return_display_df,
)
from aftersales_dashboard.data_io import (
    DEFAULT_DEMO_DIR,
    build_sales_denominator_df,
    build_order_report_denominator_df,
    clean_mapping_df,
    clean_order_report_df,
    clean_return_df,
    clean_sales_df,
    collect_local_inputs,
    discover_default_data_dir,
    load_order_report_from_bytes,
    load_table_from_bytes,
)


def _inject_style() -> None:
    st.markdown(
        """
        <style>
        :root {
            --after-ink: #17212b;
            --after-muted: #687587;
            --after-line: #d8e0e7;
            --after-panel: #f7f9fb;
            --after-accent: #176b87;
            --after-warn: #bd4b21;
        }
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            max-width: 1500px;
        }
        h1, h2, h3 {
            letter-spacing: 0;
            color: var(--after-ink);
        }
        div[data-testid="stMetric"] {
            background: linear-gradient(180deg, #ffffff 0%, var(--after-panel) 100%);
            border: 1px solid var(--after-line);
            border-radius: 8px;
            padding: 14px 16px;
        }
        div[data-testid="stMetricLabel"] p {
            color: var(--after-muted);
            font-size: 0.86rem;
        }
        div[data-testid="stMetricValue"] {
            color: var(--after-ink);
        }
        .section-note {
            color: var(--after-muted);
            font-size: 0.9rem;
            margin-top: -0.4rem;
            margin-bottom: 0.6rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _collect_uploads(files) -> list[tuple[str, bytes]]:
    return [(item.name, item.getvalue()) for item in files] if files else []


@st.cache_data(show_spinner=False)
def _load_returns(inputs: list[tuple[str, bytes]]) -> pd.DataFrame:
    parts = [clean_return_df(load_table_from_bytes(name, content), name) for name, content in inputs]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


@st.cache_data(show_spinner=False)
def _load_sales_detail(
    sales_inputs: list[tuple[str, bytes]],
    mapping_inputs: list[tuple[str, bytes]],
    order_report_inputs: list[tuple[str, bytes]],
    conversion_basis: str,
) -> tuple[pd.DataFrame, list[str]]:
    messages: list[str] = []
    sales_parts = [clean_sales_df(load_table_from_bytes(name, content), name) for name, content in sales_inputs]
    mapping_parts = [clean_mapping_df(load_table_from_bytes(name, content), name) for name, content in mapping_inputs]
    order_parts = [clean_order_report_df(load_order_report_from_bytes(name, content), name) for name, content in order_report_inputs]
    sales_df = pd.concat(sales_parts, ignore_index=True) if sales_parts else pd.DataFrame()
    mapping_df = pd.concat(mapping_parts, ignore_index=True) if mapping_parts else pd.DataFrame()
    order_df = pd.concat(order_parts, ignore_index=True) if order_parts else pd.DataFrame()
    if not mapping_df.empty:
        mapping_df = mapping_df.drop_duplicates("goods_id")
    if not sales_df.empty:
        messages.append(f"销售分母载入 {len(sales_inputs)} 个文件，共 {len(sales_df):,} 行")
    if not mapping_df.empty:
        messages.append(f"SKU 映射载入 {len(mapping_inputs)} 个文件，共 {len(mapping_df):,} 个 Goods ID")
    if not order_df.empty:
        messages.append(f"TEMU 全部订单报表载入 {len(order_report_inputs)} 个文件，共 {len(order_df):,} 行")
        return build_order_report_denominator_df(order_df), messages
    return build_sales_denominator_df(sales_df, mapping_df, conversion_basis), messages


def _sort_display_df(display_df: pd.DataFrame, field: str, order: str) -> pd.DataFrame:
    if display_df.empty or not field:
        return display_df
    sort_series = display_df[field].astype(str)
    if field in {"申请退款金额", "退还给买家的金额", "退款金额"}:
        sort_series = pd.to_numeric(sort_series.str.replace("MX$", "", regex=False).str.replace(",", "", regex=False), errors="coerce")
    elif field in {"订单维度退货率", "产品件数退货率"}:
        sort_series = pd.to_numeric(sort_series.str.replace("%", "", regex=False), errors="coerce")
    elif field in {"退货数量", "退货退款订单数", "退货退款件数"}:
        sort_series = pd.to_numeric(sort_series.str.replace(",", "", regex=False), errors="coerce")
    else:
        sort_series = sort_series.fillna("")
    return display_df.assign(_sort_key=sort_series).sort_values("_sort_key", ascending=(order == "升序"), na_position="last").drop(columns=["_sort_key"])


def _format_sku_summary(df: pd.DataFrame) -> pd.DataFrame:
    show = df.copy()
    rename = {
        "sku_id": "SKU ID",
        "seller_sku": "商家自定义SKU",
        "product_name": "产品名称",
        "sku_spec": "商品规格",
        "refund_amount": "退款金额",
        "return_order_count": "退货退款订单数",
        "return_unit_count": "退货退款件数",
        "sales_order_count": "已签收订单数",
        "sales_unit_count": "已签收销售件数",
        "order_return_rate": "订单维度退货率",
        "unit_return_rate": "产品件数退货率",
    }
    show = show.rename(columns=rename)
    for col in ["退款金额"]:
        if col in show:
            show[col] = pd.to_numeric(show[col], errors="coerce").fillna(0).map(lambda x: f"MX${x:,.2f}")
    for col in ["退货退款订单数", "退货退款件数", "已签收订单数", "已签收销售件数"]:
        if col in show:
            show[col] = pd.to_numeric(show[col], errors="coerce").fillna(0).map(lambda x: f"{x:,.0f}")
    for col in ["订单维度退货率", "产品件数退货率"]:
        if col in show:
            show[col] = pd.to_numeric(show[col], errors="coerce").fillna(0).map(format_pct)
    return show


def main() -> None:
    st.set_page_config(page_title="产品售后监控看板", layout="wide")
    _inject_style()

    st.title("产品售后监控看板")
    st.caption("SKU 退货退款统计独立版：聚焦售后报表、退货率分母、SKU 风险和原因复盘。")

    with st.sidebar:
        st.header("数据")
        data_source = st.radio("取数方式", ["本地数据", "上传文件"], horizontal=False)
        conversion_basis = st.selectbox("订单口径", ["订单商品数", "买家数", "下单件数"], index=0, help="用于计算订单维度退货率的分母。")

        local_inputs = {"returns": [], "sales": [], "mapping": [], "order_reports": []}
        return_files = sales_files = mapping_files = order_report_files = None
        if data_source == "本地数据":
            local_data_dir = st.text_input("数据目录", value=str(discover_default_data_dir()), help="可填写包含 TEMU 退货 / 全部订单 / sales / mapping 文件的目录。")
            local_inputs = collect_local_inputs(local_data_dir)
            st.caption(
                f"识别到售后 {len(local_inputs['returns'])} 个，"
                f"TEMU 全部订单 {len(local_inputs['order_reports'])} 个，"
                f"销售 {len(local_inputs['sales'])} 个，SKU 映射 {len(local_inputs['mapping'])} 个"
            )
        else:
            return_files = st.file_uploader("上传售后退货报表", type=["csv", "xlsx", "xls"], accept_multiple_files=True)
            order_report_files = st.file_uploader("上传 TEMU 全部订单 / Order report（推荐，用于退货率分母）", type=["csv", "xlsx", "xls"], accept_multiple_files=True)
            sales_files = st.file_uploader("上传销售表（可选，用于退货率分母）", type=["csv", "xlsx", "xls"], accept_multiple_files=True)
            mapping_files = st.file_uploader("上传 SKU 映射表（可选）", type=["csv", "xlsx", "xls"], accept_multiple_files=True)

        st.markdown("---")
        st.caption("售后表必需字段：Order ID、SKU ID。销售表和映射表可选；缺失时仍展示退款金额、订单数和件数。")

    return_inputs = list(local_inputs["returns"]) + _collect_uploads(return_files)
    order_report_inputs = list(local_inputs["order_reports"]) + _collect_uploads(order_report_files)
    sales_inputs = list(local_inputs["sales"]) + _collect_uploads(sales_files)
    mapping_inputs = list(local_inputs["mapping"]) + _collect_uploads(mapping_files)

    if not return_inputs:
        st.info("请先上传售后退货报表，或使用内置演示数据。")
        st.stop()

    try:
        return_df = _load_returns(return_inputs)
        sales_detail_df, load_messages = _load_sales_detail(sales_inputs, mapping_inputs, order_report_inputs, conversion_basis)
    except Exception as exc:
        st.error(f"数据读取或清洗失败：{exc}")
        st.stop()

    if return_df.empty:
        st.warning("售后报表清洗后没有可用数据，请检查 Order ID / SKU ID 是否为空。")
        st.stop()

    for message in load_messages:
        st.success(message)
    st.success(f"售后退货报表载入 {len(return_inputs)} 个文件，共 {len(return_df):,} 行")

    valid_sales_stores = sorted({
        str(x).strip() for x in sales_detail_df.get("store", pd.Series(dtype="object")).dropna().astype(str).tolist()
        if str(x).strip() and str(x).strip().casefold() not in {"nan", "none", "null", "<na>", "未分类店铺"}
    })
    if valid_sales_stores and "未识别店铺" in set(return_df["store"].astype(str)):
        with st.sidebar:
            assignment = st.selectbox(
                "未识别售后店铺归属",
                ["保持未识别"] + [f"全部归入：{store}" for store in valid_sales_stores],
                index=0,
            )
        if assignment.startswith("全部归入："):
            return_df = return_df.copy()
            return_df.loc[return_df["store"].astype(str) == "未识别店铺", "store"] = assignment.split("：", 1)[1]

    requested_dates = return_df["requested_date"].dropna()
    if requested_dates.empty:
        st.error("售后报表缺少可识别的申请日期，暂无法进行日期筛选。")
        st.stop()
    min_date = requested_dates.min().date()
    max_date = requested_dates.max().date()
    default_start_date, default_end_date = min_date, max_date
    denominator_dates = sales_detail_df["date"].dropna() if not sales_detail_df.empty and "date" in sales_detail_df.columns else pd.Series(dtype="datetime64[ns]")
    has_denominator_date_overlap = True
    if not denominator_dates.empty:
        denominator_min_date = denominator_dates.min().date()
        denominator_max_date = denominator_dates.max().date()
        default_start_date = max(min_date, denominator_min_date)
        default_end_date = min(max_date, denominator_max_date)
        has_denominator_date_overlap = default_start_date <= default_end_date
        if not has_denominator_date_overlap:
            default_start_date, default_end_date = min_date, max_date

    st.markdown("## 筛选")
    f1, f2, f3 = st.columns([1.0, 1.35, 1.65])
    with f1:
        store_options = ["全部店铺"] + sorted({s for s in return_df["store"].dropna().astype(str).tolist() if s.strip() and s.strip().casefold() not in {"nan", "none", "null", "<na>"}})
        selected_store = st.selectbox("店铺", store_options, index=0)
    with f2:
        date_range = st.date_input("申请日期范围", value=(default_start_date, default_end_date), min_value=min_date, max_value=max_date)
    with f3:
        search_text = st.text_input("精确查询", placeholder="订单ID / 售后单ID / SKU ID / 运单号 / 申请理由关键词")

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = default_start_date, default_end_date
    if not has_denominator_date_overlap and not sales_detail_df.empty:
        st.warning("售后申请日期与订单分母日期没有重叠，退货率分母可能为 0；请检查文件日期范围。")

    scoped_for_options = filter_return_df(return_df, store=selected_store, start_date=start_date, end_date=end_date)
    f4, f5, f6, f7 = st.columns([1.25, 1.0, 1.0, 1.5])
    with f4:
        sku_options = sorted(scoped_for_options["sku_id"].dropna().astype(str).unique().tolist())
        selected_skus = st.multiselect("SKU ID", sku_options, default=[])
    with f5:
        selected_statuses = st.multiselect("售后状态", ["尚未退款", "已退款", "已拒绝"], default=[])
    with f6:
        service_options = sorted(scoped_for_options["service_type"].dropna().astype(str).loc[lambda x: x.str.strip() != ""].unique().tolist())
        selected_service_types = st.multiselect("售后类型", service_options, default=[])
    with f7:
        reason_options = sorted(scoped_for_options["reason_for_request"].dropna().astype(str).loc[lambda x: x.str.strip() != ""].unique().tolist())
        selected_reasons = st.multiselect("申请理由", reason_options, default=[])

    f8, _ = st.columns([1.25, 3.75])
    with f8:
        selected_first_reasons = st.multiselect("一级原因", ["配送问题", "客户问题", "发货问题", "产品问题", "配送和产品问题", "其他"], default=[])

    filtered = filter_return_df(
        return_df,
        store=selected_store,
        sku_ids=selected_skus,
        statuses=selected_statuses,
        reasons=selected_reasons,
        first_reasons=selected_first_reasons,
        service_types=selected_service_types,
        start_date=start_date,
        end_date=end_date,
        search_text=search_text,
    )
    summary = build_return_summary(filtered, sales_detail_df, start_date=start_date, end_date=end_date, store=selected_store, denominator_skus=selected_skus)
    sku_summary = build_sku_summary(filtered, sales_detail_df, start_date=start_date, end_date=end_date, store=selected_store)
    reason_summary = build_reason_summary(filtered)
    daily_summary = build_daily_summary(filtered)

    st.markdown("## 总览")
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    kpi1.metric("退款金额", f"MX${summary['refund_amount']:,.2f}")
    kpi2.metric("退货退款订单数", f"{summary['return_order_count']:,}")
    kpi3.metric("退货退款件数", f"{summary['return_unit_count']:,.0f}")
    kpi4.metric("订单维度退货率", format_pct(summary["order_return_rate"]))
    kpi5.metric("产品件数退货率", format_pct(summary["unit_return_rate"]))
    if sales_detail_df.empty:
        st.caption("当前未载入销售表，退货率分母为 0；可上传销售表和 SKU 映射表补齐订单/件数分母。")
    else:
        suffix = "" if summary.get("signed_status_available", False) else " 当前销售表未识别到订单/物流状态字段，系统暂按销售表总量作为分母。"
        st.caption(
            f"分母来自销售数据：已签收订单数 {summary['sales_order_count']:,.0f}，"
            f"已签收销售件数 {summary['sales_unit_count']:,.0f}。若 SKU 可匹配，系统会自动缩小到当前售后 SKU 范围。{suffix}"
        )

    chart_col1, chart_col2 = st.columns([1.35, 1.0])
    with chart_col1:
        st.markdown("### SKU 风险排行")
        if sku_summary.empty:
            st.info("当前筛选范围没有可展示的 SKU 汇总。")
        else:
            chart_df = sku_summary.head(20).copy()
            fig = px.bar(
                chart_df,
                x="sku_id",
                y="refund_amount",
                color="return_order_count",
                labels={"sku_id": "SKU ID", "refund_amount": "退款金额", "return_order_count": "退货退款订单数"},
                color_continuous_scale=["#8fb9aa", "#176b87", "#bd4b21"],
            )
            fig.update_layout(height=360, margin=dict(l=8, r=8, t=24, b=8), xaxis_tickangle=-30, coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)
    with chart_col2:
        st.markdown("### 一级原因分布")
        if reason_summary.empty:
            st.info("当前筛选范围没有可展示的原因汇总。")
        else:
            fig = px.bar(
                reason_summary,
                x="return_order_count",
                y="first_reason",
                orientation="h",
                labels={"return_order_count": "退货退款订单数", "first_reason": "一级原因"},
                color="refund_amount",
                color_continuous_scale=["#f2c078", "#bd4b21"],
            )
            fig.update_layout(height=360, margin=dict(l=8, r=8, t=24, b=8), yaxis={"categoryorder": "total ascending"}, coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)

    trend_col, status_col = st.columns([1.35, 1.0])
    with trend_col:
        st.markdown("### 每日售后趋势")
        if daily_summary.empty:
            st.info("当前筛选范围没有每日趋势。")
        else:
            fig = px.line(
                daily_summary,
                x="requested_date",
                y=["return_order_count", "return_unit_count", "refund_amount"],
                markers=True,
                labels={"requested_date": "申请日期", "value": "数值", "variable": "指标"},
            )
            fig.update_layout(height=340, margin=dict(l=8, r=8, t=24, b=8), legend_title_text="")
            st.plotly_chart(fig, use_container_width=True)
    with status_col:
        st.markdown("### 售后状态")
        status_df = filtered.groupby("return_status", as_index=False).agg(return_count=("order_id", "nunique")) if not filtered.empty else pd.DataFrame()
        if status_df.empty:
            st.info("当前筛选范围没有售后状态。")
        else:
            fig = px.pie(status_df, names="return_status", values="return_count", hole=0.56, color_discrete_sequence=["#176b87", "#8fb9aa", "#bd4b21", "#f2c078"])
            fig.update_layout(height=340, margin=dict(l=8, r=8, t=24, b=8), showlegend=True)
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("## SKU 汇总")
    st.dataframe(_format_sku_summary(sku_summary), use_container_width=True, hide_index=True)

    st.markdown("## 售后明细")
    display_df = format_return_display_df(filtered, summary)
    sortable_fields = [
        "申请日期", "下单日期", "店铺", "SKU ID", "售后单状态", "申请理由", "一级原因",
        "退货数量", "申请退款金额", "退还给买家的金额", "订单维度退货率", "产品件数退货率",
        "退款金额", "退货退款订单数", "退货退款件数",
    ]
    sortable_fields = [c for c in sortable_fields if c in display_df.columns]
    s1, s2, s3 = st.columns([1.2, 1.0, 2.3])
    with s1:
        sort_field = st.selectbox("排序字段", sortable_fields, index=0 if sortable_fields else None)
    with s2:
        sort_order = st.selectbox("排序方式", ["降序", "升序"], index=0)
    with s3:
        st.markdown('<div class="section-note">表格和导出均受当前筛选条件影响。</div>', unsafe_allow_html=True)
    display_df = _sort_display_df(display_df, sort_field, sort_order)
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.download_button(
        label="导出售后监控 Excel",
        data=build_return_export_file(display_df, _format_sku_summary(sku_summary), reason_summary, daily_summary),
        file_name="产品售后监控_SKU退货退款统计.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
