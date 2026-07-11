from sqlalchemy.orm import Session

from app.models import ScreenerSnapshot

SORTABLE_COLUMNS = {
    "symbol",
    "name",
    "sector",
    "price",
    "change_1d",
    "change_1w",
    "change_1m",
    "change_ytd",
    "avg_volume_20",
    "rsi_14",
    "pct_from_52w_high",
    "pct_from_52w_low",
    "market_cap",
    "pe_ratio",
    "ai_prob_up",
}

# (query param, column, operator) — every numeric range filter follows the
# same min_/max_ pattern, so the service builds them from this table.
RANGE_FILTERS = [
    ("min_price", "price", ">="),
    ("max_price", "price", "<="),
    ("min_avg_volume", "avg_volume_20", ">="),
    ("min_market_cap", "market_cap", ">="),
    ("max_market_cap", "market_cap", "<="),
    ("min_pe", "pe_ratio", ">="),
    ("max_pe", "pe_ratio", "<="),
    ("min_rsi", "rsi_14", ">="),
    ("max_rsi", "rsi_14", "<="),
    ("min_change_1d", "change_1d", ">="),
    ("max_change_1d", "change_1d", "<="),
    ("min_change_1w", "change_1w", ">="),
    ("max_change_1w", "change_1w", "<="),
    ("min_change_1m", "change_1m", ">="),
    ("max_change_1m", "change_1m", "<="),
    ("min_change_ytd", "change_ytd", ">="),
    ("max_change_ytd", "change_ytd", "<="),
    ("max_pct_from_52w_high", "pct_from_52w_high", "<="),
    ("min_pct_from_52w_high", "pct_from_52w_high", ">="),
    ("min_ai_prob", "ai_prob_up", ">="),
]


def run_screen(db: Session, params: dict) -> tuple[list[ScreenerSnapshot], int]:
    query = db.query(ScreenerSnapshot)

    for param_name, column_name, op in RANGE_FILTERS:
        value = params.get(param_name)
        if value is None:
            continue
        column = getattr(ScreenerSnapshot, column_name)
        query = query.filter(column >= value if op == ">=" else column <= value)

    if params.get("sector"):
        query = query.filter(ScreenerSnapshot.sector == params["sector"])

    total = query.count()

    sort_by = params.get("sort_by") or "market_cap"
    if sort_by not in SORTABLE_COLUMNS:
        sort_by = "market_cap"
    sort_column = getattr(ScreenerSnapshot, sort_by)
    if params.get("sort_dir", "desc") == "asc":
        query = query.order_by(sort_column.asc().nullslast())
    else:
        query = query.order_by(sort_column.desc().nullslast())

    limit = min(int(params.get("limit") or 50), 200)
    offset = int(params.get("offset") or 0)
    rows = query.offset(offset).limit(limit).all()
    return rows, total
