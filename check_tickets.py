#!/usr/bin/env python3
"""
TSG Hoffenheim bilet nobetcisi.

Shop'un ic JSON ucundan (saalinterface) blok bazinda bos koltuk sayisini okur.
Izlenen bloklardan biri 0'dan >0'a gecerse Telegram'dan mesaj atar.

Gerekli ortam degiskenleri:
  TELEGRAM_BOT_TOKEN   @BotFather'dan aldigin token
  TELEGRAM_CHAT_ID     Mesajin gidecegi chat id

Istege bagli:
  PERFORMANCE_ID  varsayilan 3188  (TSG Hoffenheim - Borussia Dortmund, 05.09.2026)
  WATCH_BLOCKS    varsayilan: su an tukenmis olan tum ev sahibi bloklari
  STATE_FILE      varsayilan "state.json"

Hangi bloklarin oldugunu gormek icin: python list_blocks.py

Kullanim:
  python check_tickets.py           normal kontrol
  python check_tickets.py --test    Telegram baglantisini test et
  python check_tickets.py --dry-run mesaj atmadan sadece durumu yazdir
"""

import json
import os
import re
import sys
import time
from pathlib import Path

import requests


def load_dotenv(path=".env"):
    """Yerelde calistirirken .env varsa oku. GitHub Actions'ta .env yok --
    orada degerler Secrets'tan ortam degiskeni olarak gelir, bu fonksiyon
    sessizce hicbir sey yapmaz. Zaten tanimli degiskenlerin uzerine yazmaz."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_dotenv()

BASE = "https://tickets.tsg-hoffenheim.de"
SHOP_ID = 104

PERFORMANCE_ID = os.environ.get("PERFORMANCE_ID", "3188").strip()

# Varsayilan: 30.08.2026 itibariyla tukenmis olan ev sahibi bloklari.
# O-V = kale arkasi / ev sahibi tarafi (shop'un kendi notu: bu bloklara
# deplasman formasiyla giris yasak). A ve W deplasman bolgesi, 100/200/300'ler
# loca oldugu icin listede yok; J K L M N P'de zaten bilet var.
DEFAULT_BLOCKS = "B,C,D,E,F,G1,G2,H1,H2,I,O,Q,R,S1,S2,T,U,V"
WATCH_BLOCKS = [
    b.strip().upper()
    for b in os.environ.get("WATCH_BLOCKS", DEFAULT_BLOCKS).split(",")
    if b.strip()
]
STATE_FILE = Path(os.environ.get("STATE_FILE", "state.json"))

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

EVENT_URL = f"{BASE}/shops/{SHOP_ID}/events/{PERFORMANCE_ID}"

WAITING_ROOM_HOST = "waitingroom.ticketing.cloud.sap"


class WaitingRoom(Exception):
    """Shop yogun; SAP sanal bekleme odasina yonlendirildik."""


# ---------------------------------------------------------------- shop access

def parse_blockinfo(payload):
    """saalinterface JSON -> {blok adi: bos koltuk}.

    sitze_frei alani bazen string ("0"), bazen int (1) geliyor; ikisini de kabul et.
    Ayni ada sahip birden fazla kayit olabiliyor (ornegin farkli fiyat gruplari),
    bu durumda ayni blok adi icin bos koltuklari topluyoruz.
    """
    blocks = {}
    for entry in (payload.get("blockinfo") or {}).values():
        name = str(entry.get("bezeichnung", "")).strip()
        if not name:
            continue
        raw = entry.get("sitze_frei", 0)
        try:
            free = int(str(raw).strip() or 0)
        except (TypeError, ValueError):
            free = 0
        blocks[name] = blocks.get(name, 0) + max(free, 0)
    return blocks


def check_waiting_room(response):
    if WAITING_ROOM_HOST in response.url:
        raise WaitingRoom(
            "Shop yogun -- SAP bekleme odasina yonlendirildik, bu tur atlaniyor."
        )


def fetch_blocks(session):
    """Uc adimli akis: taze oturum -> mac sayfasi -> salon bilgisi."""
    # 1) Bos oturumla etkinlik listesini ac, sunucu bize taze bir "wes" versin.
    r1 = session.get(
        f"{BASE}/shop",
        params={
            "shopid": SHOP_ID,
            "wes": f"empty_session_{SHOP_ID}",
            "language": 1,
            "nextstate": 2,
        },
        timeout=30,
    )
    r1.raise_for_status()
    check_waiting_room(r1)
    m = re.search(r"wes=([0-9a-f]{6,}%d)\b" % SHOP_ID, r1.text)
    if not m:
        raise RuntimeError("Oturum (wes) alinamadi -- shop sayfasi degismis olabilir.")
    wes = m.group(1)

    # 2) Mac sayfasini ac; oturum "urun secimi" durumuna gecsin.
    r2 = session.get(EVENT_URL, params={"wes": wes}, timeout=30)
    r2.raise_for_status()
    check_waiting_room(r2)
    m2 = re.search(r'data-session-tab-id="([^"]+)"', r2.text)
    if m2:
        wes = m2.group(1)
    if f'data-performanceid="{PERFORMANCE_ID}"' not in r2.text:
        raise RuntimeError(
            f"Mac sayfasi acilmadi (performance {PERFORMANCE_ID}). "
            "Satis kapali veya ID degismis olabilir."
        )

    # 3) Salon bilgisi -- asil veri burada.
    r3 = session.get(
        f"{BASE}/backend/saalinterface",
        params={"wes": wes, "getSaalInfos": PERFORMANCE_ID, "abohouseid": ""},
        timeout=30,
    )
    r3.raise_for_status()
    payload = r3.json()
    if not payload.get("blockinfo"):
        raise RuntimeError(f"blockinfo bos geldi: {r3.text[:200]}")
    return parse_blockinfo(payload)


def fetch_blocks_with_retry(attempts=3):
    last = None
    for i in range(attempts):
        try:
            session = requests.Session()
            session.headers.update(
                {"User-Agent": USER_AGENT, "Accept-Language": "de-DE,de;q=0.9"}
            )
            return fetch_blocks(session)
        except WaitingRoom:
            raise
        except Exception as exc:  # noqa: BLE001
            last = exc
            if i < attempts - 1:
                time.sleep(3 * (i + 1))
    raise last


# ------------------------------------------------------------------- telegram

def send_telegram(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID tanimli degil.")
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=30,
    )
    if not r.ok:
        raise RuntimeError(f"Telegram hatasi {r.status_code}: {r.text[:300]}")


# ----------------------------------------------------------------------- main

def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def main():
    args = set(sys.argv[1:])

    if "--test" in args:
        send_telegram(
            "✅ <b>TSG bilet nöbetçisi kuruldu.</b>\n"
            f"İzlenen bloklar: {', '.join(WATCH_BLOCKS)}\n"
            f'<a href="{EVENT_URL}">Maç sayfası</a>'
        )
        print("Test mesaji gonderildi.")
        return 0

    try:
        blocks = fetch_blocks_with_retry()
    except WaitingRoom as wr:
        # Bekleme odasi = shop cok yogun. Durumu bozmadan bu turu atla,
        # bir sonraki calisma tekrar dener. Kirmizi hata sayilmaz.
        print(wr)
        return 0

    current = {b: blocks.get(b, 0) for b in WATCH_BLOCKS}
    print("Guncel durum:", ", ".join(f"{k}={v}" for k, v in current.items()))

    state = load_state()
    previous = state.get("blocks", {})

    # Sadece 0 -> >0 gecislerini bildir; blok dolu kaldigi surece susalim.
    newly_open = [b for b in WATCH_BLOCKS if current[b] > 0 and previous.get(b, 0) == 0]

    if newly_open and "--dry-run" not in args:
        lines = ["🎟️ <b>Yeni bilet çıktı!</b>", ""]
        for b in newly_open:
            lines.append(f"• Blok <b>{b}</b>: {current[b]} yer")
        # Cok blok izlenirken listeyi sisirmemek icin sadece dolu olanlari yaz.
        others = [
            f"{b}:{current[b]}"
            for b in WATCH_BLOCKS
            if b not in newly_open and current[b] > 0
        ]
        if others:
            lines.append("")
            lines.append("Ayrıca açık: " + ", ".join(others))
        lines.append("")
        lines.append(f'<a href="{EVENT_URL}">➡️ Hemen shop\'u aç</a>')
        send_telegram("\n".join(lines))
        print("Bildirim gonderildi:", newly_open)
    elif newly_open:
        print("[dry-run] Bildirim gonderilecekti:", newly_open)
    else:
        print("Yeni acilis yok.")

    if "--dry-run" not in args:
        save_state({"blocks": current, "checked_at": int(time.time())})

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"HATA: {exc}", file=sys.stderr)
        sys.exit(1)
