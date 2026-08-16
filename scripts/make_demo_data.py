from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "demo"


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20260621)
    dates = pd.date_range("2026-06-01", periods=14, freq="D")
    products = [
        {"goods_id": "10000001", "sku": "SKU-BAG-001", "name": "Travel Makeup Bag", "qty": 420, "price": 68.0},
        {"goods_id": "10000002", "sku": "SKU-LAMP-002", "name": "LED Desk Lamp", "qty": 180, "price": 125.0},
        {"goods_id": "10000003", "sku": "SKU-TOY-003", "name": "Kids Building Toy", "qty": 260, "price": 92.0},
    ]

    sales_rows = []
    traffic_rows = []
    order_rows = []
    order_id = 900000
    for day_idx, dt in enumerate(dates):
        for p_idx, p in enumerate(products):
            trend = 1 + day_idx * (0.025 + p_idx * 0.008)
            impressions = int((6500 + p_idx * 1800) * trend + rng.normal(0, 350))
            clicks = max(1, int(impressions * (0.022 + p_idx * 0.006) + rng.normal(0, 30)))
            orders = max(0, int(clicks * (0.035 + p_idx * 0.012) + rng.normal(0, 3)))
            units = max(orders, int(orders * (1.05 + p_idx * 0.12) + rng.integers(0, 4)))
            buyers = max(1, int(orders * 0.92)) if orders else 0
            sales_amount = round(units * p["price"] * (0.92 + rng.random() * 0.16), 2)

            sales_rows.append({
                "Date": dt.strftime("%Y-%m-%d"),
                "Goods ID": p["goods_id"],
                "Goods Name": p["name"],
                "Base price sales": sales_amount,
                "Buyers": buyers,
                "Total order items": orders,
                "Units ordered": units,
                "Order status": "delivered",
            })
            traffic_rows.append({
                "Date": dt.strftime("%Y-%m-%d"),
                "Goods ID": p["goods_id"],
                "Goods Name": p["name"],
                "Product impressions": impressions,
                "Product clicks": clicks,
                "CTR": clicks / impressions if impressions else 0,
            })
            for _ in range(min(orders, 6)):
                order_id += 1
                qty = int(rng.integers(1, 3))
                order_rows.append({
                    "purchase date": dt.strftime("%b %d, %Y, %I:%M %p"),
                    "product name": p["name"],
                    "contribution sku": p["sku"],
                    "Retail price (tax excl.)": round(p["price"] / 1.16 * (0.96 + rng.random() * 0.08) * qty, 2),
                    "quantity purchased": qty,
                    "order status": "Delivered",
                    "Order ID": str(order_id),
                })

    mapping_rows = [{
        "Goods ID": p["goods_id"],
        "SKU": p["sku"],
        "Product name": p["name"],
        "Quantity": p["qty"],
        "Date created": "2026-05-15",
        "Store": "DemoStore",
    } for p in products]

    return_rows = [
        {
            "Store": "DemoStore",
            "Return ID": "R-10001",
            "Order ID": "900010",
            "Return status": "Refunded",
            "SKU ID": "SKU-BAG-001",
            "Reason for request": "Product damaged but shipping box ok",
            "Return quantity": 1,
            "Amount request to refund": 68.0,
            "Amount refund to buyer": 68.0,
            "Order date": "2026-06-05",
            "Requested date": "2026-06-08",
            "Types of after-sales service": "Return and refund",
        },
        {
            "Store": "DemoStore",
            "Return ID": "R-10002",
            "Order ID": "900025",
            "Return status": "Not refunded yet",
            "SKU ID": "SKU-LAMP-002",
            "Reason for request": "No longer need",
            "Return quantity": 1,
            "Amount request to refund": 125.0,
            "Amount refund to buyer": 0.0,
            "Order date": "2026-06-09",
            "Requested date": "2026-06-11",
            "Types of after-sales service": "Returnless refund",
        },
    ]

    pd.DataFrame(sales_rows).to_csv(DATA_DIR / "sales_demo.csv", index=False)
    pd.DataFrame(traffic_rows).to_csv(DATA_DIR / "traffic_demo.csv", index=False)
    pd.DataFrame(mapping_rows).to_csv(DATA_DIR / "mapping_demo.csv", index=False)
    pd.DataFrame(order_rows).to_csv(DATA_DIR / "frontend_orders_demo.csv", index=False)
    pd.DataFrame(return_rows).to_csv(DATA_DIR / "returns_demo.csv", index=False)
    print(f"Demo data generated in {DATA_DIR}")


if __name__ == "__main__":
    main()
