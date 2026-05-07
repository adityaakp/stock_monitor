"""Saham monitor — entry point.

Usage:
    python -m src.main                     # jalan sekali
    python -m src.main --config path.yaml  # config custom
    python -m src.main --dry-run           # tanpa kirim Telegram
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import yaml

from src.analysis import fundamental as fund_mod
from src.analysis import technical as tech_mod
from src.analysis import volume as vol_mod
from src.data.idx_scraper import fetch_many_fundamental
from src.data.price_fetcher import fetch_many
from src.notifier import telegram as tg
from src.scoring import composite, rank
from src.watchlist import get_watchlist

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("saham-monitor")


def load_config(path: Path) -> dict:
    if not path.exists():
        log.error("Config file tidak ditemukan: %s", path)
        log.error("Salin config/settings.example.yaml ke config/settings.yaml dan isi nilainya.")
        sys.exit(1)
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def analyze_all(cfg: dict, codes_override: list[str] | None = None):
    """Run full pipeline (fetch + analyze + rank) and return ranked signals."""
    if codes_override:
        codes = [c.upper().replace(".JK", "") for c in codes_override]
    else:
        wl_cfg = cfg.get("watchlist", {})
        codes = get_watchlist(
            use_lq45=wl_cfg.get("use_lq45", True),
            custom=wl_cfg.get("custom") or None,
        )
    log.info("Watchlist: %d saham", len(codes))

    data_cfg = cfg.get("data", {})
    history_days = data_cfg.get("history_days", 90)
    delay = data_cfg.get("request_delay_seconds", 1.0)

    log.info("Fetching OHLCV...")
    price_data = fetch_many(codes, days=history_days, delay=delay)
    log.info("OHLCV fetched: %d/%d", len(price_data), len(codes))

    log.info("Fetching fundamentals...")
    fundamentals = fetch_many_fundamental(list(price_data.keys()), delay=delay)
    log.info("Fundamentals fetched: %d", len(fundamentals))

    tech_cfg = cfg.get("technical", {})
    vol_cfg = cfg.get("volume", {})
    fund_cfg = cfg.get("fundamental", {})
    weights = cfg.get("scoring", {}).get("weights", {})

    signals = []
    for code, pdat in price_data.items():
        try:
            t = tech_mod.analyze(code, pdat.df, tech_cfg)
            v = vol_mod.analyze(code, pdat.df, vol_cfg)
            f = fund_mod.analyze(fundamentals.get(code) or _empty_fund(code), fund_cfg)
            signals.append(composite(t, v, f, weights))
        except Exception as e:
            log.error("Analysis failed for %s: %s", code, e)

    return rank(signals)


def run_once(cfg: dict, dry_run: bool = False) -> None:
    ranked = analyze_all(cfg)
    min_score = cfg.get("scoring", {}).get("min_score_to_alert", 65)

    log.info("=" * 60)
    log.info("TOP 10 KANDIDAT (skor tertinggi):")
    for s in ranked[:10]:
        flag = "✓" if s.composite_score >= min_score else " "
        log.info(
            "  %s %-6s  skor=%5.1f  T=%4.1f V=%4.1f F=%4.1f  Rp%s",
            flag, s.code, s.composite_score, s.technical.score,
            s.volume.score, s.fundamental.score, f"{s.last_close:,.0f}",
        )
    log.info("=" * 60)

    tg_cfg = cfg.get("telegram", {})
    if dry_run:
        log.info("--dry-run: skip Telegram")
        return
    if not tg_cfg.get("enabled"):
        log.info("Telegram disabled di config")
        return

    sent = tg.send_report(
        token=tg_cfg.get("bot_token", ""),
        chat_id=tg_cfg.get("chat_id", ""),
        top_signals=ranked,
        min_score=min_score,
    )
    log.info("Telegram: %d pesan terkirim", sent)


def _empty_fund(code):
    from src.data.idx_scraper import Fundamental
    return Fundamental(code=code, per=None, pbv=None, roe=None, market_cap=None, sector=None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/settings.yaml")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--bot", action="store_true",
                    help="Jalankan listener Telegram (interaktif: terima command /list, /scan, dst.)")
    args = ap.parse_args()

    cfg = load_config(Path(args.config))

    if args.bot:
        from src.notifier.telegram_listener import Listener
        Listener(cfg, analyze_all).start()
        return

    sched = cfg.get("schedule", {})
    mode = sched.get("run_mode", "once")

    if mode == "once":
        run_once(cfg, dry_run=args.dry_run)
        return

    if mode == "interval":
        minutes = sched.get("interval_minutes", 60)
        log.info("Interval mode: every %d min", minutes)
        while True:
            try:
                run_once(cfg, dry_run=args.dry_run)
            except Exception as e:
                log.exception("Run failed: %s", e)
            time.sleep(minutes * 60)

    if mode == "daily":
        import schedule as sch
        target = sched.get("daily_time", "16:30")
        log.info("Daily mode: every day at %s", target)
        sch.every().day.at(target).do(lambda: run_once(cfg, dry_run=args.dry_run))
        run_once(cfg, dry_run=args.dry_run)  # run sekali di startup
        while True:
            sch.run_pending()
            time.sleep(30)


if __name__ == "__main__":
    main()
