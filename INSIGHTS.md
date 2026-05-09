# QuickKart - Task A2 findings

Source notebooks: `01_load_profile`, `02_clean_features`, `03_task_a_eda`, `04_task_b_sql`. The four sections below map one-to-one to the four business questions in the assessment brief so each claim is verifiable.

## Background numbers

| | |
|---|---|
| Window | 2024-07-01 to 2025-12-30 (18 months) |
| Customers | 25,000 |
| Orders | 100,000 (Delivered 82,069 / Cancelled 8,006 / Shipped 5,043 / Returned 4,882) |
| Shipments | 91,994 (every non-cancelled order has exactly one shipment) |
| Gross GMV | Rs 3,391,994,349 (qty x unit_price across all line items) |

Out of 86,951 shipments with a known outcome (everything except still-in-transit), **23,269 (26.8%) failed the delivery promise**. Eighty-eight percent of those failures are 1-2 days late. Multi-day misses (3+ days) and lost shipments together are 2,881 shipments, about 3.3% of evaluable volume.

## Q1. GMV and orders trends by city and category
*See notebook 03, sections A1.1 and A1.2.*

- GMV grows month-on-month over the 18-month window. The top three cities (Mumbai, Delhi, Bangalore) together account for the bulk of marketplace volume, consistent with their share of the customer base.
- Electronics is the largest category by GMV; Books the smallest. Category mix is broadly stable month-to-month, so leadership shouldn't expect category rotation to explain the on-time decline.
- Order count and unique active customers both trend up. Orders-per-customer-per-month is roughly flat, so the growth is driven by acquisition rather than higher per-customer activity.

## Q2. Delivery delays and their effect on repeat / cancellation / return rate
*See notebook 03 A1.3 (repeat trend) and notebook 04 B2 (90-day cohort).*

- The 90-day repeat rate is **42.41% for OnTime first-orders vs 42.07% for Delayed first-orders** (16,986 and 5,719 customers respectively). The 0.34 percentage-point gap is well within sampling noise, so we cannot claim that a delayed first delivery measurably depresses 90-day repeat in this data.
- This is a counter-intuitive finding worth flagging to the Head of Marketplace: the loyalty case for on-time delivery does not show up in the cohort comparison the brief asked for. The case for fixing delays must rest on the cost-of-delay (fee credits, support load, brand) rather than a measurable repeat-rate lift.
- Cancellation rate (8.0%) and return rate (4.9%) sit in normal e-commerce ranges. Returns do not move with delay rate at the carrier or city level, so returns appear to be a product or expectations problem rather than a logistics one.
- The cumulative monthly repeat rate trends upward over the 18-month window, but that is mostly mechanical: as the customer base ages, more customers cross the two-delivery threshold. The level matters less than the cohort comparison.

## Q3. Seller, city, carrier combinations driving delays and lost GMV
*See notebook 03 A1.4 (heatmap) and notebook 04 B3 + B3 extension.*

- **The brief's B3 threshold of >=100 delivered orders per (seller, carrier, ship_to_city) yields zero rows.** Volume is too thinly spread - 15,812 combinations exist, but the busiest hits 39 orders. The seller dimension is the bottleneck (400 sellers split across 4 carriers and 12 cities). The notebook runs the spec query and reports zero, then adds a relaxed extension at >=30 orders to surface the actual signal.
- **Carrier × ship_to_city is where the real signal lives.** Two lanes are catastrophically broken: **Delhivery → Jaipur (86.6% delayed, 1,458 orders)** and **Delhivery → Lucknow (86.6% delayed, 1,380 orders)**. Every other lane sits in the 25-30% band. These two lanes alone account for the bulk of lost GMV and are the single highest-leverage intervention.
- **Carrier-level summary:** InHouse 7.4% delayed, BlueDart 27.3%, Ekart 32.4%, Delhivery 33.2%. InHouse is roughly 4× better than the worst external carrier. Shifting volume from Delhivery to InHouse on the broken lanes (where InHouse capacity allows) is the clearest action.
- At the relaxed >=30 threshold the seller-level B3 still doesn't show seller-specific patterns - delayed-rate variance across sellers in the same carrier/city is small. The takeaway is that seller behaviour is not driving delays; carrier-and-lane behaviour is.

## Q4. Effect of tightening or relaxing promised delivery times
*See notebook 05 for the per-lane scenario table.*

- The current `OnTime` label is **unusually strict**: it requires delivery at least 1 day before the promised date. 15,831 shipments labelled `Late_1_2d` actually arrived on the promised day. Re-labelling "on or before promise day" as OnTime (industry standard) lifts the headline on-time rate from 73.24% to 91.45% with zero operational change. This is the single highest-leverage change and worth auditing with Logistics first.
- **Promise widening on the two broken lanes** is mostly cosmetic and does not solve the root cause. Even at +3 days the Delhivery → Jaipur and Delhivery → Lucknow lanes only reach ~76% on-time. They are a capacity problem, not a promise problem. The right intervention is **switching carrier** on those lanes (InHouse runs 7.4% delayed marketwide vs Delhivery 33.2%).
- **Tightening the promise by 1 day** flips roughly 40 pp of currently-on-time GMV to "delayed". Given Q2's null repeat-rate finding, there is no retention upside to extract from being faster, so this is strictly value-destroying on the visible-delay channel.
- Reminder: the dollar number on "delayed GMV" is the visible support / fee-credit / brand exposure, not lost revenue. The order still ships and the customer still pays.

## Assumptions

- **GMV** uses the brief's definition: `quantity x unit_price` across all order_items, before platform fee, with no discount adjustment. A discount-adjusted figure (`gmv_after_disc`) is also computed in `items_enriched.parquet` for sanity views.
- **Delayed** = any `delivery_status` other than `OnTime`. Lost shipments are treated as delayed (the customer never received the order). `InTransit` shipments are excluded from delayed-rate denominators since the outcome is not yet known.
- **Repeat customer** = at least 2 delivered orders. **Active in month M** = placed any order in M (regardless of status).
- **B2 90-day window**: only customers whose first delivered order is at least 90 days before the data cutoff are included, so each cohort has a full observation window.
- **One shipment per non-cancelled order** holds in this dataset (verified in notebook 02). All cancelled orders have no shipment.
- **Late_5p** is documented as 5+ days but the data caps at exactly 5 days, so the bucket is small (27 rows) and treated as part of the multi-day-late tail.
