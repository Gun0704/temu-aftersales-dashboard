from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

import pandas as pd
import requests


@dataclass(frozen=True)
class TemuApiConfig:
    """TEMU API 基础配置。"""

    app_key: str
    app_secret: str
    access_token: str
    base_url: str


class TemuApiClient:
    """TEMU Open API 客户端：负责公共参数、签名、请求与分页。"""

    def __init__(self, config: TemuApiConfig, timeout: int = 30):
        self.config = config
        self.timeout = timeout

    def _sign(self, params: Dict[str, Any]) -> str:
        """按 TEMU 开放平台常见规则生成 MD5 大写签名。"""
        items = []
        for key, value in params.items():
            if key == "sign" or value is None:
                continue
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            items.append((key, str(value)))
        items.sort(key=lambda x: x[0])
        raw = self.config.app_secret + "".join(f"{k}{v}" for k, v in items) + self.config.app_secret
        return hashlib.md5(raw.encode("utf-8")).hexdigest().upper()

    def call(self, api_type: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """调用单个 TEMU API。api_type 例如 bg.open.accesstoken.info。"""
        body: Dict[str, Any] = dict(payload or {})
        body.update(
            {
                "type": api_type,
                "app_key": self.config.app_key,
                "access_token": self.config.access_token,
                "timestamp": int(time.time()),
            }
        )
        body["sign"] = self._sign(body)
        response = requests.post(self.config.base_url, json=body, timeout=self.timeout)
        response.raise_for_status()
        result = response.json()
        if isinstance(result, dict) and result.get("success") is False:
            raise RuntimeError(result.get("errorMsg") or result.get("msg") or str(result))
        return result

    def call_pages(
        self,
        api_type: str,
        payload: Optional[Dict[str, Any]] = None,
        list_keys: Iterable[str] = ("list", "records", "result", "data"),
        page_no_key: str = "pageNo",
        page_size_key: str = "pageSize",
        page_size: int = 100,
        max_pages: int = 50,
    ) -> list[dict]:
        """通用分页拉取。不同接口字段不一致，所以 list_keys 可按接口调整。"""
        rows: list[dict] = []
        base_payload = dict(payload or {})
        for page_no in range(1, max_pages + 1):
            req = dict(base_payload)
            req[page_no_key] = page_no
            req[page_size_key] = page_size
            res = self.call(api_type, req)
            page_rows = _extract_rows(res, list_keys)
            if not page_rows:
                break
            rows.extend(page_rows)
            if len(page_rows) < page_size:
                break
        return rows


def _extract_rows(obj: Any, list_keys: Iterable[str]) -> list[dict]:
    """从 TEMU 响应中递归找列表结果。"""
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if not isinstance(obj, dict):
        return []
    for key in list_keys:
        value = obj.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
        if isinstance(value, dict):
            nested = _extract_rows(value, list_keys)
            if nested:
                return nested
    for value in obj.values():
        nested = _extract_rows(value, list_keys)
        if nested:
            return nested
    return []


def _first(row: dict, *keys: str, default: Any = "") -> Any:
    """兼容接口返回的驼峰/下划线/大小写字段。"""
    lower_map = {str(k).lower(): v for k, v in row.items()}
    for key in keys:
        if key in row:
            return row[key]
        found = lower_map.get(key.lower())
        if found is not None:
            return found
    return default


def sales_rows_to_df(rows: list[dict], source_name: str = "TEMU_API") -> pd.DataFrame:
    """把订单/销售接口返回转换成看板销售表字段。"""
    data = []
    for r in rows:
        data.append(
            {
                "Date": _first(r, "date", "statDate", "orderDate", "payTime", "createTime"),
                "Goods ID": _first(r, "goodsId", "goods_id", "productId"),
                "Goods Name": _first(r, "goodsName", "goods_name", "productName"),
                "Sales": _first(r, "sales", "saleAmount", "amount", "gmv", default=0),
                "Buyers": _first(r, "buyers", "buyerCount", "payBuyerCnt", default=0),
                "Total order items": _first(r, "totalOrderItems", "orderItemCount", "orderCnt", default=0),
                "Units ordered": _first(r, "unitsOrdered", "quantity", "qty", "skuQuantity", default=0),
                "Order status": _first(r, "orderStatus", "status", default="delivered"),
                "Source": source_name,
            }
        )
    return pd.DataFrame(data)


def traffic_rows_to_df(rows: list[dict], source_name: str = "TEMU_API") -> pd.DataFrame:
    """把流量/商品统计接口返回转换成看板流量表字段。"""
    data = []
    for r in rows:
        data.append(
            {
                "Date": _first(r, "date", "statDate"),
                "Goods ID": _first(r, "goodsId", "goods_id", "productId"),
                "Goods Name": _first(r, "goodsName", "goods_name", "productName"),
                "Product impressions": _first(r, "impressions", "productImpressions", "exposureCnt", default=0),
                "Product clicks": _first(r, "clicks", "productClicks", "clickCnt", default=0),
                "CTR": _first(r, "ctr", "clickThroughRate", default=0),
                "Source": source_name,
            }
        )
    return pd.DataFrame(data)


def mapping_rows_to_df(rows: list[dict], source_name: str = "TEMU_API") -> pd.DataFrame:
    """把商品/SKU接口返回转换成看板映射表字段。"""
    data = []
    for r in rows:
        data.append(
            {
                "Goods ID": _first(r, "goodsId", "goods_id", "productId"),
                "SKU": _first(r, "sku", "skuId", "extCode"),
                "Product name": _first(r, "goodsName", "goods_name", "productName"),
                "Store": _first(r, "storeName", "mallName", "shopName", default=source_name),
                "Quantity": _first(r, "quantity", "inventory", "stock", default=0),
            }
        )
    return pd.DataFrame(data)


def fetch_orders(client,start_ts:int,end_ts:int)->list[dict]:
    rows=[]
    page=1
    while True:
        res=client.call("bg.order.list.v2.get",{
            "pageNumber":page,
            "pageSize":100,
            "createAfter":start_ts,
            "createBefore":end_ts,
        })
        page_items=res.get("result",{}).get("pageItems",[])
        if not page_items:
            break
        for parent in page_items:
            rows.extend(parent.get("orderList",[]))
        if len(page_items)<100:
            break
        page+=1
    return rows

def fetch_mall_ad_report(client,start_ts:int,end_ts:int):
    res=client.call("temu.searchrec.ad.reports.mall.query",{
        "startTs":start_ts,
        "endTs":end_ts,
        "data_type":"DAY",
    })
    return res.get("result",{}).get("reportsItemList",[])

def fetch_goods_ad_report(client,goods_id:int,start_ts:int,end_ts:int):
    res=client.call("temu.searchrec.ad.reports.goods.query",{
        "goodsId":goods_id,
        "startTs":start_ts,
        "endTs":end_ts,
        "data_type":"DAY",
    })
    return res.get("result",{}).get("reportInfo",{}).get("reportsItemList",[])

def orders_to_sales_df(rows):
    data=[]
    for r in rows:
        data.append({
            "Date":pd.to_datetime(r.get("orderCreateTime"),unit="ms",errors="coerce"),
            "Goods ID":r.get("goodsId"),
            "Goods Name":r.get("goodsName"),
            "Sales":r.get("quantity",0),
            "Buyers":1,
            "Total order items":1,
            "Units ordered":r.get("quantity",0),
            "Order status":r.get("orderStatus"),
            "SKU":r.get("skuId"),
            "Order SN":r.get("orderSn"),
            "Source":"TEMU_ORDER",
        })
    return pd.DataFrame(data)

def mall_report_to_df(rows):
    data=[]
    for r in rows:
        data.append({
            "Date":pd.to_datetime(r.get("ts"),unit="ms",errors="coerce"),
            "Product impressions":r.get("imprCnt",{}).get("val",0),
            "Product clicks":r.get("clkCnt",{}).get("val",0),
            "CTR":r.get("ctr",{}).get("val",0),
            "Orders":r.get("orderPayCnt",{}).get("val",0),
            "Revenue":r.get("orderPayAmt",{}).get("val",0),
            "Spend":r.get("adSpend",{}).get("val",0),
            "ROAS":r.get("roas",{}).get("val",0),
            "ACOS":r.get("acos",{}).get("val",0),
            "Source":"TEMU_AD_MALL",
        })
    return pd.DataFrame(data)

def goods_report_to_df(rows):
    data=[]
    for r in rows:
        data.append({
            "Date":pd.to_datetime(r.get("ts"),unit="ms",errors="coerce"),
            "Goods ID":r.get("goodsId"),
            "Impressions":r.get("imprCnt",{}).get("val",0),
            "Clicks":r.get("clkCnt",{}).get("val",0),
            "CTR":r.get("ctr",{}).get("val",0),
            "Orders":r.get("orderPayCnt",{}).get("val",0),
            "Revenue":r.get("orderPayAmt",{}).get("val",0),
            "Spend":r.get("adSpend",{}).get("val",0),
            "ROAS":r.get("roas",{}).get("val",0),
            "ACOS":r.get("acos",{}).get("val",0),
            "Units":r.get("goodsNum",{}).get("val",0),
            "Source":"TEMU_AD_GOODS",
        })
    return pd.DataFrame(data)
