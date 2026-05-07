"""OHLCV fetcher via yfinance. Data bersumber dari IDX (delay ~15 menit)."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import pandas as pd
import yfinance as yf

from src.watchlist import to_yahoo_ticker

log = logging.getLogger(__name__)


@dataclass
class PriceData:
    code: str
    df: pd.DataFrame  # kolom: Open, High, Low, Close, Volume; index: Date


def fetch_one(code: str, days: int = 90) -> PriceData | None:
    ticker = to_yahoo_ticker(code)
    try:
        df = yf.download(
            ticker,
            period=f"{days}d",
            interval="1d",
            progress=False,
            auto_adjust=False,
        )
        if df is None or df.empty:
            log.warning("No data for %s", ticker)
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        if len(df) < 30:
            log.warning("Insufficient history for %s (%d rows)", ticker, len(df))
            return None
        return PriceData(code=code, df=df)
    except Exception as e:
        log.error("Failed to fetch %s: %s", ticker, e)
        return None


def fetch_many(codes: list[str], days: int = 90, delay: float = 0.5) -> dict[str, PriceData]:
    out: dict[str, PriceData] = {}
    for code in codes:
        pd_obj = fetch_one(code, days=days)
        if pd_obj is not None:
            out[code] = pd_obj
        time.sleep(delay)
    return out
