import streamlit as st
import pandas as pd
import numpy as np
import networkx as nx
import plotly.express as px
import plotly.graph_objects as go
import io
from ai_chat_sidebar_deepseek import render_chat_sidebar

st.set_page_config(
    page_title="SkeinBoard",
    page_icon="logimatices_logo.png",
    layout="wide"
   )


# Load the dataset
REQUIRED_COLUMNS = [
    'Category Name', 'Order Region', 'Order Item Quantity', 'Sales',
    'Order Item Profit Ratio', 'Order Profit Per Order',
    'Late_delivery_risk', 'Days for shipping (real)'
]


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
    '''merges the different formatings of the same nodes'''
    for col in ['Category Name', 'Order Region']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    return df


def validate_columns(df) -> list:
    """Returns a list of any required columns missing from df."""
    return [c for c in REQUIRED_COLUMNS if c not in df.columns]


@st.cache_data
def build_graph(df):
    """
    Builds a bipartite Category <-> Order Region flow network.

    Nodes: every unique Category Name + every unique Order Region.
    Edges: one edge per (Category, Region) pair that actually co-occurs
    in the data, weighted by order volume, with additional business
    metrics (sales, profit, late delivery rate) attached as edge attributes.
    """
    edge_data = df.groupby(['Category Name', 'Order Region']).agg(
        order_count=('Order Item Quantity', 'count'),
        total_quantity=('Order Item Quantity', 'sum'),
        total_sales=('Sales', 'sum'),
        avg_profit_ratio=('Order Item Profit Ratio', 'mean'),
        total_profit=('Order Profit Per Order', 'sum'),
        late_delivery_rate=('Late_delivery_risk', 'mean'),
        avg_shipping_days=('Days for shipping (real)', 'mean')
    ).reset_index()

    G = nx.Graph()
    for c in df['Category Name'].unique():
        G.add_node(c, node_type='Category')
    for r in df['Order Region'].unique():
        G.add_node(r, node_type='Region')

    for _, row in edge_data.iterrows():
        G.add_edge(
            row['Category Name'], row['Order Region'],
            weight=row['order_count'],
            total_sales=row['total_sales'],
            total_profit=row['total_profit'],
            late_delivery_rate=row['late_delivery_rate'],
            avg_shipping_days=row['avg_shipping_days']
        )

    return G, edge_data


@st.cache_data
def compute_centralities(_G):
    eig = nx.eigenvector_centrality_numpy(_G, weight='weight')
    btw = nx.betweenness_centrality(_G, weight='weight')
    close = nx.closeness_centrality(_G, distance='weight')

    rows = []
    for node in _G.nodes():
        rows.append({
            'Node': node,
            'Type': _G.nodes[node]['node_type'],
            'Degree': _G.degree(node),
            'Eigenvector Centrality': eig[node],
            'Betweenness Centrality': btw[node],
            'Closeness Centrality': close[node]
        })
    return pd.DataFrame(rows)


# ==============================================================================
# SIDEBAR: dataset upload (native left sidebar, separate from the AI chat
# panel which lives in the right-hand column)
# ==============================================================================
with st.sidebar:
    st.markdown("### 📁 Dataset")
    uploaded_file = st.file_uploader(
        "Upload your own dataset (.xlsx or .csv)",
        type=["xlsx", "csv"],
        help="Must contain the same columns as the DataCo Smart Supply Chain dataset."
    )
    if uploaded_file is None:
        st.caption("No file uploaded — using the preloaded DataCo dataset.")

# ==============================================================================
# LOAD DATA
# ==============================================================================
if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    try:
        df = load_uploaded_data(file_bytes, uploaded_file.name)
    except Exception as e:
        st.error(f"Couldn't read '{uploaded_file.name}': {e}")
        st.stop()

    missing_cols = validate_columns(df)
    if missing_cols:
        st.error(
            f"'{uploaded_file.name}' is missing required columns: {', '.join(missing_cols)}. "
            f"Falling back to the preloaded dataset."
        )
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
    .kpi-context { font-size: 0.8rem; color: #9ca3af; margin-top: 0.35rem; }
    
    .panel {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 1.3rem 1.4rem;
        height: 100%;}
    .panel-title { font-size: 1.05rem; font-weight: 600; color: #111827; margin-bottom: 0.9rem; }
""", unsafe_allow_html=True)
    
st.markdown("""
<div class="hero">
    <h1> Graph based Supply Chain Analyisis</h1>
    <p>Category ↔ Region flow network — eigenvector, betweenness & closeness centrality.</p>
</div>
""", unsafe_allow_html=True)

G, edge_data = build_graph(df)
centrality_df = compute_centralities(G)

# ==============================================================================
# DEBUG: raw region/category values as loaded — expand this if node counts
# ever look off (e.g. more regions than expected). Whitespace or casing
# differences (e.g. "Western Europe" vs "Western Europe ") show up here
# as separate list entries even though they look identical at a glance.
# ==============================================================================
with st.expander(""):
    dcol1, dcol2 = st.columns(2)
    with dcol1:
        st.markdown(f"**Order Region** — {df['Order Region'].nunique()} unique values")
        st.write(sorted(df['Order Region'].unique().tolist()))
    with dcol2:
        st.markdown(f"**Category Name** — {df['Category Name'].nunique()} unique values")
        st.write(sorted(df['Category Name'].unique().tolist()))

# ==============================================================================

def query_centrality(node_name: str) -> dict:
    """Look up centrality scores for one category or region node."""
    row = centrality_df[centrality_df['Node'].str.lower() == node_name.lower()]
    if row.empty:
        return {"error": f"No node named '{node_name}' found. "
                          f"Available types are Category and Region."}
    return row.iloc[0].to_dict()


def get_top_nodes(metric: str, n: int = 5) -> dict:
    """Get the top N nodes ranked by a centrality metric."""
    valid_metrics = {
        "eigenvector": "Eigenvector Centrality",
        "betweenness": "Betweenness Centrality",
        "closeness": "Closeness Centrality",
    }
    col = valid_metrics.get(metric.lower())
    if col is None:
        return {"error": f"metric must be one of {list(valid_metrics.keys())}"}
    top = centrality_df.sort_values(col, ascending=False).head(n)
    return top[['Node', 'Type', col]].to_dict('records')


def query_edge(category_name: str, region_name: str) -> dict:
    """Look up the aggregated stats for a specific Category-Region edge."""
    row = edge_data[
        (edge_data['Category Name'].str.lower() == category_name.lower()) &
        (edge_data['Order Region'].str.lower() == region_name.lower())
    ]
    if row.empty:
        return {"error": f"No edge found between '{category_name}' and '{region_name}'."}
    return row.iloc[0].to_dict()


AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_centrality",
            "description": "Look up eigenvector, betweenness, and closeness centrality "
                            "scores for a specific category or region node in the graph.",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_name": {"type": "string", "description": "Exact category or region name, e.g. 'Lacrosse' or 'Central America'."}
                },
                "required": ["node_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_nodes",
            "description": "Get the top N nodes ranked by a given centrality metric "
                            "(eigenvector, betweenness, or closeness).",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric": {"type": "string", "enum": ["eigenvector", "betweenness", "closeness"]},
                    "n": {"type": "integer", "description": "How many top nodes to return, default 5."}
                },
                "required": ["metric"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_edge",
            "description": "Look up aggregated order stats (volume, sales, profit, late "
                            "delivery rate) for a specific Category-Region pair.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category_name": {"type": "string"},
                    "region_name": {"type": "string"},
                },
                "required": ["category_name", "region_name"],
            },
        },
    },
]

AGENT_TOOL_FUNCTIONS = {
    "query_centrality": query_centrality,
    "get_top_nodes": get_top_nodes,
    "query_edge": query_edge,
}

GRAPH_PAGE_SYSTEM_PROMPT = (
    "You are an analytics assistant embedded in a supply chain graph dashboard. "
    "The graph has two node types: Category (50 product categories) and Region "
    "(23 order regions), connected by edges wherever orders link them. "
    "Use your tools to look up real centrality scores and edge stats before "
    "answering — never guess numbers. Explain results in plain business language."
)

# ==============================================================================
# RENDER: chat sidebar first (gives us main_col to put everything else in)
# ==============================================================================
main_col, chat_col = render_chat_sidebar(
    tools=AGENT_TOOLS,
    tool_functions=AGENT_TOOL_FUNCTIONS,
    system_prompt=GRAPH_PAGE_SYSTEM_PROMPT,
)



with main_col:

    # ==========================================================================
    # KPI ROW
    # ==========================================================================
    st.subheader(" Network Overview")
    col1, col2, col3 = st.columns(3)
    r1c1, r1c2, r1c3 = st.columns(3)
    with r1c1:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Categories & Regions Tracked</div>
            <div class="kpi-value">{G.number_of_nodes()}</div>
        </div>""", unsafe_allow_html=True)
    with r1c2:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Active Trade Connections</div>
            <div class="kpi-value">{G.number_of_edges()}</div>
        </div>""", unsafe_allow_html=True)
    density = nx.density(G)
    with r1c3:
        num_categories = sum(1 for n in G.nodes() if G.nodes[n]['node_type'] == 'Category')
        num_regions = sum(1 for n in G.nodes() if G.nodes[n]['node_type'] == 'Region')
        market_coverage = G.number_of_edges() / (num_categories * num_regions)

        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Market Coverage</div>
            <div class="kpi-value">{market_coverage*100:.1f}%</div>
        </div>""", unsafe_allow_html=True)

    st.write("")
    r2c1, r2c2, r2c3 = st.columns(3)
    top_eig_node = centrality_df.sort_values('Eigenvector Centrality', ascending=False).iloc[0]
    with r2c1:
       st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Most Connected</div>
            <div class="kpi-value">{top_eig_node['Node']}</div>
        </div>""", unsafe_allow_html=True)
       top_btw_node = centrality_df.sort_values('Betweenness Centrality', ascending=False).iloc[0]
    with r2c2:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Biggest Bottleneck</div>
            <div class="kpi-value">{top_btw_node['Node']}</div>
        </div>""", unsafe_allow_html=True)
    with r2c3:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Total Nodes</div>
            <div class="kpi-value">{G.number_of_nodes()}</div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    # ==========================================================================
    # TABS
    # ==========================================================================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🌐 Network Map",
        "⭐ Eigenvector Centrality",
        "🚧 Betweenness Centrality",
        "📍 Closeness Centrality",
        "📋 Full Data Table"
    ])

    # --------------------------------------------------------------------------
    # TAB 1: Network Map
    # --------------------------------------------------------------------------
    with tab1:
        st.subheader("Category ↔ Region Network")
        st.caption(f"Showing all {G.number_of_nodes()} nodes and {G.number_of_edges()} edges in the network.")

        layout_seed = st.slider("Layout seed (change to reshuffle node positions)", 0, 100, 42)
        pos = nx.spring_layout(G, weight='weight', seed=layout_seed, k=0.6)

        edge_x, edge_y = [], []
        for u, v in G.edges():
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            edge_x += [x0, x1, None]
            edge_y += [y0, y1, None]

        edge_trace = go.Scatter(
            x=edge_x, y=edge_y,
            line=dict(width=0.5, color='#bbb'),
            hoverinfo='none',
            mode='lines'
        )

        node_x, node_y, node_color, node_text, node_size = [], [], [], [], []
        for node in G.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            ntype = G.nodes[node]['node_type']
            node_color.append('#1f77b4' if ntype == 'Category' else '#ff7f0e')
            deg = G.degree(node)
            node_size.append(8 + deg * 1.5)
            eig_val = centrality_df.loc[centrality_df['Node'] == node, 'Eigenvector Centrality'].values[0]
            node_text.append(f"{node} ({ntype})<br>Degree: {deg}<br>Eigenvector: {eig_val:.3f}")

        node_trace = go.Scatter(
            x=node_x, y=node_y,
            mode='markers',
            hoverinfo='text',
            text=node_text,
            marker=dict(color=node_color, size=node_size, line=dict(width=1, color='white'))
        )

        fig_network = go.Figure(data=[edge_trace, node_trace])
        fig_network.update_layout(
            showlegend=False,
            hovermode='closest',
            margin=dict(l=0, r=0, t=20, b=0),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            height=650
        )
        st.plotly_chart(fig_network, use_container_width=True)
        st.caption("🔵 Blue = Category nodes  🟠 Orange = Region nodes. Node size reflects degree.")

    # --------------------------------------------------------------------------
    # TAB 2: Eigenvector Centrality
    # --------------------------------------------------------------------------
    with tab2:
        st.subheader("Eigenvector Centrality")
        top_n = st.slider("Show top N nodes", 5, 30, 15, key="eig_slider")
        eig_top = centrality_df.sort_values('Eigenvector Centrality', ascending=False).head(top_n)

        fig_eig = px.bar(
            eig_top, x='Eigenvector Centrality', y='Node', color='Type',
            orientation='h', title=f"Top {top_n} Nodes by Eigenvector Centrality",
            color_discrete_map={'Category': '#1f77b4', 'Region': '#ff7f0e'}
        )
        fig_eig.update_layout(yaxis=dict(categoryorder='total ascending'))
        st.plotly_chart(fig_eig, use_container_width=True)

        st.dataframe(
            eig_top[['Node', 'Type', 'Degree', 'Eigenvector Centrality']].round(4),
            use_container_width=True, hide_index=True
        )

    # --------------------------------------------------------------------------
    # TAB 3: Betweenness Centrality
    # --------------------------------------------------------------------------
    with tab3:
        st.subheader("Betweenness Centrality")
        top_n_b = st.slider("Show top N nodes", 5, 30, 15, key="btw_slider")
        btw_top = centrality_df.sort_values('Betweenness Centrality', ascending=False).head(top_n_b)

        fig_btw = px.bar(
            btw_top, x='Betweenness Centrality', y='Node', color='Type',
            orientation='h', title=f"Top {top_n_b} Nodes by Betweenness Centrality",
            color_discrete_map={'Category': '#1f77b4', 'Region': '#ff7f0e'}
        )
        fig_btw.update_layout(yaxis=dict(categoryorder='total ascending'))
        st.plotly_chart(fig_btw, use_container_width=True)

        st.dataframe(
            btw_top[['Node', 'Type', 'Degree', 'Betweenness Centrality']].round(4),
            use_container_width=True, hide_index=True
        )

    # --------------------------------------------------------------------------
    # TAB 4: Closeness Centrality
    # --------------------------------------------------------------------------
    with tab4:
        st.subheader("Closeness Centrality")
        top_n_c = st.slider("Show top N nodes", 5, 30, 15, key="close_slider")
        close_top = centrality_df.sort_values('Closeness Centrality', ascending=False).head(top_n_c)

        fig_close = px.bar(
            close_top, x='Closeness Centrality', y='Node', color='Type',
            orientation='h', title=f"Top {top_n_c} Nodes by Closeness Centrality",
            color_discrete_map={'Category': '#1f77b4', 'Region': '#ff7f0e'}
        )
        fig_close.update_layout(yaxis=dict(categoryorder='total ascending'))
        st.plotly_chart(fig_close, use_container_width=True)

        st.dataframe(
            close_top[['Node', 'Type', 'Degree', 'Closeness Centrality']].round(4),
            use_container_width=True, hide_index=True
        )

    # --------------------------------------------------------------------------
    # TAB 5: Full Data Table
    # --------------------------------------------------------------------------
    with tab5:
        st.subheader("Full Centrality Table")

        filter_type = st.multiselect(
            "Filter by node type", options=['Category', 'Region'],
            default=['Category', 'Region']
        )
        filtered = centrality_df[centrality_df['Type'].isin(filter_type)].sort_values(
            'Eigenvector Centrality', ascending=False
        )
        st.dataframe(filtered.round(4), use_container_width=True, hide_index=True)

        st.markdown("### Underlying Category ↔ Region Edge List")
        st.dataframe(edge_data.round(3), use_container_width=True, hide_index=True)

        excel_buffer = io.BytesIO()
        filtered.to_excel(excel_buffer, index=False, engine='openpyxl')
        excel_buffer.seek(0)
        st.download_button(
            "⬇️ Download centrality table as Excel",
            excel_buffer,
            "centrality_scores.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )