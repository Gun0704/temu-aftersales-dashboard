from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DEMO_DIR = PROJECT_ROOT / "data" / "demo"
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def resolve_project_path(path_text: str | Path) -> Path:
    """Resolve a user-entered path relative to the project root when needed."""
    path = Path(path_text).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def classify_data_file(path: Path) -> str | None:
    """Classify a local demo/raw data file from its filename."""
    name = path.name.lower()
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return None
    if any(key in name for key in ["frontend", "front_price", "front-price", "前端价"]):
        return "frontend_order"
    if any(key in name for key in ["return", "refund", "returns", "售后", "退款", "退货"]):
        return "returns"
    if any(key in name for key in ["traffic", "impression", "click", "流量", "曝光", "点击"]):
        return "traffic"
    if any(key in name for key in ["mapping", "sku", "product", "goods", "商品", "映射"]):
        return "mapping"
    if any(key in name for key in ["sales", "order", "销售", "订单"]):
        return "sales"
    return "mixed"


def collect_local_data_inputs(base_dir: str | Path) -> dict[str, list[tuple[str, bytes]] | tuple[str, bytes] | None]:
    """Collect local data files into the same byte format used by uploads."""
    directory = resolve_project_path(base_dir)
    result: dict[str, list[tuple[str, bytes]] | tuple[str, bytes] | None] = {
        "sales": [],
        "traffic": [],
        "mapping": [],
        "mixed": [],
        "returns": [],
        "frontend_order": None,
    }
    if not directory.exists():
        return result
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        item = (path.name, path.read_bytes())
        kind = classify_data_file(path)
        if kind == "frontend_order":
            result["frontend_order"] = item
        elif kind in {"sales", "traffic", "mapping", "mixed", "returns"}:
            result[kind].append(item)  # type: ignore[index, union-attr]
    return result


def local_data_summary(inputs: dict[str, list[tuple[str, bytes]] | tuple[str, bytes] | None]) -> str:
    """Human-readable summary for the sidebar."""
    frontend_count = 1 if inputs.get("frontend_order") else 0
    return (
        f"销售 {len(inputs.get('sales') or [])} 个，"
        f"流量 {len(inputs.get('traffic') or [])} 个，"
        f"商品映射 {len(inputs.get('mapping') or [])} 个，"
        f"混合 {len(inputs.get('mixed') or [])} 个，"
        f"前端订单 {frontend_count} 个，"
        f"售后 {len(inputs.get('returns') or [])} 个"
    )
