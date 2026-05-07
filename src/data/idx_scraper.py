"""Fundamental data fetcher.

Strategi: pakai yfinance.Ticker.info dulu (PER, PBV, ROE umumnya tersedia
untuk emiten IDX yang likuid). Jika tidak lengkap, fallback ke None dan
biarkan composite scoring menangani missing data.

Catatan: scraping langsung dari Stockbit/RTI butuh login session dan
melanggar ToS sebagian besar platform. yfinance ambil data dari sumber
publik (Yahoo Finance) yang menarik dari IDX juga.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import yfinance as yf

from src.watchlist import to_yahoo_ticker

log = logging.getLogger(__name__)


@dataclass
class Fundamental:
    code: str
    per: float | None       # trailing P/E
    pbv: float | None       # price-to-book
    roe: float | None       # return on equity (%)
    market_cap: float | None
    sector: str | None


def fetch_fundamental(code: str) -> Fundamental:
    ticker = to_yahoo_ticker(code)
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception as e:
        log.warning("Fundamental fetch failed for %s: %s", ticker, e)
        info = {}

    roe = info.get("returnOnEquity")
    if roe is not None:
        roe = roe * 100  # yfinance kasih dalam desimal

    return Fundamental(
        code=code,
        per=_to_float(info.get("trailingPE")),
        pbv=_to_float(info.get("priceToBook")),
        roe=_to_float(roe),
        market_cap=_to_float(info.get("marketCap")),
        sector=info.get("sector"),
    )


def fetch_many_fundamental(codes: list[str], delay: float = 0.5) -> dict[str, Fundamental]:
    out: dict[str, Fundamental] = {}
    for code in codes:
        out[code] = fetch_fundamental(code)
        time.sleep(delay)
    return out


def _to_float(v) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        if f != f:  # NaN check
            return None
        return f
    except (TypeError, ValueError):
        return None
