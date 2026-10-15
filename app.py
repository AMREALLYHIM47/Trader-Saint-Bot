
import streamlit as st

st.set_page_config(
    page_title="SAINT TRADER AI",
    page_icon="📈",
    layout="wide"
)

st.title("👑 SAINT TRADER AI")
st.caption("Multi-pair Forex Signal Scanner")

st.info(
    "Prototype mode: signals are examples only. "
    "Connect verified market data and test the strategy "
    "before using signals for trading."
)

pairs = [
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF",
    "AUD/USD", "NZD/USD", "USD/CAD", "EUR/GBP",
    "EUR/JPY", "GBP/JPY", "EUR/AUD", "GBP/AUD",
    "AUD/JPY", "EUR/CAD", "GBP/CAD", "CAD/JPY",
    "CHF/JPY", "NZD/JPY", "AUD/NZD"
]

st.subheader("Forex Scanner")

selected_pairs = st.multiselect(
    "Choose currency pairs",
    pairs,
    default=["EUR/USD", "GBP/USD", "USD/JPY"]
)

timeframe = st.selectbox(
    "Entry timeframe",
    ["M5"],
    index=0
)

st.write("Confirmation timeframes: M15 + H1")

if st.button("Scan selected pairs"):
    st.warning(
        "Market data is not connected yet. "
        "No live trading signals are being generated."
    )

st.subheader("Signal Dashboard")

st.dataframe(
    {
        "Pair": selected_pairs,
        "H1 Trend": ["Awaiting data"] * len(selected_pairs),
        "M15 Confirmation": ["Awaiting data"] * len(selected_pairs),
        "M5 Signal": ["NO SIGNAL"] * len(selected_pairs),
    },
    use_container_width=True,
    hide_index=True
)

st.divider()
st.caption(
    "SAINT TRADER AI • Educational prototype • "
    "Paper trading only"
)

