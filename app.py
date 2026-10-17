
import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

st.set_page_config(
    page_title="SAINT TRADER AI",
    page_icon="📈",
    layout="wide"
)

st.title("👑 SAINT TRADER AI")
st.caption("Forex scanner | Historical backtesting | Paper trading only")

PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD"]
TIMEFRAMES = {"M5": "5min", "M15": "15min", "H1": "1h"}

PIP = 0.0001
STOP_ATR = 1.5
TARGET_R = 2.0
COST_PIPS = 1.6


def utc_string(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


@st.cache_data(ttl=300)
def fetch_history(pair, interval, start_text, end_text, api_key):
    response = requests.get(
        "https://api.twelvedata.com/time_series",
        params={
            "symbol": pair,
            "interval": interval,
            "start_date": start_text,
            "end_date": end_text,
            "outputsize": 5000,
            "timezone": "UTC",
            "apikey": api_key
        },
        timeout=30
    )
    response.raise_for_status()
    data = response.json()

    if data.get("status") == "error":
        raise ValueError(data.get("message", "Provider error"))

    if not data.get("values"):
        raise ValueError("No historical candles returned")

    df = pd.DataFrame(data["values"])
    df["datetime"] = pd.to_datetime(
        df["datetime"], errors="coerce", utc=True
    )

    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(
        subset=["datetime", "open", "high", "low", "close"]
    )

    return (
        df.sort_values("datetime")
        .drop_duplicates("datetime")
        .reset_index(drop=True)
    )


def get_history(pair, interval, start, end, api_key):
    # Split M5 history into 15-day requests to stay under
    # the usual 5000-candle per-request limit.
    chunks = []

    if interval == "5min":
        cursor = start
        while cursor < end:
            chunk_end = min(cursor + timedelta(days=15), end)
            chunks.append((cursor, chunk_end))
            cursor = chunk_end
    else:
        chunks.append((start, end))

    frames = []

    for chunk_start, chunk_end in chunks:
        df = fetch_history(
            pair,
            interval,
            utc_string(chunk_start),
            utc_string(chunk_end),
            api_key
        )
        frames.append(df)

    result = pd.concat(frames, ignore_index=True)
    result = (
        result.sort_values("datetime")
        .drop_duplicates("datetime")
        .reset_index(drop=True)
    )

    # Exclude the newest candle, which may still be forming.
    if len(result) > 1:
        result = result.iloc[:-1].reset_index(drop=True)

    return result


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
        alpha=1 / 14, min_periods=14, adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / 14, min_periods=14, adjust=False
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - 100 / (1 + rs)

    high_low = df["high"] - df["low"]
    high_close = (
        df["high"] - df["close"].shift()
    ).abs()
    low_close = (
        df["low"] - df["close"].shift()
    ).abs()

    tr = pd.concat(
        [high_low, high_close, low_close], axis=1
    ).max(axis=1)

    up = df["high"].diff()
    down = -df["low"].diff()

    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where(
        (down > up) & (down > 0), 0.0
    )

    df["atr"] = tr.ewm(
        alpha=1 / 14, min_periods=14, adjust=False
    ).mean()

    plus_di = 100 * plus_dm.ewm(
        alpha=1 / 14, min_periods=14, adjust=False
    ).mean() / df["atr"].replace(0, np.nan)

    minus_di = 100 * minus_dm.ewm(
        alpha=1 / 14, min_periods=14, adjust=False
    ).mean() / df["atr"].replace(0, np.nan)

    dx = 100 * (plus_di - minus_di).abs() / (
        plus_di + minus_di
    ).replace(0, np.nan)

    df["adx"] = dx.ewm(
        alpha=1 / 14, min_periods=14, adjust=False
    ).mean()

    return df


def direction(df):
    result = df.copy()
    result["trend"] = "NEUTRAL"

    result.loc[
        result["ema20"] > result["ema50"], "trend"
    ] = "BULLISH"

    result.loc[
        result["ema20"] < result["ema50"], "trend"
    ] = "BEARISH"

    result.loc[
        result[["ema20", "ema50"]].isna().any(axis=1),
        "trend"
    ] = "UNKNOWN"

    return result


def prepare_signals(m5, m15, h1):
    m5 = add_indicators(m5)
    m15 = direction(add_indicators(m15))
    h1 = direction(add_indicators(h1))

    # A candle's information is only available after it closes.
    m5["signal_time"] = m5["datetime"] + pd.Timedelta(minutes=5)
    m15["available_at"] = (
        m15["datetime"] + pd.Timedelta(minutes=15)
    )
    h1["available_at"] = (
        h1["datetime"] + pd.Timedelta(hours=1)
    )

    # At each M5 close, use only the most recent fully closed
    # M15 and H1 candle available at that time.
    result = pd.merge_asof(
        m5.sort_values("signal_time"),
        m15[["available_at", "trend"]].sort_values("available_at"),
        left_on="signal_time",
        right_on="available_at",
        direction="backward"
    ).rename(columns={"trend": "m15_trend"})

    result = pd.merge_asof(
        result.sort_values("signal_time"),
        h1[["available_at", "trend"]].sort_values("available_at"),
        left_on="signal_time",
        right_on="available_at",
        direction="backward",
        suffixes=("", "_h1")
    ).rename(columns={"trend": "h1_trend"})

    result["signal"] = "NONE"

    buy = (
        (result["ema20"] > result["ema50"])
        & (result["rsi"] >= 55)
        & (result["adx"] >= 20)
        & (result["m15_trend"] == "BULLISH")
        & (result["h1_trend"] == "BULLISH")
    )

    sell = (
        (result["ema20"] < result["ema50"])
        & (result["rsi"] <= 45)
        & (result["adx"] >= 20)
        & (result["m15_trend"] == "BEARISH")
        & (result["h1_trend"] == "BEARISH")
    )

    result.loc[buy, "signal"] = "BUY"
    result.loc[sell, "signal"] = "SELL"

    return result


def run_backtest(df):
    trades = []
    i = 0

    while i < len(df) - 1:
        row = df.iloc[i]
        side = row["signal"]

        if side not in ("BUY", "SELL"):
            i += 1
            continue

        if pd.isna(row["atr"]) or row["atr"] <= 0:
            i += 1
            continue

        # Enter at the NEXT candle open, not at the signal close.
        entry_index = i + 1
        entry = float(df.iloc[entry_index]["open"])
        risk_distance = float(row["atr"]) * STOP_ATR

        if side == "BUY":
            stop = entry - risk_distance
            target = entry + TARGET_R * risk_distance
        else:
            stop = entry + risk_distance
            target = entry - TARGET_R * risk_distance

        exit_index = None
        gross_r = None
        exit_reason = None

        for j in range(entry_index, len(df)):
            candle = df.iloc[j]

            if side == "BUY":
                hit_stop = candle["low"] <= stop
                hit_target = candle["high"] >= target
            else:
                hit_stop = candle["high"] >= stop
                hit_target = candle["low"] <= target

            # Conservative rule: if both are hit in one candle,
            # assume the stop was hit first.
            if hit_stop:
                exit_index = j
                gross_r = -1.0
                exit_reason = "Stop loss"
                break

            if hit_target:
                exit_index = j
                gross_r = TARGET_R
                exit_reason = "Take profit"
                break

        # Ignore trades still open at the end of the dataset.
        if exit_index is None:
            break

        cost_r = (COST_PIPS * PIP) / risk_distance
        net_r = gross_r - cost_r

        trades.append({
            "Entry time": df.iloc[entry_index]["datetime"],
            "Side": side,
            "Entry": entry,
            "Stop": stop,
            "Target": target,
            "Exit time": df.iloc[exit_index]["datetime"],
            "Exit reason": exit_reason,
            "Gross R": gross_r,
            "Cost R": cost_r,
            "Net R": net_r
        })

        # One trade at a time; don't overlap positions.
        i = exit_index + 1

    return pd.DataFrame(trades)


st.header("Historical backtest")

pair = st.selectbox("Backtest pair", PAIRS, index=0)

days = st.selectbox(
    "History length",
    [7, 14, 30],
    index=2,
    format_func=lambda d: f"{d} days"
)

st.write(
    f"Risk model: SL = {STOP_ATR} × ATR | "
    f"TP = {TARGET_R}R | "
    f"Estimated round-trip cost = {COST_PIPS} pips"
)

st.warning(
    "Historical data availability and API quotas depend on your "
    "Twelve Data plan. Results are simulated, not live trading."
)

if st.button("Run historical backtest", type="primary"):
    try:
        api_key = st.secrets["TWELVE_DATA_API_KEY"]

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)

        with st.spinner("Downloading history and testing signals..."):
            m5 = get_history(
                pair, "5min", start, end, api_key
            )
            m15 = get_history(
                pair, "15min", start, end, api_key
            )
            h1 = get_history(
                pair, "1h", start, end, api_key
            )

            st.write(
                f"Candles downloaded: M5 {len(m5):,} | "
                f"M15 {len(m15):,} | H1 {len(h1):,}"
            )

            if min(len(m5), len(m15), len(h1)) < 100:
                st.error(
                    "Insufficient history. Check your provider plan "
                    "or select a shorter period."
                )
                st.stop()

            signals = prepare_signals(m5, m15, h1)
            trades = run_backtest(signals)

        if trades.empty:
            st.warning(
                "No completed trades were found in this sample. "
                "This is a valid result; do not loosen filters just "
                "to force trades."
            )
        else:
            wins = trades[trades["Net R"] > 0]
            losses = trades[trades["Net R"] < 0]

            win_rate = 100 * len(wins) / len(trades)
            gross_profit = wins["Net R"].sum()
            gross_loss = abs(losses["Net R"].sum())

            if gross_loss == 0:
                profit_factor = (
                    float("inf") if gross_profit > 0 else 0.0
                )
            else:
                profit_factor = gross_profit / gross_loss

            equity = trades["Net R"].cumsum()
            drawdown = equity - equity.cummax()
            max_drawdown = abs(drawdown.min())

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Completed trades", len(trades))
            c2.metric("Win rate", f"{win_rate:.1f}%")
            c3.metric(
                "Profit factor",
                "∞" if np.isinf(profit_factor)
                else f"{profit_factor:.2f}"
            )
            c4.metric("Net result", f"{trades['Net R'].sum():.2f} R")

            st.metric("Maximum drawdown", f"{max_drawdown:.2f} R")

            st.subheader("Trade history")
            st.dataframe(
                trades.sort_values("Entry time", ascending=False),
                use_container_width=True
            )

            st.subheader("Cumulative net R")
            chart = trades[["Entry time", "Net R"]].copy()
            chart["Cumulative R"] = chart["Net R"].cumsum()
            st.line_chart(
                chart.set_index("Entry time")["Cumulative R"]
            )

            csv = trades.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download trade history CSV",
                data=csv,
                file_name="saint_trader_backtest.csv",
                mime="text/csv"
            )

            st.caption(
                "Profit factor and drawdown are calculated in R units. "
                "The cost estimate is simplified; actual spread, "
                "slippage, and execution can differ."
            )

    except KeyError:
        st.error(
            "Missing TWELVE_DATA_API_KEY in Streamlit Secrets."
        )
    except Exception as error:
        st.error(f"Backtest failed: {error}")

st.divider()
st.caption(
    "SAINT TRADER AI | Educational prototype | "
    "No live orders | Backtest results do not guarantee future returns"
)
