#!/usr/bin/env python3
"""@ugrkrakas Reels üreticisi.

icerik/<slug>.json içindeki "reels.sahneler" listesinden 1080x1920, 30 fps MP4 üretir.
Her sahne bir fotoğraf ya da bir video klip olabilir; üstüne konuşur gibi yazılmış,
kısa altyazı tarzı metinler gelir. Sonda siyah bir "kaydet / takip et" kartı vardır.

  "reels": {
    "sahneler": [
      {"video": "roma-sokak.mp4", "baslangic": 2.0, "sure": 3.0,
       "metin": "Roma'ya gidiyorsan bunu kaydet"},
      {"foto": "roma-merdiven.jpg", "etiket": "Kural 1",
       "metin": "Güne erken başla", "alt": "Sabah 8'den önce merdivenler neredeyse boş."}
    ]
  }

Alanlar:
  foto / video   kaynak/ altındaki dosya (biri zorunlu)
  baslangic      video klipte kaçıncı saniyeden alınacağı (varsayılan 0)
  sure           sahne süresi, saniye (varsayılan: alt metin varsa 3.6, yoksa 2.8)
  fotolar        birden fazla fotoğraf: vuruşa denk gelen hızlı kesmelerle art arda gösterilir
                 (her biri "dosya.jpg" ya da {"foto": "dosya.jpg", "odak": [x, y]})
  vurus_basina   çok fotoğraflı sahnede her fotoğrafın kaç vuruş kalacağı (varsayılan 2)
  etiket         küçük üst yazı (Kural 1, 02 gibi)
  metin          ana cümle
  alt            ana cümlenin altında beliren detay cümlesi

  odak          fotoğrafın dikey kırpımda nereden ortalanacağı, ör. [0.4, 0.5]

Müzik: araclar/muzik.py ile kodla üretilen telifsiz ritim eklenir.
  "muzik": {"tarz": "yaz" | "aksam" | "enerji", "tohum": 7}   kapatmak için "muzik": null
  Hazır telifsiz parça (Pixabay Music vb.), kaynak/ altında:
  "muzik": {"dosya": "muzik/sitar-story.mp3", "bpm": 100, "baslangic": 0, "ses": 1.0}
  Parça videodan kısaysa başa sarılır; sonda 1.5 sn'de kısılır. Kredi caption'a yazılır.

Kullanım:
  python3 araclar/reels.py icerik/<slug>.json
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
import muzik  # noqa: E402
import uret  # noqa: E402

KOK = uret.KOK
W, H = uret.STORY
FPS = 30
GECIS = 0.35
YAKINLASMA = 0.06
KENAR = 96
GENISLIK = W - 2 * KENAR


def yumusak(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# ---------- görüntü kaynakları ----------

class FotoKaynak:
    def __init__(self, dosya, odak=(0.5, 0.5)):
        bw, bh = int(W * (1 + YAKINLASMA)), int(H * (1 + YAKINLASMA))
        img = ImageOps.exif_transpose(Image.open(KOK / "kaynak" / dosya)).convert("RGB")
        self.img = ImageOps.fit(img, (bw, bh), Image.LANCZOS, centering=tuple(odak))

    def kare(self, ilerleme):
        # kesmeden sonra hızlı, sonra yavaşlayan bir yakınlaşma hissi
        e = 1 - (1 - ilerleme) ** 2.2
        olcek = 1 + YAKINLASMA * (1 - e)
        cw, ch = int(W * olcek), int(H * olcek)
        bw, bh = self.img.size
        x, y = (bw - cw) // 2, (bh - ch) // 2
        return self.img.crop((x, y, x + cw, y + ch)).resize((W, H), Image.BILINEAR)

    def kapat(self):
        pass


RENKLER = {
    # varsayılan: canlı ve net
    None: "eq=contrast=1.06:saturation=1.12,unsharp=5:5:0.6",
    # film: sıcak, hafif soluk, yumuşak kontrast, ince vinyet ve gren (belgesel / Apple havası)
    "film": ("eq=contrast=1.03:saturation=0.86:gamma=1.03:brightness=0.01,"
             "colorbalance=rs=0.05:bs=-0.05:rm=0.03:bm=-0.03:rh=0.02:bh=-0.03,"
             "curves=all='0/0.03 0.5/0.5 1/0.97',vignette=angle=PI/6,"
             "unsharp=5:5:0.4,noise=alls=3:allf=t"),
}
RENK = RENKLER[None]


class VideoKaynak:
    """Video klip: dikey kadraja kırpılır, istenirse yavaşlatılır (sinematik), hafif renk derecelendirmesi."""
    def __init__(self, dosya, baslangic, sure, hiz=1.0, odak_x=0.5):
        vf = (f"setpts=PTS/{hiz},scale={W}:{H}:force_original_aspect_ratio=increase,"
              f"crop={W}:{H}:(iw-{W})*{odak_x}:(ih-{H})/2,fps={FPS},"
              + RENK)
        self.p = subprocess.Popen(
            ["ffmpeg", "-loglevel", "error", "-ss", str(baslangic), "-t", str(sure * hiz + 0.5),
             "-i", str(KOK / "kaynak" / dosya), "-vf", vf, "-an",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            stdout=subprocess.PIPE,
        )
        self.son = None

    def kare(self, ilerleme):
        veri = self.p.stdout.read(W * H * 3)
        if len(veri) == W * H * 3:
            self.son = Image.frombytes("RGB", (W, H), veri)
        return self.son if self.son is not None else Image.new("RGB", (W, H))

    def kapat(self):
        self.p.kill()
        self.p.wait()
        self.p.stdout.close()


# ---------- yazı katmanları ----------

def _maske():
    m = Image.new("L", (1, H), 0)
    for y in range(H):
        t = y / H
        a = max(0.35 * max(0.0, 1 - t / 0.28) ** 1.6, 0.8 * max(0.0, (t - 0.42) / 0.58) ** 1.5)
        m.putpixel((0, y), int(255 * a))
    return m.resize((W, H))


MASKE = _maske()
SIYAH = Image.new("RGB", (W, H), (0, 0, 0))


def karart(img):
    """Fotoğraf/videonun alt ve üstünü yazı okunacak kadar koyulaştırır."""
    return Image.composite(SIYAH, img, MASKE)


def altyazi_kutusu(metin, fnt, y, katman):
    """Instagram'ın kendi altyazı stilini andıran, yarı saydam yumuşak kutulu metin."""
    c = ImageDraw.Draw(katman)
    sh = int(fnt.size * 1.32)
    for s in uret.satirlar(metin, fnt, GENISLIK - 60):
        tw = c.textlength(s, font=fnt)
        x = (W - tw) / 2
        c.rounded_rectangle((x - 26, y - 12, x + tw + 26, y + sh - 2), radius=18, fill=(0, 0, 0, 125))
        c.text((x, y), s, font=fnt, fill=(255, 255, 255, 255))
        y += sh + 6
    return y


def sahne_katmanlari(sahne, ilk):
    """(ana metin katmanı, detay metin katmanı) döndürür."""
    ana = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    alt = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    etiket_f = uret.font(uret.ARA, 30)
    if ilk:
        # İlk sahne: büyük, net bir giriş cümlesi (hook) ekranın üst kısmında
        y = 380
        if sahne.get("etiket"):
            uret.harfli(ana, (KENAR, y - 80), sahne["etiket"], etiket_f, uret.BEYAZ,
                        seffaflik=230, hiza="orta", genislik=GENISLIK)
        uret.yaz(ana, (KENAR, y), sahne["metin"], uret.font(uret.BASLIK, 108), uret.BEYAZ,
                 GENISLIK, 1.08, hiza="orta")
        if sahne.get("alt"):
            altyazi_kutusu(sahne["alt"], uret.font(uret.KUCUK, 42), H - 640, alt)
        return ana, alt

    bf = uret.font(uret.BASLIK, 78)
    af = uret.font(uret.KUCUK, 42)
    bh = uret.blok_yuksekligi(sahne["metin"], bf, GENISLIK, 1.1)
    ah = len(uret.satirlar(sahne.get("alt", ""), af, GENISLIK - 60)) * (int(af.size * 1.32) + 6)
    y = H - 520 - ah - (40 if ah else 0) - bh
    if sahne.get("etiket"):
        uret.harfli(ana, (KENAR, y - 70), sahne["etiket"], etiket_f, uret.BEYAZ,
                    seffaflik=235, hiza="orta", genislik=GENISLIK)
    y = uret.yaz(ana, (KENAR, y), sahne["metin"], bf, uret.BEYAZ, GENISLIK, 1.1, hiza="orta") + 40
    if sahne.get("alt"):
        altyazi_kutusu(sahne["alt"], af, y, alt)
    return ana, alt


def golgeli(katman, guc=0.6, yaricap=18):
    """Yazının arkasına yumuşak bir gölge ekler; açık renkli fotoğraflarda okunurluğu korur."""
    a = katman.getchannel("A").filter(ImageFilter.GaussianBlur(yaricap)).point(lambda v: int(min(255, v * guc * 1.6)))
    golge = Image.new("RGBA", katman.size, (0, 0, 0, 0))
    golge.putalpha(a)
    golge.alpha_composite(katman)
    return golge


def alfali(katman, alfa):
    if alfa >= 1:
        return katman
    k = katman.copy()
    k.putalpha(katman.getchannel("A").point(lambda v: int(v * alfa)))
    return k


def isaret_katmani():
    """Sağ üstte sabit @ugrkrakas imzası (kapanış kartı hariç tüm karelerde)."""
    k = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    c = ImageDraw.Draw(k)
    f = uret.font(uret.KUCUK, 34)
    hw = c.textlength(uret.HANDLE, font=f)
    c.text((W - KENAR + 36 - hw, 150), uret.HANDLE, font=f, fill=uret.BEYAZ + (225,))
    return golgeli(k, guc=0.5, yaricap=10)


ISARET = None


def kapanis(veri):
    r = veri.get("reels", {})
    k = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    cta = r.get("kapanis", veri.get("cta", "Kaydet, gidince aç."))
    bf = uret.font(uret.BASLIK, 96)
    bh = uret.blok_yuksekligi(cta, bf, GENISLIK, 1.08)
    y = (H - bh) // 2 - 80
    y = uret.yaz(k, (KENAR, y), cta, bf, uret.BEYAZ, GENISLIK, 1.08, hiza="orta") + 40
    uret.yaz(k, (KENAR, y), r.get("kapanis_alt", "Daha fazla rota için takip et."),
             uret.font(uret.GOVDE, 42), (161, 161, 166), GENISLIK, 1.4, hiza="orta")
    uret.harfli(k, (KENAR, H - 460), uret.HANDLE, uret.font(uret.ARA, 34), uret.BEYAZ,
                aralik=0.04, hiza="orta", genislik=GENISLIK, buyuk=False)
    return k.convert("RGB")


# ---------- üretim ----------

def sahneleri_al(veri):
    r = veri.get("reels") or {}
    if r.get("sahneler"):
        return r["sahneler"]
    sahneler = [{"foto": veri["foto"], "metin": veri["baslik"], "alt": veri.get("alt_baslik", "")}]
    for i, s in enumerate(veri.get("slaytlar", []), start=1):
        if s.get("foto"):
            sahneler.append({"foto": s["foto"], "etiket": f"{i:02d}", "metin": s["baslik"], "alt": s["metin"]})
    return sahneler


def uret_reels(json_yolu):
    global ISARET, RENK
    if ISARET is None:
        ISARET = isaret_katmani()
    veri = json.loads(Path(json_yolu).read_text(encoding="utf-8"))
    RENK = RENKLER[veri.get("reels", {}).get("renk")]
    sahneler = sahneleri_al(veri)
    cikis = KOK / "reels" / f"{veri['slug']}.mp4"
    cikis.parent.mkdir(exist_ok=True)

    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", str(cikis)],
        stdin=subprocess.PIPE,
    )
    ayar = veri.get("reels", {}).get("muzik", {"tarz": "tropik", "tohum": 7})
    if ayar and ayar.get("dosya"):
        # Hazır, telifsiz parça (ör. Pixabay Music): kesmeler parçanın bpm'ine oturur
        _tarz = {"bpm": ayar.get("bpm", 100), "kesim": ayar.get("kesim", 1)}
    else:
        _tarz = muzik.TARZLAR[(ayar or {}).get("tarz", "tropik")]
    vurus = 60 / _tarz["bpm"] * _tarz.get("kesim", 1)  # kesim: hızlı tempolarda (vals) kesmeleri seyrelt
    g = int(GECIS * FPS)
    onceki = None
    zaman = 0.0  # kesmeleri vuruşa oturtmak için birikimli süre

    for idx, s in enumerate(sahneler):
        if s.get("fotolar"):
            # Çok fotoğraflı sahne: her fotoğraf "vurus_basina" vuruş sürer, kesmeler vuruşa denk gelir
            vb = s.get("vurus_basina", 2)
            ana, alt = sahne_katmanlari(s, idx == 0)
            ana = golgeli(ana)
            sahne_kare = 0
            for fi, foto in enumerate(s["fotolar"]):
                ovb = foto.get("vurus", vb) if isinstance(foto, dict) else vb
                bitis = zaman + ovb * vurus
                if isinstance(foto, dict) and foto.get("video"):
                    kaynak = VideoKaynak(foto["video"], foto.get("baslangic", 0), bitis - zaman,
                                         foto.get("hiz", 0.8), foto.get("odak_x", 0.5))
                else:
                    dosya, odak = (foto, (0.5, 0.5)) if isinstance(foto, str) else (foto["foto"], foto.get("odak", (0.5, 0.5)))
                    kaynak = FotoKaynak(dosya, odak)
                n = int(round(bitis * FPS)) - int(round(zaman * FPS))
                for f in range(n):
                    img = karart(kaynak.kare(f / max(1, n - 1))).convert("RGBA")
                    a1 = yumusak((sahne_kare - 3) / 7)
                    a2 = yumusak((sahne_kare - 18) / 8)
                    if a1 > 0:
                        img.alpha_composite(alfali(ana, a1))
                    if a2 > 0:
                        img.alpha_composite(alfali(alt, a2))
                    img.alpha_composite(ISARET)
                    img = img.convert("RGB")
                    onceki = img
                    ff.stdin.write(img.tobytes())
                    sahne_kare += 1
                kaynak.kapat()
                zaman = bitis
            continue

        sure = s.get("sure", 3.6 if s.get("alt") else 2.8)
        sure = max(1, round(sure / vurus)) * vurus  # süreyi vuruşa yuvarla
        n = int(round((zaman + sure) * FPS)) - int(round(zaman * FPS))
        zaman += sure
        if s.get("video"):
            kaynak = VideoKaynak(s["video"], s.get("baslangic", 0), sure, s.get("hiz", 0.8), s.get("odak_x", 0.5))
        else:
            kaynak = FotoKaynak(s["foto"], s.get("odak", (0.5, 0.5)))
        ana, alt = sahne_katmanlari(s, idx == 0)
        ana = golgeli(ana)
        for f in range(n):
            img = karart(kaynak.kare(f / max(1, n - 1))).convert("RGBA")
            a1 = yumusak((f - 4) / 9)
            a2 = yumusak((f - 22) / 9)  # detay cümlesi ~0.7 sn sonra gelir
            if a1 > 0:
                img.alpha_composite(alfali(ana, a1))
            if a2 > 0:
                img.alpha_composite(alfali(alt, a2))
            img.alpha_composite(ISARET)
            img = img.convert("RGB")
            if onceki is not None and f < g:
                img = Image.blend(onceki, img, yumusak(f / g))
            if f == n - 1:
                onceki = img
            ff.stdin.write(img.tobytes())
        kaynak.kapat()

    son = kapanis(veri)
    for f in range(int(round(4 * vurus * FPS))):
        ff.stdin.write(son.tobytes())

    ff.stdin.close()
    ff.wait()

    if ayar and ayar.get("dosya"):
        sure = float(subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(cikis)]))
        parca = KOK / "kaynak" / ayar["dosya"]
        bas = float(ayar.get("baslangic", 0))
        sonmak = max(sure - 1.5, 0)
        gecici = cikis.with_name(cikis.stem + "-sessiz.mp4")
        cikis.rename(gecici)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(gecici),
                        "-stream_loop", "-1", "-ss", str(bas), "-i", str(parca),
                        "-filter_complex",
                        f"[1:a]volume={ayar.get('ses', 1.0)},afade=t=in:d=0.3,"
                        f"afade=t=out:st={sonmak}:d=1.5,atrim=0:{sure}[a]",
                        "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                        "-shortest", "-movflags", "+faststart", str(cikis)], check=True)
        gecici.unlink()
    elif ayar:
        sure = float(subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(cikis)]))
        wav = cikis.with_suffix(".wav")
        muzik.kaydet(muzik.uret(sure, ayar.get("tarz", "tropik"), ayar.get("tohum", 7)), wav)
        gecici = cikis.with_name(cikis.stem + "-sessiz.mp4")
        cikis.rename(gecici)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(gecici), "-i", str(wav),
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                        "-movflags", "+faststart", str(cikis)], check=True)
        gecici.unlink()
        wav.unlink()
    print("  ", cikis.relative_to(KOK))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    for d in sys.argv[1:]:
        uret_reels(d)
