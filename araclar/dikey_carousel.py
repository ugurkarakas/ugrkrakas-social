#!/usr/bin/env python3
"""Carousel slaytlarını 9:16 (1080x1920) üretir: uygulamadan fotoğraflı reels olarak paylaşmak için.

  python3 araclar/dikey_carousel.py icerik/<slug>.json   ->  carousel-dikey/<slug>/01.jpg ...
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import uret  # noqa: E402

uret.POST = uret.STORY  # tüm slayt düzenleri boyutu POST sabitinden alıyor

for yol in sys.argv[1:]:
    veri = json.loads(Path(yol).read_text(encoding="utf-8"))
    slug, sl = veri["slug"], veri["slaytlar"]
    hedef = uret.KOK / "carousel-dikey" / slug
    toplam = len(sl) + 2
    uret.kaydet(uret.kapak(veri), hedef / "01.jpg")
    for i, s in enumerate(sl, start=1):
        uret.kaydet(uret.icerik_slayti(s, i, toplam, veri.get("konum", "")), hedef / f"{i + 1:02d}.jpg")
    uret.kaydet(uret.kapanis_slayti(veri), hedef / f"{toplam:02d}.jpg")
    print(hedef.relative_to(uret.KOK))
