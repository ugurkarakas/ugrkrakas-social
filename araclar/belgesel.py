#!/usr/bin/env python3
"""@ugrkrakas belgesel tarzı Reels kurgusu (1080x1920, 30 fps).

Yazıyla anlatılan, ses tasarımı güçlü kısa belgesel: siyah ekranda soğuk açılış, serif bölüm
başlıkları, belgesel alt bandı (konum / rakım), sayaçla büyüyen rakamlar, daktilo altyazılar,
siyaha geçişler; altta rüzgar/ortam yatağı, whoosh / darbe / riser / tık / daktilo efektleri
(araclar/sesefekt.py, hepsi sentez) ve darbeden önce müziğin kesildiği sessizlik anları.

icerik/<slug>.json içinde:
  "belgesel": {
    "konum": "BAMYAN, AFGANİSTAN",          sol üst küçük konum (boş bırakılabilir)
    "renk": "film",                          reels.py renk derecelendirmesi
    "muzik": {"dosya": "muzik/x.mp3", "baslangic": 0, "ses": 0.8},   ya da null
             ya da sentez: {"sentez": "yumusak" | "khmer" | "parlak", "bpm": 84, "kok": 50, "ses": 0.8}  (araclar/belgesel_muzik.py)
    "efektler": "sade",                      yalnızca müzik + daktilo sesi (diğer efektler ve ortam kapalı)
    "ton": "parlak",                         efektleri umutlu/büyülü tona çevirir (varsayılan: "karanlik")
    "ortam": "ruzgar",                       ortam yatağı: "ruzgar" | null
    "kapanis": "Heykeller gitti. Hikayesi kaldı.",
    "kapanis_alt": "Kaydet. Bu hikayeyi bilen az.",
    "gecis_sesi": "ters_yanki",              geçiş sesi: "ters_yanki" (varsayılan) | "whoosh" | null
    "sahneler": [ ... ]
  }

Sahne alanları:
  siyah: true | video | foto        görüntü (siyah = boş siyah ekran)
  sure                              saniye
  baslangic, hiz (0.7 = yavaş), odak_x   video için;  odak [x, y] fotoğraf için
  yakinlas                          yavaş itme miktarı (varsayılan 0.06; 0 = sabit)
  gecis                             bu sahneye giriş: "kesme" | "erime" | "siyah" | "darbe" | "parlama"
                                    (parlama: yumuşak alt vuruş + büyülü pırıltı; olumlu, umutlu anlar için)
  sessizlik: true                   girişten hemen önce müzik kısılır (darbe öncesi boşluk)
  riser: true                       girişe 2 sn kala yükselen gerilim ("ton": "parlak" ise ters pırıltı)
  yazi                              (siyah sahnede) ortada serif italik cümle
  bolum / baslik                    "BÖLÜM I" + büyük serif başlık
  bant: ["Bamyan, Afganistan", "2.500 m"]   sol altta belgesel alt bandı
  sayac: {"deger": 55, "birim": "METRE", "ust": "BATI BUDA", "bas": 0.4}
  alt                               altyazı cümlesi;  "yazdir": true -> daktilo efektiyle
  alt_bas                           altyazının başlama saniyesi (sahne içinde)
  sfx: [{"ad": "darbe", "t": 1.2, "kazanc": 0.8}]   ek efektler (t sahne başına göre)

Kullanım:
  python3 araclar/belgesel.py icerik/<slug>.json [--cikis yol.mp4] [--taslak]
"""
import argparse
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reels  # noqa: E402
import sesefekt as sx  # noqa: E402
import uret  # noqa: E402
import belgesel_muzik  # noqa: E402

KOK = uret.KOK
W, H = 1080, 1920
FPS = 30
SR = sx.SR
KENAR = 96
GENIS = W - 2 * KENAR
BEYAZ = (255, 255, 255)


def buyuk(metin):
    """Türkçe büyük harf (i -> İ, ı -> I)."""
    return metin.replace("i", "İ").replace("ı", "I").upper()


def yumusak(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def cikis_egri(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


# ---------- görüntü kaynakları ----------

class Foto:
    def __init__(self, dosya, odak=(0.5, 0.5), yakinlas=0.06):
        self.z = yakinlas
        bw, bh = int(W * (1 + yakinlas)), int(H * (1 + yakinlas))
        img = ImageOps.exif_transpose(Image.open(KOK / "kaynak" / dosya)).convert("RGB")
        self.img = ImageOps.fit(img, (bw, bh), Image.LANCZOS, centering=tuple(odak))
        vf = ",".join(p for p in reels.RENK.split(",") if not p.startswith("noise"))
        out = subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{bw}x{bh}",
             "-i", "-", "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            input=self.img.tobytes(), capture_output=True, check=True).stdout
        self.img = Image.frombytes("RGB", (bw, bh), out)

    def kare(self, p):
        # Ken Burns: yavaşça içeri it
        olcek = 1 + self.z * (1 - p * 0.999)
        cw, ch = int(W * (1 + self.z) / olcek), int(H * (1 + self.z) / olcek)
        bw, bh = self.img.size
        x, y = (bw - cw) // 2, (bh - ch) // 2
        return self.img.crop((x, y, x + cw, y + ch)).resize((W, H), Image.BILINEAR)

    def kapat(self):
        pass


class Video:
    def __init__(self, dosya, bas, sure, hiz, odak_x, yakinlas):
        self.v = reels.VideoKaynak(dosya, bas, sure, hiz, odak_x)
        self.z = yakinlas

    def kare(self, p):
        img = self.v.kare(p)
        if self.z <= 0:
            return img
        olcek = 1 + self.z * p
        cw, ch = int(W / olcek), int(H / olcek)
        x, y = (W - cw) // 2, (H - ch) // 2
        return img.crop((x, y, x + cw, y + ch)).resize((W, H), Image.BILINEAR)

    def kapat(self):
        self.v.kapat()


class Siyah:
    def kare(self, p):
        return Image.new("RGB", (W, H), (0, 0, 0))

    def kapat(self):
        pass


# ---------- yazı "sprite"ları: (RGBA görüntü, x, y) ----------

def _sprite(katman, golge=0.7, yaricap=16, pay=40):
    kutu = katman.getbbox()
    if not kutu:
        return None
    x0, y0, x1, y1 = max(0, kutu[0] - pay), max(0, kutu[1] - pay), min(W, kutu[2] + pay), min(H, kutu[3] + pay)
    parca = katman.crop((x0, y0, x1, y1))
    if golge:
        a = parca.getchannel("A").filter(ImageFilter.GaussianBlur(yaricap)).point(lambda v: int(min(255, v * golge * 1.5)))
        g = Image.new("RGBA", parca.size, (0, 0, 0, 0))
        g.putalpha(a)
        g.alpha_composite(parca)
        parca = g
    return parca, x0, y0


def bos():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def aralikli(c, xy, metin, fnt, renk, ara, hiza="orta"):
    gen = sum(c.textlength(ch, font=fnt) for ch in metin) + ara * (len(metin) - 1)
    x, y = xy
    if hiza == "orta":
        x = (W - gen) / 2
    for ch in metin:
        c.text((x, y), ch, font=fnt, fill=renk)
        x += c.textlength(ch, font=fnt) + ara
    return gen


def baslik_sprite(baslik, bolum=None):
    k = bos()
    c = ImageDraw.Draw(k)
    y = int(H * 0.40)
    if bolum:
        f = uret.font(uret.ARA, 30)
        gen = aralikli(c, (0, y - 90), buyuk(bolum), f, BEYAZ + (230,), 9)
        orta = W / 2
        c.line((orta - gen / 2 - 90, y - 72, orta - gen / 2 - 26, y - 72), fill=BEYAZ + (200,), width=2)
        c.line((orta + gen / 2 + 26, y - 72, orta + gen / 2 + 90, y - 72), fill=BEYAZ + (200,), width=2)
    boyut = 168
    metin = buyuk(baslik)
    while boyut > 60:  # ekrana (kenar boşluklarıyla) sığana kadar küçült
        f = reels.serif(boyut, "Medium")
        gen = sum(c.textlength(ch, font=f) for ch in metin) + int(boyut * 0.12) * (len(metin) - 1)
        if gen <= GENIS:
            break
        boyut -= 6
    aralikli(c, (0, y), metin, reels.serif(boyut, "Medium"), BEYAZ + (250,), int(boyut * 0.12))
    return _sprite(k, 0.8, 22)


def bant_sprite(satirlar):
    k = bos()
    c = ImageDraw.Draw(k)
    x, y = KENAR, H - 820
    c.rectangle((x, y, x + 64, y + 4), fill=BEYAZ + (240,))
    y += 30
    if satirlar:
        aralikli(c, (x, y), buyuk(satirlar[0]), uret.font(uret.ARA, 40), BEYAZ + (250,), 6, hiza="sol")
        y += 62
    for s in satirlar[1:]:
        aralikli(c, (x, y), buyuk(s), uret.font(uret.KUCUK, 30), (235, 235, 235, 225), 5, hiza="sol")
        y += 46
    return _sprite(k, 1.0, 20)


def sayac_sprite(deger, birim, ust):
    k = bos()
    c = ImageDraw.Draw(k)
    y = int(H * 0.34)
    if ust:
        aralikli(c, (0, y - 60), buyuk(ust), uret.font(uret.ARA, 30), BEYAZ + (230,), 9)
    f = uret.font(uret.BASLIK, 260)
    s = f"{deger:,}".replace(",", ".")
    tw = c.textlength(s, font=f)
    c.text(((W - tw) / 2, y), s, font=f, fill=BEYAZ + (252,))
    if birim:
        aralikli(c, (0, y + 335), buyuk(birim), uret.font(uret.ARA, 40), BEYAZ + (240,), 14)
    return _sprite(k, 0.8, 22)


def ortali(metin, n, fnt, y, aralik, golge, yaricap):
    """Metni tam hâliyle satırlara böler ve ortalar; yalnızca ilk n harfi çizer (daktilo kaymadan yazar)."""
    k = bos()
    c = ImageDraw.Draw(k)
    sh = int(fnt.size * aralik)
    kalan = n
    for satir in uret.satirlar(metin, fnt, GENIS - 20):
        x = (W - c.textlength(satir, font=fnt)) / 2
        if kalan > 0:
            c.text((x, y), satir[:kalan], font=fnt, fill=BEYAZ + (255,))
        kalan -= len(satir) + 1
        y += sh
    return _sprite(k, golge, yaricap)


def satir_sayisi(metin, fnt):
    return len(uret.satirlar(metin, fnt, GENIS - 20))


def alt_sprite(metin, n=None):
    f = uret.font(uret.KUCUK, 46)
    return ortali(metin, len(metin) if n is None else n, f, H - 660, 1.3, 0.95, 12)


def yazi_sprite(metin, n=None):
    f = reels.serif(76, "Medium", True)
    yuk = satir_sayisi(metin, f) * int(f.size * 1.22)
    return ortali(metin, len(metin) if n is None else n, f, (H - yuk) // 2 - 40, 1.22, 0, 0)


def yapistir(img, sp, alfa=1.0, dx=0, dy=0, olcek=1.0):
    if sp is None or alfa <= 0:
        return
    parca, x, y = sp
    if olcek != 1.0:
        w, h = parca.size
        nw, nh = int(w * olcek), int(h * olcek)
        parca = parca.resize((nw, nh), Image.BILINEAR)
        x, y = x + (w - nw) // 2, y + (h - nh) // 2
    if alfa < 1:
        parca = parca.copy()
        parca.putalpha(parca.getchannel("A").point(lambda v: int(v * alfa)))
    img.alpha_composite(parca, (int(x + dx), int(y + dy)))


class Daktilo:
    """Harf harf beliren metin; her harf sayısı için sprite önbelleği."""
    def __init__(self, metin, yapici, hiz=24):
        self.metin, self.yapici, self.hiz, self.onbellek = metin, yapici, hiz, {}

    def sure(self):
        return len(self.metin) / self.hiz

    def sprite(self, t):
        n = min(len(self.metin), max(0, int(t * self.hiz) + 1)) if t >= 0 else 0
        if n == 0:
            return None
        if n not in self.onbellek:
            self.onbellek[n] = self.yapici(self.metin, n)
        return self.onbellek[n]

    def harf_zamanlari(self):
        return [i / self.hiz for i, ch in enumerate(self.metin) if not ch.isspace()]


# ---------- kurgu ----------

def kaynak_ac(s):
    z = s.get("yakinlas", 0.06)
    if s.get("siyah"):
        return Siyah()
    if s.get("video"):
        return Video(s["video"], s.get("baslangic", 0), s["sure"], s.get("hiz", 0.75), s.get("odak_x", 0.5), z)
    return Foto(s["foto"], s.get("odak", (0.5, 0.5)), z)


def kapanis_karesi(b):
    k = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    y = uret.yaz(k, (KENAR, H // 2 - 180), b.get("kapanis", ""), reels.serif(92, "Medium", True),
                 BEYAZ, GENIS, 1.15, hiza="orta") + 60
    uret.yaz(k, (KENAR, y), b.get("kapanis_alt", ""), uret.font(uret.GOVDE, 40), (170, 170, 175),
             GENIS, 1.4, hiza="orta")
    uret.harfli(k, (KENAR, H - 470), uret.HANDLE, uret.font(uret.ARA, 34), BEYAZ,
                aralik=0.04, hiza="orta", genislik=GENIS, buyuk=False)
    return k


def uret_belgesel(json_yolu, cikis=None, taslak=False):
    veri = json.loads(Path(json_yolu).read_text(encoding="utf-8"))
    b = veri["belgesel"]
    reels.RENK = reels.RENKLER[b.get("renk", "film")]
    isaret = reels.isaret_katmani(b.get("konum", ""))
    cikis = Path(cikis) if cikis else KOK / "reels" / f"{veri['slug']}.mp4"
    cikis.parent.mkdir(parents=True, exist_ok=True)
    sessiz = cikis.with_name(cikis.stem + "-sessiz.mp4")

    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "ultrafast" if taslak else "medium", "-crf", "18",
         "-maxrate", "11M", "-bufsize", "22M",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(sessiz)],
        stdin=subprocess.PIPE)

    parlak = b.get("ton") == "parlak"
    kok_nota = (b.get("muzik") or {}).get("kok", 50) if parlak else 45
    olaylar = []      # (zaman, efekt, kazanc)
    daktilo_olay = []  # yazı efektleri ayrı tutulur ("efektler": "sade" iken yalnızca bunlar çalar)
    sade = b.get("efektler") == "sade"
    sessizlikler = []  # müzik kısma anları
    sahneler = b["sahneler"]
    zaman = 0.0
    onceki = None

    for i, s in enumerate(sahneler):
        sure = s["sure"]
        n = int(round((zaman + sure) * FPS)) - int(round(zaman * FPS))
        gecis = s.get("gecis", "kesme" if i else "siyah")
        sonraki = sahneler[i + 1].get("gecis", "kesme") if i + 1 < len(sahneler) else "siyah"
        kaynak = kaynak_ac(s)

        # --- ses olayları ---
        gs = b.get("gecis_sesi", "ters_yanki")
        if gecis == "erime" and i and gs:
            if gs == "whoosh":
                olaylar.append((zaman - 0.45, sx.whoosh(0.9, i, 0.6), 0.35))
            else:
                olaylar.append((zaman + 0.05 - 1.2, sx.ters_yanki(1.2, i, kok_nota + 7 * (i % 2), 0.3), 0.16))
        if gecis == "siyah" and i and gs:
            if gs == "whoosh":
                olaylar.append((zaman - 0.5, sx.whoosh(1.0, i, 0.8), 0.45))
            else:
                olaylar.append((zaman - 1.6, sx.ters_yanki(1.7, i, kok_nota - 12, 0.45), 0.24))
                olaylar.append((zaman, sx.alcak_vurus(i), 0.3))
        if gecis == "darbe":
            olaylar.append((zaman, sx.darbe(3.2, i), 1.0))
        if gecis == "parlama":
            olaylar.append((zaman, sx.alcak_vurus(i, 0.8), 0.45))
            olaylar.append((zaman, sx.parilti(i, kok_nota + 24), 0.32))
        if s.get("riser"):
            if parlak:
                olaylar.append((zaman - 2.0, sx.ters_parilti(2.0, i, kok_nota + 24), 0.3))
            else:
                olaylar.append((zaman - 2.2, sx.riser(2.2, i), 0.55))
        if s.get("sessizlik"):
            sessizlikler.append(zaman)
        for e in s.get("sfx", []):
            ses = {"darbe": lambda: sx.darbe(3.2, 50 + i), "whoosh": lambda: sx.whoosh(0.9, 50 + i),
                   "riser": lambda: sx.riser(2.2, 50 + i), "nefes": lambda: sx.nefes(0.7, 50 + i),
                   "drone": lambda: sx.drone(sure, 50 + i)}[e["ad"]]()
            olaylar.append((zaman + e.get("t", 0), ses, e.get("kazanc", 0.7)))

        # --- yazı katmanları ---
        baslik = baslik_sprite(s["baslik"], s.get("bolum")) if s.get("baslik") else None
        if baslik:
            olaylar.append((zaman + 0.15, sx.nefes(0.8, i), 0.12))
        bant = bant_sprite(s["bant"]) if s.get("bant") else None
        yazi = Daktilo(s["yazi"], yazi_sprite, s.get("yazi_hiz", 20)) if s.get("yazi") else None
        yazi_bas = s.get("yazi_bas", 0.5)
        if yazi:
            for t in yazi.harf_zamanlari():
                daktilo_olay.append((zaman + yazi_bas + t, sx.daktilo(int(t * 1000) + i), 0.22))
        alt, alt_bas = None, s.get("alt_bas", 0.9 if (baslik or s.get("sayac")) else 0.35)
        if s.get("alt"):
            if s.get("yazdir"):
                alt = Daktilo(s["alt"], alt_sprite, 26)
                for t in alt.harf_zamanlari():
                    daktilo_olay.append((zaman + alt_bas + t, sx.daktilo(int(t * 1000) + 7 * i), 0.16))
            else:
                alt = alt_sprite(s["alt"])
        sayac = s.get("sayac")
        sayac_onb, son_deger = {}, -1
        if sayac:
            sb = sayac.get("bas", 0.3)
            if parlak:
                olaylar.append((zaman + sb + 1.3, sx.alcak_vurus(90 + i, 0.6), 0.3))
            else:
                olaylar.append((zaman + sb + 1.3, sx.darbe(2.4, 90 + i, 0.6), 0.45))

        for f in range(n):
            t = f / FPS
            p = f / max(1, n - 1)
            img = kaynak.kare(p)
            if not s.get("siyah"):
                img = reels.karart(img)
            img = img.convert("RGBA")
            if baslik:
                a = yumusak((t - 0.15) / 0.7)
                yapistir(img, baslik, a, olcek=1.0 + 0.035 * (1 - cikis_egri((t - 0.15) / 1.6)))
            if bant:
                a = cikis_egri((t - s.get("bant_bas", 0.5)) / 0.6)
                yapistir(img, bant, a, dx=-40 * (1 - a))
            if sayac:
                tt = (t - sayac.get("bas", 0.3)) / 1.3
                if tt >= 0:
                    d = int(round(sayac["deger"] * cikis_egri(tt)))
                    if d != son_deger:
                        if d not in sayac_onb:
                            sayac_onb[d] = sayac_sprite(d, sayac.get("birim", ""), sayac.get("ust", ""))
                        if tt < 1:
                            olaylar.append((zaman + t, sx.tik(d, 2600 + (d % 5) * 120), 0.18))
                        son_deger = d
                    yapistir(img, sayac_onb[d], yumusak(tt * 4))
            if yazi:
                yapistir(img, yazi.sprite(t - yazi_bas))
            if alt is not None:
                if isinstance(alt, Daktilo):
                    yapistir(img, alt.sprite(t - alt_bas))
                else:
                    yapistir(img, alt, yumusak((t - alt_bas) / 0.5))
            if not s.get("siyah"):
                img.alpha_composite(isaret)
            img = img.convert("RGB")

            # geçişler
            if gecis == "erime" and onceki is not None and t < 0.6:
                img = Image.blend(onceki, img, yumusak(t / 0.6))
            if gecis == "siyah" and t < 0.5:
                img = Image.blend(Image.new("RGB", (W, H)), img, yumusak(t / 0.5))
            if gecis in ("darbe", "parlama") and f < 4:
                img = Image.blend(img, Image.new("RGB", (W, H), (255, 255, 255)), 0.28 * (1 - f / 4))
            if sonraki == "siyah" and (n - f) <= 12:
                img = Image.blend(Image.new("RGB", (W, H)), img, yumusak((n - f - 1) / 12))
            ff.stdin.write(img.tobytes())
            onceki = img
        kaynak.kapat()
        zaman += sure

    # kapanış kartı
    kap = kapanis_karesi(b)
    kap_sure = 3.2
    if parlak:
        olaylar.append((zaman + 0.1, sx.parilti(99, kok_nota + 24), 0.25))
    else:
        olaylar.append((zaman + 0.1, sx.darbe(3.0, 99, 0.7), 0.5))
    for f in range(int(kap_sure * FPS)):
        img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        yapistir(img, (kap, 0, 0), yumusak(f / 18))
        ff.stdin.write(img.convert("RGB").tobytes())
    zaman += kap_sure
    ff.stdin.close()
    ff.wait()

    # ---------- ses miksajı ----------
    N = int(zaman * SR) + SR
    sfx_iz = np.zeros((N, 2))
    for t, ses, k in (daktilo_olay if sade else olaylar + daktilo_olay):
        sx.ekle(sfx_iz, ses, t, k)

    muzik_iz = np.zeros((N, 2))
    m = b.get("muzik")
    if m and m.get("sentez"):
        bolumler, tt = [], 0.0
        for s_ in sahneler:
            if s_.get("bolum"):
                bolumler.append(tt)
            tt += s_["sure"]
        uretici = {"yumusak": belgesel_muzik.yumusak, "khmer": belgesel_muzik.khmer}.get(m["sentez"], belgesel_muzik.uret)
        a = uretici(zaman, bolumler, m.get("bpm", 84), m.get("kok", 50), m.get("tohum", 7))
        muzik_iz[: len(a)] = a * m.get("ses", 0.8)
    elif m and m.get("dosya"):
        ham = subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-stream_loop", "-1", "-ss", str(m.get("baslangic", 0)),
             "-i", str(KOK / "kaynak" / m["dosya"]), "-t", str(zaman + 1), "-f", "f32le", "-ac", "2",
             "-ar", str(SR), "-"], capture_output=True, check=True).stdout
        a = np.frombuffer(ham, dtype=np.float32).reshape(-1, 2).astype(np.float64)
        muzik_iz[: min(N, len(a))] = a[:N] * m.get("ses", 0.8)
        # giriş: müzik soğuk açılıştan sonra yavaşça gelsin
        gir = int(m.get("giris", 0) * SR)
        if gir:
            muzik_iz[:gir] *= np.linspace(0, 1, gir)[:, None] ** 2
    zarf = np.ones(N)
    for t in sessizlikler:
        a0, a1 = int((t - 0.9) * SR), int((t - 0.15) * SR)
        b0, b1 = int((t + 0.6) * SR), int((t + 2.6) * SR)
        zarf[a0:a1] = np.minimum(zarf[a0:a1], np.linspace(1, 0.04, a1 - a0))
        zarf[a1:b0] = np.minimum(zarf[a1:b0], 0.04)
        zarf[b0:b1] = np.minimum(zarf[b0:b1], np.linspace(0.04, 1, b1 - b0))
    son = int((zaman - 2.6) * SR)
    zarf[son:] *= np.linspace(1, 0, N - son)
    muzik_iz *= zarf[:, None]

    ortam_iz = np.zeros((N, 2))
    if b.get("ortam") == "ruzgar" and not sade:
        ortam_iz = sx.ruzgar(N / SR, 11)[:N] * b.get("ortam_ses", 0.16)
        ortam_iz[son:] *= np.linspace(1, 0, N - son)[:, None]

    karisim = muzik_iz + sfx_iz + ortam_iz
    karisim = np.tanh(karisim * 0.9) / np.tanh(0.9)
    karisim = karisim[: int(zaman * SR)]
    wav = cikis.with_suffix(".wav")
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(karisim / (np.max(np.abs(karisim)) or 1) * 0.95, -1, 1) * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(sessiz), "-i", str(wav),
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000",
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
                    "-shortest", "-movflags", "+faststart", str(cikis)], check=True)
    sessiz.unlink()
    wav.unlink()
    print("  ", cikis, f"{zaman:.1f} sn")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("json")
    ap.add_argument("--cikis")
    ap.add_argument("--taslak", action="store_true")
    a = ap.parse_args()
    uret_belgesel(a.json, a.cikis, a.taslak)
