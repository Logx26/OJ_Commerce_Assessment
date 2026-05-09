# QuickKart - marketplace & logistics assessment

This is my submission for the QuickKart take-home. It covers the four business
questions in the brief, the four SQL deliverables (B1-B4), a Streamlit
dashboard, and the write-up.

If you only have ten minutes, read [INSIGHTS.md](INSIGHTS.md) first - that's
the deliverable for the two stakeholders. [workflow.md](workflow.md) is the
engineering journal if you want to see how the analysis came together.

## How to run

```
pip install -r requirements.txt

# 1. (optional) re-execute the notebooks end-to-end. They write parquet
#    intermediates into data/processed/ that the dashboard reads.
jupyter nbconvert --to notebook --execute --inplace notebooks/*.ipynb

# 2. (optional) rebuild the dashboard's denormalised parquet. Only needed if
#    data/processed/dashboard_lines.parquet is missing.
python app/data_prep.py

# 3. start the dashboard.
streamlit run app/app.py
```

The Streamlit app reads from `data/processed/` so it starts in under a second.
Steps 1 and 2 are only needed if those parquet files don't already exist.

## Repo layout

```
submission/
  README.md
  INSIGHTS.md                Task A2 - findings against the four questions
  workflow.md                engineering journal (planning, debugging, decisions)
  requirements.txt
  notebooks/
    01_load_profile.ipynb    raw load + dtype + integrity profile
    02_clean_features.ipynb  cleaning, derived columns, parquet outputs
    03_task_a_eda.ipynb      Task A - monthly metrics & charts
    04_task_b_sql.ipynb      Task B - B1-B4 run via DuckDB
    05_scenario_q4.ipynb     Q4 - promise-window scenario table
    06_validate.ipynb        cross-checks: python vs SQL, totals, edge cases
  sql/
    queries.sql              B1, B2, B3, B4 - ANSI SQL, runs on DuckDB or Postgres
  app/
    app.py                   Streamlit dashboard
    styles.py                CSS + Plotly theme
    data_prep.py             builds dashboard_lines.parquet
  data/processed/            parquet outputs produced by the notebooks
```

The original CSVs live one level above this folder, untouched.

## Approach

I split the work into six notebooks, one per stage, so any single check is
re-runnable on its own and the data flow is left-to-right:

1. **Load & profile** - row counts, dtype audit, date coverage, referential
   integrity, value distributions for every status / carrier / category column.
   Anything surprising went into the assumptions list before features were
   built.
2. **Clean & feature** - cast timestamps, derive `delivery_delay_days`,
   `is_delayed`, monthly buckets, lane (`ship_from_city -> ship_to_city`),
   platform fee, order-level GMV. Outputs go to parquet so downstream notebooks
   and the dashboard share one source of truth.
3. **Task A EDA** - monthly GMV by city x category, monthly orders, active
   customers, repeat-purchase rate, delayed-order share by city x carrier.
   Each chart is paired with a short read-out so the notebook is review
   friendly.
4. **Task B SQL** - queries are written in `sql/queries.sql`, then executed
   against DuckDB attached to the raw CSVs in notebook 04 so every result is
   reproducible without spinning up a Postgres server.
5. **Q4 scenarios** - per-lane table comparing today's labelling against
   `+1d / +2d / +3d` widening on the broken lanes, widening market-wide, and
   `-1d` tightening. Drives the recommendation in INSIGHTS Q4.
6. **Validation** - notebook 06 asserts that the parquet outputs reconcile to
   the raw CSVs to the rupee, that monthly city GMV in pandas equals B1's SQL
   output across all 216 (month, city) cells, and spot-checks 10 random
   customers against the B2 cohort logic.

The full play-by-play (including dead ends and the calls I had to make on
ambiguous parts of the brief) is in [workflow.md](workflow.md).

## Key findings (full version in [INSIGHTS.md](INSIGHTS.md))

- **GMV grows month-on-month** over the 18-month window, driven by acquisition
  rather than higher per-customer activity. Top three cities (Mumbai, Delhi,
  Bangalore) carry the marketplace.
- **First-order delay does NOT measurably depress 90-day repeat** - 42.41%
  (OnTime first-orders) vs 42.07% (Delayed). The 0.34pp gap is well within
  sampling noise. The case for fixing delays must rest on support cost / fee
  credits / brand exposure, not retention.
- **Two carrier-city lanes are catastrophically broken**: Delhivery -> Jaipur
  and Delhivery -> Lucknow at ~87% delayed each. The rest of the marketplace
  sits at 25-30%. InHouse is roughly 4x better than the worst external carrier
  (7.4% vs 33.2%). Carrier switch on those two lanes is the highest-leverage
  intervention.
- **The current OnTime label is unusually strict** - it requires delivery at
  least 1 day before the promised date. Re-labelling "on or before promise day"
  as OnTime (industry standard) lifts the headline on-time rate from 73.24% to
  91.45% with zero operational change.
- **Promise widening doesn't fix the broken lanes** - even at +3 days the
  Delhivery -> Jaipur and Delhivery -> Lucknow lanes only reach ~76% on-time.
  Capacity problem, not promise problem.

## Assumptions

Stated in the notebooks where they bite, but in one place:

- **GMV** = `quantity * unit_price` summed across `order_items`, before
  platform fee, with no discount adjustment. A discount-adjusted variant
  (`gmv_after_disc`) is also computed for sanity views.
- **Delayed** = any `delivery_status` other than `OnTime`. `Lost` shipments are
  treated as delayed (the customer never received the order). `InTransit`
  shipments are excluded from delayed-rate denominators.
- **Repeat customer** = at least 2 delivered orders. **Active in month M** =
  placed any order in M (regardless of status).
- **B2 cohort** - only customers whose first delivery is at least 90 days
  before the latest delivered order are included, so every cohort member has a
  full 90-day observation window.
- **One shipment per non-cancelled order** - verified in notebook 02.
  Cancelled orders carry no shipment.
- **OnTime label quirk** - in this dataset, `OnTime` corresponds to
  `delivered_at - promised_delivery_date <= -1 day`. Delivery on the promised
  day is labelled `Late_1_2d`. The Q4 scenario notebook treats this explicitly,
  and the README's Key findings flag it.

## Limitations & next steps

- The 90-day window for B2 is what the brief asked for; if delay-fatigue plays
  out over a longer horizon the same query supports a 180-day variant by
  changing one interval.
- The B3 spec threshold (>=100 delivered orders per seller-carrier-city)
  returns zero rows because volume is thinly spread. Notebook 04 reports the
  spec-literal answer (zero rows) and adds a relaxed extension at >=30 plus a
  carrier x ship_to_city aggregation that surfaces the lane-level signal used
  in INSIGHTS Q3. The reasoning is in `sql/queries.sql` directly above the
  query.
- Only structural fields are present (no NPS, support tickets, or refund
  volumes), so the cost-of-delay number is qualitative.
- Promise scenarios assume zero second-order effects (no demand response, no
  carrier capacity reallocation). For real planning, capacity constraints on
  InHouse on the broken lanes would need to be modelled.

## AI usage

Used Claude as a coding aid - mostly for environment / boilerplate, syntax
help on the more involved Plotly figures, CSS scaffolding for the dashboard
theme, and as a rubber duck on a couple of debugging passes (the OnTime label
mismatch in Q4, and the empty B3 result). The analysis decisions, query
structure, assumption list, and findings are mine. Every number in INSIGHTS
was cross-checked against the raw CSVs by notebook 06 before it went into the
write-up.
