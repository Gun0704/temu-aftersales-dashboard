from __future__ import annotations

import re

import streamlit as st


def extract_goods_ids(raw_text: str) -> list[str]:
    """Extract Goods IDs from arbitrary pasted text, preserving first-seen order."""
    if not raw_text:
        return []
    candidates = re.findall(r"\d{6,}", str(raw_text))
    seen = set()
    ordered = []
    for item in candidates:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def render_metric_card(
    title: str,
    value: str,
    group_class: str,
    delta_text: str | None = None,
    good: bool | None = None,
    tooltip_html: str | None = None,
) -> None:
    delta_html = ""
    if delta_text:
        status_class = "neutral"
        if good is True:
            status_class = "good"
        elif good is False:
            status_class = "bad"
        delta_html = f'<div class="metric-delta {status_class}">{delta_text}</div>'
    tooltip_block = ""
    if tooltip_html:
        tooltip_block = f'<div class="metric-tooltip">{tooltip_html}</div>'
    html = (
        f'<div class="metric-card {group_class}">'
        f'<div class="metric-title">{title}</div>'
        f'<div class="metric-value">{value}</div>'
        f"{delta_html}"
        f"{tooltip_block}"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def build_metric_tooltip(definition: str, formula: str, recent_value: str) -> str:
    return f"<b>指标定义</b><br>{definition}<br><br><b>计算逻辑</b><br>{formula}<br><br><b>近7天均值</b><br>{recent_value}"


def inject_metric_card_style() -> None:
    st.markdown(
        """
<style>
.metric-card {
    position: relative;
    border-radius: 16px;
    padding: 16px 18px;
    min-height: 132px;
    border: 1px solid rgba(15, 23, 42, 0.08);
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
    background: #ffffff;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.metric-card:hover { transform: translateY(-2px); box-shadow: 0 10px 24px rgba(15, 23, 42, 0.10); }
.metric-card.flow { background: linear-gradient(180deg, #eef6ff 0%, #ffffff 100%); }
.metric-card.conv { background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%); }
.metric-card.sales { background: linear-gradient(180deg, #eefbf3 0%, #ffffff 100%); }
.metric-title {
    color: #334155;
    font-size: 0.96rem;
    margin-bottom: 14px;
    font-weight: 600;
}
.metric-value {
    color: #0f172a;
    font-size: 1.95rem;
    font-weight: 700;
    line-height: 1.1;
    margin-bottom: 10px;
}
.metric-delta {
    display: inline-block;
    padding: 4px 10px;
    border-radius: 999px;
    font-size: 0.86rem;
    font-weight: 600;
}
.metric-delta.good { color: #15803d; background: #dcfce7; }
.metric-delta.bad { color: #b91c1c; background: #fee2e2; }
.metric-delta.neutral { color: #475569; background: #e2e8f0; }
.goods-id-help { font-size: 0.85rem; color: #64748b; margin-top: 6px; }
.metric-tooltip {
    display: none;
    position: absolute;
    left: 12px;
    right: 12px;
    bottom: calc(100% + 10px);
    z-index: 999;
    padding: 12px 14px;
    border-radius: 12px;
    background: rgba(15, 23, 42, 0.96);
    color: #f8fafc;
    font-size: 0.82rem;
    line-height: 1.5;
    box-shadow: 0 12px 30px rgba(15, 23, 42, 0.24);
}
.metric-tooltip b { color: #ffffff; }
.metric-card:hover .metric-tooltip { display: block; }
</style>
""",
        unsafe_allow_html=True,
    )
