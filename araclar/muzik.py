#!/usr/bin/env python3
"""@ugrkrakas için telifsiz, kodla üretilen ritmik arka plan müziği.

Hiçbir örnek (sample) ya da hazır parça kullanılmaz; tüm sesler sentezlenir,
bu yüzden telif sorunu yoktur. Akor yürüyüşü, tempo ve tarz değiştirilebilir.

Tarzlar:
  yaz     116 BPM, hafif house: dört vuruşlu kick, clap, açık hi-hat, pompalayan akorlar
  aksam   96 BPM, lo-fi / chill: yumuşak kick, swing'li hi-hat, sıcak akorlar
  enerji  124 BPM, daha parlak ve hızlı, arpej ağırlıklı

Kullanım:
  python3 araclar/muzik.py <cikis.wav> <saniye> [tarz] [tohum]
"""
import sys
import wave

import numpy as np
from scipy.signal import butter, lfilter

SR = 44100

TARZLAR = {
    "yaz": {"bpm": 116, "akorlar": [(57, "m"), (53, "M"), (48, "M"), (55, "M")], "swing": 0.0, "arp": True},
    "aksam": {"bpm": 96, "akorlar": [(50, "m7"), (55, "7"), (48, "M7"), (57, "m7")], "swing": 0.12, "arp": False},
    "enerji": {"bpm": 124, "akorlar": [(54, "m"), (50, "M"), (45, "M"), (52, "M")], "swing": 0.0, "arp": True},
}
ARALIKLAR = {"m": [0, 3, 7], "M": [0, 4, 7], "m7": [0, 3, 7, 10], "7": [0, 4, 7, 10], "M7": [0, 4, 7, 11]}


def frek(nota):
    return 440.0 * 2 ** ((nota - 69) / 12)


def filtre(x, kesim, tur="low", derece=2):
    b, a = butter(derece, np.asarray(kesim) / (SR / 2), btype=tur)
    return lfilter(b, a, x)


def zarf(n, atak=0.005, sonum=0.3):
    t = np.arange(n) / SR
    z = np.exp(-t / sonum)
    a = int(atak * SR)
    if a > 0:
        z[:a] *= np.linspace(0, 1, a)
    return z


def testere(f, n, detune=0.0):
    t = np.arange(n) / SR
    x = np.zeros(n)
    for d in (-detune, 0.0, detune):
        x += 2 * ((t * f * (1 + d)) % 1.0) - 1
    return x / 3


def kick(n=int(0.35 * SR)):
    t = np.arange(n) / SR
    f = 48 + 110 * np.exp(-t * 28)
    faz = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(faz) * np.exp(-t * 7.5) * 1.0


def clap(rng, n=int(0.22 * SR)):
    g = rng.standard_normal(n)
    g = filtre(g, [900, 3500], "band")
    z = np.zeros(n)
    for o in (0, 0.012, 0.024):
        i = int(o * SR)
        z[i:] += np.exp(-np.arange(n - i) / SR / (0.05 if o == 0.024 else 0.008))
    return g * z * 0.55


def hat(rng, acik=False):
    n = int((0.18 if acik else 0.05) * SR)
    g = filtre(rng.standard_normal(n), 7000, "high")
    return g * zarf(n, 0.001, 0.06 if acik else 0.015) * (0.15 if acik else 0.12)


def yerlestir(iz, ses, bas):
    bas = int(bas)
    if bas >= len(iz):
        return
    son = min(len(iz), bas + len(ses))
    iz[bas:son] += ses[: son - bas]


def uret(saniye, tarz="yaz", tohum=7):
    s = TARZLAR[tarz]
    rng = np.random.default_rng(tohum)
    vurus = 60 / s["bpm"]
    olcu = 4 * vurus
    n = int(saniye * SR)
    davul = np.zeros(n)
    bas = np.zeros(n)
    akor = np.zeros(n)
    arp = np.zeros(n)
    pompa = np.ones(n)

    olcu_sayisi = int(np.ceil(saniye / olcu))
    for o in range(olcu_sayisi):
        kok, tip = s["akorlar"][o % len(s["akorlar"])]
        notalar = [kok + i for i in ARALIKLAR[tip]]
        t0 = o * olcu
        giris = o == 0  # ilk ölçü: davulsuz, sadece akor ve hi-hat

        # akor pad (tüm ölçü boyunca)
        m = int(olcu * SR)
        pad = sum(testere(frek(nt + 12), m, 0.004) for nt in notalar) / len(notalar)
        pad = filtre(pad, 1800 if tarz != "aksam" else 1200) * zarf(m, 0.04, olcu * 1.5)
        yerlestir(akor, pad * 0.35, t0 * SR)

        for v in range(4):
            tv = t0 + v * vurus
            if not giris:
                yerlestir(davul, kick(), tv * SR)
                # kick geldiğinde diğer sesleri hafifçe bastır (sidechain hissi)
                k = int(vurus * SR)
                b = int(tv * SR)
                if b < n:
                    e = min(n, b + k)
                    pompa[b:e] = np.minimum(pompa[b:e], 1 - 0.55 * np.exp(-np.arange(e - b) / SR / 0.09))
                if v in (1, 3):
                    yerlestir(davul, clap(rng), tv * SR)
                # bas: vuruş arası (offbeat) kök nota
                bn = int(vurus / 2 * SR)
                bsx = np.sin(2 * np.pi * frek(kok - 24) * np.arange(bn) / SR)
                bsx += 0.35 * testere(frek(kok - 24), bn)
                yerlestir(bas, filtre(bsx, 500) * zarf(bn, 0.004, 0.16) * 0.6, (tv + vurus / 2) * SR)
            # hi-hat: sekizlikler, swing ile
            yerlestir(davul, hat(rng), tv * SR)
            gecik = vurus / 2 + s["swing"] * vurus
            yerlestir(davul, hat(rng, acik=not giris), (tv + gecik) * SR)

            # arpej: on altılıklar, ikinci ölçüden itibaren
            if s["arp"] and o >= 1:
                for k16 in range(4):
                    nt = notalar[(v * 4 + k16) % len(notalar)] + 24
                    pn = int(vurus / 4 * SR)
                    p = np.sign(np.sin(2 * np.pi * frek(nt) * np.arange(pn) / SR)) * 0.5
                    p += np.sin(2 * np.pi * frek(nt) * np.arange(pn) / SR)
                    p = filtre(p, 3200) * zarf(pn, 0.002, 0.07) * 0.12
                    yerlestir(arp, p, (tv + k16 * vurus / 4) * SR)

    karisim = davul * 0.9 + (bas + akor * 0.8 + arp) * pompa
    # basit yankı (stereo genişlik için sağ/sol farklı gecikme)
    sol = karisim.copy()
    sag = karisim.copy()
    for g, d in ((int(0.19 * SR), 0.18), (int(0.27 * SR), 0.12)):
        sol[g:] += (akor * 0.8 + arp)[:-g] * pompa[:-g] * d
    for g, d in ((int(0.23 * SR), 0.18), (int(0.31 * SR), 0.12)):
        sag[g:] += (akor * 0.8 + arp)[:-g] * pompa[:-g] * d
    st = np.stack([sol, sag], axis=1)

    # giriş ve çıkış yumuşatma
    fi, fo = int(0.3 * SR), int(1.8 * SR)
    st[:fi] *= np.linspace(0, 1, fi)[:, None]
    st[-fo:] *= np.linspace(1, 0, fo)[:, None]
    st = np.tanh(st * 1.2)  # hafif sıkıştırma
    st *= 0.89 / np.max(np.abs(st))
    return st


def kaydet(st, yol):
    veri = (st * 32767).astype(np.int16)
    with wave.open(str(yol), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(veri.tobytes())


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    tarz = sys.argv[3] if len(sys.argv) > 3 else "yaz"
    tohum = int(sys.argv[4]) if len(sys.argv) > 4 else 7
    kaydet(uret(float(sys.argv[2]), tarz, tohum), sys.argv[1])
    print("  ", sys.argv[1])
