
import streamlit as st
import requests
import pandas as pd

st.set_page_config(
    page_title="SAINT TRADER AI",
    page_icon="📈",
    layout="wide"
)

st.title("👑 SAINT TRADER AI")
st.caption("M5 entries | M15 + H1 confirmation | Paper trading only")

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


@st.cache_data(ttl=60)
def fetch_candles(pair, interval, api_key):
    response = requests.get(
        "https://api.twelvedata.com/time_series",
        params={
            "symbol": pair,
            "interval": interval,
            "outputsize": 100,
            "apikey": api_key
        },
        timeout=20
    )

    response.raise_for_status()
    data = response.json()

    if data.get("status") == "error":
        raise ValueError(
            data.get("message", "Data provider error")
        )

    if not data.get("values"):
        raise ValueError("No candles returned")

    df = pd.DataFrame(data["values"])

    df["datetime"] = pd.to_datetime(
        df["datetime"], errors="coerce"
    )

    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(
            df[col], errors="coerce"
        )

    df = df.dropna(
        subset=["datetime", "open", "high", "low", "close"]
    )

    df = df.sort_values("datetime").reset_index(drop=True)

    # Conservatively exclude the newest candle.
    # Provider timestamps should be checked before relying on signals.
    if len(df) > 1:
        df = df.iloc[:-1].reset_index(drop=True)

    return df


def add_indicators(df):
    df = df.copy()

    df["ema20"] = df["close"].ewm(
        span=20, adjust=False
    ).mean()

    df["ema50"] = df["close"].ewm(
        span=50, adjust=False
    ).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / 14,
        min_periods=14,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / 14,
        min_periods=14,
        adjust=False
    ).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))
    df["rsi"] = 100 - (100 / (1 + rs))

    high_low = df["high"] - df["low"]
    high_close = (
        df["high"] - df["close"].shift()
    ).abs()
    low_close = (
        df["low"] - df["close"].shift()
    ).abs()

    tr = pd.concat(
        [high_low, high_close, low_close],
        axis=1
    ).max(axis=1)

    up_move = df["high"].diff()
    down_move = -df["low"].diff()

    plus_dm = up_move.where(
        (up_move > down_move) & (up_move > 0),
        0.0
    )

    minus_dm = down_move.where(
        (down_move > up_move) & (down_move > 0),
        0.0
    )

    df["atr"] = tr.ewm(
        alpha=1 / 14,
        min_periods=14,
        adjust=False
    ).mean()

    plus_di = (
        100 * plus_dm.ewm(
            alpha=1 / 14,
            min_periods=14,
            adjust=False
        ).mean()
        / df["atr"].replace(0, float("nan"))
    )

    minus_di = (
        100 * minus_dm.ewm(
            alpha=1 / 14,
            min_periods=14,
            adjust=False
        ).mean()
        / df["atr"].replace(0, float("nan"))
    )

    dx = (
        100 * (plus_di - minus_di).abs()
        / (plus_di + minus_di).replace(0, float("nan"))
    )

    df["adx"] = dx.ewm(
        alpha=1 / 14,
        min_periods=14,
        adjust=False
    ).mean()

    return df


def trend_direction(df):
    if len(df) < 60:
        return "UNKNOWN"

    last = df.iloc[-1]

    if pd.isna(last["ema20"]) or pd.isna(last["ema50"]):
        return "UNKNOWN"

    if last["ema20"] > last["ema50"]:
        return "BULLISH"

    if last["ema20"] < last["ema50"]:
        return "BEARISH"

    return "NEUTRAL"


def entry_signal(df):
    if len(df) < 60:
        return "NO SIGNAL", "Not enough M5 candles"

    last = df.iloc[-1]

    required = ["ema20", "ema50", "rsi", "adx", "atr"]

    if last[required].isna().any():
        return "NO SIGNAL", "Indicators not ready"

    if (
        last["ema20"] > last["ema50"]
        and last["rsi"] >= 55
        and last["adx"] >= 20
    ):
        return "BUY", "M5 bullish filters agree"

    if (
        last["ema20"] < last["ema50"]
        and last["rsi"] <= 45
        and last["adx"] >= 20
    ):
        return "SELL", "M5 bearish filters agree"

    return "NO SIGNAL", "M5 filters do not fully agree"


selected_pairs = st.multiselect(
    "Select currency pairs",
    PAIRS,
    default=["EUR/USD"]
)

if st.button(
    "Scan with M5 + M15 + H1 confirmation",
    type="primary"
):
    if not selected_pairs:
        st.warning("Select at least one pair.")

    else:
        try:
            api_key = st.secrets["TWELVE_DATA_API_KEY"]

            for pair in selected_pairs:
                st.subheader(pair)

                results = {}
                errors = {}

                # Fetch each timeframe once per pair.
                for tf, interval in TIMEFRAMES.items():
                    try:
                        raw = fetch_candles(
                            pair, interval, api_key
                        )
                        results[tf] = add_indicators(raw)

                    except Exception as error:
                        errors[tf] = str(error)

                if errors:
                    for tf, message in errors.items():
                        st.warning(
                            f"{tf} data unavailable: {message}"
                        )

                    st.info(
                        "NO SIGNAL — confirmation data is incomplete."
                    )
                    continue

                m5 = results["M5"]
                m15 = results["M15"]
                h1 = results["H1"]

                signal, reason = entry_signal(m5)

                trend15 = trend_direction(m15)
                trend1h = trend_direction(h1)

                if signal == "BUY":
                    if not (
                        trend15 == "BULLISH"
                        and trend1h == "BULLISH"
                    ):
                        signal = "NO SIGNAL"
                        reason = (
                            "M15 and H1 must both be bullish"
                        )

                elif signal == "SELL":
                    if not (
                        trend15 == "BEARISH"
                        and trend1h == "BEARISH"
                    ):
                        signal = "NO SIGNAL"
                        reason = (
                            "M15 and H1 must both be bearish"
                        )

                last = m5.iloc[-1]

                c1, c2, c3, c4 = st.columns(4)

                c1.metric("Final signal", signal)
                c2.metric(
                    "M5 close",
                    f"{last['close']:.5f}"
                )
                c3.metric(
                    "RSI 14",
                    f"{last['rsi']:.1f}"
                )
                c4.metric(
                    "ADX 14",
                    f"{last['adx']:.1f}"
                )

                st.write(f"**M5 setup:** {reason}")
                st.write(f"**M15 trend:** {trend15}")
                st.write(f"**H1 trend:** {trend1h}")

                st.write(
                    f"**EMA20:** {last['ema20']:.5f} | "
                    f"**EMA50:** {last['ema50']:.5f} | "
                    f"**ATR14:** {last['atr']:.5f}"
                )

                with st.expander("View latest M5 candles"):
                    st.dataframe(
                        m5.tail(10),
                        use_container_width=True
                    )

        except KeyError:
            st.error(
                "Missing TWELVE_DATA_API_KEY in Streamlit Secrets."
            )

        except Exception as error:
            st.error(f"Unexpected error: {error}")

st.divider()

st.caption(
    "Educational prototype | No live orders | "
    "Signals are experimental and not guaranteed profitable."
)
