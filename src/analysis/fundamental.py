"""Fundamental scoring berbasis PER, PBV, ROE."""
from __future__ import annotations

from dataclasses import dataclass

from src.data.idx_scraper import Fundamental


@dataclass
class FundamentalSignal:
    code: str
    per: float | None
    pbv: float | None
    roe: float | None
    score: float                 # 0-100, atau 50 jika data tidak lengkap (neutral)
    reasons: list[str]
    has_data: bool


def analyze(f: Fundamental, cfg: dict) -> FundamentalSignal:
    max_per = cfg.get("max_per", 25.0)
    max_pbv = cfg.get("max_pbv", 3.0)
    min_roe = cfg.get("min_roe", 10.0)

    score = 50.0
    reasons: list[str] = []
    data_count = 0

    if f.per is not None and f.per > 0:
        data_count += 1
        if f.per <= max_per * 0.6:
            score += 15
            reasons.append(f"PER murah ({f.per:.1f})")
        elif f.per <= max_per:
            score += 8
            reasons.append(f"PER wajar ({f.per:.1f})")
        elif f.per > max_per * 1.5:
            score -= 10
            reasons.append(f"PER mahal ({f.per:.1f})")

    if f.pbv is not None and f.pbv > 0:
        data_count += 1
        if f.pbv < 1.0:
            score += 12
            reasons.append(f"PBV < 1 (undervalued, {f.pbv:.2f})")
        elif f.pbv <= max_pbv:
            score += 6
            reasons.append(f"PBV wajar ({f.pbv:.2f})")
        elif f.pbv > max_pbv * 1.5:
            score -= 8
            reasons.append(f"PBV mahal ({f.pbv:.2f})")

    if f.roe is not None:
        data_count += 1
        if f.roe >= min_roe * 2:
            score += 18
            reasons.append(f"ROE sangat baik ({f.roe:.1f}%)")
        elif f.roe >= min_roe:
            score += 10
            reasons.append(f"ROE sehat ({f.roe:.1f}%)")
        elif f.roe < 0:
            score -= 15
            reasons.append(f"ROE negatif ({f.roe:.1f}%)")

    has_data = data_count >= 2
    if not has_data:
        score = 50.0
        reasons.append("Data fundamental tidak lengkap (skor netral)")

    score = max(0.0, min(100.0, score))

    return FundamentalSignal(
        code=f.code,
        per=f.per,
        pbv=f.pbv,
        roe=f.roe,
        score=score,
        reasons=reasons,
        has_data=has_data,
    )
