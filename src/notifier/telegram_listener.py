"""Long-polling Telegram listener supaya bot bisa nerima command interaktif.

Mode hybrid: kalau schedule.run_mode = "interval", listener juga jalan auto-scan
periodik di thread terpisah.
"""
from __future__ import annotations

import datetime as dt
import logging
import threading
import time

import requests

from src.notifier import telegram as tg

log = logging.getLogger(__name__)

GETUPDATES_URL = "https://api.telegram.org/bot{token}/getUpdates"
POLL_TIMEOUT = 25

HELP_TEXT = (
    "<b>🤖 Saham Monitor Bot</b>\n\n"
    "Perintah:\n"
    "• <b>/list</b> — analisis semua saham di watchlist\n"
    "• <b>/scan KODE [KODE2 ...]</b> — analisis saham tertentu\n"
    "    contoh: <code>/scan BBCA TLKM ASII</code>\n"
    "• <b>/status</b> — info bot &amp; scan terakhir\n"
    "• <b>/help</b> — pesan ini"
)


class Listener:
    def __init__(self, cfg: dict, analyze_func):
        self.cfg = cfg
        tg_cfg = cfg.get("telegram", {})
        self.token = tg_cfg.get("bot_token", "")
        self.allowed_chat = str(tg_cfg.get("chat_id", ""))
        self.analyze = analyze_func
        self.offset = 0
        self.last_scan_time: float | None = None
        self.last_scan_count = 0
        self.scan_lock = threading.Lock()
        self.running = False

        if not self.token or self.token.startswith("PASTE_"):
            raise SystemExit(
                "telegram.bot_token belum diisi di config/settings.yaml"
            )
        if not self.allowed_chat or self.allowed_chat.startswith("PASTE_"):
            raise SystemExit(
                "telegram.chat_id belum diisi di config/settings.yaml"
            )

    def start(self) -> None:
        log.info("Bot listener starting (chat_id=%s)", self.allowed_chat)
        tg.send_message(
            self.token,
            self.allowed_chat,
            "🤖 Bot saham aktif. Kirim /help untuk daftar perintah.",
        )
        self.running = True

        sched = self.cfg.get("schedule", {})
        if sched.get("run_mode") == "interval":
            mins = int(sched.get("interval_minutes", 60))
            t = threading.Thread(target=self._periodic_scan, args=(mins,), daemon=True)
            t.start()
            log.info("Auto-scan thread started: every %d min", mins)

        try:
            self._poll_loop()
        except KeyboardInterrupt:
            log.info("Bot dihentikan (Ctrl+C)")
            self.running = False

    def _periodic_scan(self, minutes: int) -> None:
        while self.running:
            time.sleep(minutes * 60)
            try:
                self._do_scan(None, "🔁 Auto-scan terjadwal...")
            except Exception as e:
                log.exception("Auto-scan failed: %s", e)

    def _poll_loop(self) -> None:
        while self.running:
            try:
                r = requests.get(
                    GETUPDATES_URL.format(token=self.token),
                    params={"offset": self.offset, "timeout": POLL_TIMEOUT},
                    timeout=POLL_TIMEOUT + 5,
                )
                data = r.json()
                if not data.get("ok"):
                    log.error("getUpdates failed: %s", data)
                    time.sleep(5)
                    continue
                for upd in data.get("result", []):
                    self.offset = upd["update_id"] + 1
                    try:
                        self._handle_update(upd)
                    except Exception as e:
                        log.exception("Update handler error: %s", e)
            except requests.exceptions.RequestException as e:
                log.warning("Poll network error: %s", e)
                time.sleep(5)
            except Exception as e:
                log.exception("Poll loop error: %s", e)
                time.sleep(5)

    def _handle_update(self, upd: dict) -> None:
        msg = upd.get("message") or upd.get("edited_message")
        if not msg:
            return
        chat_id = str(msg.get("chat", {}).get("id", ""))
        if chat_id != self.allowed_chat:
            log.warning("Ignored message from unauthorized chat %s", chat_id)
            return
        text = (msg.get("text") or "").strip()
        if not text.startswith("/"):
            return

        parts = text.split()
        cmd = parts[0].split("@")[0].lower().lstrip("/")
        args = parts[1:]
        log.info("Command: /%s args=%s", cmd, args)

        if cmd in ("start", "help"):
            tg.send_message(self.token, chat_id, HELP_TEXT)
        elif cmd in ("list", "list-saham", "listsaham"):
            threading.Thread(
                target=self._do_scan, args=(None, "📊 Scanning watchlist..."),
                daemon=True,
            ).start()
        elif cmd == "scan":
            if not args:
                tg.send_message(
                    self.token, chat_id,
                    "Usage: <code>/scan KODE [KODE2 ...]</code>\n"
                    "Contoh: <code>/scan BBCA TLKM</code>",
                )
                return
            threading.Thread(
                target=self._do_scan,
                args=(args, f"📊 Scanning {len(args)} saham..."),
                daemon=True,
            ).start()
        elif cmd == "status":
            self._send_status()
        else:
            tg.send_message(
                self.token, chat_id,
                f"Perintah tidak dikenal: /{cmd}\nKirim /help untuk daftar.",
            )

    def _do_scan(self, codes_override, ack_text: str) -> None:
        if not self.scan_lock.acquire(blocking=False):
            tg.send_message(
                self.token, self.allowed_chat,
                "⏳ Scan sebelumnya masih berjalan, tunggu sebentar...",
            )
            return
        try:
            tg.send_message(self.token, self.allowed_chat, ack_text)
            ranked = self.analyze(self.cfg, codes_override=codes_override)
            min_score = self.cfg.get("scoring", {}).get("min_score_to_alert", 65)
            if not ranked:
                tg.send_message(
                    self.token, self.allowed_chat,
                    "⚠️ Tidak ada data berhasil diambil. Coba lagi nanti.",
                )
            else:
                tg.send_report(self.token, self.allowed_chat, ranked, min_score)
            self.last_scan_time = time.time()
            self.last_scan_count = len(ranked)
        except Exception as e:
            log.exception("Scan failed: %s", e)
            tg.send_message(self.token, self.allowed_chat, f"❌ Scan gagal: {e}")
        finally:
            self.scan_lock.release()

    def _send_status(self) -> None:
        if self.last_scan_time:
            ts = dt.datetime.fromtimestamp(self.last_scan_time).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            line = f"Scan terakhir: {ts} ({self.last_scan_count} saham)"
        else:
            line = "Belum pernah scan sejak bot dinyalakan."
        sched = self.cfg.get("schedule", {})
        mode = sched.get("run_mode", "once")
        auto = ""
        if mode == "interval":
            auto = f"\nAuto-scan: tiap {sched.get('interval_minutes', 60)} menit"
        tg.send_message(
            self.token, self.allowed_chat,
            f"✅ Bot aktif\n{line}{auto}",
        )
