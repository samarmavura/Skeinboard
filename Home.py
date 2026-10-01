import streamlit as st
from data_source import get_data_source

# Page configuration - MUST be the first Streamlit command
st.set_page_config(
    page_title="SkeinBoard",
    page_icon="logimatices_logo.png",
    layout="wide",
  )


STATUS_STYLE = {
    "Shipping on time": ("#dcfce7", "#166534"),
    "Advance shipping": ("#dbeafe", "#1e40af"),
    "Late delivery": ("#fee2e2", "#991b1b"),
    "Shipping canceled": ("#f3f4f6", "#4b5563"),
}


def status_pill(status: str) -> str:
    bg, fg = STATUS_STYLE.get(status, ("#f3f4f6", "#4b5563"))
    return f'<span class="status-pill" style="background:{bg};color:{fg};">{status}</span>'


with st.sidebar:
    st.markdown("### 📁 Dataset")
    uploaded_file = st.file_uploader(
        "Upload your own dataset (.xlsx or .csv)",
        type=["xlsx", "csv"],
        key="home_uploader",
        help="Must contain the same columns as the DataCo Smart Supply Chain dataset."
    )
    if uploaded_file is None:
        st.caption("No file uploaded — using the preloaded DataCo dataset.")
    else:
        st.success(f"✅ Using '{uploaded_file.name}'")

try:
    if uploaded_file is not None:
        source = get_data_source(file_bytes=uploaded_file.getvalue(), filename=uploaded_file.name)
    else:
        source = get_data_source()
    metrics = source.get_kpis()
    recent_orders = source.get_recent_orders(n=8)
    alerts = source.get_alerts()
except Exception as e:
    st.sidebar.error(f"Couldn't load that file: {e}")
    metrics = None
    recent_orders = None
    alerts = None

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
    .kpi-context { font-size: 0.8rem; color: #9ca3af; margin-top: 0.35rem; }

    .panel {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 1.3rem 1.4rem;
        height: 100%;
    }
    .panel-title { font-size: 1.05rem; font-weight: 600; color: #111827; margin-bottom: 0.9rem; }

    .status-pill {
        padding: 0.2rem 0.6rem; border-radius: 999px; font-size: 0.76rem; font-weight: 600;
        white-space: nowrap;
    }

    .alert-item { display: flex; align-items: flex-start; gap: 0.6rem; margin-bottom: 0.9rem; }
    .alert-dot { width: 9px; height: 9px; border-radius: 50%; margin-top: 5px; flex-shrink: 0; }
    .alert-dot-red { background: #dc2626; }
    .alert-dot-amber { background: #f59e0b; }
    .alert-dot-green { background: #16a34a; }
    .alert-text { font-size: 0.88rem; color: #111827; font-weight: 600; line-height: 1.3; }
    .alert-subtext { font-size: 0.8rem; color: #6b7280; margin-top: 0.1rem; }

    .section-label {
        font-size: 0.8rem; color: #9ca3af; text-transform: uppercase;
        letter-spacing: 0.06em; font-weight: 600; margin: 1.6rem 0 0.6rem 0;
    }
    table.orders-table { width: 100%; border-collapse: collapse; font-size: 0.86rem; }
    table.orders-table th {
        text-align: left; color: #9ca3af; font-weight: 600; text-transform: uppercase;
        font-size: 0.72rem; letter-spacing: 0.04em; padding: 0.4rem 0.6rem;
        border-bottom: 1px solid #e5e7eb;
    }
    table.orders-table td { padding: 0.55rem 0.6rem; border-bottom: 1px solid #f3f4f6; color: #111827; }
</style>
""", unsafe_allow_html=True)


# HERO

st.markdown("""
<div class="hero">
    <h1> SkeinBoard</h1>
    <p>A graph-based analysis of your supply chain — Inventory, Suppliers, Deliveries,
    and Network-level risk, all in one place.</p>
</div>
""", unsafe_allow_html=True)

if metrics is None:
    st.info("Dataset not found yet — this page will populate once DataCoSupplyChainDataset.xlsx is in place.")
else:
       # KPI GRID — 6 cards, 3 per row

    r1c1, r1c2, r1c3 = st.columns(3)
    with r1c1:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Overall Late Delivery Rate</div>
            <div class="kpi-value">{metrics['late_rate']*100:.1f}%</div>
            <div class="kpi-context">{metrics['late_count']:,} of {metrics['total_orders']:,} orders</div>
        </div>""", unsafe_allow_html=True)
    with r1c2:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Average Profit Margin</div>
            <div class="kpi-value">{metrics['avg_margin']*100:.1f}%</div>
            <div class="kpi-context">${metrics['total_profit']:,.0f} total profit</div>
        </div>""", unsafe_allow_html=True)
    with r1c3:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Average Delay vs Scheduled</div>
            <div class="kpi-value">{metrics['avg_delay']:+.2f} days</div>
            <div class="kpi-context">Actual vs scheduled shipping time</div>
        </div>""", unsafe_allow_html=True)

    st.write("")
    r2c1, r2c2, r2c3 = st.columns(3)
    with r2c1:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Revenue at Risk</div>
            <div class="kpi-value">${metrics['revenue_at_risk']/1e6:.1f}M</div>
            <div class="kpi-context">{metrics['revenue_at_risk_pct']:.1f}% of total revenue, tied to late orders</div>
        </div>""", unsafe_allow_html=True)
    with r2c2:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Most Reliable Mode</div>
            <div class="kpi-value">{metrics['most_reliable_mode']}</div>
            <div class="kpi-context">{metrics['most_reliable_mode_rate']*100:.1f}% late-delivery rate</div>
        </div>""", unsafe_allow_html=True)
    with r2c3:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Top Network Bottleneck</div>
            <div class="kpi-value">{metrics['top_bottleneck']}</div>
            <div class="kpi-context">Betweenness centrality {metrics['top_bottleneck_score']:.3f} — highest in network</div>
        </div>""", unsafe_allow_html=True)

    st.write("")

  
    # RECENT ORDERS TABLE + ALERTS PANEL
    
    table_col, alerts_col = st.columns([2, 1])

    with table_col:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<div class="panel-title">📦 Recent Orders</div>', unsafe_allow_html=True)

        rows_html = ""
        for order in recent_orders:
            rows_html += f"""<tr>
                <td>#{order['order_id']}</td>
                <td>{order['origin']} → {order['destination']}</td>
                <td>{order['mode']}</td>
                <td>{status_pill(order['status'])}</td>
                <td>{order['date'].strftime('%b %d, %Y')}</td>
                <td>${order['value']:,.2f}</td>
            </tr>"""

        st.markdown(f"""
        <table class="orders-table">
            <tr>
                <th>Order</th><th>Route</th><th>Mode</th><th>Status</th><th>Date</th><th>Value</th>
            </tr>
            {rows_html}
        </table>
        """, unsafe_allow_html=True)
        st.caption("Most recent orders by date in the dataset — this is historical order data, not a live feed. "
                    "Swap the data source in data_source.py once a live system exists.")
        st.markdown('</div>', unsafe_allow_html=True)

    with alerts_col:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<div class="panel-title">⚠️ Alerts</div>', unsafe_allow_html=True)

        alerts_html = ""
        for alert in alerts:
            alerts_html += f"""<div class="alert-item">
                <div class="alert-dot alert-dot-{alert['severity']}"></div>
                <div>
                    <div class="alert-text">{alert['text']}</div>
                    <div class="alert-subtext">{alert['subtext']}</div>
                </div>
            </div>"""

        st.markdown(alerts_html, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
st.divider()
st.caption("SkeinBoard · Supply chain intelligence, mapped as a graph.")