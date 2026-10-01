import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import io
from ai_chat_sidebar_deepseek import render_chat_sidebar

st.set_page_config(
    page_title="Delieveries",
    page_icon="logimatices_logo.png",
    layout="wide"
)

REQUIRED_COLUMNS = [
    'Category Name', 'Order Region', 'Shipping Mode',
    'Days for shipping (real)', 'Days for shipment (scheduled)',
    'Late_delivery_risk', 'Order Item Quantity'
]

# Loading the preloaded/Historical data to the system

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
    for col in ['Category Name', 'Order Region', 'Shipping Mode']:
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
        key="deliveries_uploader",
        help="Must contain Region, Shipping Mode, shipping day, and late-delivery columns."
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
        st.error("Please ensure preloaded/default data is in the same directory as this script, "
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
""", unsafe_allow_html=True)
    
st.markdown("""
<div class="hero">
    <h1> Deliveries — Shipping Mode Optimization</h1>
    <p>Find which shipping mode actually performs best, by region.</p>
</div>
""", unsafe_allow_html=True)

# =================================
# the shipping mode performance recommendation table and the graph view below are built on the aggragate of
# late-delievery rate and delay by region and shipping mode.
# =================================
@st.cache_data
def compute_mode_performance(df):
    perf = df.groupby(['Order Region', 'Shipping Mode']).agg(
        order_count=('Order Item Quantity', 'count'),
        late_delivery_rate=('Late_delivery_risk', 'mean'),
        avg_days_real=('Days for shipping (real)', 'mean'),
        avg_days_scheduled=('Days for shipment (scheduled)', 'mean'),
    ).reset_index()
    perf['avg_delay'] = perf['avg_days_real'] - perf['avg_days_scheduled']
    return perf


@st.cache_data
def compute_recommendations(perf):
    """
    For each region: find the current dominant mode (highest order volume)
    vs. the best-performing mode (lowest late-delivery rate). Flags a
    mismatch when the mode actupyally being used most isn't the best one.
    """
    rows = []
    for region, group in perf.groupby('Order Region'):
        dominant = group.loc[group['order_count'].idxmax()]
        best = group.loc[group['late_delivery_rate'].idxmin()]
        rows.append({
            'Order Region': region,
            'Current Dominant Mode': dominant['Shipping Mode'],
            'Current Late Delivery Rate': dominant['late_delivery_rate'],
            'Recommended Mode': best['Shipping Mode'],
            'Recommended Late Delivery Rate': best['late_delivery_rate'],
            'Potential Improvement (pts)': (dominant['late_delivery_rate'] - best['late_delivery_rate']) * 100,
            'Mismatch': dominant['Shipping Mode'] != best['Shipping Mode'],
        })
    return pd.DataFrame(rows).sort_values('Potential Improvement (pts)', ascending=False)


perf_df = compute_mode_performance(df)
rec_df = compute_recommendations(perf_df)


def get_region_mode_performance(region: str) -> dict:
    """Agent tool: full mode breakdown for one region."""
    sub = perf_df[perf_df['Order Region'].str.lower() == region.lower()]
    if sub.empty:
        return {"error": f"No data for region '{region}'."}
    return sub.sort_values('late_delivery_rate').to_dict('records')


def get_region_recommendation(region: str) -> dict:
    """Agent tool: the recommended mode vs currently dominant mode for a region."""
    sub = rec_df[rec_df['Order Region'].str.lower() == region.lower()]
    if sub.empty:
        return {"error": f"No data for region '{region}'."}
    return sub.iloc[0].to_dict()


AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_region_mode_performance",
            "description": "Get the late-delivery rate and delay for every shipping mode "
                            "used in a specific region.",
            "parameters": {
                "type": "object",
                "properties": {"region": {"type": "string"}},
                "required": ["region"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_region_recommendation",
            "description": "Get the recommended shipping mode vs the currently dominant "
                            "mode for a specific region, including potential improvement.",
            "parameters": {
                "type": "object",
                "properties": {"region": {"type": "string"}},
                "required": ["region"],
            },
        },
    },
]

AGENT_TOOL_FUNCTIONS = {
    "get_region_mode_performance": get_region_mode_performance,
    "get_region_recommendation": get_region_recommendation,
}

DELIVERIES_SYSTEM_PROMPT = (
    "You are a logistics assistant embedded in a deliveries/shipping mode optimization dashboard. "
    "Use your tools to look up real historical late-delivery rates by region and shipping mode "
    "before answering — never guess numbers. Explain trade-offs in plain business language."
)

# RENDER
main_col, chat_col = render_chat_sidebar(
    tools=AGENT_TOOLS,
    tool_functions=AGENT_TOOL_FUNCTIONS,
    system_prompt=DELIVERIES_SYSTEM_PROMPT,
)



with main_col:
   
    # --------------------------------------------------------------------
    # KPI ROW
    # --------------------------------------------------------------------
    overall_late_rate = df['Late_delivery_risk'].mean()
    overall_avg_delay = (df['Days for shipping (real)'] - df['Days for shipment (scheduled)']).mean()
    mismatch_count = rec_df['Mismatch'].sum()
    best_overall_mode = perf_df.groupby('Shipping Mode')['late_delivery_rate'].mean().idxmin()

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Overall Late Delivery Rate", f"{overall_late_rate*100:.1f}%")
    with k2:
        st.metric("Avg Delay vs Scheduled", f"{overall_avg_delay:+.2f} days")
    with k3:
        st.metric("Regions Using Suboptimal Mode", f"{mismatch_count} / {len(rec_df)}")
    with k4:
        st.metric("Most Reliable Mode Overall", best_overall_mode)

    st.divider()

    tab1, tab2 = st.tabs([
        " Transport Mode Performance by Region",
        " Optimization Recommendations",
    ])

    # ----------------------------------------------------------------------
    # TAB 1: Mode performance
    # ----------------------------------------------------------------------
    with tab1:
        st.subheader("Late Delivery Rate by Shipping Mode")
        region_pick = st.selectbox("Select a region", sorted(perf_df['Order Region'].unique()))
        region_data = perf_df[perf_df['Order Region'] == region_pick].sort_values('late_delivery_rate')

        fig = px.bar(
            region_data, x='Shipping Mode', y='late_delivery_rate',
            color='late_delivery_rate', color_continuous_scale='RdYlGn_r',
            title=f"Late Delivery Rate by Mode — {region_pick}",
            labels={'late_delivery_rate': 'Late Delivery Rate'}
        )
        fig.update_layout(yaxis_tickformat='.0%')
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(
            region_data[['Shipping Mode', 'order_count', 'late_delivery_rate', 'avg_days_real',
                         'avg_days_scheduled', 'avg_delay']].round(3),
            use_container_width=True, hide_index=True
        )

    # ----------------------------------------------------------------------
    # TAB 2: Recommendations table
    # ----------------------------------------------------------------------
    with tab2:
        st.subheader("Mode Optimization Recommendations")
        st.caption("Comparing each region's current highest-volume shipping mode against the "
                    "historically best-performing mode for that region.")

        show_mismatch_only = st.checkbox("Show only regions using a suboptimal mode", value=False)
        display_df = rec_df[rec_df['Mismatch']] if show_mismatch_only else rec_df

        st.dataframe(
            display_df.style.format({
                'Current Late Delivery Rate': '{:.1%}',
                'Recommended Late Delivery Rate': '{:.1%}',
                'Potential Improvement (pts)': '{:.1f}',
            }),
            use_container_width=True, hide_index=True
        )

        csv = rec_df.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Download recommendations as CSV", csv, "route_recommendations.csv", "text/csv")