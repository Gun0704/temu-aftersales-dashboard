from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re
from typing import Iterable

import numpy as np
import pandas as pd

try:
    import streamlit as st
except ModuleNotFoundError:
    st = None

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent
DEFAULT_DEMO_DIR = PACKAGE_ROOT / "data" / "demo"
SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}

STORE_KEYS = ["Store", "店铺", "Shop", "shop", "店铺名称"]
RETURN_ID_KEYS = ["Return ID", "退货单ID", "售后单ID", "售后编号"]
ORDER_ID_KEYS = ["Order ID", "订单ID", "订单号"]
RETURN_STATUS_KEYS = ["Return status", "售后单状态", "退货状态", "退款状态"]
SKU_ID_KEYS = ["SKU ID", "SKU", "sku id", "sku", "商品SKU ID"]
REASON_KEYS = ["Reason for request", "申请理由", "退货原因", "退款原因"]
RETURN_QTY_KEYS = ["Return quantity", "退货数量", "退款数量", "数量"]
AMOUNT_REQUEST_KEYS = ["Amount request to refund", "申请退款金额", "退款申请金额"]
AMOUNT_REFUND_KEYS = ["Amount refund to buyer", "退还给买家的金额", "实际退款金额", "退款金额"]
ORDER_DATE_KEYS = ["Order date", "下单日期", "订单日期"]
REQUESTED_DATE_KEYS = ["Requested date", "申请日期", "发起时间", "申请时间"]
COURIER_KEYS = ["Courier", "承运商"]
TRACKING_KEYS = ["Tracking number", "运单号", "物流单号"]
SERVICE_TYPE_KEYS = ["Types of after-sales service", "售后类型", "售后服务类型"]
RETURNLESS_KEYS = ["Returnless resolution", "仅退款解决方案", "无需退货处理"]
COST_RESPONSIBLE_KEYS = ["Responsible for covering after-sale cost", "售后费用承担方", "责任方"]

SALES_DATE_KEYS = ["Date", "日期"]
SALES_ID_KEYS = ["Goods ID", "GoodsID", "商品ID", "goods id"]
SALES_NAME_KEYS = ["Goods Name", "商品名", "商品名称"]
SALES_STATUS_KEYS = [
    "Order status", "order status", "order_status", "订单状态", "订单状态名称",
    "Delivery status", "delivery status", "delivery_status", "物流状态", "配送状态",
    "Status", "status", "签收状态", "履约状态", "包裹状态",
]
SALES_FIELD_MAP = {
    "sales": ["sales", "Sales", "销售额", "成交金额", "Base price sales"],
    "buyers": ["Buyers", "buyers", "买家数", "支付买家数"],
    "total_order_items": ["Total order items", "订单商品数", "订单数"],
    "units_ordered": ["Units ordered", "下单件数", "销量", "件数"],
    "avg_sales_per_order_item": ["Avg. sales per order item", "平均每个订单商品销售额"],
}
SIGNED_STATUS_PATTERNS = [
    "已签收", "已完成", "已送达", "已收货", "交易成功",
    "delivered", "completed", "received", "signed", "signed for",
]

MAP_ID_KEYS = ["Goods ID", "GoodsID", "商品ID", "goods id"]
MAP_SKU_KEYS = ["SKU", "sku", "Sku"]
MAP_STORE_KEYS = ["Store", "店铺", "Shop", "shop", "店铺名称"]
MAP_PRODUCT_KEYS = ["Product name", "Goods Name", "商品名称", "商品名"]

ORDER_REPORT_HEADER_KEYS = ["订单号", "Order ID", "SKU编号", "SKU ID", "购买数量", "Quantity"]
ORDER_ID_REPORT_KEYS = ["订单号", "Order ID", "订单ID"]
ORDER_STATUS_REPORT_KEYS = ["订单状态", "Order status", "订单商品状态"]
ORDER_ITEM_STATUS_REPORT_KEYS = ["订单商品状态", "Order item status"]
LOGISTICS_STATUS_REPORT_KEYS = ["物流状态", "Delivery status", "Logistics status"]
ORDER_ITEM_ID_REPORT_KEYS = ["商品订单编号", "Order item ID", "订单商品ID"]
ORDER_SKU_ID_REPORT_KEYS = ["SKU编号", "SKU ID", "商品SKU ID"]
SELLER_SKU_REPORT_KEYS = ["商家自定义SKU", "Seller SKU", "Merchant SKU"]
ORDER_PRODUCT_REPORT_KEYS = ["产品名称", "Product name", "按客户订单的产品名称"]
ORDER_SPEC_REPORT_KEYS = ["商品规格", "SKU", "Variation"]
ORDER_QTY_REPORT_KEYS = ["购买数量", "Quantity purchased", "quantity", "购买件数"]
ORDER_DATE_REPORT_KEYS = ["购买日期", "Purchase date", "Order date", "下单日期"]

STATUS_MAP = {
    "refunded": "已退款",
    "not refunded yet": "尚未退款",
    "denied": "已拒绝",
    "rejected": "已拒绝",
    "closed": "已拒绝",
}
SERVICE_TYPE_MAP = {"returnless refund": "仅退款", "return and refund": "退货退款"}
FIRST_REASON_RULES = [
    ("配送和产品问题", r"product\s+and\s+shipping\s+box\s+both\s+damaged|商品和运输包装均损坏"),
    ("配送问题", r"haven'?t\s+received|not\s+received|package\s+not\s+received|delivery\s+failed|派送失败|还没有收到包裹|未收到"),
    ("客户问题", r"no\s+longer\s+need|price\s+difference|inaccurate\s+website\s+description|网站描述不准确|不再需要|降价补差"),
    ("发货问题", r"wrong\s+item|missing\s+item|错发|少件|漏发"),
    ("产品问题", r"defective|doesn'?t\s+work|broken\s+parts|missing\s+or\s+broken\s+parts|damaged\s+but\s+shipping\s+box|product\s+damaged.*shipping\s+box\s+ok|商品损坏|有缺陷|无法使用|缺少配件|配件损坏"),
]


def resolve_path(path_text: str | Path) -> Path:
    path = Path(path_text).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def discover_default_data_dir() -> Path:
    for directory in sorted([p for p in PROJECT_ROOT.iterdir() if p.is_dir()]):
        if directory == PACKAGE_ROOT:
            continue
        names = [p.name.lower() for p in directory.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
        has_temu_returns = any("temu" in name and any(key in name for key in ["退货", "return", "refund"]) for name in names)
        has_order_report = any(any(key in name for key in ["全部订单", "order report", "all orders", "all-orders"]) for name in names)
        if has_temu_returns and has_order_report:
            return directory
    return DEFAULT_DEMO_DIR


def infer_store_from_filename(filename: str) -> str:
    raw_path = Path(filename or "")
    parent_name = raw_path.parent.name if raw_path.parent.name not in {"", "."} else ""
    stem = re.sub(r"\.[^.]+$", "", raw_path.name or filename or "")
    stem = stem.replace("_", "-").strip()
    if not stem:
        return parent_name or "未分类店铺"
    parts = [p for p in stem.split("-") if p]
    first = parts[0] if parts else stem
    generic = (
        first.casefold() in {"return", "returns", "refund", "order", "orders", "order report", "all orders"}
        or first.startswith("退货Temu")
        or first.startswith("退货")
        or first.startswith("Temu全部订单")
        or first.startswith("全部订单")
    )
    if generic and parent_name:
        return parent_name
    return first


def get_first_existing_column(df: pd.DataFrame, candidates: Iterable[str]) -> str | None:
    lower_map = {str(c).strip().lower(): c for c in df.columns}
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
        found = lower_map.get(str(candidate).strip().lower())
        if found:
            return found
    return None


def parse_numeric_series(series: pd.Series | None) -> pd.Series:
    if series is None:
        return pd.Series(dtype=float)
    cleaned = (
        series.astype(str).str.strip()
        .replace({"": np.nan, "None": np.nan, "nan": np.nan, "--": np.nan, "N/A": np.nan, "n/a": np.nan})
        .str.replace(",", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.replace("MX$", "", regex=False)
        .str.replace("US$", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace("￥", "", regex=False)
        .str.replace("¥", "", regex=False)
        .str.replace(r"[A-Za-z]+", "", regex=True)
        .str.replace(r"[^\d.\-]", "", regex=True)
    )
    return pd.to_numeric(cleaned, errors="coerce").fillna(0)


def parse_date_series(series: pd.Series | None) -> pd.Series:
    if series is None:
        return pd.Series(dtype="datetime64[ns]")
    text = (
        series.astype(str).str.strip()
        .replace({"": np.nan, "None": np.nan, "nan": np.nan, "NaN": np.nan, "<NA>": np.nan})
        .str.replace(r"\s+[A-Z]{2,5}\(UTC[+-]\d+\)$", "", regex=True)
        .str.replace(r"\s+[A-Z]{2,5}$", "", regex=True)
        .str.replace(r"\s+UTC[+-]?\d+$", "", regex=True)
        .str.replace(r"(\d{4})年(\d{1,2})月(\d{1,2})日", r"\1-\2-\3", regex=True)
    )
    parsed = pd.to_datetime(text, errors="coerce", dayfirst=False)
    excel_like = pd.to_numeric(series, errors="coerce")
    if parsed.isna().mean() > 0.6 and excel_like.notna().mean() > 0.4:
        parsed_excel = pd.to_datetime("1899-12-30") + pd.to_timedelta(excel_like, unit="D")
        parsed = parsed.fillna(parsed_excel)
    return parsed.dt.floor("D")


def parse_return_datetime(series: pd.Series | None) -> pd.Series:
    if series is None:
        return pd.Series(dtype="datetime64[ns]")
    return parse_date_series(series)


def cache_data(*args, **kwargs):
    if st is not None:
        return st.cache_data(*args, **kwargs)
    if args and callable(args[0]) and len(args) == 1 and not kwargs:
        return args[0]

    def decorator(func):
        return func

    return decorator


@cache_data(show_spinner=False)
def load_table_from_bytes(file_name: str, file_bytes: bytes) -> pd.DataFrame:
    suffix = file_name.lower().split(".")[-1]
    bio = BytesIO(file_bytes)
    if suffix == "csv":
        last_error: Exception | None = None
        for encoding in ("utf-8", "utf-8-sig", "latin1", "cp1252"):
            try:
                bio.seek(0)
                return pd.read_csv(bio, encoding=encoding)
            except Exception as exc:
                last_error = exc
        raise ValueError(f"CSV 读取失败：{last_error}")
    return pd.read_excel(bio)


@cache_data(show_spinner=False)
def load_order_report_from_bytes(file_name: str, file_bytes: bytes) -> pd.DataFrame:
    suffix = file_name.lower().split(".")[-1]
    if suffix == "csv":
        raw = load_table_from_bytes(file_name, file_bytes)
        if get_first_existing_column(raw, ORDER_ID_REPORT_KEYS) and get_first_existing_column(raw, ORDER_SKU_ID_REPORT_KEYS):
            return raw

    xl = pd.ExcelFile(BytesIO(file_bytes))
    sheet_name = next((name for name in xl.sheet_names if "order" in str(name).casefold() or "订单" in str(name)), xl.sheet_names[0])
    raw = pd.read_excel(BytesIO(file_bytes), sheet_name=sheet_name, header=None)
    header_idx = None
    for idx, row in raw.iterrows():
        values = [str(x).strip() for x in row.tolist() if str(x).strip() and str(x).strip().casefold() != "nan"]
        hit_count = sum(any(key.casefold() == value.casefold() for value in values) for key in ORDER_REPORT_HEADER_KEYS)
        if hit_count >= 2:
            header_idx = idx
            break
    if header_idx is None:
        raise ValueError("订单报表未找到有效表头：需要包含订单号 / SKU编号 / 购买数量等字段")

    columns = [str(x).strip() if str(x).strip().casefold() != "nan" else f"Unnamed: {i}" for i, x in enumerate(raw.iloc[header_idx].tolist())]
    df = raw.iloc[header_idx + 1:].copy()
    df.columns = columns
    df = df.dropna(how="all")
    return df.reset_index(drop=True)


def classify_local_file(path: Path) -> str | None:
    name = path.name.lower()
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return None
    if name.startswith("tk-") or "\\tk-" in str(path).lower() or "/tk-" in str(path).lower():
        return None
    if any(key in name for key in ["全部订单", "order report", "all orders", "all-orders", "order_report"]):
        return "order_reports"
    if any(key in name for key in ["return", "refund", "returns", "售后", "退款", "退货"]):
        return "returns"
    if any(key in name for key in ["mapping", "sku", "product", "goods", "商品", "映射"]):
        return "mapping"
    if any(key in name for key in ["sales", "order", "销售", "订单"]):
        return "sales"
    return None


def collect_local_inputs(base_dir: str | Path) -> dict[str, list[tuple[str, bytes]]]:
    directory = resolve_path(base_dir)
    result = {"returns": [], "sales": [], "mapping": [], "order_reports": []}
    if not directory.exists():
        return result
    for path in sorted(directory.iterdir()):
        if not path.is_file():
            continue
        kind = classify_local_file(path)
        if kind:
            try:
                source_name = str(path.relative_to(PROJECT_ROOT))
            except ValueError:
                source_name = path.name
            result[kind].append((source_name, path.read_bytes()))
    return result


def classify_first_reason(reason: str) -> str:
    text = str(reason or "").strip()
    for label, pattern in FIRST_REASON_RULES:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return label
    return "其他"


def _pick(raw: pd.DataFrame, keys: list[str]) -> pd.Series | None:
    col = get_first_existing_column(raw, keys)
    return raw[col] if col else None


def _text_series(raw: pd.DataFrame, keys: list[str], default: str = "") -> pd.Series:
    series = _pick(raw, keys)
    if series is None:
        return pd.Series([default] * len(raw), index=raw.index, dtype="object")
    return series.astype(str).str.strip().replace({"nan": "", "None": "", "<NA>": ""})


def _safe_text_column(raw: pd.DataFrame, col: str | None, default: str = "") -> pd.Series:
    if not col:
        return pd.Series([default] * len(raw), index=raw.index, dtype="object")
    return (
        raw[col]
        .fillna(default)
        .astype(str)
        .str.strip()
        .replace({"nan": default, "None": default, "<NA>": default})
    )


def clean_return_df(raw: pd.DataFrame, source_name: str = "") -> pd.DataFrame:
    order_id_col = get_first_existing_column(raw, ORDER_ID_KEYS)
    sku_col = get_first_existing_column(raw, SKU_ID_KEYS)
    if not order_id_col or not sku_col:
        raise ValueError("售后退货表缺少必要字段：Order ID / SKU ID")

    store_col = get_first_existing_column(raw, STORE_KEYS)
    df = pd.DataFrame(index=raw.index)
    if store_col:
        df["store"] = raw[store_col].astype(str).str.strip().replace({"": "未识别店铺", "nan": "未识别店铺", "None": "未识别店铺", "<NA>": "未识别店铺"})
    else:
        inferred_store = infer_store_from_filename(source_name)
        if inferred_store.strip().casefold() in {"return", "return report", "return-report", "return_report", "report", "order", "order reports", "order-reports"}:
            inferred_store = "未识别店铺"
        df["store"] = inferred_store

    df["return_id"] = _text_series(raw, RETURN_ID_KEYS)
    df["order_id"] = raw[order_id_col].astype(str).str.strip()
    df["return_status_raw"] = _text_series(raw, RETURN_STATUS_KEYS)
    df["return_status"] = df["return_status_raw"].str.casefold().map(STATUS_MAP).fillna(df["return_status_raw"].replace("", "未知"))
    df["sku_id"] = raw[sku_col].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    df["reason_for_request"] = _text_series(raw, REASON_KEYS)
    df["return_quantity"] = parse_numeric_series(_pick(raw, RETURN_QTY_KEYS))
    df["amount_request_to_refund"] = parse_numeric_series(_pick(raw, AMOUNT_REQUEST_KEYS))
    df["amount_refund_to_buyer"] = parse_numeric_series(_pick(raw, AMOUNT_REFUND_KEYS))
    df["order_date"] = parse_return_datetime(_pick(raw, ORDER_DATE_KEYS))
    df["requested_date"] = parse_return_datetime(_pick(raw, REQUESTED_DATE_KEYS))
    df["courier"] = _text_series(raw, COURIER_KEYS)
    df["tracking_number"] = _text_series(raw, TRACKING_KEYS)
    df["service_type_raw"] = _text_series(raw, SERVICE_TYPE_KEYS)
    df["service_type"] = df["service_type_raw"].str.casefold().map(SERVICE_TYPE_MAP).fillna(df["service_type_raw"].replace("", "未知"))
    df["returnless_resolution"] = _text_series(raw, RETURNLESS_KEYS)
    df["cost_responsible"] = _text_series(raw, COST_RESPONSIBLE_KEYS)
    df["first_reason"] = df["reason_for_request"].apply(classify_first_reason)
    df["source_file"] = source_name or ""
    df = df[(df["order_id"] != "") & (df["sku_id"] != "")].copy()
    return df.reset_index(drop=True)


def parse_signed_status(raw: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    status_col = get_first_existing_column(raw, SALES_STATUS_KEYS)
    if not status_col:
        return (
            pd.Series([True] * len(raw), index=raw.index, dtype=bool),
            pd.Series([False] * len(raw), index=raw.index, dtype=bool),
        )
    status_text = raw[status_col].astype(str).str.strip().str.casefold()
    has_status = ~status_text.isin(["", "nan", "none", "null", "<na>"])
    pattern = "|".join(re.escape(x.casefold()) for x in SIGNED_STATUS_PATTERNS)
    is_signed = status_text.str.contains(pattern, na=False) & has_status
    return is_signed.fillna(False), has_status.fillna(False)


def clean_sales_df(raw: pd.DataFrame, source_name: str = "") -> pd.DataFrame:
    date_col = get_first_existing_column(raw, SALES_DATE_KEYS)
    id_col = get_first_existing_column(raw, SALES_ID_KEYS)
    if not date_col or not id_col:
        raise ValueError("销售表缺少必要字段：Date / Goods ID")

    name_col = get_first_existing_column(raw, SALES_NAME_KEYS)
    df = pd.DataFrame()
    df["date"] = parse_date_series(raw[date_col])
    df["goods_id"] = raw[id_col].astype(str).str.strip().str.replace(r"\.0$", "", regex=True).str.replace(r"\s+", "", regex=True)
    df["product_name"] = raw[name_col].astype(str).str.strip() if name_col else ""
    df["is_signed_order"], df["status_available"] = parse_signed_status(raw)
    for target, candidates in SALES_FIELD_MAP.items():
        picked = _pick(raw, candidates)
        df[target] = parse_numeric_series(picked) if picked is not None else 0.0
    df["sales"] = np.where(
        (df["sales"] <= 0) & (df["total_order_items"] > 0) & (df["avg_sales_per_order_item"] > 0),
        df["total_order_items"] * df["avg_sales_per_order_item"],
        df["sales"],
    )
    df["store"] = infer_store_from_filename(source_name)
    df["source_file"] = source_name or ""
    df = df.dropna(subset=["date"])
    df = df[df["goods_id"] != ""].copy()
    return df


def clean_order_report_df(raw: pd.DataFrame, source_name: str = "") -> pd.DataFrame:
    order_id_col = get_first_existing_column(raw, ORDER_ID_REPORT_KEYS)
    sku_id_col = get_first_existing_column(raw, ORDER_SKU_ID_REPORT_KEYS)
    if not order_id_col or not sku_id_col:
        raise ValueError("订单报表缺少必要字段：订单号 / SKU编号")

    order_status_col = get_first_existing_column(raw, ORDER_STATUS_REPORT_KEYS)
    item_status_col = get_first_existing_column(raw, ORDER_ITEM_STATUS_REPORT_KEYS)
    logistics_status_col = get_first_existing_column(raw, LOGISTICS_STATUS_REPORT_KEYS)
    item_id_col = get_first_existing_column(raw, ORDER_ITEM_ID_REPORT_KEYS)
    seller_sku_col = get_first_existing_column(raw, SELLER_SKU_REPORT_KEYS)
    product_col = get_first_existing_column(raw, ORDER_PRODUCT_REPORT_KEYS)
    spec_col = get_first_existing_column(raw, ORDER_SPEC_REPORT_KEYS)
    qty_col = get_first_existing_column(raw, ORDER_QTY_REPORT_KEYS)
    date_col = get_first_existing_column(raw, ORDER_DATE_REPORT_KEYS)

    df = pd.DataFrame(index=raw.index)
    df["date"] = parse_date_series(raw[date_col]) if date_col else pd.NaT
    df["order_id"] = _safe_text_column(raw, order_id_col)
    df["order_item_id"] = _safe_text_column(raw, item_id_col)
    df["sku_id"] = _safe_text_column(raw, sku_id_col).str.replace(r"\.0$", "", regex=True)
    df["seller_sku"] = _safe_text_column(raw, seller_sku_col)
    df["product_name"] = _safe_text_column(raw, product_col)
    df["sku_spec"] = _safe_text_column(raw, spec_col)
    df["quantity"] = parse_numeric_series(raw[qty_col]) if qty_col else 1.0
    df["order_status"] = _safe_text_column(raw, order_status_col)
    df["order_item_status"] = _safe_text_column(raw, item_status_col)
    df["logistics_status"] = _safe_text_column(raw, logistics_status_col)
    df["store"] = infer_store_from_filename(source_name)
    signed_text = (
        df["order_status"].fillna("").astype(str).str.casefold() + " "
        + df["order_item_status"].fillna("").astype(str).str.casefold() + " "
        + df["logistics_status"].fillna("").astype(str).str.casefold()
    )
    signed_pattern = "|".join(re.escape(x.casefold()) for x in SIGNED_STATUS_PATTERNS)
    signed_pattern = signed_pattern + "|已签收|已送达"
    has_status = signed_text.str.strip().ne("")
    df["is_signed_order"] = signed_text.str.contains(signed_pattern, na=False) & has_status
    df["status_available"] = has_status
    df = df[(df["order_id"] != "") & (df["sku_id"] != "")].copy()
    return df.reset_index(drop=True)


def clean_mapping_df(raw: pd.DataFrame, source_name: str = "") -> pd.DataFrame:
    id_col = get_first_existing_column(raw, MAP_ID_KEYS)
    if not id_col:
        raise ValueError("SKU 映射表缺少必要字段：Goods ID")
    sku_col = get_first_existing_column(raw, MAP_SKU_KEYS)
    product_col = get_first_existing_column(raw, MAP_PRODUCT_KEYS)
    store_col = get_first_existing_column(raw, MAP_STORE_KEYS)

    df = pd.DataFrame()
    df["goods_id"] = raw[id_col].astype(str).str.strip().str.replace(r"\.0$", "", regex=True).str.replace(r"\s+", "", regex=True)
    df["sku"] = raw[sku_col].astype(str).str.strip() if sku_col else ""
    df["product_name"] = raw[product_col].astype(str).str.strip() if product_col else ""
    df["store"] = raw[store_col].astype(str).str.strip() if store_col else infer_store_from_filename(source_name)
    df = df[df["goods_id"] != ""].copy()

    def _first_text(series: pd.Series) -> str:
        return next((str(x).strip() for x in series if str(x).strip() and str(x).strip().casefold() != "nan"), "")

    return df.groupby("goods_id", as_index=False).agg(
        sku=("sku", _first_text),
        product_name=("product_name", _first_text),
        store=("store", _first_text),
    )


def build_sales_denominator_df(sales_df: pd.DataFrame, mapping_df: pd.DataFrame, conversion_basis: str) -> pd.DataFrame:
    if sales_df.empty:
        return pd.DataFrame(columns=["date", "goods_id", "store", "display_sku", "orders", "units_ordered", "signed_orders", "signed_units_ordered", "status_available_count"])

    work = sales_df.copy()
    for col in ["buyers", "total_order_items", "units_ordered"]:
        work[f"signed_{col}"] = work[col].where(work["is_signed_order"].fillna(False), 0)
    grouped = work.groupby(["date", "goods_id", "store"], as_index=False).agg(
        units_ordered=("units_ordered", "sum"),
        total_order_items=("total_order_items", "sum"),
        buyers=("buyers", "sum"),
        signed_units_ordered=("signed_units_ordered", "sum"),
        signed_total_order_items=("signed_total_order_items", "sum"),
        signed_buyers=("signed_buyers", "sum"),
        status_available_count=("status_available", "sum"),
    )
    if not mapping_df.empty:
        grouped = grouped.merge(mapping_df[["goods_id", "sku"]], on="goods_id", how="left")
    else:
        grouped["sku"] = ""

    if conversion_basis == "订单商品数":
        grouped["orders"] = grouped["total_order_items"]
        grouped["signed_orders"] = grouped["signed_total_order_items"]
    elif conversion_basis == "下单件数":
        grouped["orders"] = grouped["units_ordered"]
        grouped["signed_orders"] = grouped["signed_units_ordered"]
    else:
        grouped["orders"] = grouped["buyers"]
        grouped["signed_orders"] = grouped["signed_buyers"]

    no_status = grouped["status_available_count"].fillna(0) <= 0
    grouped.loc[no_status, "signed_orders"] = grouped.loc[no_status, "orders"]
    grouped.loc[no_status, "signed_units_ordered"] = grouped.loc[no_status, "units_ordered"]
    grouped["display_sku"] = grouped["sku"].fillna("").astype(str).str.strip()
    grouped["display_sku"] = grouped["display_sku"].mask(grouped["display_sku"].isin(["", "nan", "None"]), grouped["goods_id"].astype(str))
    return grouped


def build_order_report_denominator_df(order_df: pd.DataFrame) -> pd.DataFrame:
    if order_df.empty:
        return pd.DataFrame(columns=[
            "date", "store", "display_sku", "seller_sku", "product_name", "sku_spec",
            "orders", "units_ordered", "signed_orders", "signed_units_ordered", "status_available_count",
        ])

    work = order_df.copy()
    work["signed_units"] = work["quantity"].where(work["is_signed_order"].fillna(False), 0)
    grouped = work.groupby(["date", "store", "sku_id"], dropna=False, as_index=False).agg(
        orders=("order_id", "nunique"),
        units_ordered=("quantity", "sum"),
        signed_orders=("order_id", lambda s: s[work.loc[s.index, "is_signed_order"].fillna(False)].nunique()),
        signed_order_ids=("order_id", lambda s: set(s[work.loc[s.index, "is_signed_order"].fillna(False)].astype(str))),
        signed_units_ordered=("signed_units", "sum"),
        status_available_count=("status_available", "sum"),
        seller_sku=("seller_sku", lambda s: next((str(x).strip() for x in s if str(x).strip() and str(x).strip().casefold() != "nan"), "")),
        product_name=("product_name", lambda s: next((str(x).strip() for x in s if str(x).strip() and str(x).strip().casefold() != "nan"), "")),
        sku_spec=("sku_spec", lambda s: next((str(x).strip() for x in s if str(x).strip() and str(x).strip().casefold() != "nan"), "")),
    )
    no_status = grouped["status_available_count"].fillna(0) <= 0
    grouped.loc[no_status, "signed_orders"] = grouped.loc[no_status, "orders"]
    grouped.loc[no_status, "signed_units_ordered"] = grouped.loc[no_status, "units_ordered"]
    grouped["display_sku"] = grouped["sku_id"].astype(str)
    grouped["goods_id"] = grouped["sku_id"].astype(str)
    return grouped
