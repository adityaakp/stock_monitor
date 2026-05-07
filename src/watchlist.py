"""LQ45 — daftar 45 saham paling likuid di IDX (per periode Feb 2025).
Diperbarui setiap 6 bulan oleh IDX. Cek idx.co.id untuk daftar terbaru."""

LQ45 = [
    "ACES", "ADRO", "AKRA", "AMMN", "AMRT", "ANTM", "ARTO", "ASII", "BBCA",
    "BBNI", "BBRI", "BBTN", "BMRI", "BRIS", "BRPT", "CPIN", "ESSA", "EXCL",
    "GOTO", "ICBP", "INCO", "INDF", "INDY", "INKP", "ISAT", "ITMG", "JSMR",
    "KLBF", "MAPI", "MBMA", "MDKA", "MEDC", "MTEL", "PGAS", "PGEO", "PTBA",
    "SCMA", "SIDO", "SMGR", "SMRA", "TLKM", "TOWR", "UNTR", "UNVR", "BREN",
]


def get_watchlist(use_lq45: bool = True, custom: list | None = None) -> list[str]:
    """Return daftar kode saham (tanpa suffix .JK)."""
    if custom:
        return [s.upper().replace(".JK", "") for s in custom]
    if use_lq45:
        return LQ45.copy()
    return []


def to_yahoo_ticker(code: str) -> str:
    """BBCA -> BBCA.JK"""
    code = code.upper().replace(".JK", "")
    return f"{code}.JK"
