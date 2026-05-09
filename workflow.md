# Workflow notes

This file is a running engineering journal of how the assessment came together.
It captures the order of work, the dead-ends, the things that surprised me, and
the calls I had to make. The deliverables themselves (notebooks, SQL, dashboard)
are clean; this is the messy version behind them.


## 0. Reading the brief

First pass through `ASSESSMENT.md`. Two things were obvious right away:

- The four business questions drive everything. They map cleanly onto the four
  SQL deliverables (B1-B4) and onto the four sections of the write-up. So the
  natural shape of the project is "answer the questions once, then re-package
  for whichever audience is reading next."
- The brief mixes Marketplace (commercial) and Logistics (operational)
  stakeholders. That meant the deliverable couldn't just be a metrics dashboard;
  the write-up had to translate technical findings into actions for both teams.

Before touching code I sketched the rough layout on paper:

```
01 load + profile     → know what we have
02 clean + features   → one source of truth for downstream
03 EDA (Task A)       → answer business questions visually
04 SQL  (Task B)      → answer them in SQL, sanity-check vs notebook 03
05 scenario (Q4)      → promise-window what-if
06 validate           → cross-check python ↔ SQL ↔ raw CSVs
README + INSIGHTS     → external-facing summary
streamlit             → live filter / explore for non-analysts
```

I committed to that order before writing anything. The discipline of building
the pipeline left to right (raw → enriched parquet → analysis → dashboard) saved
a lot of pain later because every downstream artefact pulled from the same
trustworthy parquet layer.


## 1. Loading and profiling the raw data

The CSVs are small enough that everything fits in pandas, so I didn't bother
with chunked loads. First-pass profile:

- 6 tables, 25k customers, 400 sellers, 3k products, 100k orders,
  ~170k order_items, ~92k shipments.
- Date range 2024-07-01 to 2025-12-30 (18 months), no gaps in months.
- Status distribution (orders): Delivered 82,069 / Cancelled 8,006 /
  Shipped 5,043 / Returned 4,882. The 5,043 "Shipped" rows are in-transit.
- Carriers: Delhivery, BlueDart, Ekart, InHouse. Ship-to cities: 12.
- Categories: Electronics, Fashion, Grocery, Home & Kitchen, Books.

The thing I checked next was referential integrity. I expected some dangling
rows but everything tied out:

- Every order has a customer.
- Every order_item has a product and an order.
- 91,994 shipments tie 1-to-1 to non-cancelled orders (8,006 cancelled orders
  carry no shipment - confirmed). So "one shipment per non-cancelled order" is a
  real invariant in this dataset, not an assumption.

That last point mattered later: it meant carrier and ship_to_city are
unambiguous per order, which simplified the B3 query.


## 2. Cleaning, derived columns, and the assumptions that bit later

This is where most of the early time went, because every downstream notebook
depends on these decisions.

The non-trivial bits:

- **Timestamps.** All four time columns (`created_at`, `shipped_at`,
  `delivered_at`, `promised_delivery_date`) parse cleanly. Cast everything to
  `datetime64[ns]` and `signup_date` / `promised_delivery_date` to date.
- **GMV definition.** The brief says `quantity * unit_price`, no discount
  adjustment, pre-fee. I computed both `gmv_line` (the brief's definition) and
  `gmv_after_disc` (for sanity). The dashboard and INSIGHTS report `gmv_line`.
- **Order-level GMV.** Aggregated up from items. Stored as `order_gmv` on
  `orders_enriched.parquet` so downstream code never has to re-join.
- **Delay days.** `delivery_delay_days = (delivered_at::date -
  promised_delivery_date)`. Negative = early, zero = on-promise-day, positive =
  late.
- **`is_delayed`.** True when `delivery_status != 'OnTime'`. I treat `Lost`
  shipments as delayed (the customer never received the order). `InTransit` is
  excluded from delayed-rate denominators - we don't know the outcome yet.
- **First delivered order per customer.** Saved to `customer_first_order.parquet`
  with the delay status of that first delivery. This is what the B2 cohort
  query keys off.

### The OnTime label trap (found in stage 4, not stage 2)

This one bit me later. When I started building the Q4 scenario notebook I
defined "current on-time" as `delay <= 0` (i.e. delivered on or before the
promise day - the industry-standard definition). The number came back at
~91.5%, which contradicted the headline "26.8% delayed" finding from notebook
03.

Investigation:

```
crosstab(delivery_status, delivery_delay_days)
```

revealed that in this dataset, `OnTime` is exclusively `delay <= -1`. Delivery
on the promised day itself is labelled `Late_1_2d`. So the data uses a stricter
definition of "on time" than I'd assumed.

I had two choices:
1. Override the labels and recompute everything against `delay <= 0`.
2. Treat the dataset's labelling as source of truth and surface the gap as a
   finding for stakeholders.

I picked option 2, because (a) overriding labels would diverge from any
downstream BI tooling that might already report off the same field, and (b) the
gap itself is an actionable insight - "you can lift your headline on-time rate
18 percentage points just by adopting the industry-standard definition" is a
useful business observation.

That observation became the lead bullet in INSIGHTS Q4 and the recommended
first action ahead of any operational change.

Lesson: never trust a label without inspecting the underlying numeric field.


## 3. Task A EDA

The four A1 sub-questions map to four notebook sections:

- A1.1 monthly GMV by city × category - pivot + heatmap.
- A1.2 monthly orders + monthly active customers - simple line.
- A1.3 monthly repeat-purchase rate - cumulative ≥2 delivered / active.
- A1.4 delayed-order share by city × carrier - heatmap.

The interesting findings emerged in A1.4. Two cells in the carrier × city
heatmap glowed bright red:

- Delhivery → Jaipur ≈ 87% delayed
- Delhivery → Lucknow ≈ 87% delayed

Every other (carrier, city) cell sat in the 25-30% band. I wasn't expecting
that level of concentration. Before claiming "Delhivery is broken in Jaipur" I
checked:

- Volume - 1,400+ orders each, not noise.
- Time stability - both lanes were broken across all 18 months, not a one-time
  spike.
- Seller mix - the bad delivered-rate didn't track with which seller shipped.
  It was a lane property, not a seller property.

That's the finding I led with for Q3.


## 4. Task B SQL

Wrote the queries directly in `sql/queries.sql` with each block commented as
its own deliverable. Ran them against the raw CSVs via DuckDB
(`CREATE OR REPLACE VIEW {name} AS SELECT * FROM read_csv_auto(...)`) inside
notebook 04.

### B1 - monthly city metrics

Straightforward GROUP BY. The wrinkle was the repeat-purchase rate
definition. I went with "customers active in month M who already have ≥2
delivered orders by end of M" rather than "customers active in M with a prior
order" because it matched the cumulative trend I was charting in notebook 03.
Either is defensible; I documented the choice in the SQL.

### B2 - first-order delay → 90-day repeat

Three CTEs: rank deliveries per customer, isolate the first, gate by 90-day
eligibility from the data cutoff so every cohort member has a full window.

The result was the surprise of the project:

- OnTime first-orders: 16,986 customers, 42.41% repeated within 90 days.
- Delayed first-orders: 5,719 customers, 42.07% repeated.

A 0.34 percentage-point gap. That's well within sampling noise. I had been
expecting a 5-10pp gap. Two possibilities:

1. The signal genuinely isn't there in this cut.
2. The Lost / Returned customers were filtered out of "first delivered order"
   and they're the ones who churn - so the cohort is biased.

I ran a sensitivity check: defined the cohort instead as "first non-cancelled
order regardless of delivery success" and re-ran. The gap stayed within 1pp.

So the conclusion stands: in this data, first-order delay does not measurably
depress 90-day repeat. That null result reframed Q4 - the business case for
fixing delays has to rest on visible cost (fee credits, support load, brand
exposure), not retention.

I flagged this explicitly in INSIGHTS Q2 because it's counter-intuitive enough
that a reviewer would otherwise assume I'd computed it wrong.

### B3 - the empty result set

Wrote the query exactly as the brief specifies: GROUP BY (seller, carrier,
ship_to_city), HAVING `COUNT(*) >= 100`. Zero rows.

First reaction: bug. I'd had a similar issue earlier where a date filter
silently dropped everything, so I assumed the same here. Walked through the
query line by line, ran each CTE separately. Numbers all looked right.

Then I distributed the order count:

```sql
SELECT MAX(orders), AVG(orders), COUNT(*)
FROM (SELECT seller_id, carrier, ship_to_city, COUNT(*) AS orders ...
      GROUP BY 1,2,3)
```

15,812 distinct combinations, busiest one had 39 orders. The threshold of 100
just doesn't fit this dataset's shape - 400 sellers across 4 carriers and 12
cities means most cells have a handful of orders.

I had to decide what to do. Three options:

1. Lower the threshold and pretend the brief said 30.
2. Return zero rows, mention the issue in passing.
3. Return zero rows as the spec-literal answer, then add a relaxed
   extension at >=30 that surfaces the actual signal, plus a carrier ×
   ship_to_city aggregation that sidesteps the seller dimension entirely.

Option 3. Both audiences get what they need: the brief's literal answer is
honoured, and the extension explains why the lane-level aggregation is the
right unit of analysis for this dataset. Annotated the SQL with a header note
so a reviewer doesn't have to re-derive the reasoning.

### B4 - rewrite + indexes

The original has two correlated subqueries against the same `shipments` table
- one to fetch `delivered_at`, one for the EXISTS predicate. Replaced both
with a single inner join + `WHERE delivery_status != 'OnTime'`.

Index recommendations: `shipments(order_id)` for the FK join,
`shipments(delivery_status, order_id)` covering for the rewrite (since ~73% of
shipments are OnTime, the filter trims a lot before the join),
`orders(customer_id)` for the customer join.

I called out the behavioural caveat: the rewrite drops orders without any
shipment, but so does the original because EXISTS already required at least
one shipment row. So the rewrite is behaviour-preserving on this schema.


## 5. Q4 scenarios

Originally planned a fuller elasticity model. After Q2 came back null, that
plan didn't make sense - if delay → repeat doesn't show up in this data, no
elasticity number will be honest. So I scoped down to a counterfactual table:

- Current state.
- `+1d / +2d / +3d` widening on the broken lanes only.
- `+1d / +2d` widening market-wide.
- `-1d` tightening market-wide.

For each scenario, recompute on-time rate against the modified promise. The
takeaways:

- Widening the broken lanes by even 3 days only gets them to ~76% on-time -
  these are capacity problems, not promise problems.
- Widening market-wide by 1 day lifts the headline from 73.2% to 91.4% (this
  is the same as the label-audit gap).
- Tightening by 1 day flips ~40pp of GMV to "delayed", with no retention
  upside to extract per Q2.

Scenario notebook saves a lane-level table (`q4_lane_scenarios.parquet`) and a
marketplace summary (`q4_marketplace_summary.parquet`). The dashboard surfaces
the headline number from the summary in its read-out.


## 6. Validation pass

Before writing the README I built notebook 06 to assert that everything ties
out. The checks:

- Total GMV from raw `order_items.csv` = total GMV from `items_enriched.parquet`,
  to the rupee.
- Python pivot of monthly GMV by city = SQL B1 result, across all 216 (month,
  city) cells, max abs diff 0.00.
- Order status counts sum to 100,000.
- Shipment count = non-cancelled orders = 91,994.
- B2 cohort spot-check: 5 random customers from each cohort, manually trace
  their delivered-order timeline against the eligibility / repeat flag.
- Edge cases: 497 customers with zero delivered orders (excluded from B2
  denominator), 5,043 InTransit (excluded from delayed denominator), 430 Lost
  (counted as delayed).
- Headline delayed rate of 26.76% reproduced from the parquet.

The cross-check was the most useful single artefact in the project. It gave me
the confidence to publish numbers in INSIGHTS that I hadn't computed by hand.


## 7. Dashboard

Built once as a quick-functional version (Streamlit's default styling, just
the required filters and KPI strip) so the data plumbing was correct, then
rebuilt on top of a custom CSS theme.

Design choices:

- **Pre-aggregate everything at startup.** The dashboard loads from
  `dashboard_lines.parquet` (170k rows of denormalised line items with
  category, carrier, delivery status, etc. all joined in). Every chart is a
  groupby on that one DataFrame, so re-renders on filter change are
  sub-second.
- **5-card KPI strip with severity colour coding.** Delayed rate and repeat
  rate get a red / amber / green left-border based on thresholds. Makes the
  state of the marketplace legible at a glance.
- **Trend + breakdown above, 2x2 insights below.** The two charts a stakeholder
  asks for first are "how is metric X trending" and "split it by Y", so those
  go full-width on top. The 2x2 grid below answers the next four questions:
  - Worst lanes: where to focus carrier negotiations.
  - Carrier × destination heatmap: structural view of who fails where.
  - Category contribution: GMV mix.
  - Order outcome funnel: delivered vs late buckets vs returned vs cancelled,
    so the "where do orders end up" picture is in one chart.
- **Dynamic read-out under the charts.** Bullets are computed from the filtered
  slice (worst lane, best/worst carrier, category mix, Q4 reference) so when
  the user filters down to e.g. one city, the bullets update accordingly.
- **Methodology expander at the bottom.** Definitions live where someone
  questioning a number can find them in two clicks.

Plotly theming was tuned to match the dashboard chrome (Inter font, slate
gridlines, white panels) so the charts feel embedded rather than dropped in.


## 8. Things I'd do differently with more time

- **Cohort retention curve.** Q2's null finding deserves a chart of
  cumulative-repeat-by-day-since-first-delivery, faceted by cohort, so the
  curves visibly overlap. A bar chart of two cohort means doesn't really
  convince a sceptic the way a pair of overlapping curves would.
- **Carrier capacity as a constraint in Q4.** "Switch the broken lanes to
  InHouse" is the right recommendation, but I haven't proven InHouse can
  absorb the volume. With more time I'd model fulfilled-shipments-per-day per
  carrier and quantify the headroom.
- **A simple anomaly detector on lane-month delayed rate.** The two broken
  lanes are obvious by inspection, but a z-score on lane × month would catch
  newer drifts before they show up in the 18-month average.

None of these change the headline conclusions, but they'd harden the case.
