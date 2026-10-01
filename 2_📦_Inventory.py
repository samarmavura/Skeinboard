import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import io
from ai_chat_sidebar_deepseek import render_chat_sidebar

# Page configuration - MUST be the first Streamlit command
st.set_page_config(
    page_title="Inventory — Demand & Restock Priority",
    page_icon="logimatices_logo.png",
    layout="wide"
)

REQUIRED_COLUMNS = [
    'Product Name', 'Category Name', 'Order Item Quantity', 'Sales',
    'Order Item Profit Ratio', 'Order Item Id', 'order date (DateOrders)'
]

# ==============================================================================
# DATA LOADING (same pattern as the other pages)
# ==============================================================================
@st.cache_data
def load_default_data():
    df = pd.read_excel('DataCoSupplyChainDataset.xlsx')
    return _clean_dataframe(df)


@st.cache_data
def load_uploaded_data(file_bytes: bytes, filename: str):
    buffer = io.BytesIO(file_bytes)
    if filename.lower().endswith('.csv'):
        df = pd.read_csv(buffer, encoding='latin1')
    else:
        df = pd.read_excel(buffer)
    return _clean_dataframe(df)


def _clean_dataframe(df):
    for col in ['Category Name', 'Product Name']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    return df


def validate_columns(df) -> list:
    return [c for c in REQUIRED_COLUMNS if c not in df.columns]


with st.sidebar:
    st.markdown("### 📁 Dataset")
    uploaded_file = st.file_uploader(
        "Upload your own dataset (.xlsx or .csv)",
        type=["xlsx", "csv"],
        key="inventory_uploader",
        help="Must contain Product, Category, order date, and quantity/sales columns."
    )
    if uploaded_file is None:
        st.caption("No file uploaded — using the preloaded DataCo dataset.")

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    try:
        df = load_uploaded_data(file_bytes, uploaded_file.name)
    except Exception as e:
        st.error(f"Couldn't read '{uploaded_file.name}': {e}")
        st.stop()
    missing_cols = validate_columns(df)
    if missing_cols:
        st.error(f"'{uploaded_file.name}' is missing required columns: {', '.join(missing_cols)}. "
                  f"Falling back to the preloaded dataset.")
        df = load_default_data()
    else:
        st.sidebar.success(f"✅ Using '{uploaded_file.name}' ({df.shape[0]:,} rows)")
else:
    try:
        df = load_default_data()
    except FileNotFoundError:
        st.error("Please ensure DataCoSupplyChainDataset.xlsx is in the same directory as this script, "
                  "or upload a dataset using the sidebar.")
        st.stop()


st.markdown("""
<style>
    .hero {
        padding: 2.2rem 2rem;
        border-radius: 16px;
        background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
        color: #ffffff;
        margin-bottom: 1.5rem;
    }
    .hero h1 { font-size: 2.4rem; margin-bottom: 0.2rem; color: #ffffff; }
    .hero p { font-size: 1.02rem; color: #d1d5db; max-width: 680px; margin-bottom: 0; }
    .kpi-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 1.2rem 1.35rem;
        height: 100%;
    }
    .kpi-label {
        font-size: 0.78rem; color: #6b7280; text-transform: uppercase;
        letter-spacing: 0.05em; margin-bottom: 0.4rem; font-weight: 600;
    }
    .kpi-value { font-size: 1.75rem; font-weight: 700; color: #111827; line-height: 1.1; }
    .kpi-context { font-size: 0.8rem; color: #9ca3af; margin-top: 0.35rem;
    </style> 
""", unsafe_allow_html=True)
    
st.markdown("""
<div class="hero">
    <h1> Inventory : Demand & Restock Priority</h1>
    <p>Which products to restock, and which to consider clearing.</p>
</div>
""", unsafe_allow_html=True)

# ==============================================================================
# DEMAND & RESTOCK PRIORITY ANALYTICS
#
# This dataset has no literal stock-on-hand field, so "inventory priority" is
# built from three real signals instead: total sales volume, profit margin,
# and recent demand trend. A product scores as high restock priority when
# it sells a lot, makes good margin, AND demand is trending up. A product
# with shrinking demand and thin margin surfaces as a clearance candidate.
# ==============================================================================
@st.cache_data
def compute_inventory_summary(df):
    df = df.copy()
    df['order_date'] = pd.to_datetime(df['order date (DateOrders)'], errors='coerce')
    median_date = df['order_date'].median()

    recent = df[df['order_date'] > median_date]
    earlier = df[df['order_date'] <= median_date]
    recent_qty = recent.groupby('Product Name')['Order Item Quantity'].sum()
    earlier_qty = earlier.groupby('Product Name')['Order Item Quantity'].sum()

    summary = df.groupby('Product Name').agg(
        category=('Category Name', 'first'),
        total_units=('Order Item Quantity', 'sum'),
        total_revenue=('Sales', 'sum'),
        avg_profit_ratio=('Order Item Profit Ratio', 'mean'),
        order_count=('Order Item Id', 'count'),
    ).reset_index()

    summary = summary.merge(recent_qty.rename('recent_units'), on='Product Name', how='left')
    summary = summary.merge(earlier_qty.rename('earlier_units'), on='Product Name', how='left')
    summary['recent_units'] = summary['recent_units'].fillna(0)
    summary['earlier_units'] = summary['earlier_units'].fillna(0)
    summary['growth_pct'] = (
        (summary['recent_units'] - summary['earlier_units']) / summary['earlier_units'].replace(0, np.nan)
    ) * 100
    summary['growth_pct'] = summary['growth_pct'].fillna(0)

    for col in ['total_units', 'avg_profit_ratio', 'growth_pct']:
        std = summary[col].std()
        summary[col + '_z'] = (summary[col] - summary[col].mean()) / std if std else 0

    summary['priority_score'] = (
        0.4 * summary['total_units_z'] + 0.3 * summary['avg_profit_ratio_z'] + 0.3 * summary['growth_pct_z']
    )
    return summary.sort_values('priority_score', ascending=False).reset_index(drop=True)


inventory_summary = compute_inventory_summary(df)

# ==============================================================================
# AGENT TOOLS
# ==============================================================================
def get_product_stats(product_name: str) -> dict:
    row = inventory_summary[inventory_summary['Product Name'].str.lower() == product_name.lower()]
    if row.empty:
        return {"error": f"No product named '{product_name}' found."}
    r = row.iloc[0]
    return {
        "product": r['Product Name'], "category": r['category'],
        "total_units_sold": int(r['total_units']), "total_revenue": round(r['total_revenue'], 2),
        "avg_profit_ratio": round(r['avg_profit_ratio'], 3), "growth_pct": round(r['growth_pct'], 1),
        "priority_score": round(r['priority_score'], 3),
    }


def get_top_priority_products(n: int = 5) -> list:
    top = inventory_summary.head(n)
    return top[['Product Name', 'category', 'total_units', 'avg_profit_ratio', 'growth_pct']].to_dict('records')


def get_clearance_candidates(n: int = 5) -> list:
    bottom = inventory_summary.tail(n).sort_values('priority_score')
    return bottom[['Product Name', 'category', 'total_units', 'avg_profit_ratio', 'growth_pct']].to_dict('records')


AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_product_stats",
            "description": "Get sales volume, revenue, margin, growth trend, and restock "
                            "priority score for a specific product.",
            "parameters": {
                "type": "object",
                "properties": {"product_name": {"type": "string"}},
                "required": ["product_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_priority_products",
            "description": "Get the top N products by restock priority score "
                            "(high volume, good margin, growing demand).",
            "parameters": {
                "type": "object",
                "properties": {"n": {"type": "integer", "description": "How many products to return, default 5."}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_clearance_candidates",
            "description": "Get the N lowest-priority products — low volume, thin margin, "
                            "or shrinking demand — as clearance/discontinue candidates.",
            "parameters": {
                "type": "object",
                "properties": {"n": {"type": "integer", "description": "How many products to return, default 5."}},
                "required": [],
            },
        },
    },
]

AGENT_TOOL_FUNCTIONS = {
    "get_product_stats": get_product_stats,
    "get_top_priority_products": get_top_priority_products,
    "get_clearance_candidates": get_clearance_candidates,
}

INVENTORY_SYSTEM_PROMPT = (
    "You are an inventory analytics assistant. This dataset has no literal stock-on-hand "
    "numbers, so 'restock priority' is derived from sales volume, profit margin, and recent "
    "demand trend. Use your tools to look up real numbers before answering — never guess."
)

# ==============================================================================
# RENDER
# ==============================================================================
main_col, chat_col = render_chat_sidebar(
    tools=AGENT_TOOLS,
    tool_functions=AGENT_TOOL_FUNCTIONS,
    system_prompt=INVENTORY_SYSTEM_PROMPT,
)


with main_col:
    
    st.subheader(" Network Overview")
    col1, col2, col3, col4 = st.columns(4)
    r1c1, r1c2, r1c3, r1c4 = st.columns(4)
    with r1c1:
     st.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">Categories & Regions Tracked</div>
        <div class="kpi-value">{inventory_summary.shape[0]}</div>
     </div>""", unsafe_allow_html=True)
    with r1c2:
     st.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">Active Trade Connections</div>
        <div class="kpi-value">{inventory_summary['total_units'].sum():,.0f}</div>
     </div>""", unsafe_allow_html=True)
    with r1c3:
     st.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">Market Coverage</div>
        <div class="kpi-value">{inventory_summary['avg_profit_ratio'].mean()*100:.1f}</div>
     </div>""", unsafe_allow_html=True)
    top_cat = inventory_summary.groupby('category')['total_units'].sum().idxmax()
    with r1c4:
     st.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">Most Connected</div>
        <div class="kpi-value">{top_cat}</div>
     </div>""", unsafe_allow_html=True)

    st.divider()


    tab1, tab2 = st.tabs([
        " Demand Overview",
        " Restock Priority",
        ])

    # ----------------------------------------------------------------------
    # TAB 1: Demand overview
    # ----------------------------------------------------------------------
    with tab1:
     st.subheader("Top Products by Sales Volume")
     top_n = st.slider("Show top N products", 5, 30, 15)
     top_products = inventory_summary.sort_values('total_units', ascending=False).head(top_n)

     fig = px.bar(
        top_products, x='total_units', y='Product Name', color='avg_profit_ratio',
        orientation='h', color_continuous_scale='RdYlGn',
        title=f"Top {top_n} Products by Units Sold",
        labels={'total_units': 'Total Units Sold', 'avg_profit_ratio': 'Avg Profit Ratio'}
     )
    fig.update_layout(yaxis=dict(categoryorder='total ascending'), height=500)
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
     top_products[['Product Name', 'category', 'total_units', 'total_revenue',
                    'avg_profit_ratio', 'growth_pct']].round(2),
        use_container_width=True, hide_index=True
     )

    # ----------------------------------------------------------------------
    # TAB 2: Restock priority
    # ----------------------------------------------------------------------
    with tab2:
     st.subheader("Restock Priority Ranking")
     st.caption("Score combines sales volume (40%), profit margin (30%), and recent demand "
                "growth (30%). Higher score = higher restock priority.")

     view = st.radio("View", ["Top priority (restock)", "Bottom priority (clearance candidates)"], horizontal=True)
     n_show = st.slider("Number of products to show", 5, 30, 10, key="priority_n")

     if view == "Top priority (restock)":
        display_df = inventory_summary.head(n_show)
     else:
        display_df = inventory_summary.tail(n_show).sort_values('priority_score')

    st.dataframe(
        display_df[['Product Name', 'category', 'total_units', 'total_revenue',
                    'avg_profit_ratio', 'growth_pct', 'priority_score']].style.format({
            'total_revenue': '${:,.0f}',
            'avg_profit_ratio': '{:.1%}',
            'growth_pct': '{:+.1f}%',
            'priority_score': '{:.2f}',
        }),
        use_container_width=True, hide_index=True
    )

    csv = inventory_summary.to_csv(index=False).encode('utf-8')
    st.download_button("⬇️ Download full priority ranking as CSV", csv, "inventory_priority.csv", "text/csv")
