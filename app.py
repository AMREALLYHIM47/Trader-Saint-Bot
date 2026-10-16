
import streamlit as st
import requests
import pandas as pd

st.set_page_config(
    page_title="SAINT TRADER AI",
    page_icon="📈",
    layout="wide"
)

st.title("👑 SAINT TRADER AI")
st.caption("Forex signal scanner | Paper trading only")

PAIRS = [
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF",
    "AUD/USD", "NZD/USD", "USD/CAD", "EUR/GBP",
    "EUR/JPY", "GBP/JPY", "EUR/AUD", "GBP/AUD",
    "AUD/JPY", "EUR/CAD", "GBP/CAD", "CAD/JPY",
    "CHF/JPY", "NZD/JPY", "AUD/NZD"
]

TIMEFRAMES = {"M5": "5min", "M15": "15min", "H1": "1h"}

def add_indicators(df):
    df = df.copy().sort_values("datetime").reset_index(drop=True)

    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))
    df["rsi"] = 100 - (100 / (1 + rs))

    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat(
        [high_low, high_close, low_close], axis=1
    ).max(axis=1)

    up_move = df["high"].diff()
    down_move = -df["low"].diff()

    plus_dm = up_move.where(
        (up_move > down_move) & (up_move > 0), 0.0
    )
    minus_dm = down_move.where(
        (down_move > up_move) & (down_move > 0), 0.0
    )

    atr = tr.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(
        alpha=1/14, min_periods=14, adjust=False
    ).mean() / atr.replace(0, float("nan"))
    minus_di = 100 * minus_dm.ewm(
        alpha=1/14, min_periods=14, adjust=False
    ).mean() / atr.replace(0, float("nan"))

    dx = 100 * (plus_di - minus_di).abs() / (
        plus_di + minus_di
    ).replace(0, float("nan"))
    df["adx"] = dx.ewm(
        alpha=1/14, min_periods=14, adjust=False
    ).mean()

    df["atr"] = atr
    return df

def get_signal(df):
    if len(df) < 60:
        return "NO SIGNAL", "Not enough candles"

    last = df.iloc[-1]

    required = ["ema20", "ema50", "rsi", "adx", "atr"]
    if last[required].isna().any():
        return "NO SIGNAL", "Indicators not ready"

    bullish = (
        last["ema20"] > last["ema50"]
        and last["rsi"] >= 55
        and last["adx"] >= 20
    )
    bearish = (
        last["ema20"] < last["ema50"]
        and last["rsi"] <= 45
        and last["adx"] >= 20
    )

    if bullish:
        return "BUY", "Trend and momentum filters agree"
    if bearish:
        return "SELL", "Trend and momentum filters agree"
    return "NO SIGNAL", "Filters do not fully agree"

selected_pairs = st.multiselect(
    "Select currency pairs",
    PAIRS,
    default=["EUR/USD", "GBP/USD"]
)
timeframe = st.selectbox("Entry timeframe", list(TIMEFRAMES.keys()))

if st.button("Scan selected pairs", type="primary"):
    if not selected_pairs:
        st.warning("Select at least one pair.")
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
                        "outputsize": 100,
                        "apikey": api_key
                    },
                    timeout=20
                )

                data = response.json()

                if response.status_code != 200 or data.get("status") == "error":
                    st.error(
                        f"Data error: {data.get('message', 'Request failed')}"
                    )
                    continue

                if not data.get("values"):
                    st.warning("No candle data returned.")
                    continue

                df = pd.DataFrame(data["values"])
                df["datetime"] = pd.to_datetime(
                    df["datetime"], errors="coerce"
                )

                for col in ["open", "high", "low", "close"]:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

                df = df.dropna(
                    subset=["datetime", "open", "high", "low", "close"]
                )
                df = add_indicators(df)

                signal, reason = get_signal(df)
                last = df.iloc[-1]

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Signal", signal)
                c2.metric("Close", f"{last['close']:.5f}")
                c3.metric("RSI 14", f"{last['rsi']:.1f}")
                c4.metric("ADX 14", f"{last['adx']:.1f}")

                st.write(f"**Reason:** {reason}")
                st.write(
                    f"EMA20: {last['ema20']:.5f} | "
                    f"EMA50: {last['ema50']:.5f} | "
                    f"ATR14: {last['atr']:.5f}"
                )

                with st.expander("View latest candles and indicators"):
                    st.dataframe(
                        df.tail(10),
                        use_container_width=True
                    )

        except KeyError:
            st.error("Missing TWELVE_DATA_API_KEY in Streamlit Secrets.")
        except requests.exceptions.RequestException as error:
            st.error(f"Connection error: {error}")
        except Exception as error:
            st.error(f"Unexpected error: {error}")

st.divider()
st.caption(
    "Educational prototype | No live orders | "
    "Signals are experimental, not guaranteed profitable."
)
