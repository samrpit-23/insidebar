import io
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st
import yfinance as yf

from screener import drop_running_candle, find_setup

st.set_page_config(page_title="NSE Inside Bar at Bottom", page_icon="📉", layout="wide")

# ------------------------------------------------------------------ segments
INDEX_FILES = {
    "Nifty 50": "ind_nifty50list.csv",
    "Nifty Next 50": "ind_niftynext50list.csv",
    "Nifty 100": "ind_nifty100list.csv",
    "Nifty 200": "ind_nifty200list.csv",
    "Nifty 500": "ind_nifty500list.csv",
    "Nifty LargeMidcap 250": "ind_niftylargemidcap250list.csv",
    "Nifty Midcap 50": "ind_niftymidcap50list.csv",
    "Nifty Midcap 100": "ind_niftymidcap100list.csv",
    "Nifty Midcap 150": "ind_niftymidcap150list.csv",
    "Nifty Smallcap 50": "ind_niftysmallcap50list.csv",
    "Nifty Smallcap 100": "ind_niftysmallcap100list.csv",
    "Nifty Smallcap 250": "ind_niftysmallcap250list.csv",
    "Nifty MidSmallcap 400": "ind_niftymidsmallcap400list.csv",
    "Nifty Microcap 250": "ind_niftymicrocap250_list.csv",
    "Nifty Total Market": "ind_niftytotalmarket_list.csv",
    "Nifty Bank": "ind_niftybanklist.csv",
    "Nifty IT": "ind_niftyitlist.csv",
    "Nifty Pharma": "ind_niftypharmalist.csv",
    "Nifty Auto": "ind_niftyautolist.csv",
    "Nifty FMCG": "ind_niftyfmcglist.csv",
    "Nifty Metal": "ind_niftymetallist.csv",
    "Nifty Realty": "ind_niftyrealtylist.csv",
    "Nifty Energy": "ind_niftyenergylist.csv",
}
CHUNK = 100
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/csv,*/*",
    "Referer": "https://www.nseindia.com/",
}


@st.cache_data(ttl=86400, show_spinner=False)
def load_constituents(fname: str) -> pd.DataFrame:
    """NSE archive -> niftyindices.com -> local ./data/<file> fallback."""
    urls = [
        f"https://nsearchives.nseindia.com/content/indices/{fname}",
        f"https://www.niftyindices.com/IndexConstituent/{fname}",
    ]
    raw = None
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.ok and len(r.content) > 200:
                raw = pd.read_csv(io.StringIO(r.text))
                break
        except Exception:
            continue
    if raw is None:
        local = Path(__file__).parent / "data" / fname
        if local.exists():
            raw = pd.read_csv(local)
    if raw is None:
        return pd.DataFrame()
    raw.columns = [c.strip() for c in raw.columns]
    raw["Symbol"] = raw["Symbol"].astype(str).str.strip()
    for col in ("Company Name", "Industry"):
        if col not in raw:
            raw[col] = ""
    return raw[["Symbol", "Company Name", "Industry"]].drop_duplicates("Symbol")


# ------------------------------------------------------------------ OHLC data
@st.cache_data(ttl=900, show_spinner=False)
def download_chunk(tickers: tuple) -> dict:
    """Batch multi-threaded OHLC download (one HTTP burst per chunk)."""

    def _dl(tk):
        return yf.download(
            list(tk), period="6mo", interval="1d", group_by="ticker",
            auto_adjust=True, threads=True, progress=False,
        )

    def _extract(raw, tk):
        out = {}
        if raw is None or raw.empty:
            return out
        for t in tk:
            try:
                d = raw[t] if isinstance(raw.columns, pd.MultiIndex) else raw
                d = d[["Open", "High", "Low", "Close"]].dropna()
                if len(d) >= 20:
                    out[t] = d
            except KeyError:
                pass
        return out

    out = _extract(_dl(tickers), tickers)
    missing = tuple(t for t in tickers if t not in out)
    if missing and len(missing) < len(tickers):      # one quick retry
        out.update(_extract(_dl(missing), missing))
    if not out:
        raise RuntimeError("No data returned (Yahoo rate-limit?)")  # don't cache empties
    return out


def fetch_all(symbols: list[str]) -> tuple[dict, int]:
    tickers = [f"{s}.NS" for s in symbols]
    chunks = [tuple(tickers[i:i + CHUNK]) for i in range(0, len(tickers), CHUNK)]
    data, bar = {}, st.progress(0.0, text="Fetching OHLC…")
    for n, ch in enumerate(chunks, 1):
        try:
            data.update(download_chunk(ch))
        except Exception:
            pass
        bar.progress(n / len(chunks), text=f"Fetching OHLC… {n}/{len(chunks)}")
    bar.empty()
    return data, len(tickers) - len(data)


# ------------------------------------------------------------------ UI
st.title("📉 Inside Bar at Bottom Screener")
st.caption("Stocks that fell 10%+ in the last few weeks and are now forming an inside bar near the low.")

with st.sidebar:
    st.header("Filters")
    segment = st.selectbox("Segment", list(INDEX_FILES), index=4)
    timeframe = st.radio("Inside bar timeframe", ["Daily", "Weekly"], horizontal=True)
    weeks = st.slider("Fall lookback (weeks)", 2, 12, 6)
    min_fall = st.slider("Minimum fall % (high → low)", 5.0, 40.0, 10.0, 0.5)
    near_low = st.slider("Inside bar must be within X% of low", 0.0, 15.0, 3.0, 0.5)
    ib_lookback = st.slider("Inside bar in last N candles", 1, 5, 1)
    completed_only = st.checkbox("Ignore today's running candle (market hours)", True)
    if st.button("🔄 Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

cons = load_constituents(INDEX_FILES[segment])
if cons.empty:
    st.error(
        "Couldn't download the constituent list (NSE sometimes blocks cloud IPs). "
        f"Put `{INDEX_FILES[segment]}` inside a `data/` folder in your repo as a fallback."
    )
    st.stop()

data, failed = fetch_all(cons["Symbol"].tolist())

rows = []
for _, r in cons.iterrows():
    df = data.get(f"{r['Symbol']}.NS")
    if df is None:
        continue
    if completed_only:
        df = drop_running_candle(df)
    res = find_setup(df, weeks, min_fall, near_low, ib_lookback, timeframe)
    if res:
        rows.append({
            "Symbol": r["Symbol"],
            "Company": r["Company Name"],
            "Industry": r["Industry"],
            **res,
            "Chart": f"https://www.tradingview.com/chart/?symbol=NSE%3A{quote(r['Symbol'], safe='')}",
        })

c1, c2, c3 = st.columns(3)
c1.metric("Stocks scanned", len(data))
c2.metric("Matches", len(rows))
c3.metric("No data", failed)

if rows:
    out = pd.DataFrame(rows).sort_values("Fall %", ascending=False).reset_index(drop=True)
    st.dataframe(
        out,
        use_container_width=True,
        hide_index=True,
        column_config={"Chart": st.column_config.LinkColumn("Chart", display_text="Open")},
    )
    st.download_button(
        "⬇️ Download CSV",
        out.drop(columns="Chart").to_csv(index=False).encode(),
        file_name=f"inside_bar_{segment.replace(' ', '_').lower()}.csv",
        mime="text/csv",
    )
    st.caption(
        "Typical use: buy above **IB High** / mother high with stop below **IB Low** / mother low. "
        "This is a screener, not trading advice."
    )
else:
    st.info("No stocks match right now. Try lowering the fall %, widening 'near low', or raising the candle lookback.")
