
import streamlit as st
import requests
import pandas as pd

st.set_page_config(
    page_title="SAINT TRADER AI",
    page_icon="📈",
    layout="wide"
)

st.title("👑 SAINT TRADER AI")
st.caption("Multi-pair Forex Signal Scanner")

st.warning(
    "Data connection test. No trading signals are generated yet."
)

pairs = [
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF",
    "AUD/USD", "NZD/USD", "USD/CAD", "EUR/GBP",
    "EUR/JPY", "GBP/JPY", "EUR/AUD", "GBP/AUD",
    "AUD/JPY", "EUR/CAD", "GBP/CAD", "CAD/JPY",
    "CHF/JPY", "NZD/JPY", "AUD/NZD"
]

pair = st.selectbox("Currency pair", pairs)

intervals = {
    "M5": "5min",
    "M15": "15min",
    "H1": "1h"
}

timeframe = st.selectbox(
    "Candle timeframe",
    list(intervals.keys())
)

if st.button("Fetch latest candles"):
    try:
        api_key = st.secrets["TWELVE_DATA_API_KEY"]

        response = requests.get(
            "https://api.twelvedata.com/time_series",
            params={
                "symbol": pair,
                "interval": intervals[timeframe],
                "outputsize": 5,
                "apikey": api_key
            },
            timeout=20
        )

        if response.status_code != 200:
            st.error(
                f"Data provider returned HTTP "
                f"{response.status_code}."
            )
        else:
            data = response.json()

            if data.get("status") == "error":
                st.error(
                    "Data request failed: "
                    + str(data.get("message", "Unknown error"))
                )
            elif data.get("values"):
                candles = pd.DataFrame(data["values"])
                candles["datetime"] = pd.to_datetime(
                    candles["datetime"], errors="coerce"
                )
                for column in ["open", "high", "low", "close"]:
                    candles[column] = pd.to_numeric(
                        candles[column], errors="coerce"
                    )

                st.success(
                    f"Received {len(candles)} candles for "
                    f"{pair} on {timeframe}."
                )
                st.dataframe(
                    candles,
                    use_container_width=True,
                    hide_index=True
                )
                st.caption(
                    "Confirm the provider's timestamp and "
                    "data-delay details before using these prices."
                )
            else:
                st.error(
                    "No candle data was returned. "
                    "Check pair availability and API limits."
                )

    except KeyError:
        st.error(
            "API key not found. Check Streamlit Settings > Secrets."
        )
    except requests.exceptions.RequestException as error:
        st.error(
            f"Could not reach the data provider: {error}"
        )
    except Exception as error:
        st.error(f"Unexpected error: {error}")

st.divider()
st.caption(
    "SAINT TRADER AI | Educational prototype | "
    "Paper trading only"
)
