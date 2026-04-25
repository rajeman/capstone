"""Deterministic aggregates for transaction history (feeds the chart analytics sub-agent)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal


def _usd(amount_cents: int) -> float:
    return float(Decimal(amount_cents) / Decimal(100))


def _party_label(row: dict, *, flow: str) -> str:
    if flow == "out":
        recv = row.get("receiver_user") or {}
        if recv.get("found"):
            return str(recv.get("name") or recv.get("email") or recv.get("username") or "Recipient")
        rid = row.get("receiver_clerk_user_id")
        return f"User {rid[:8]}…" if rid else "Unknown recipient"
    snd = row.get("sender_user") or {}
    if snd.get("found"):
        return str(snd.get("name") or snd.get("email") or snd.get("username") or "Sender")
    sid = row.get("sender_clerk_user_id")
    return f"User {sid[:8]}…" if sid else "Unknown sender"


def _day_key(iso_ts: str | None) -> str:
    if not iso_ts:
        return "unknown"
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        return dt.date().isoformat()
    except ValueError:
        return "unknown"


def _week_key(iso_ts: str | None) -> str:
    if not iso_ts:
        return "unknown"
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00")).date()
        y, w, _ = dt.isocalendar()
        return f"{y}-W{w:02d}"
    except ValueError:
        return "unknown"


def _month_key(iso_ts: str | None) -> str:
    if not iso_ts:
        return "unknown"
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m")
    except ValueError:
        return "unknown"


def _running_series(
    sorted_periods: list[str],
    in_map: dict[str, int],
    out_map: dict[str, int],
    *,
    balance_start_cents: int,
) -> list[dict]:
    out: list[dict] = []
    running = balance_start_cents
    for p in sorted_periods:
        inc = in_map.get(p, 0)
        outc = out_map.get(p, 0)
        net = inc - outc
        running += net
        out.append(
            {
                "period": p,
                "money_in_usd": round(_usd(inc), 2),
                "money_out_usd": round(_usd(outc), 2),
                "net_usd": round(_usd(net), 2),
                "running_balance_usd": round(_usd(running), 2),
            }
        )
    return out


def _line_chart_payload(
    *,
    key: str,
    title: str,
    description: str,
    series_rows: list[dict],
    x_field: str = "period",
) -> dict:
    if not series_rows:
        return {
            "key": key,
            "title": title,
            "type": "line",
            "description": description,
            "x_axis_key": "x",
            "series": [],
        }
    xs = [row[x_field] for row in series_rows]
    return {
        "key": key,
        "title": title,
        "type": "line",
        "description": description,
        "x_axis_key": "x",
        "series": [
            {
                "name": "Spend (out)",
                "color": "#EF4444",
                "points": [{"x": x, "y": row["money_out_usd"]} for x, row in zip(xs, series_rows, strict=True)],
            },
            {
                "name": "Income (in)",
                "color": "#10B981",
                "points": [{"x": x, "y": row["money_in_usd"]} for x, row in zip(xs, series_rows, strict=True)],
            },
            {
                "name": "Running balance",
                "color": "#3B82F6",
                "points": [{"x": x, "y": row["running_balance_usd"]} for x, row in zip(xs, series_rows, strict=True)],
            },
        ],
    }


def _bar_top_payload(
    *,
    key: str,
    title: str,
    description: str,
    counter: dict[str, int],
    top_n: int,
) -> dict:
    items = sorted(counter.items(), key=lambda x: x[1], reverse=True)[:top_n]
    palette = ["#3B82F6", "#6366F1", "#8B5CF6", "#A855F7", "#D946EF", "#EC4899", "#F43F5E", "#F97316", "#EAB308", "#22C55E"]
    data = []
    for i, (name, cents) in enumerate(items):
        data.append(
            {
                "name": name,
                "value": round(_usd(cents), 2),
                "color": palette[i % len(palette)],
            }
        )
    return {
        "key": key,
        "title": title,
        "type": "bar",
        "description": description,
        "data": data,
    }


def _pie_top_plus_others(
    *,
    key: str,
    title: str,
    description: str,
    counter: dict[str, int],
    top_n: int,
) -> dict:
    items = sorted(counter.items(), key=lambda x: x[1], reverse=True)
    head = items[:top_n]
    tail_sum = sum(c for _, c in items[top_n:])
    top_palette = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6"]
    data = []
    for i, (name, cents) in enumerate(head):
        if cents <= 0:
            continue
        data.append({"name": name, "value": round(_usd(cents), 2), "color": top_palette[i % len(top_palette)]})
    if tail_sum > 0:
        data.append({"name": "Others", "value": round(_usd(tail_sum), 2), "color": "#94A3B8"})
    return {
        "key": key,
        "title": title,
        "type": "pie",
        "description": description,
        "data": data,
    }


def compute_transaction_history_stats(
    *,
    viewer_clerk_user_id: str,
    transactions: Iterable[dict],
    current_balance_usd_cents: int,
) -> dict:
    rows = list(transactions)
    money_in_cents = 0
    money_out_cents = 0
    by_day_in: dict[str, int] = defaultdict(int)
    by_day_out: dict[str, int] = defaultdict(int)
    by_week_in: dict[str, int] = defaultdict(int)
    by_week_out: dict[str, int] = defaultdict(int)
    by_month_in: dict[str, int] = defaultdict(int)
    by_month_out: dict[str, int] = defaultdict(int)
    out_by_party: dict[str, int] = defaultdict(int)
    in_by_party: dict[str, int] = defaultdict(int)

    for row in rows:
        amt = int(row.get("amount_usd_cents") or 0)
        side = row.get("side")
        ts = row.get("created_at")
        dk, wk, mk = _day_key(ts), _week_key(ts), _month_key(ts)
        if side == "credit":
            money_in_cents += amt
            if dk != "unknown":
                by_day_in[dk] += amt
            if wk != "unknown":
                by_week_in[wk] += amt
            if mk != "unknown":
                by_month_in[mk] += amt
            label = _party_label(row, flow="in")
            in_by_party[label] += amt
        elif side == "debit":
            money_out_cents += amt
            if dk != "unknown":
                by_day_out[dk] += amt
            if wk != "unknown":
                by_week_out[wk] += amt
            if mk != "unknown":
                by_month_out[mk] += amt
            label = _party_label(row, flow="out")
            out_by_party[label] += amt

    net_flow_cents = money_in_cents - money_out_cents
    balance_start_cents = current_balance_usd_cents - net_flow_cents

    def top_n(counter: dict[str, int], n: int) -> list[dict]:
        items = sorted(counter.items(), key=lambda x: x[1], reverse=True)[:n]
        return [{"name": name, "amount_usd_cents": cents, "amount_usd": round(_usd(cents), 2)} for name, cents in items]

    all_days = sorted(set(by_day_in) | set(by_day_out) - {"unknown"})
    daily_series = _running_series(all_days, by_day_in, by_day_out, balance_start_cents=balance_start_cents)

    all_weeks = sorted(set(by_week_in) | set(by_week_out) - {"unknown"})
    weekly_series = _running_series(all_weeks, by_week_in, by_week_out, balance_start_cents=balance_start_cents)

    all_months = sorted(set(by_month_in) | set(by_month_out) - {"unknown"})
    monthly_series = _running_series(all_months, by_month_in, by_month_out, balance_start_cents=balance_start_cents)

    prebuilt: list[dict] = []
    if daily_series:
        prebuilt.append(
            _line_chart_payload(
                key="daily_spend_income_running_balance",
                title="Daily spend, income, and running balance",
                description="Each day: money out (spend), money in (income), and estimated running balance after that day.",
                series_rows=daily_series,
                x_field="period",
            )
        )
    if len(all_weeks) >= 1 and weekly_series:
        prebuilt.append(
            _line_chart_payload(
                key="weekly_spend_income_running_balance",
                title="Weekly spend, income, and running balance",
                description="ISO week buckets (year-Www): spend, income, running balance through each week.",
                series_rows=weekly_series,
                x_field="period",
            )
        )
    if len(all_months) >= 1 and monthly_series:
        prebuilt.append(
            _line_chart_payload(
                key="monthly_spend_income_running_balance",
                title="Monthly spend, income, and running balance",
                description="Calendar month totals with running balance after each month in the window.",
                series_rows=monthly_series,
                x_field="period",
            )
        )

    if out_by_party:
        prebuilt.append(
            _bar_top_payload(
                key="top_beneficiaries_bar",
                title="Top beneficiaries (money sent)",
                description="Largest recipients by total amount you sent in this history window.",
                counter=out_by_party,
                top_n=10,
            )
        )
        prebuilt.append(
            _pie_top_plus_others(
                key="beneficiaries_share_pie",
                title="Share of money sent by beneficiary",
                description="Top beneficiaries by amount; smaller recipients grouped as **Others**.",
                counter=out_by_party,
                top_n=5,
            )
        )

    if in_by_party:
        prebuilt.append(
            _pie_top_plus_others(
                key="income_sources_share_pie",
                title="Share of money received by sender",
                description="Who paid you most in this window; smaller senders grouped as **Others**.",
                counter=in_by_party,
                top_n=5,
            )
        )

    legacy_daily = [
        {
            "date": row["period"],
            "money_in_usd": row["money_in_usd"],
            "money_out_usd": row["money_out_usd"],
            "net_usd": row["net_usd"],
        }
        for row in daily_series
    ]

    return {
        "viewer_clerk_user_id": viewer_clerk_user_id,
        "transaction_count": len(rows),
        "money_in_usd_cents": money_in_cents,
        "money_out_usd_cents": money_out_cents,
        "money_in_usd": round(_usd(money_in_cents), 2),
        "money_out_usd": round(_usd(money_out_cents), 2),
        "total_volume_usd": round(_usd(money_in_cents + money_out_cents), 2),
        "net_cash_flow_in_window_usd_cents": net_flow_cents,
        "net_cash_flow_in_window_usd": round(_usd(net_flow_cents), 2),
        "current_balance_usd_cents": current_balance_usd_cents,
        "current_balance_usd": round(_usd(current_balance_usd_cents), 2),
        "balance_at_start_of_window_usd": round(_usd(balance_start_cents), 2),
        "balance_at_start_of_window_usd_cents": balance_start_cents,
        "balance_change_hint": (
            "Running balance is reconstructed from your current balance and net flow in this loaded "
            "history only; if older transactions exist outside this window, the line is approximate."
        ),
        "top_outflow_beneficiaries": top_n(out_by_party, 8),
        "top_inflow_counterparties": top_n(in_by_party, 8),
        "daily_flow": legacy_daily,
        "daily_line_series": daily_series,
        "weekly_line_series": weekly_series,
        "monthly_line_series": monthly_series,
        "prebuilt_charts": prebuilt,
    }
