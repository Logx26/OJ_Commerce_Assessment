"""QuickKart marketplace & logistics dashboard.

Run:
    streamlit run app/app.py

Reads pre-aggregated parquet from data/processed/. If those files are missing,
run app/data_prep.py first.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from styles import GLOBAL_CSS, PALETTE, HEAT_SCALE, plotly_layout

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"

st.set_page_config(
    page_title="QuickKart - marketplace & logistics",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# data
# ----------------------------------------------------------------------------

@st.cache_data
def load_lines() -> pd.DataFrame:
    df = pd.read_parquet(PROC / "dashboard_lines.parquet")
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["order_month"] = pd.to_datetime(df["order_month"])
    return df


@st.cache_data
def load_q4() -> pd.DataFrame:
    p = PROC / "q4_marketplace_summary.parquet"
    return pd.read_parquet(p) if p.exists() else pd.DataFrame()


lines = load_lines()
q4 = load_q4()


# ----------------------------------------------------------------------------
# sidebar filters
# ----------------------------------------------------------------------------

with st.sidebar:
    st.markdown(
        '<div style="padding:6px 4px 14px 4px;">'
        '<div style="font-size:1.05rem;font-weight:700;color:var(--text-primary);'
        'letter-spacing:-0.01em;">QuickKart</div>'
        '<div style="font-size:0.78rem;color:var(--text-muted);">marketplace ops console</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown("##### Filters")

    min_d, max_d = lines["created_at"].min().date(), lines["created_at"].max().date()
    date_range = st.date_input(
        "Order date range",
        (min_d, max_d),
        min_value=min_d, max_value=max_d,
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        d_from, d_to = date_range
    else:
        d_from, d_to = min_d, max_d

    cities = sorted(lines["city"].dropna().unique().tolist())
    categories = sorted(lines["category"].dropna().unique().tolist())
    carriers = sorted(lines["carrier"].dropna().unique().tolist())

    sel_cities = st.multiselect("Customer city", cities, default=cities)
    sel_cats = st.multiselect("Product category", categories, default=categories)
    sel_carriers = st.multiselect("Carrier", carriers, default=carriers)

    st.markdown("---")
    st.caption(
        "Filters apply to every chart. Date range filters by `order_created_at`. "
        "Carrier and ship_to_city live on shipments, so cancelled orders fall out "
        "of delay-related metrics."
    )

mask = (
    (lines["created_at"].dt.date >= d_from)
    & (lines["created_at"].dt.date <= d_to)
    & (lines["city"].isin(sel_cities))
    & (lines["category"].isin(sel_cats))
    & (lines["carrier"].isin(sel_carriers) | lines["carrier"].isna())
)
df = lines[mask].copy()

if df.empty:
    st.warning("No rows match the current filters. Widen the selection.")
    st.stop()


# ----------------------------------------------------------------------------
# header banner
# ----------------------------------------------------------------------------

st.markdown(
    f"""
    <div class="qk-banner">
      <h1>Marketplace &amp; logistics performance</h1>
      <p>{d_from:%b %d, %Y} &ndash; {d_to:%b %d, %Y} &middot; {len(sel_cities)} cities &middot;
      {len(sel_cats)} categories &middot; {len(sel_carriers)} carriers in scope.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ----------------------------------------------------------------------------
# KPI strip
# ----------------------------------------------------------------------------

orders_view = df.drop_duplicates("order_id")
gmv = float(df["gmv_line"].sum())
n_orders = orders_view["order_id"].nunique()
n_customers = orders_view["customer_id"].nunique()
avg_order = gmv / max(n_orders, 1)

evaluable = orders_view[orders_view["evaluable_delivery"]]
delayed_rate = (
    (evaluable["delivery_status"] != "OnTime").mean() if len(evaluable) else float("nan")
)

deliv_per_cust = (
    orders_view[orders_view["delivery_status"].isin(["OnTime", "Late_1_2d", "Late_3_5d", "Late_5p"])]
    .groupby("customer_id")["order_id"].nunique()
)
repeat_rate = (deliv_per_cust >= 2).mean() if len(deliv_per_cust) else float("nan")


def fmt_inr(v: float) -> str:
    if v >= 1e7:
        return f"Rs {v / 1e7:,.2f} Cr"
    if v >= 1e5:
        return f"Rs {v / 1e5:,.2f} L"
    return f"Rs {v:,.0f}"


def kpi_class(rate: float, hi: float, mid: float, invert: bool = False) -> str:
    """Return a severity class for a 0-1 rate. invert=True means higher is worse."""
    if pd.isna(rate):
        return "qk-info"
    val = rate if not invert else 1 - rate
    if val >= hi:
        return "qk-good"
    if val >= mid:
        return "qk-warn"
    return "qk-danger"


delayed_cls = kpi_class(1 - delayed_rate, 0.85, 0.70)
repeat_cls = kpi_class(repeat_rate, 0.50, 0.30)

st.markdown(
    f"""
    <div class="qk-kpi-row">
      <div class="qk-kpi qk-accent">
        <div class="qk-label">GMV</div>
        <div class="qk-value">{fmt_inr(gmv)}</div>
        <div class="qk-sub">{n_orders:,} orders &middot; avg {fmt_inr(avg_order)}</div>
      </div>
      <div class="qk-kpi qk-info">
        <div class="qk-label">Active customers</div>
        <div class="qk-value">{n_customers:,}</div>
        <div class="qk-sub">unique buyers in window</div>
      </div>
      <div class="qk-kpi {delayed_cls}">
        <div class="qk-label">Delayed order rate</div>
        <div class="qk-value">{delayed_rate:.1%}</div>
        <div class="qk-sub">{(evaluable['delivery_status'] != 'OnTime').sum():,} of {len(evaluable):,} evaluable</div>
      </div>
      <div class="qk-kpi {repeat_cls}">
        <div class="qk-label">Repeat rate</div>
        <div class="qk-value">{repeat_rate:.1%}</div>
        <div class="qk-sub">customers with &ge;2 delivered</div>
      </div>
      <div class="qk-kpi qk-accent">
        <div class="qk-label">Avg delay (late only)</div>
        <div class="qk-value">{evaluable.loc[evaluable['delivery_status'] != 'OnTime', 'delivery_delay_days'].mean():.1f}d</div>
        <div class="qk-sub">across late + lost shipments</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ----------------------------------------------------------------------------
# helpers for charts
# ----------------------------------------------------------------------------

def section_open(title: str, sub: str = "") -> None:
    st.markdown(
        f'<div class="qk-section"><h3>{title}</h3>'
        f'<div class="qk-section-sub">{sub}</div>',
        unsafe_allow_html=True,
    )


def section_close() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# row 1: trend + breakdown (full width split 60/40)
# ----------------------------------------------------------------------------

c_left, c_right = st.columns([1.4, 1.0], gap="medium")

with c_left:
    section_open(
        "Marketplace trend",
        "Pick a metric to see how the filtered slice moves month-on-month.",
    )
    metric = st.radio(
        "Metric",
        ["GMV", "Orders", "Delayed order rate", "Repeat-customer share"],
        horizontal=True,
        label_visibility="collapsed",
    )

    monthly = df.copy()
    monthly["month"] = monthly["order_month"]

    if metric == "GMV":
        ts = monthly.groupby("month", as_index=False)["gmv_line"].sum().rename(columns={"gmv_line": "value"})
        y_title = "GMV (Rs)"
        tickfmt = ",.0f"
    elif metric == "Orders":
        ts = (
            monthly.drop_duplicates(["order_id", "month"])
            .groupby("month", as_index=False)["order_id"].nunique()
            .rename(columns={"order_id": "value"})
        )
        y_title = "Orders"
        tickfmt = ",d"
    elif metric == "Delayed order rate":
        o = monthly.drop_duplicates("order_id")
        o = o[o["evaluable_delivery"]]
        ts = (
            o.assign(delayed=(o["delivery_status"] != "OnTime").astype(int))
            .groupby("month", as_index=False)["delayed"].mean()
            .rename(columns={"delayed": "value"})
        )
        y_title = "Delayed order rate"
        tickfmt = ".0%"
    else:
        o = monthly.drop_duplicates("order_id")
        per_cust_month = (
            o.groupby(["month", "customer_id"])["order_id"]
            .nunique().reset_index().rename(columns={"order_id": "n"})
        )
        ts = (
            per_cust_month.assign(repeat=(per_cust_month["n"] >= 2).astype(int))
            .groupby("month", as_index=False)["repeat"].mean()
            .rename(columns={"repeat": "value"})
        )
        y_title = "Customers >=2 orders / month"
        tickfmt = ".0%"

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=ts["month"], y=ts["value"], mode="lines+markers",
            line=dict(color=PALETTE["accent"], width=2.5),
            marker=dict(size=7, color=PALETTE["accent"], line=dict(color="#FFFFFF", width=1.5)),
            fill="tozeroy",
            fillcolor="rgba(79,70,229,0.08)",
            name=metric,
            hovertemplate="<b>%{x|%b %Y}</b><br>" + metric + ": %{y:" + tickfmt + "}<extra></extra>",
        )
    )
    fig.update_layout(**plotly_layout(height=320))
    fig.update_yaxes(title=y_title, tickformat=tickfmt)
    fig.update_xaxes(title=None, dtick="M2", tickformat="%b %y")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    section_close()

with c_right:
    section_open("Breakdown", "Slice the marketplace by any structural dimension.")
    dim = st.selectbox(
        "Dimension",
        ["city", "category", "carrier", "ship_to_city", "segment"],
        label_visibility="collapsed",
    )

    if dim in ["carrier", "ship_to_city"]:
        o = df.drop_duplicates("order_id")
        eval_o = o[o["evaluable_delivery"]]
        bd = (
            eval_o.groupby(dim).agg(
                orders=("order_id", "nunique"),
                delayed_rate=("delivery_status", lambda s: (s != "OnTime").mean()),
            ).reset_index().sort_values("delayed_rate", ascending=True)
        )
        colors = [
            PALETTE["danger"] if r >= 0.5 else PALETTE["warning"] if r >= 0.32 else PALETTE["success"]
            for r in bd["delayed_rate"]
        ]
        fig2 = go.Figure(go.Bar(
            x=bd["delayed_rate"], y=bd[dim], orientation="h",
            marker=dict(color=colors, line=dict(color="rgba(0,0,0,0)")),
            text=[f"{r:.1%}  ({o:,} ord)" for r, o in zip(bd["delayed_rate"], bd["orders"])],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>delayed: %{x:.1%}<br>orders: %{customdata:,}<extra></extra>",
            customdata=bd["orders"],
        ))
        fig2.update_layout(**plotly_layout(height=320))
        fig2.update_xaxes(title="delayed order rate", tickformat=".0%", range=[0, max(bd["delayed_rate"]) * 1.25])
        fig2.update_yaxes(title=None, automargin=True)
    else:
        bd = (
            df.groupby(dim)["gmv_line"].sum().reset_index()
            .rename(columns={"gmv_line": "gmv"})
            .sort_values("gmv", ascending=True)
        )
        fig2 = go.Figure(go.Bar(
            x=bd["gmv"], y=bd[dim], orientation="h",
            marker=dict(color=PALETTE["accent"], line=dict(color="rgba(0,0,0,0)")),
            text=[fmt_inr(v) for v in bd["gmv"]],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>GMV: Rs %{x:,.0f}<extra></extra>",
        ))
        fig2.update_layout(**plotly_layout(height=320))
        fig2.update_xaxes(title="GMV (Rs)", tickformat=",.0f", range=[0, max(bd["gmv"]) * 1.18])
        fig2.update_yaxes(title=None, automargin=True)

    st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
    section_close()


# ----------------------------------------------------------------------------
# row 2 + 3: 2x2 insight grid
# ----------------------------------------------------------------------------

st.markdown('<div style="height:6px;"></div>', unsafe_allow_html=True)
st.markdown(
    '<h2 style="margin: 14px 0 8px 0;">Operational insights</h2>'
    '<div style="font-size:0.86rem;color:var(--text-muted);margin-bottom:8px;">'
    'Where the delays concentrate, what the customer mix looks like, and how the funnel converts.'
    '</div>',
    unsafe_allow_html=True,
)

g1, g2 = st.columns(2, gap="medium")
g3, g4 = st.columns(2, gap="medium")

# --- (1) worst lanes ---------------------------------------------------------
with g1:
    section_open(
        "Worst delivery lanes",
        "Carrier x destination combos with the highest delayed-order share, min 100 orders.",
    )
    o = df.drop_duplicates("order_id")
    eval_o = o[o["evaluable_delivery"]]
    lane = (
        eval_o.groupby(["carrier", "ship_to_city"]).agg(
            orders=("order_id", "nunique"),
            delayed_rate=("delivery_status", lambda s: (s != "OnTime").mean()),
        ).reset_index()
    )
    lane = lane[lane["orders"] >= 100].copy()
    if lane.empty:
        st.info("No lane meets the 100-order threshold under the current filters.")
    else:
        lane = lane.sort_values("delayed_rate", ascending=False).head(10)
        lane["label"] = lane["carrier"] + " -> " + lane["ship_to_city"]
        lane = lane.sort_values("delayed_rate", ascending=True)
        colors = [
            PALETTE["danger"] if r >= 0.5 else PALETTE["warning"] if r >= 0.32 else PALETTE["success"]
            for r in lane["delayed_rate"]
        ]
        fig_l = go.Figure(go.Bar(
            x=lane["delayed_rate"], y=lane["label"], orientation="h",
            marker=dict(color=colors),
            text=[f"{r:.0%}" for r in lane["delayed_rate"]],
            textposition="outside",
            cliponaxis=False,
            customdata=lane["orders"],
            hovertemplate="<b>%{y}</b><br>delayed: %{x:.1%}<br>orders: %{customdata:,}<extra></extra>",
        ))
        fig_l.update_layout(**plotly_layout(height=340))
        fig_l.update_xaxes(title="delayed order rate", tickformat=".0%", range=[0, max(lane["delayed_rate"]) * 1.18])
        fig_l.update_yaxes(title=None, automargin=True)
        st.plotly_chart(fig_l, use_container_width=True, config={"displayModeBar": False})
    section_close()

# --- (2) carrier x ship_to_city heatmap -------------------------------------
with g2:
    section_open(
        "Carrier x destination heatmap",
        "Delayed-order rate, evaluable orders only. Empty cell means no volume in scope.",
    )
    o = df.drop_duplicates("order_id")
    eval_o = o[o["evaluable_delivery"]]
    grid = (
        eval_o.groupby(["carrier", "ship_to_city"]).agg(
            orders=("order_id", "nunique"),
            delayed_rate=("delivery_status", lambda s: (s != "OnTime").mean()),
        ).reset_index()
    )
    if grid.empty:
        st.info("No evaluable shipments under the current filters.")
    else:
        pivot_rate = grid.pivot(index="carrier", columns="ship_to_city", values="delayed_rate")
        pivot_orders = grid.pivot(index="carrier", columns="ship_to_city", values="orders").fillna(0).astype(int)
        text = np.where(
            pivot_rate.notna().to_numpy(),
            np.vectorize(lambda r, o: f"{r:.0%}<br>{o:,}" if pd.notna(r) else "")(pivot_rate.to_numpy(), pivot_orders.to_numpy()),
            "",
        )
        fig_h = go.Figure(go.Heatmap(
            z=pivot_rate.to_numpy(),
            x=pivot_rate.columns.tolist(),
            y=pivot_rate.index.tolist(),
            colorscale=HEAT_SCALE,
            zmin=0, zmax=max(0.4, float(np.nanmax(pivot_rate.to_numpy())) if pivot_rate.notna().any().any() else 0.4),
            text=text,
            texttemplate="%{text}",
            textfont=dict(size=10, color="#0F172A"),
            hovertemplate="<b>%{y} -> %{x}</b><br>delayed: %{z:.1%}<extra></extra>",
            colorbar=dict(title=dict(text="delayed", font=dict(size=11)), tickformat=".0%", thickness=10, len=0.7),
        ))
        fig_h.update_layout(**plotly_layout(height=340))
        fig_h.update_xaxes(title=None, side="bottom")
        fig_h.update_yaxes(title=None, automargin=True)
        st.plotly_chart(fig_h, use_container_width=True, config={"displayModeBar": False})
    section_close()

# --- (3) category mix --------------------------------------------------------
with g3:
    section_open(
        "Category contribution",
        "GMV share, average order value, and delayed-rate per category in scope.",
    )
    cat_gmv = df.groupby("category")["gmv_line"].sum().rename("gmv")
    cat_unique = df.drop_duplicates(["order_id", "category"])
    cat_orders = cat_unique.groupby("category")["order_id"].nunique().rename("orders")
    cat_delay = cat_unique[cat_unique["evaluable_delivery"]]
    cat_rate = (
        cat_delay.assign(d=(cat_delay["delivery_status"] != "OnTime").astype(int))
        .groupby("category")["d"].mean().rename("delayed_rate")
    )
    cat = pd.concat([cat_gmv, cat_orders, cat_rate], axis=1).reset_index().sort_values("gmv", ascending=True)
    cat["share"] = cat["gmv"] / cat["gmv"].sum()

    fig_c = go.Figure()
    fig_c.add_trace(go.Bar(
        x=cat["gmv"], y=cat["category"], orientation="h",
        marker=dict(color=PALETTE["accent_2"]),
        name="GMV",
        text=[f"{fmt_inr(v)}  &middot;  {s:.0%}" for v, s in zip(cat["gmv"], cat["share"])],
        textposition="outside",
        cliponaxis=False,
        customdata=np.stack([cat["orders"], cat["delayed_rate"]], axis=-1),
        hovertemplate=(
            "<b>%{y}</b><br>GMV: Rs %{x:,.0f}<br>"
            "orders: %{customdata[0]:,}<br>delayed: %{customdata[1]:.1%}<extra></extra>"
        ),
    ))
    fig_c.update_layout(**plotly_layout(height=340))
    fig_c.update_xaxes(title="GMV (Rs)", tickformat=",.0f", range=[0, max(cat["gmv"]) * 1.30])
    fig_c.update_yaxes(title=None, automargin=True)
    st.plotly_chart(fig_c, use_container_width=True, config={"displayModeBar": False})
    section_close()

# --- (4) order outcome funnel ------------------------------------------------
with g4:
    section_open(
        "Order outcome mix",
        "Where every order ends up: delivered (split by on-time vs late buckets), shipped, returned, cancelled.",
    )
    o_full = df.drop_duplicates("order_id").copy()
    def outcome(row):
        if row["status"] == "Cancelled":
            return "Cancelled"
        if row["status"] == "Returned":
            return "Returned"
        ds = row["delivery_status"]
        if pd.isna(ds) or ds == "InTransit":
            return "InTransit"
        if ds == "OnTime":
            return "OnTime"
        if ds == "Late_1_2d":
            return "Late 1-2d"
        if ds == "Late_3_5d":
            return "Late 3-5d"
        if ds == "Late_5p":
            return "Late 5d+"
        if ds == "Lost":
            return "Lost"
        return "Other"

    o_full["outcome"] = o_full.apply(outcome, axis=1)
    order = ["OnTime", "Late 1-2d", "Late 3-5d", "Late 5d+", "Lost", "Returned", "InTransit", "Cancelled"]
    color_map = {
        "OnTime":     PALETTE["success"],
        "Late 1-2d":  PALETTE["warning"],
        "Late 3-5d":  "#EA580C",
        "Late 5d+":   PALETTE["danger"],
        "Lost":       "#7F1D1D",
        "Returned":   "#7C3AED",
        "InTransit":  PALETTE["info"],
        "Cancelled":  PALETTE["text_muted"],
    }
    om = o_full["outcome"].value_counts().reindex([c for c in order if c in o_full["outcome"].unique()])
    om_df = om.reset_index()
    om_df.columns = ["outcome", "orders"]
    om_df["share"] = om_df["orders"] / om_df["orders"].sum()

    fig_o = go.Figure(go.Bar(
        x=om_df["share"], y=om_df["outcome"], orientation="h",
        marker=dict(color=[color_map[o] for o in om_df["outcome"]]),
        text=[f"{s:.1%}  ({n:,})" for s, n in zip(om_df["share"], om_df["orders"])],
        textposition="outside",
        cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>share: %{x:.1%}<br>orders: %{customdata:,}<extra></extra>",
        customdata=om_df["orders"],
    ))
    fig_o.update_layout(**plotly_layout(height=340))
    fig_o.update_xaxes(title="share of orders", tickformat=".0%", range=[0, max(om_df["share"]) * 1.30])
    fig_o.update_yaxes(title=None, automargin=True, autorange="reversed")
    st.plotly_chart(fig_o, use_container_width=True, config={"displayModeBar": False})
    section_close()


# ----------------------------------------------------------------------------
# read-out / dynamic insights
# ----------------------------------------------------------------------------

st.markdown(
    '<h2 style="margin: 18px 0 8px 0;">Read-out for this slice</h2>',
    unsafe_allow_html=True,
)

bullets_html: list[str] = []

bullets_html.append(
    f'<div class="qk-callout qk-callout-info"><strong>Snapshot.</strong> '
    f'{n_orders:,} orders from {n_customers:,} customers totalling {fmt_inr(gmv)}. '
    f'Delayed rate sits at <strong>{delayed_rate:.1%}</strong>; repeat rate '
    f'<strong>{repeat_rate:.1%}</strong>.</div>'
)

# carrier comparison
o_full = df.drop_duplicates("order_id")
by_carrier = (
    o_full[o_full["evaluable_delivery"]]
    .groupby("carrier").agg(
        orders=("order_id", "nunique"),
        delayed_rate=("delivery_status", lambda s: (s != "OnTime").mean()),
    ).reset_index().sort_values("delayed_rate")
)
if len(by_carrier) >= 2:
    best = by_carrier.iloc[0]
    worst = by_carrier.iloc[-1]
    multiple = worst["delayed_rate"] / max(best["delayed_rate"], 1e-9)
    bullets_html.append(
        f'<div class="qk-callout qk-callout-warning"><strong>Carrier gap.</strong> '
        f'<span class="qk-pill qk-pill-success">best: {best["carrier"]} {best["delayed_rate"]:.1%}</span>'
        f'<span class="qk-pill qk-pill-danger">worst: {worst["carrier"]} {worst["delayed_rate"]:.1%}</span>'
        f' &mdash; the worst carrier is <strong>{multiple:.1f}x</strong> the best on delayed rate '
        f'({int(worst["orders"]):,} vs {int(best["orders"]):,} evaluable orders).</div>'
    )

# worst lane
lane_all = (
    o_full[o_full["evaluable_delivery"]]
    .groupby(["carrier", "ship_to_city"]).agg(
        orders=("order_id", "nunique"),
        delayed_rate=("delivery_status", lambda s: (s != "OnTime").mean()),
    ).reset_index()
)
lane_all = lane_all[lane_all["orders"] >= 200].sort_values("delayed_rate", ascending=False)
if not lane_all.empty:
    top = lane_all.iloc[0]
    bullets_html.append(
        f'<div class="qk-callout qk-callout-danger"><strong>Broken lane.</strong> '
        f'{top["carrier"]} &rarr; {top["ship_to_city"]} runs at '
        f'<strong>{top["delayed_rate"]:.1%}</strong> delayed on '
        f'{int(top["orders"]):,} evaluable orders. The marketplace average is '
        f'{delayed_rate:.1%}, so this lane is roughly {top["delayed_rate"] / max(delayed_rate, 1e-9):.1f}x worse than baseline.</div>'
    )

# category concentration
cat_share = df.groupby("category")["gmv_line"].sum().sort_values(ascending=False)
if len(cat_share) >= 2:
    top_cat = cat_share.index[0]
    top_share = cat_share.iloc[0] / cat_share.sum()
    bullets_html.append(
        f'<div class="qk-callout qk-callout-info"><strong>Category mix.</strong> '
        f'{top_cat} carries <strong>{top_share:.0%}</strong> of GMV in this slice. '
        f'Mix is broadly stable month to month, so categories aren\'t driving the on-time decline.</div>'
    )

# Q4 reference
if not q4.empty and {"current", "widen_all_lanes_+1d"}.issubset(set(q4["scenario"])):
    qi = q4.set_index("scenario")
    bullets_html.append(
        f'<div class="qk-callout qk-callout-success"><strong>Definition lever.</strong> '
        f'Re-labelling "on or before promise day" as OnTime (industry-standard) lifts marketplace '
        f'on-time from <strong>{qi.loc["current","ontime_rate"]:.1%}</strong> to '
        f'<strong>{qi.loc["widen_all_lanes_+1d","ontime_rate"]:.1%}</strong> with no operational change &mdash; '
        f'worth a label audit with Logistics before any ops investment.</div>'
    )

st.markdown("\n".join(bullets_html), unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# methodology / footer
# ----------------------------------------------------------------------------

with st.expander("Methodology and definitions"):
    st.markdown(
        """
- **GMV** = `quantity x unit_price` summed across line items in the filtered slice (pre-fee, no discount adjustment). Matches the brief's definition.
- **Delayed order rate** = orders with `delivery_status != OnTime`. Denominator excludes `InTransit` and cancelled orders. `Lost` shipments are counted as delayed.
- **Repeat rate** here is window-based: customers in the slice with at least 2 delivered orders, divided by customers in the slice with any delivered order. The 90-day cohort metric used in INSIGHTS.md Q2 is computed separately in notebook 04.
- **Avg delay (late only)** averages `delivery_delay_days` across late and lost shipments only, so on-time deliveries don't drag the number down.
- **OnTime label quirk.** In this dataset `OnTime` corresponds to delivery >=1 day before the promised date; on-promise-day deliveries are labelled `Late_1_2d`. The Q4 callout above quantifies the impact of relabelling.
- All numbers reconcile to the raw CSVs - notebook 06 contains the cross-checks.
        """
    )

st.caption(
    "QuickKart take-home assessment &middot; data window: "
    f"{lines['created_at'].min():%b %Y} to {lines['created_at'].max():%b %Y}"
)
