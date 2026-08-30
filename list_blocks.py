#!/usr/bin/env python3
"""
Macin TUM bloklarini listeler: bos koltuk, kapasite, fiyat, numarali/ayakta.

WATCH_BLOCKS'u kendine gore ayarlamak icin bunu bir kez calistir:

    pip install requests
    python list_blocks.py                # varsayilan mac (3188)
    PERFORMANCE_ID=1234 python list_blocks.py

Telegram gerekmez.
"""

import os
import sys

import check_tickets as ct
import requests


def price_of(entry):
    """preis_id alani "#renk|fiyat|...|...|..." bicimindedir."""
    raw = str(entry.get("preis_id", ""))
    parts = raw.split("|")
    if len(parts) > 1:
        try:
            return float(parts[1].rstrip("_").replace(",", "."))
        except ValueError:
            pass
    try:
        return float(entry.get("defaultPrice") or 0)
    except (TypeError, ValueError):
        return 0.0


def main():
    session = requests.Session()
    session.headers.update(
        {"User-Agent": ct.USER_AGENT, "Accept-Language": "de-DE,de;q=0.9"}
    )

    # check_tickets ile ayni uc adimli akis, ama ham JSON'u tutuyoruz.
    r1 = session.get(
        f"{ct.BASE}/shop",
        params={
            "shopid": ct.SHOP_ID,
            "wes": f"empty_session_{ct.SHOP_ID}",
            "language": 1,
            "nextstate": 2,
        },
        timeout=30,
    )
    r1.raise_for_status()
    ct.check_waiting_room(r1)
    import re

    wes = re.search(r"wes=([0-9a-f]{6,}%d)\b" % ct.SHOP_ID, r1.text).group(1)

    r2 = session.get(ct.EVENT_URL, params={"wes": wes}, timeout=30)
    r2.raise_for_status()
    ct.check_waiting_room(r2)
    m = re.search(r'data-session-tab-id="([^"]+)"', r2.text)
    if m:
        wes = m.group(1)

    r3 = session.get(
        f"{ct.BASE}/backend/saalinterface",
        params={"wes": wes, "getSaalInfos": ct.PERFORMANCE_ID, "abohouseid": ""},
        timeout=30,
    )
    r3.raise_for_status()
    blockinfo = (r3.json() or {}).get("blockinfo")
    if not blockinfo:
        print(f"blockinfo bos: {r3.text[:200]}", file=sys.stderr)
        return 1

    rows = []
    for entry in blockinfo.values():
        name = str(entry.get("bezeichnung", "")).strip()
        if not name:
            continue
        try:
            free = int(str(entry.get("sitze_frei", 0)).strip() or 0)
        except ValueError:
            free = 0
        try:
            total = int(str(entry.get("sitze_gesamt", 0)).strip() or 0)
        except ValueError:
            total = 0
        rows.append(
            {
                "name": name,
                "free": free,
                "total": total,
                "price": price_of(entry),
                "numbered": "koltuk" if entry.get("numbered") == "y" else "ayakta",
            }
        )

    # Sadece gercek seyirci bloklari: otopark, basin, personel vb. eleniyor.
    rows = [r for r in rows if r["total"] >= 100]
    rows.sort(key=lambda r: (r["price"], -r["total"]))

    print(f"{'Blok':<10}{'Boş':>7}{'Kapasite':>10}{'Fiyat':>10}   Tip")
    print("-" * 48)
    for r in rows:
        print(
            f"{r['name']:<10}{r['free']:>7}{r['total']:>10}"
            f"{r['price']:>9.2f}€   {r['numbered']}"
        )

    tukenmis = [r["name"] for r in rows if r["free"] == 0]
    print()
    print("Şu an tükenmiş (izlemeye değer) bloklar:")
    print("WATCH_BLOCKS: " + ",".join(tukenmis))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ct.WaitingRoom as wr:
        print(wr, file=sys.stderr)
        sys.exit(2)
