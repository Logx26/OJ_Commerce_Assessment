-- ============================================================================
-- QuickKart - Task B SQL queries (B1, B2, B3, B4)
--
-- Verified end-to-end in DuckDB against the raw CSVs;
-- see notebook 04_task_b_sql.ipynb for the run harness and result outputs.
--
-- Tables expected in scope: customers, sellers, products, orders,
--                          order_items, shipments
-- ============================================================================


-- ----------------------------------------------------------------------------
-- B1. Monthly Marketplace Metrics
--
-- For each (calendar month, customer city) return:
--     gmv, number_of_orders, unique_customers, repeat_purchase_rate
--
-- repeat_purchase_rate = customers active in month M who already have at
-- least 2 delivered orders by the end of M, divided by customers active in M.
-- A customer becomes "repeat" the moment their 2nd delivery arrives.
-- ----------------------------------------------------------------------------

WITH order_gmv AS (
    SELECT order_id, SUM(quantity * unit_price) AS gmv
    FROM order_items
    GROUP BY order_id
),
month_orders AS (
    SELECT
        DATE_TRUNC('month', o.created_at)::DATE AS month,
        c.city,
        o.customer_id,
        o.order_id,
        og.gmv
    FROM orders o
    JOIN customers c USING (customer_id)
    LEFT JOIN order_gmv og USING (order_id)
),
delivered_ranked AS (
    SELECT
        o.customer_id,
        s.delivered_at,
        ROW_NUMBER() OVER (PARTITION BY o.customer_id ORDER BY s.delivered_at) AS rn
    FROM orders o
    JOIN shipments s USING (order_id)
    WHERE s.delivered_at IS NOT NULL
),
became_repeat AS (
    -- The 2nd delivery per customer = the moment they qualify as repeat.
    SELECT customer_id, delivered_at AS became_repeat_at
    FROM delivered_ranked
    WHERE rn = 2
),
city_month AS (
    SELECT month, city,
           SUM(gmv)                  AS gmv,
           COUNT(*)                  AS number_of_orders,
           COUNT(DISTINCT customer_id) AS unique_customers
    FROM month_orders
    GROUP BY month, city
),
city_month_repeat AS (
    SELECT mo.month, mo.city,
           COUNT(DISTINCT mo.customer_id) AS repeat_customers
    FROM month_orders mo
    JOIN became_repeat br ON br.customer_id = mo.customer_id
    WHERE br.became_repeat_at < (mo.month + INTERVAL '1 month')
    GROUP BY mo.month, mo.city
)
SELECT
    cm.month,
    cm.city,
    ROUND(cm.gmv, 2) AS gmv,
    cm.number_of_orders,
    cm.unique_customers,
    ROUND(COALESCE(cmr.repeat_customers, 0) * 1.0
          / NULLIF(cm.unique_customers, 0), 4) AS repeat_purchase_rate
FROM city_month cm
LEFT JOIN city_month_repeat cmr USING (month, city)
ORDER BY cm.month, cm.city;


-- ----------------------------------------------------------------------------
-- B2. Impact of First-Order Delay on Repeat
--
-- Compare the 90-day repeat rate for customers whose first delivered order
-- was OnTime vs Delayed (any non-OnTime status).
--
-- Eligibility: a customer is included only if their first delivery is at
-- least 90 days before the latest delivery in the data, so every cohort
-- member has a full 90-day observation window.
-- A customer is counted as "repeated within 90 days" if there is any further
-- delivered order in the (first_delivery, first_delivery + 90 days] window.
-- ----------------------------------------------------------------------------

WITH delivered_orders AS (
    SELECT o.order_id, o.customer_id, s.delivered_at, s.delivery_status
    FROM orders o
    JOIN shipments s USING (order_id)
    WHERE s.delivered_at IS NOT NULL
),
ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY delivered_at) AS rn
    FROM delivered_orders
),
first_orders AS (
    SELECT
        customer_id,
        delivered_at AS first_delivered_at,
        CASE WHEN delivery_status = 'OnTime' THEN 'OnTime' ELSE 'Delayed' END
            AS first_order_delay_status
    FROM ranked
    WHERE rn = 1
),
data_cutoff AS (
    SELECT MAX(delivered_at) AS max_delivered FROM delivered_orders
),
eligible AS (
    SELECT fo.*
    FROM first_orders fo
    CROSS JOIN data_cutoff d
    WHERE fo.first_delivered_at + INTERVAL '90 day' <= d.max_delivered
),
repeats AS (
    SELECT
        e.customer_id,
        e.first_order_delay_status,
        CASE WHEN EXISTS (
            SELECT 1
            FROM delivered_orders d2
            WHERE d2.customer_id = e.customer_id
              AND d2.delivered_at >  e.first_delivered_at
              AND d2.delivered_at <= e.first_delivered_at + INTERVAL '90 day'
        ) THEN 1 ELSE 0 END AS repeated_within_90d
    FROM eligible e
)
SELECT
    first_order_delay_status,
    COUNT(*)                                            AS customers,
    SUM(repeated_within_90d)                            AS repeated,
    ROUND(SUM(repeated_within_90d) * 1.0 / COUNT(*), 4) AS "90_day_repeat_rate"
FROM repeats
GROUP BY first_order_delay_status
ORDER BY first_order_delay_status;


-- ----------------------------------------------------------------------------
-- B3. Seller-Carrier Performance
--
-- For each (seller, carrier, ship_to_city) combination with at least 100
-- delivered orders return:
--     total_gmv, delayed_gmv, delayed_order_rate, avg_delay_days
--
-- An order can have multiple sellers via order_items, so GMV is attributed
-- per seller-share of each order. Each non-cancelled order has exactly one
-- shipment, so carrier and ship_to_city are unambiguous per order.
--
-- Note on this dataset: the spec threshold of >=100 returns zero rows here
-- because volume is thinly spread (400 sellers x 4 carriers x 12 cities;
-- the busiest combo has 39 delivered orders). The query is the literal
-- answer to the brief. See notebook 04 for a relaxed-threshold extension
-- and a carrier x ship_to_city aggregation that surface the lane-level
-- signal used in INSIGHTS.md Q3.
-- ----------------------------------------------------------------------------

WITH order_seller AS (
    SELECT
        o.order_id,
        oi.seller_id,
        s.carrier,
        s.ship_to_city,
        s.delivery_status,
        s.delivered_at,
        o.promised_delivery_date,
        SUM(oi.quantity * oi.unit_price) AS seller_gmv
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    JOIN shipments  s  ON s.order_id  = o.order_id
    WHERE s.delivered_at IS NOT NULL
    GROUP BY o.order_id, oi.seller_id, s.carrier, s.ship_to_city,
             s.delivery_status, s.delivered_at, o.promised_delivery_date
)
SELECT
    seller_id,
    carrier,
    ship_to_city,
    COUNT(*)                                AS delivered_orders,
    ROUND(SUM(seller_gmv), 2)               AS total_gmv,
    ROUND(SUM(CASE WHEN delivery_status <> 'OnTime'
                   THEN seller_gmv ELSE 0 END), 2) AS delayed_gmv,
    ROUND(AVG(CASE WHEN delivery_status <> 'OnTime'
                   THEN 1.0 ELSE 0.0 END), 4)      AS delayed_order_rate,
    ROUND(AVG(CASE WHEN delivery_status <> 'OnTime'
                   THEN (delivered_at::DATE - promised_delivery_date::DATE)
              END), 2)                              AS avg_delay_days
FROM order_seller
GROUP BY seller_id, carrier, ship_to_city
HAVING COUNT(*) >= 100
ORDER BY delayed_gmv DESC;


-- ----------------------------------------------------------------------------
-- B4. Query Optimisation
-- ----------------------------------------------------------------------------

-- Original (slow) version, copied from the assessment for reference:
--
--   SELECT o.order_id,
--          (SELECT delivered_at
--           FROM shipments s
--           WHERE s.order_id = o.order_id) AS delivered_at,
--          o.created_at,
--          c.city
--   FROM orders o
--   JOIN customers c ON c.customer_id = o.customer_id
--   WHERE EXISTS (
--       SELECT 1
--       FROM shipments s2
--       WHERE s2.order_id = o.order_id
--         AND s2.delivery_status <> 'OnTime'
--   );


-- (a) Rewrite

SELECT
    o.order_id,
    s.delivered_at,
    o.created_at,
    c.city
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
JOIN shipments s ON s.order_id    = o.order_id
WHERE s.delivery_status <> 'OnTime';


-- (b) Why this is faster
--
-- The original runs two correlated sub-queries against shipments per row of
-- orders: one to fetch delivered_at, one to test the EXISTS predicate. That
-- effectively probes shipments twice per order, which on 100k orders means
-- 200k point lookups. The planner cannot turn correlated sub-queries with
-- the same target table into a single scan.
--
-- The rewrite replaces both sub-queries with a single inner join to
-- shipments. The planner can choose a hash join (build the smaller side,
-- probe the larger), push the delivery_status filter down so most rows are
-- discarded before the join, and stream rows through. shipments is read
-- once, not twice. On the 100k / 92k tables in this dataset the rewrite is
-- typically an order of magnitude faster.
--
-- Caveat: the rewrite drops orders without a shipment (cancelled in this
-- dataset). That matches the original behaviour, since EXISTS already
-- required at least one shipment row to exist.


-- (c) Indexes that support these queries

-- 1. shipments(order_id)
--    The FK index. Drives the join in the rewrite and the EXISTS in the
--    original. Without it the planner is forced into a full table scan or
--    hash build of the entire shipments table for every query.
--
-- 2. shipments(delivery_status, order_id)
--    Composite index for the rewrite. The planner can seek directly to
--    non-OnTime rows and read order_id without going back to the heap. Since
--    about 73% of shipments are OnTime in this data, this trims the work
--    materially.
--
-- 3. orders(customer_id)
--    FK index for the orders <-> customers join. Standard. Helps every
--    customer-keyed query in this codebase, not just B4.
--
-- 4. customers(customer_id)
--    Already the primary key (assumed), so no action required. Listed for
--    completeness.
--
-- For B1, B2, B3 the same FK indexes pay off, plus
-- order_items(order_id, seller_id) helps B3's per-seller rollup, and
-- orders(created_at) helps the date_trunc('month', ...) filter in B1.
