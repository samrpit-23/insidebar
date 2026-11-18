"""Core logic: 10%+ fall in last N weeks + inside bar near the bottom."""
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

import pandas as pd

IST = ZoneInfo("Asia/Kolkata")


def drop_running_candle(df: pd.DataFrame) -> pd.DataFrame:
    """If NSE is open right now, drop today's incomplete daily candle."""
    now = datetime.now(IST)
    market_open = now.weekday() < 5 and dtime(9, 15) <= now.time() < dtime(15, 45)
    if market_open and len(df) and df.index[-1].date() == now.date():
        return df.iloc[:-1]
    return df


def to_weekly(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.resample("W-FRI")
        .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"})
        .dropna()
    )


def find_setup(
    df: pd.DataFrame,
    weeks: int = 6,
    min_fall: float = 10.0,
    near_low_pct: float = 3.0,
    ib_lookback: int = 1,
    timeframe: str = "Daily",
):
    """Return a dict if the stock matches the setup, else None.

    Rules
    -----
    1. In the last `weeks` weeks, the swing high must come BEFORE the swing low
       and the fall (high -> low) must be >= `min_fall` %.
    2. One of the last `ib_lookback` candles is an inside bar
       (high < mother high AND low > mother low).
    3. The mother candle's low must be within `near_low_pct` % of the window low
       (i.e. the inside bar is forming at the bottom).
    """
    if timeframe == "Weekly":
        df = to_weekly(df)
        win = weeks
    else:
        win = weeks * 5

    if len(df) < win + 1:
        return None

    w = df.iloc[-win:]
    peak, low = float(w["High"].max()), float(w["Low"].min())
    peak_dt, low_dt = w["High"].idxmax(), w["Low"].idxmin()

    if peak_dt >= low_dt:          # high must precede low (a real fall)
        return None
    fall = (peak - low) / peak * 100
    if fall < min_fall:
        return None

    n = len(df)
    for k in range(ib_lookback):
        i = n - 1 - k
        if i < 1:
            break
        ib, mother = df.iloc[i], df.iloc[i - 1]
        if ib["High"] < mother["High"] and ib["Low"] > mother["Low"]:
            dist_low = (float(mother["Low"]) - low) / low * 100
            if dist_low > near_low_pct:
                continue
            ltp = float(df["Close"].iloc[-1])
            m_rng = float(mother["High"] - mother["Low"])
            return {
                "LTP": round(ltp, 2),
                "Peak": round(peak, 2),
                "Low": round(low, 2),
                "Fall %": round(fall, 2),
                "LTP vs Peak %": round((ltp - peak) / peak * 100, 2),
                "Mother High": round(float(mother["High"]), 2),
                "Mother Low": round(float(mother["Low"]), 2),
                "IB High": round(float(ib["High"]), 2),
                "IB Low": round(float(ib["Low"]), 2),
                "IB Size % of Mother": round(
                    float(ib["High"] - ib["Low"]) / m_rng * 100, 1
                ) if m_rng else None,
                "Dist from Low %": round(dist_low, 2),
                "IB Date": df.index[i].strftime("%d-%b-%Y"),
            }
    return None
