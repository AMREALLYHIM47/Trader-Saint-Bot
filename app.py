
import streamlit as st
import requests
import pandas as pd

st.set_page_config(
    page_title="SAINT TRADER AI",
    page_icon="📈",
    layout="wide"
)

st.title("👑 SAINT TRADER AI")
st.caption("Selected-pair Forex Scanner | Paper Trading Only")

PAIRS = [
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF",
    "AUD/USD", "NZD/USD", "USD/CAD", "EUR/GBP",
    "EUR/JPY", "GBP/JPY", "EUR/AUD", "GBP/AUD",
    "AUD/JPY", "EUR/CAD", "GBP/CAD", "CAD/JPY",
    "CHF/JPY", "NZD/JPY", "AUD/NZD"
]

TIMEFRAMES = {
    "M5": "5min",
    "M15": "15min",
    "H1": "1h"
}

selected_pairs = st.multiselect(
    "Select currency pairs",
    PAIRS,
    default=["EUR/USD", "GBP/USD"]
)

timeframe = st.selectbox(
    "Entry timeframe",
    list(TIMEFRAMES.keys()),
    index=0
)

if st.button("Fetch latest candles", type="primary"):
    if not selected_pairs:
        st.warning("Select at least one currency pair.")
    else:
        try:
            api_key = st.secrets["TWELVE_DATA_API_KEY"]

            for pair in selected_pairs:
                st.subheader(pair)

                response = requests.get(
                    "https://api.twelvedata.com/time_series",
                    params={
                        "symbol": pair,
                        "interval": TIMEFRAMES[timeframe],
                        "outputsize": 60,
                        "apikey": api_key
                    },
                    timeout=20
                )

                data = response.json()

                if response.status_code != 200 or data.get("status") == "error":
                    st.error(
                        f"Could not fetch {pair}: "
                        f"{data.get('message', 'Data request failed')}"
                    )
                    continue

                if not data.get("values"):
                    st.warning(f"No candles returned for {pair}.")
                    continue

                candles = pd.DataFrame(data["values"])
                candles["datetime"] = pd.to_datetime(
                    candles["datetime"], errors="coerce"
                )

                for column in ["open", "high", "low", "close"]:
                    candles[column] = pd.to_numeric(
                        candles[column], errors="coerce"
                    )

                candles = candles.dropna(
                    subset=["open", "high", "low", "close"]
                ).sort_values("datetime")

                st.success(
                    f"Loaded {len(candles)} candles on {timeframe}."
                )
                st.dataframe(candles, use_container_width=True)

        except KeyError:
            st.error(
                "API key missing. Add TWELVE_DATA_API_KEY "
                "under Streamlit app Settings > Secrets."
            )
        except requests.exceptions.RequestException as error:
            st.error(f"Connection error: {error}")
        except Exception as error:
            st.error(f"Unexpected error: {error}")

st.divider()
st.caption(
    "SAINT TRADER AI | Educational prototype | "
    "No live orders | Signals are not guaranteed profitable"
)
