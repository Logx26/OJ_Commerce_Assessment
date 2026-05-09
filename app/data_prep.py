"""Build a single denormalised line-item table the Streamlit app loads at startup.

Run once after the notebooks have written `data/processed/`:
    python app/data_prep.py
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT.parent
PROC = ROOT / 'data' / 'processed'

orders = pd.read_parquet(PROC / 'orders_enriched.parquet')
items = pd.read_parquet(PROC / 'items_enriched.parquet')
products = pd.read_csv(RAW / 'products.csv')[['product_id', 'category']]

order_dims = orders[[
    'order_id', 'customer_id', 'created_at', 'order_month', 'city', 'segment',
    'carrier', 'ship_to_city', 'delivery_status', 'is_delayed',
    'delivery_delay_days', 'status',
]]

lines = (
    items[['order_id', 'product_id', 'seller_id', 'quantity', 'unit_price', 'gmv_line']]
    .merge(products, on='product_id', how='left')
    .merge(order_dims, on='order_id', how='left')
)

lines['evaluable_delivery'] = lines['delivery_status'].isin(
    ['OnTime', 'Late_1_2d', 'Late_3_5d', 'Late_5p', 'Lost']
)

out = PROC / 'dashboard_lines.parquet'
lines.to_parquet(out, index=False)
print(f"wrote {out}  rows={len(lines):,}  cols={list(lines.columns)}")
