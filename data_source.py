"""
data_source.py

A thin data-access layer that every page should go through instead of
calling pd.read_csv/read_excel directly. The point: today there is no
live system, so CSVDataSource just reads the DataCo file. Later, when a
real TMS/ERP/database exists, you write ONE new class that implements
the same methods, flip DATA_SOURCE_MODE, and every page that already
uses get_data_source() keeps working without changes.

USAGE (in any page):

    from data_source import get_data_source
    source = get_data_source()
    kpis = source.get_kpis()
    recent_orders = source.get_recent_orders(n=8)
    alerts = source.get_alerts()

WHEN A LIVE SYSTEM EXISTS LATER:
    1. Write a new class (e.g. TmsApiDataSource) implementing the same
       four methods below, pulling from the real API/DB instead of a file.
    2. Change DATA_SOURCE_MODE to "live" (or pass mode="live" explicitly).
    3. Nothing in home.py, inventory.py, etc. needs to change — they only
       ever called get_data_source(), never pandas directly.
"""

from abc import ABC, abstractmethod
import io
import pandas as pd
import networkx as nx
import streamlit as st

# Change this when a real live source exists. Kept as a plain constant
# (not an env var) for now since there's nothing to point it at yet —
# swap to os.environ.get("DATA_SOURCE_MODE", "csv") once deployment
# environments exist.
DATA_SOURCE_MODE = "csv"

# How long a CSV-backed read stays cached before re-reading the file.
# Meaningless for a static file today, but wiring it in now means a
# future live source just gets a much shorter TTL — the refresh pattern
# doesn't have to be invented later.
CSV_CACHE_TTL_SECONDS = 300


class DataSource(ABC):
    """
    The contract every data source must fulfill. Any class implementing
    these four methods can be dropped in via get_data_source() without
    touching page code.
    """

    @abstractmethod
    def get_kpis(self) -> dict:
        """
        Returns a flat dict of summary metrics. Expected keys:
        late_rate, late_count, total_orders, avg_margin, total_profit,
        avg_delay, revenue_at_risk, revenue_at_risk_pct,
        most_reliable_mode, most_reliable_mode_rate,
        least_reliable_mode, least_reliable_mode_rate,
        riskiest_region, riskiest_region_rate,
        top_bottleneck, top_bottleneck_score
        """
        ...

    @abstractmethod
    def get_recent_orders(self, n: int = 8) -> list:
        """
        Returns a list of dicts, most-recent-first, each with keys:
        order_id, origin, destination, mode, status, date (datetime), value (float)
        """
        ...

    @abstractmethod
    def get_alerts(self) -> list:
        """
        Returns a list of dicts, each with keys:
        severity ("red" | "amber" | "green"), text, subtext
        """
        ...

    @abstractmethod
    def get_raw_dataframe(self) -> pd.DataFrame:
        """
        Returns the underlying dataframe for pages that need full access
        (e.g. Graph Analysis, Inventory). A future live source would
        return a dataframe built from API/DB results in the same shape.
        """
        ...


class CSVDataSource(DataSource):
    """
    Today's only real implementation. Reads the DataCo dataset from a
    local file (or an uploaded file, if provided), computes the same
    metrics home.py used to compute inline.
    """

    def __init__(self, file_bytes: bytes = None, filename: str = None):
        self._file_bytes = file_bytes
        self._filename = filename

    def _load(self) -> pd.DataFrame:
        return _load_csv_dataframe(self._file_bytes, self._filename)

    def get_raw_dataframe(self) -> pd.DataFrame:
        return self._load()

    def get_kpis(self) -> dict:
        return _compute_kpis(self._load())

    def get_recent_orders(self, n: int = 8) -> list:
        df = self._load()
        recent = df.sort_values('order_date', ascending=False).head(n)
        return [
            {
                "order_id": row['Order Id'],
                "origin": row['Customer City'],
                "destination": row['Order City'],
                "mode": row['Shipping Mode'],
                "status": row['Delivery Status'],
                "date": row['order_date'],
                "value": row['Sales'],
            }
            for _, row in recent.iterrows()
        ]

    def get_alerts(self) -> list:
        k = self.get_kpis()
        return [
            {
                "severity": "red",
                "text": f"{k['least_reliable_mode']} has a {k['least_reliable_mode_rate']*100:.1f}% late-delivery rate",
                "subtext": "Highest-risk shipping mode overall",
            },
            {
                "severity": "red",
                "text": f"{k['riskiest_region']} has a {k['riskiest_region_rate']*100:.1f}% late-delivery rate",
                "subtext": "Highest-risk region overall",
            },
            {
                "severity": "amber",
                "text": f"${k['revenue_at_risk']/1e6:.1f}M in revenue tied to late orders",
                "subtext": f"{k['revenue_at_risk_pct']:.1f}% of total revenue",
            },
            {
                "severity": "green",
                "text": f"{k['most_reliable_mode']} is the most reliable mode",
                "subtext": f"{k['most_reliable_mode_rate']*100:.1f}% late-delivery rate",
            },
        ]


class LiveApiDataSource(DataSource):
    """
    STUB — not implemented. This is the class you'll actually write once
    a real TMS/ERP/carrier API or database exists. Every method needs to
    return data in the exact same shape as CSVDataSource above so pages
    don't need to change.

    Example of what a real implementation would look like:

        def __init__(self, api_base_url: str, api_key: str):
            self.api_base_url = api_base_url
            self.api_key = api_key

        def get_kpis(self) -> dict:
            resp = requests.get(f"{self.api_base_url}/kpis",
                                 headers={"Authorization": f"Bearer {self.api_key}"})
            return resp.json()

        def get_recent_orders(self, n=8) -> list:
            resp = requests.get(f"{self.api_base_url}/shipments/recent",
                                 params={"limit": n},
                                 headers={"Authorization": f"Bearer {self.api_key}"})
            return resp.json()

        # ...and so on for get_alerts() and get_raw_dataframe()
    """

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "LiveApiDataSource is a stub. Implement get_kpis(), get_recent_orders(), "
            "get_alerts(), and get_raw_dataframe() against your real API/DB before using this."
        )

    def get_kpis(self) -> dict:
        raise NotImplementedError

    def get_recent_orders(self, n: int = 8) -> list:
        raise NotImplementedError

    def get_alerts(self) -> list:
        raise NotImplementedError

    def get_raw_dataframe(self) -> pd.DataFrame:
        raise NotImplementedError


def get_data_source(mode: str = None, file_bytes: bytes = None, filename: str = None) -> DataSource:
    """
    Factory. Pages call this instead of instantiating a data source class
    directly, so swapping the active source is a one-line change here
    rather than an edit in every page.
    """
    mode = mode or DATA_SOURCE_MODE
    if mode == "csv":
        return CSVDataSource(file_bytes=file_bytes, filename=filename)
    elif mode == "live":
        return LiveApiDataSource()
    else:
        raise ValueError(f"Unknown data source mode: {mode}")


# ==============================================================================
# Internal helpers — the actual pandas/networkx logic, unchanged from before,
# just relocated here so it's shared by every page instead of duplicated.
# ==============================================================================
@st.cache_data(ttl=CSV_CACHE_TTL_SECONDS)
def _load_csv_dataframe(file_bytes: bytes = None, filename: str = None) -> pd.DataFrame:
    if file_bytes is not None:
        buffer = io.BytesIO(file_bytes)
        if filename and filename.lower().endswith('.csv'):
            df = pd.read_csv(buffer, encoding='latin1')
        else:
            df = pd.read_excel(buffer)
    else:
        df = pd.read_excel('DataCoSupplyChainDataset.xlsx')

    for col in ['Category Name', 'Order Region', 'Shipping Mode']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    if 'order date (DateOrders)' in df.columns:
        df['order_date'] = pd.to_datetime(df['order date (DateOrders)'], errors='coerce')
    return df


@st.cache_data(ttl=CSV_CACHE_TTL_SECONDS)
def _compute_kpis(df: pd.DataFrame) -> dict:
    late_rate = df['Late_delivery_risk'].mean()
    avg_margin = df['Order Item Profit Ratio'].mean()
    avg_delay = (df['Days for shipping (real)'] - df['Days for shipment (scheduled)']).mean()

    total_revenue = df['Sales'].sum()
    revenue_at_risk = df.loc[df['Late_delivery_risk'] == 1, 'Sales'].sum()
    revenue_at_risk_pct = revenue_at_risk / total_revenue * 100

    mode_perf = df.groupby('Shipping Mode')['Late_delivery_risk'].mean().sort_values()
    most_reliable_mode = mode_perf.index[0]
    most_reliable_mode_rate = mode_perf.iloc[0]
    least_reliable_mode = mode_perf.index[-1]
    least_reliable_mode_rate = mode_perf.iloc[-1]

    region_risk = df.groupby('Order Region')['Late_delivery_risk'].mean().sort_values(ascending=False)
    riskiest_region = region_risk.index[0]
    riskiest_region_rate = region_risk.iloc[0]

    edge_data = df.groupby(['Category Name', 'Order Region']).agg(
        order_count=('Order Item Quantity', 'count')
    ).reset_index()
    G = nx.Graph()
    for c in df['Category Name'].unique():
        G.add_node(c, node_type='Category')
    for r in df['Order Region'].unique():
        G.add_node(r, node_type='Region')
    for _, row in edge_data.iterrows():
        G.add_edge(row['Category Name'], row['Order Region'], weight=row['order_count'])
    btw = nx.betweenness_centrality(G, weight='weight')
    top_bottleneck, top_bottleneck_score = max(btw.items(), key=lambda x: x[1])

    return {
        "late_rate": late_rate,
        "late_count": int(df['Late_delivery_risk'].sum()),
        "total_orders": df['Order Id'].nunique(),
        "avg_margin": avg_margin,
        "total_profit": (df['Sales'] * df['Order Item Profit Ratio']).sum(),
        "avg_delay": avg_delay,
        "revenue_at_risk": revenue_at_risk,
        "revenue_at_risk_pct": revenue_at_risk_pct,
        "most_reliable_mode": most_reliable_mode,
        "most_reliable_mode_rate": most_reliable_mode_rate,
        "least_reliable_mode": least_reliable_mode,
        "least_reliable_mode_rate": least_reliable_mode_rate,
        "riskiest_region": riskiest_region,
        "riskiest_region_rate": riskiest_region_rate,
        "top_bottleneck": top_bottleneck,
        "top_bottleneck_score": top_bottleneck_score,
    }