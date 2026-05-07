"""Volume analysis: deteksi spike, akumulasi, dan price-volume confirmation."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class VolumeSignal:
    code: str
    last_volume: float
    avg_volume: float
    volume_ratio: float          # last / avg
    is_spike: bool
    price_change_pct: float
    score: float                 # 0-100
    reasons: list[str]


def analyze(code: str, df: pd.DataFrame, cfg: dict) -> VolumeSignal:
    lookback = cfg.get("lookback_days", 20)
    spike_mult = cfg.get("spike_multiplier", 1.5)

    vol = df["Volume"]
    close = df["Close"]

    last_vol = float(vol.iloc[-1])
    avg_vol = float(vol.iloc[-(lookback + 1):-1].mean()) if len(vol) > lookback else float(vol.mean())
    ratio = last_vol / avg_vol if avg_vol > 0 else 0.0
    is_spike = ratio >= spike_mult

    last_close = float(close.iloc[-1])
    prev_close = float(close.iloc[-2])
    price_change = (last_close - prev_close) / prev_close * 100 if prev_close > 0 else 0.0

    score = 50.0
    reasons: list[str] = []

    if is_spike and price_change > 0:
        boost = min(25, 10 + (ratio - 1) * 10)
        score += boost
        reasons.append(f"Volume spike {ratio:.1f}x + harga +{price_change:.2f}% (akumulasi)")
    elif is_spike and price_change < 0:
        score -= 10
        reasons.append(f"Volume spike {ratio:.1f}x tapi harga {price_change:.2f}% (distribusi)")
    elif ratio > 1.2 and price_change > 1.0:
        score += 12
        reasons.append(f"Volume naik ({ratio:.1f}x) + harga +{price_change:.2f}%")
    elif ratio < 0.5:
        score -= 5
        reasons.append(f"Volume sangat rendah ({ratio:.1f}x avg)")

    recent_vol = vol.iloc[-5:].mean()
    older_vol = vol.iloc[-(lookback + 1):-5].mean() if len(vol) > lookback else recent_vol
    if older_vol > 0 and recent_vol / older_vol > 1.3:
        score += 8
        reasons.append("Volume 5 hari terakhir naik vs rata-rata")

    score = max(0.0, min(100.0, score))

    return VolumeSignal(
        code=code,
        last_volume=last_vol,
        avg_volume=avg_vol,
        volume_ratio=ratio,
        is_spike=is_spike,
        price_change_pct=price_change,
        score=score,
        reasons=reasons,
    )
