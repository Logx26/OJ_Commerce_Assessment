"""Global CSS and Plotly theme for the dashboard.

Palette and component styling adapted from a Lumeo-inspired reference
(indigo / sky accents on neutral slate canvas).
"""

PALETTE = {
    "bg_canvas": "#F6F7FB",
    "bg_panel": "#FFFFFF",
    "bg_elevated": "#EEF1F7",
    "border_subtle": "#E2E6EF",
    "border_strong": "#C9D1DD",
    "text_primary": "#0F172A",
    "text_secondary": "#475569",
    "text_muted": "#94A3B8",
    "accent": "#4F46E5",
    "accent_2": "#0EA5E9",
    "accent_soft": "rgba(79, 70, 229, 0.10)",
    "success": "#16A34A",
    "warning": "#CA8A04",
    "danger": "#DC2626",
    "info": "#0284C7",
}

# Used by Plotly. First few colors map to high-volume cities / carriers.
CHART_SEQUENCE = [
    "#4F46E5", "#0EA5E9", "#16A34A", "#CA8A04",
    "#DC2626", "#7C3AED", "#0F766E", "#2563EB",
    "#0284C7", "#94A3B8", "#475569", "#E2E6EF",
]

# Sequential ramp for heatmaps - light slate to indigo.
HEAT_SCALE = [
    [0.0, "#EEF1F7"],
    [0.25, "#C7D2FE"],
    [0.55, "#818CF8"],
    [0.80, "#4F46E5"],
    [1.0, "#312E81"],
]


GLOBAL_CSS = """
<style>
:root {
  --bg-canvas: #F6F7FB;
  --bg-panel: #FFFFFF;
  --bg-elevated: #EEF1F7;
  --border-subtle: #E2E6EF;
  --border-strong: #C9D1DD;
  --text-primary: #0F172A;
  --text-secondary: #475569;
  --text-muted: #94A3B8;
  --accent: #4F46E5;
  --accent-hover: #4338CA;
  --accent-soft: rgba(79, 70, 229, 0.10);
  --accent-2: #0EA5E9;
  --success: #16A34A;
  --warning: #CA8A04;
  --danger: #DC2626;
  --info: #0284C7;
}

html, body, [class*="css"] {
  font-family: "Inter", "Segoe UI", -apple-system, system-ui, sans-serif;
  color: var(--text-primary);
}

.stApp {
  background: var(--bg-canvas);
}

/* trim default streamlit top padding */
.block-container {
  padding-top: 1.5rem !important;
  padding-bottom: 3rem !important;
  max-width: 1400px !important;
}

/* hide default streamlit chrome we don't need */
[data-testid="stToolbar"] { display: none; }
footer { display: none; }
#MainMenu { visibility: hidden; }

h1, h2, h3 { color: var(--text-primary); letter-spacing: -0.01em; }
h1 { font-size: 1.75rem; font-weight: 650; }
h2 { font-size: 1.25rem; font-weight: 600; }
h3 { font-size: 1.05rem; font-weight: 600; }

/* hero banner ----------------------------------------------------------- */

.qk-banner {
  background: linear-gradient(135deg, #FFFFFF 0%, #F1F4FB 100%);
  border-left: 4px solid var(--accent);
  border: 1px solid var(--border-subtle);
  border-left: 4px solid var(--accent);
  border-radius: 14px;
  padding: 18px 22px;
  margin-bottom: 18px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.qk-banner .qk-eyebrow {
  display: inline-block;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.10em;
  text-transform: uppercase;
  color: var(--accent);
  background: var(--accent-soft);
  padding: 3px 10px;
  border-radius: 999px;
  margin-bottom: 8px;
}
.qk-banner h1 {
  margin: 0 0 4px 0;
  font-size: 1.6rem;
  font-weight: 700;
}
.qk-banner p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.94rem;
  line-height: 1.55;
}

/* KPI cards ------------------------------------------------------------- */

.qk-kpi-row {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}
.qk-kpi {
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  padding: 14px 16px 16px 16px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.qk-kpi:hover {
  border-color: var(--border-strong);
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06);
}
.qk-kpi .qk-label {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.10em;
  text-transform: uppercase;
  color: var(--text-secondary);
  margin-bottom: 6px;
}
.qk-kpi .qk-value {
  font-size: 1.6rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.15;
}
.qk-kpi .qk-sub {
  font-size: 0.78rem;
  color: var(--text-muted);
  margin-top: 4px;
}
.qk-kpi.qk-accent { border-left: 3px solid var(--accent); }
.qk-kpi.qk-warn   { border-left: 3px solid var(--warning); }
.qk-kpi.qk-danger { border-left: 3px solid var(--danger); }
.qk-kpi.qk-good   { border-left: 3px solid var(--success); }
.qk-kpi.qk-info   { border-left: 3px solid var(--info); }

/* section / chart card ------------------------------------------------- */

.qk-section {
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  padding: 16px 18px 14px 18px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
  margin-bottom: 14px;
}
.qk-section h3 {
  margin: 0 0 4px 0;
  font-size: 1rem;
  font-weight: 600;
}
.qk-section .qk-section-sub {
  font-size: 0.82rem;
  color: var(--text-muted);
  margin-bottom: 10px;
}

/* callout boxes -------------------------------------------------------- */

.qk-callout {
  border-radius: 10px;
  padding: 12px 14px;
  border: 1px solid;
  margin-bottom: 10px;
  font-size: 0.92rem;
  line-height: 1.55;
}
.qk-callout-info    { background: var(--accent-soft); border-color: rgba(79,70,229, 0.25); color: var(--text-primary); }
.qk-callout-warning { background: rgba(202,138,4, 0.08); border-color: rgba(202,138,4, 0.30); color: var(--text-primary); }
.qk-callout-danger  { background: rgba(220,38,38, 0.06); border-color: rgba(220,38,38, 0.30); color: var(--danger); }
.qk-callout-success { background: rgba(22,163,74, 0.08); border-color: rgba(22,163,74, 0.30); color: var(--text-primary); }

.qk-callout strong { color: var(--text-primary); }

/* pills ---------------------------------------------------------------- */

.qk-pill {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 600;
  border: 1px solid;
  margin-right: 6px;
}
.qk-pill-danger  { background: rgba(220,38,38, 0.10); color: var(--danger);  border-color: rgba(220,38,38, 0.35); }
.qk-pill-warning { background: rgba(202,138,4, 0.10); color: var(--warning); border-color: rgba(202,138,4, 0.35); }
.qk-pill-info    { background: rgba(2,132,199, 0.10); color: var(--info);    border-color: rgba(2,132,199, 0.35); }
.qk-pill-success { background: rgba(22,163,74, 0.10); color: var(--success); border-color: rgba(22,163,74, 0.35); }

/* sidebar -------------------------------------------------------------- */

[data-testid="stSidebar"] {
  background: var(--bg-panel);
  border-right: 1px solid var(--border-subtle);
}
[data-testid="stSidebar"] .stMultiSelect [data-baseweb="tag"] {
  background: var(--accent-soft);
  color: var(--accent);
  border: 1px solid rgba(79,70,229, 0.25);
}

/* widgets -------------------------------------------------------------- */

.stRadio [role="radiogroup"] label {
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 4px 10px;
  margin-right: 6px;
}
.stRadio [role="radiogroup"] label[data-checked="true"],
.stRadio [role="radiogroup"] label:has(input:checked) {
  background: var(--accent-soft);
  border-color: var(--accent);
  color: var(--accent);
}

div[data-baseweb="select"] > div {
  border-radius: 8px !important;
  border: 1px solid var(--border-strong) !important;
}

.stTabs [data-baseweb="tab-list"] { gap: 4px; }
.stTabs [aria-selected="true"] {
  color: var(--accent) !important;
  border-bottom: 2px solid var(--accent) !important;
}

/* expander ------------------------------------------------------------- */

.streamlit-expanderHeader, [data-testid="stExpander"] {
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  border-radius: 10px !important;
}

/* divider tightening */
hr { margin: 10px 0 !important; border-color: var(--border-subtle) !important; }
</style>
"""


def plotly_layout(title: str | None = None, height: int = 320) -> dict:
    """Common Plotly layout overrides matched to the dashboard theme."""
    return dict(
        title=dict(
            text=title or "",
            font=dict(size=14, color=PALETTE["text_primary"], family="Inter, Segoe UI, sans-serif"),
            x=0.0,
            xanchor="left",
            pad=dict(l=4, t=2),
        ),
        paper_bgcolor=PALETTE["bg_panel"],
        plot_bgcolor=PALETTE["bg_panel"],
        font=dict(family="Inter, Segoe UI, sans-serif", size=12, color=PALETTE["text_primary"]),
        margin=dict(l=10, r=10, t=36 if title else 14, b=10),
        height=height,
        xaxis=dict(
            gridcolor=PALETTE["border_subtle"],
            zerolinecolor=PALETTE["border_subtle"],
            linecolor=PALETTE["border_subtle"],
            tickfont=dict(size=11, color=PALETTE["text_secondary"]),
            title=dict(font=dict(size=12, color=PALETTE["text_secondary"])),
        ),
        yaxis=dict(
            gridcolor=PALETTE["border_subtle"],
            zerolinecolor=PALETTE["border_subtle"],
            linecolor=PALETTE["border_subtle"],
            tickfont=dict(size=11, color=PALETTE["text_secondary"]),
            title=dict(font=dict(size=12, color=PALETTE["text_secondary"])),
        ),
        legend=dict(
            bgcolor=PALETTE["bg_panel"],
            bordercolor=PALETTE["border_subtle"],
            borderwidth=1,
            font=dict(size=11, color=PALETTE["text_secondary"]),
        ),
        hoverlabel=dict(
            bgcolor=PALETTE["bg_panel"],
            bordercolor=PALETTE["border_strong"],
            font=dict(family="Inter, Segoe UI, sans-serif", color=PALETTE["text_primary"]),
        ),
    )
