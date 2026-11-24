#!/usr/bin/env python3
"""Carousel slaytlarının 9:16 (1080x1920) hali: uygulamadan fotoğraflı reels olarak paylaşmak için.

Dikey ekranda fotoğraflar aşırı uzamasın diye fotoğraf alanı sabit tutulur, altına
"detay" maddeleri (nerede, ne zaman, ipucu) gelir. Alt ~350 px, Instagram'ın reels
arayüzü (açıklama, düğmeler) için boş bırakılır.

  python3 araclar/dikey_carousel.py icerik/<slug>.json   ->  carousel-dikey/<slug>/01.jpg ...
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
import uret  # noqa: E402
from uret import (BASLIK, BEYAZ, GOVDE, IKINCIL, KOK, METIN, ZEMIN, birlestir, blok_yuksekligi,  # noqa: E402
                  doldur, font, karartma, ust_yazi, yaz, yuvarlak_yapistir)

W, H = 1080, 1920
KENAR = 84
GEN = W - 2 * KENAR
FOTO_H = 760
ALT_BOS = 360  # reels arayüzü


def _foto(ad, boyut):
    if isinstance(ad, dict):
        return doldur(KOK / "kaynak" / ad["foto"], boyut, tuple(ad.get("odak", (0.5, 0.5))))
    return doldur(KOK / "kaynak" / ad, boyut)


def kapak(veri):
    img = karartma(doldur(KOK / "kaynak" / veri["foto"], (W, H), (0.5, 0.45)), ust=0.4, alt=0.75)
    k = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ust_yazi(k, W, KENAR, 140, veri.get("konum", ""), BEYAZ)
    bf, af = font(BASLIK, 104), font(GOVDE, 40)
    bh = blok_yuksekligi(veri["baslik"], bf, GEN, 1.08)
    ah = blok_yuksekligi(veri.get("alt_baslik", ""), af, GEN, 1.35) if veri.get("alt_baslik") else 0
    y = H - ALT_BOS - 40 - ah - 30 - bh
    y = yaz(k, (KENAR, y), veri["baslik"], bf, BEYAZ, GEN, 1.08) + 30
    if ah:
        yaz(k, (KENAR, y), veri["alt_baslik"], af, BEYAZ, GEN, 1.35, seffaflik=215)
    return birlestir(img, k)


def detay_karti(k, img, y, maddeler):
    """Beyaz yuvarlak kart içinde madde işaretli detaylar."""
    f = font(GOVDE, 36)
    satir_h = []
    for m in maddeler:
        satir_h.append(blok_yuksekligi(m, f, GEN - 120, 1.35))
    ic = 48
    kart_h = ic * 2 + sum(satir_h) + 26 * (len(maddeler) - 1)
    ImageDraw.Draw(img).rounded_rectangle((KENAR, y, W - KENAR, y + kart_h), radius=36, fill=BEYAZ)
    c = ImageDraw.Draw(k)
    yy = y + ic
    for m, sh in zip(maddeler, satir_h):
        c.ellipse((KENAR + 48, yy + 17, KENAR + 60, yy + 29), fill=METIN + (255,))
        yaz(k, (KENAR + 84, yy), m, f, METIN, GEN - 120, 1.35)
        yy += sh + 26
    return y + kart_h


def icerik(slayt, sira, konum):
    img = Image.new("RGB", (W, H), ZEMIN)
    k = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ust_yazi(k, W, KENAR, 140, f"{sira:02d}  ·  {konum}" if konum else f"{sira:02d}", IKINCIL, 255)
    y = 230
    y = yaz(k, (KENAR, y), slayt["baslik"], font(BASLIK, 72), METIN, GEN, 1.1) + 24
    y = yaz(k, (KENAR, y), slayt["metin"], font(GOVDE, 36), IKINCIL, GEN, 1.42) + 44
    fotolar = slayt.get("fotolar") or ([slayt["foto"]] if slayt.get("foto") else [])
    fh = min(FOTO_H, H - ALT_BOS - y - (380 if slayt.get("detay") else 40))
    ara = 16
    if len(fotolar) >= 3:
        sol = int((GEN - ara) * 0.6)
        sag = GEN - ara - sol
        kh = (fh - ara) // 2
        yuvarlak_yapistir(img, _foto(fotolar[0], (sol, fh)), (KENAR, y))
        yuvarlak_yapistir(img, _foto(fotolar[1], (sag, kh)), (KENAR + sol + ara, y))
        yuvarlak_yapistir(img, _foto(fotolar[2], (sag, fh - kh - ara)), (KENAR + sol + ara, y + kh + ara))
    elif len(fotolar) == 2:
        yarim = (GEN - ara) // 2
        for i, f in enumerate(fotolar):
            yuvarlak_yapistir(img, _foto(f, (yarim, fh)), (KENAR + i * (yarim + ara), y))
    elif len(fotolar) == 1:
        yuvarlak_yapistir(img, _foto(fotolar[0], (GEN, fh)), (KENAR, y), r=36)
    if fotolar:
        y += fh + 40
    if slayt.get("detay"):
        detay_karti(k, img, y, slayt["detay"])
    return birlestir(img, k)


def kapanis(veri):
    img = Image.new("RGB", (W, H), (0, 0, 0))
    k = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bf, gf = font(BASLIK, 96), font(GOVDE, 40)
    cta = veri.get("cta", "Kaydet, gidince aç.")
    alt = veri.get("cta_alt", "Daha fazla rota ve durak için takip et.")
    bh, gh = blok_yuksekligi(cta, bf, GEN, 1.08), blok_yuksekligi(alt, gf, GEN, 1.4)
    y = (H - ALT_BOS - bh - 32 - gh) // 2 + 60
    y = yaz(k, (KENAR, y), cta, bf, BEYAZ, GEN, 1.08, hiza="orta") + 32
    yaz(k, (KENAR, y), alt, gf, (161, 161, 166), GEN, 1.4, hiza="orta")
    uret.harfli(k, (KENAR, y + gh + 80), uret.HANDLE, font(uret.ARA, 32), BEYAZ, aralik=0.04,
                hiza="orta", genislik=GEN, buyuk=False)
    return birlestir(img, k)


for yol in sys.argv[1:]:
    veri = json.loads(Path(yol).read_text(encoding="utf-8"))
    slug, sl = veri["slug"], veri["slaytlar"]
    hedef = KOK / "carousel-dikey" / slug
    for eski in hedef.glob("*.jpg"):
        eski.unlink()
    toplam = len(sl) + 2
    uret.kaydet(kapak(veri), hedef / "01.jpg")
    for i, s in enumerate(sl, start=1):
        uret.kaydet(icerik(s, i, veri.get("konum", "")), hedef / f"{i + 1:02d}.jpg")
    uret.kaydet(kapanis(veri), hedef / f"{toplam:02d}.jpg")
