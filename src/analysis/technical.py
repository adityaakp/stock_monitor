"""Indikator teknikal: RSI, MACD, Moving Average, Bollinger Bands.
Implementasi manual via pandas — tidak butuh TA-Lib (susah install di Windows).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class TechnicalSignal:
    code: str
    last_close: float
    rsi: float
    macd: float
    macd_signal: float
    macd_hist: float
    ma_short: float
    ma_long: float
    bb_upper: float
    bb_middle: float
    bb_lower: float
    bb_position: float       # 0 = di lower band, 1 = di upper band
    score: float             # 0-100, semakin tinggi semakin bullish
    reasons: list[str]


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def bollinger(close: pd.Series, period: int = 20, num_std: float = 2.0):
    middle = close.rolling(period).mean()
    std = close.rolling(period).std()
    return middle + num_std * std, middle, middle - num_std * std


def analyze(code: str, df: pd.DataFrame, cfg: dict) -> TechnicalSignal:
    close = df["Close"]
    rsi_period = cfg.get("rsi_period", 14)
    ma_short = cfg.get("ma_short", 20)
    ma_long = cfg.get("ma_long", 50)
    bb_period = cfg.get("bollinger_period", 20)
    bb_std = cfg.get("bollinger_std", 2)

    rsi_series = rsi(close, rsi_period)
    macd_line, signal_line, hist = macd(close)
    bb_up, bb_mid, bb_low = bollinger(close, bb_period, bb_std)
    ma_s = close.rolling(ma_short).mean()
    ma_l = close.rolling(ma_long).mean()

    last = -1
    last_close = float(close.iloc[last])
    last_rsi = float(rsi_series.iloc[last])
    last_macd = float(macd_line.iloc[last])
    last_sig = float(signal_line.iloc[last])
    last_hist = float(hist.iloc[last])
    last_ma_s = float(ma_s.iloc[last])
    last_ma_l = float(ma_l.iloc[last])
    last_bb_up = float(bb_up.iloc[last])
    last_bb_mid = float(bb_mid.iloc[last])
    last_bb_low = float(bb_low.iloc[last])

    bb_range = last_bb_up - last_bb_low
    bb_pos = (last_close - last_bb_low) / bb_range if bb_range > 0 else 0.5

    score = 50.0
    reasons: list[str] = []
    bullish_lo, bullish_hi = cfg.get("rsi_bullish_zone", [40, 60])
    rsi_oversold = cfg.get("rsi_oversold", 30)

    if last_rsi < rsi_oversold:
        score += 15
        reasons.append(f"RSI oversold ({last_rsi:.1f})")
    elif bullish_lo <= last_rsi <= bullish_hi:
        score += 10
        reasons.append(f"RSI di zona momentum ({last_rsi:.1f})")
    elif last_rsi > 70:
        score -= 10
        reasons.append(f"RSI overbought ({last_rsi:.1f})")

    prev_hist = float(hist.iloc[last - 1])
    if last_hist > 0 and prev_hist <= 0:
        score += 15
        reasons.append("MACD baru golden cross")
    elif last_hist > 0:
        score += 8
        reasons.append("MACD positif")
    elif last_hist < 0 and prev_hist >= 0:
        score -= 10
        reasons.append("MACD baru death cross")

    if last_ma_s > last_ma_l and last_close > last_ma_s:
        score += 12
        reasons.append(f"Harga di atas MA{ma_short} > MA{ma_long} (uptrend)")
    elif last_close < last_ma_l:
        score -= 8
        reasons.append(f"Harga di bawah MA{ma_long}")

    if bb_pos < 0.2:
        score += 10
        reasons.append("Dekat lower Bollinger (potensi bounce)")
    elif bb_pos > 0.9:
        score -= 5
        reasons.append("Dekat upper Bollinger (overbought)")

    score = max(0.0, min(100.0, score))

    return TechnicalSignal(
        code=code,
        last_close=last_close,
        rsi=last_rsi,
        macd=last_macd,
        macd_signal=last_sig,
        macd_hist=last_hist,
        ma_short=last_ma_s,
        ma_long=last_ma_l,
        bb_upper=last_bb_up,
        bb_middle=last_bb_mid,
        bb_lower=last_bb_low,
        bb_position=bb_pos,
        score=score,
        reasons=reasons,
    )
