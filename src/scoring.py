"""Composite scoring engine — gabungkan technical, volume, fundamental."""
from __future__ import annotations

from dataclasses import dataclass, field

from src.analysis.fundamental import FundamentalSignal
from src.analysis.technical import TechnicalSignal
from src.analysis.volume import VolumeSignal


@dataclass
class CompositeSignal:
    code: str
    last_close: float
    composite_score: float
    technical: TechnicalSignal
    volume: VolumeSignal
    fundamental: FundamentalSignal
    all_reasons: list[str] = field(default_factory=list)


def composite(
    tech: TechnicalSignal,
    vol: VolumeSignal,
    fund: FundamentalSignal,
    weights: dict,
) -> CompositeSignal:
    w_tech = weights.get("technical", 0.40)
    w_vol = weights.get("volume", 0.25)
    w_fund = weights.get("fundamental", 0.35)

    if not fund.has_data:
        total_w = w_tech + w_vol
        if total_w > 0:
            w_tech = w_tech / total_w
            w_vol = w_vol / total_w
            w_fund = 0.0

    score = tech.score * w_tech + vol.score * w_vol + fund.score * w_fund

    reasons = []
    reasons.extend(f"[T] {r}" for r in tech.reasons)
    reasons.extend(f"[V] {r}" for r in vol.reasons)
    reasons.extend(f"[F] {r}" for r in fund.reasons)

    return CompositeSignal(
        code=tech.code,
        last_close=tech.last_close,
        composite_score=score,
        technical=tech,
        volume=vol,
        fundamental=fund,
        all_reasons=reasons,
    )


def rank(signals: list[CompositeSignal]) -> list[CompositeSignal]:
    return sorted(signals, key=lambda s: s.composite_score, reverse=True)
