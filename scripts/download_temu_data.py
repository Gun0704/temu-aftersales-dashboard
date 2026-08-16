from __future__ import annotations

import argparse
import os
import sys
import tomllib
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from marketing_dashboard.analytics.advanced_analytics import extra_rows_to_df
from marketing_dashboard.integrations.temu_api import (
    TemuApiClient,
    TemuApiConfig,
    mapping_rows_to_df,
    sales_rows_to_df,
    traffic_rows_to_df,
)


def load_temu_config() -> dict[str, str]:
    """Read TEMU config from env first, then .streamlit/secrets.toml."""
    config = {
        "APP_KEY": os.getenv("TEMU_APP_KEY", ""),
        "APP_SECRET": os.getenv("TEMU_APP_SECRET", ""),
        "ACCESS_TOKEN": os.getenv("TEMU_ACCESS_TOKEN", ""),
        "BASE_URL": os.getenv("TEMU_BASE_URL", ""),
        "SALES_API_TYPE": os.getenv("TEMU_SALES_API_TYPE", ""),
        "TRAFFIC_API_TYPE": os.getenv("TEMU_TRAFFIC_API_TYPE", ""),
        "MAPPING_API_TYPE": os.getenv("TEMU_MAPPING_API_TYPE", ""),
        "EXTRA_API_TYPES": os.getenv("TEMU_EXTRA_API_TYPES", ""),
    }
    secrets_path = ROOT / ".streamlit" / "secrets.toml"
    if secrets_path.exists():
        with secrets_path.open("rb") as f:
            secrets = tomllib.load(f).get("TEMU", {})
        for key in config:
            config[key] = config[key] or str(secrets.get(key, ""))
    return config


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"saved {path.relative_to(ROOT)} rows={len(df):,}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download TEMU data into data/raw for offline dashboard demos.")
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--out-dir", default="data/raw", help="Output directory relative to project root")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=50)
    parser.add_argument("--sales-api-type", default="")
    parser.add_argument("--traffic-api-type", default="")
    parser.add_argument("--mapping-api-type", default="")
    parser.add_argument("--extra-api-types", default="", help="Comma-separated or newline-separated extra API types")
    args = parser.parse_args()

    cfg = load_temu_config()
    required = ["APP_KEY", "APP_SECRET", "ACCESS_TOKEN", "BASE_URL"]
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        raise SystemExit("Missing TEMU config: " + ", ".join(missing))

    sales_type = args.sales_api_type or cfg.get("SALES_API_TYPE", "")
    traffic_type = args.traffic_api_type or cfg.get("TRAFFIC_API_TYPE", "")
    mapping_type = args.mapping_api_type or cfg.get("MAPPING_API_TYPE", "")
    extra_types_text = args.extra_api_types or cfg.get("EXTRA_API_TYPES", "")
    extra_types = [x.strip() for x in extra_types_text.replace(",", "\n").splitlines() if x.strip()]
    if not sales_type or not traffic_type:
        raise SystemExit("Missing sales/traffic API type. Pass --sales-api-type and --traffic-api-type or set them in secrets/env.")

    client = TemuApiClient(TemuApiConfig(
        app_key=cfg["APP_KEY"],
        app_secret=cfg["APP_SECRET"],
        access_token=cfg["ACCESS_TOKEN"],
        base_url=cfg["BASE_URL"],
    ))
    payload = {"startDate": args.start_date, "endDate": args.end_date}
    out_dir = (ROOT / args.out_dir).resolve()

    sales_rows = client.call_pages(sales_type, payload, page_size=args.page_size, max_pages=args.max_pages)
    traffic_rows = client.call_pages(traffic_type, payload, page_size=args.page_size, max_pages=args.max_pages)
    mapping_rows = client.call_pages(mapping_type, {}, page_size=args.page_size, max_pages=args.max_pages) if mapping_type else []

    extra_rows = []
    for api_type in extra_types:
        extra_rows.extend(client.call_pages(api_type, payload, page_size=args.page_size, max_pages=args.max_pages))

    suffix = f"{args.start_date}_to_{args.end_date}"
    write_csv(sales_rows_to_df(sales_rows), out_dir / f"sales_temu_{suffix}.csv")
    write_csv(traffic_rows_to_df(traffic_rows), out_dir / f"traffic_temu_{suffix}.csv")
    if mapping_rows:
        write_csv(mapping_rows_to_df(mapping_rows), out_dir / f"mapping_temu_{suffix}.csv")
    if extra_rows:
        write_csv(extra_rows_to_df(extra_rows), out_dir / f"extra_temu_{suffix}.csv")


if __name__ == "__main__":
    main()
