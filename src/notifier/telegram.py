"""Telegram notifier — pakai HTTP API langsung supaya tidak perlu async runtime."""
from __future__ import annotations

import html
import logging

import requests

from src.scoring import CompositeSignal

log = logging.getLogger(__name__)

API_URL = "https://api.telegram.org/bot{token}/sendMessage"
MAX_MESSAGE_LEN = 4000


def send_message(token: str, chat_id: str, text: str) -> bool:
    if not token or not chat_id or token.startswith("PASTE_"):
        log.error("Telegram bot_token / chat_id belum dikonfigurasi")
        return False
    try:
        r = requests.post(
            API_URL.format(token=token),
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=10,
        )
        if r.status_code != 200:
            log.error("Telegram API error %s: %s", r.status_code, r.text)
            return False
        return True
    except Exception as e:
        log.error("Telegram send failed: %s", e)
        return False


def format_signal(s: CompositeSignal) -> str:
    e = html.escape  # escape user-facing content supaya aman untuk HTML parse mode
    lines = [
        f"<b>{e(s.code)}</b> — Skor: <b>{s.composite_score:.1f}</b>/100",
        f"Harga: Rp {s.last_close:,.0f}",
        "",
        f"📊 Teknikal: {s.technical.score:.0f} | RSI {s.technical.rsi:.1f} | "
        f"MACD hist {s.technical.macd_hist:+.2f}",
        f"📈 Volume: {s.volume.score:.0f} | "
        f"{s.volume.volume_ratio:.1f}x avg | "
        f"Δ harga {s.volume.price_change_pct:+.2f}%",
    ]
    if s.fundamental.has_data:
        f = s.fundamental
        lines.append(
            f"💼 Fundamental: {f.score:.0f} | "
            f"PER {_fmt(f.per)} | PBV {_fmt(f.pbv)} | ROE {_fmt(f.roe)}%"
        )
    else:
        lines.append("💼 Fundamental: data tidak lengkap")
    lines.append("")
    lines.append("<b>Alasan:</b>")
    for r in s.all_reasons[:8]:
        lines.append(f"  • {e(r)}")
    return "\n".join(lines)


def send_report(
    token: str,
    chat_id: str,
    top_signals: list[CompositeSignal],
    min_score: float,
) -> int:
    qualified = [s for s in top_signals if s.composite_score >= min_score]

    header_lines = [
        f"🔔 <b>Laporan Saham — {len(qualified)} kandidat lulus threshold ({min_score:.0f})</b>",
        f"Total dianalisis: {len(top_signals)} saham",
        "",
    ]
    if not qualified:
        header_lines.append("Tidak ada saham yang melewati threshold hari ini.")
        header_lines.append("Top 3 berdasarkan skor:")
        qualified = top_signals[:3]
        header = "\n".join(header_lines)
        body_parts = [format_signal(s) for s in qualified]
        full = header + "\n\n" + "\n\n———\n\n".join(body_parts)
        return _send_chunks(token, chat_id, full)

    header = "\n".join(header_lines)
    body_parts = [format_signal(s) for s in qualified[:10]]
    full = header + "\n\n" + "\n\n———\n\n".join(body_parts)
    return _send_chunks(token, chat_id, full)


def _send_chunks(token: str, chat_id: str, text: str) -> int:
    sent = 0
    while text:
        chunk = text[:MAX_MESSAGE_LEN]
        if len(text) > MAX_MESSAGE_LEN:
            cut = chunk.rfind("\n\n———")
            if cut > 0:
                chunk = chunk[:cut]
        if send_message(token, chat_id, chunk):
            sent += 1
        text = text[len(chunk):].lstrip()
    return sent


def _fmt(v) -> str:
    return f"{v:.2f}" if v is not None else "-"
