#!/usr/bin/env python3
"""@ugrkrakas için telifsiz, kodla üretilen ritmik arka plan müziği.

Hiçbir örnek (sample) ya da hazır parça kullanılmaz; tüm sesler sentezlenir,
bu yüzden telif sorunu yoktur.

Tarzlar:
  tropik  118 BPM tropical house: marimba melodisi, senkoplu bas, piyano vuruşları, shaker (varsayılan)
  yaz     116 BPM hafif house: dört vuruşlu kick, clap, pompalayan akorlar
  aksam   96 BPM lo-fi / chill: yumuşak, swing'li, sıcak akorlar
  enerji  124 BPM daha parlak ve hızlı

Kullanım:
  python3 araclar/muzik.py <cikis.wav> <saniye> [tarz] [tohum]
"""
import sys
import wave

import numpy as np
from scipy.signal import butter, fftconvolve, lfilter

SR = 44100

TARZLAR = {
    "tropik": {"bpm": 118},
    "yaz": {"bpm": 116, "akorlar": [(57, "m"), (53, "M"), (48, "M"), (55, "M")], "swing": 0.0, "arp": True},
    "aksam": {"bpm": 96, "akorlar": [(50, "m7"), (55, "7"), (48, "M7"), (57, "m7")], "swing": 0.12, "arp": False},
    "enerji": {"bpm": 124, "akorlar": [(54, "m"), (50, "M"), (45, "M"), (52, "M")], "swing": 0.0, "arp": True},
}
ARALIKLAR = {"m": [0, 3, 7], "M": [0, 4, 7], "m7": [0, 3, 7, 10], "7": [0, 4, 7, 10], "M7": [0, 4, 7, 11],
             "add9": [0, 4, 7, 14], "m9": [0, 3, 7, 10, 14]}


# ---------- yardımcılar ----------

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


def yerlestir(iz, ses, bas):
    bas = int(bas)
    if bas >= len(iz) or bas < 0:
        return
    son = min(len(iz), bas + len(ses))
    iz[bas:son] += ses[: son - bas]


def yanki_ir(sure, rng):
    n = int(sure * SR)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / SR / (sure / 5))
    ir = filtre(ir, 5000)
    ir[0] = 0
    return ir / np.sqrt(np.sum(ir ** 2))


def yanki(x, ir, oran):
    return x + oran * fftconvolve(x, ir)[: len(x)]


# ---------- enstrümanlar ----------

def kick(guc=1.0):
    n = int(0.32 * SR)
    t = np.arange(n) / SR
    f = 50 + 120 * np.exp(-t * 32)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 8)
    x[: int(0.003 * SR)] += 0.3  # tık sesi
    return x * guc


def clap(rng):
    n = int(0.25 * SR)
    g = filtre(rng.standard_normal(n), [1000, 4000], "band")
    z = np.zeros(n)
    for o in (0, 0.01, 0.021):
        i = int(o * SR)
        z[i:] += np.exp(-np.arange(n - i) / SR / (0.07 if o == 0.021 else 0.006))
    return g * z * 0.5


def shaker(rng, guc):
    n = int(0.07 * SR)
    g = filtre(rng.standard_normal(n), 6500, "high")
    z = np.minimum(1, np.arange(n) / (0.012 * SR)) * np.exp(-np.arange(n) / SR / 0.025)
    return g * z * guc


def acik_hat(rng):
    n = int(0.2 * SR)
    return filtre(rng.standard_normal(n), 8000, "high") * zarf(n, 0.001, 0.07) * 0.1


def marimba(nota, sure=0.35, guc=0.25):
    n = int(sure * SR)
    t = np.arange(n) / SR
    f = frek(nota)
    x = np.sin(2 * np.pi * f * t) * np.exp(-t * 9)
    x += 0.35 * np.sin(2 * np.pi * f * 4 * t) * np.exp(-t * 30)
    x += 0.12 * np.sin(2 * np.pi * f * 9.2 * t) * np.exp(-t * 60)
    a = int(0.002 * SR)
    x[:a] *= np.linspace(0, 1, a)
    return x * guc


def piyano_vurus(notalar, sure=0.22, guc=0.16):
    """Kısa, parlak house piyanosu akor vuruşu."""
    n = int(sure * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for nt in notalar:
        f = frek(nt)
        for h, a in ((1, 1.0), (2, 0.5), (3, 0.25), (4, 0.12)):
            x += a * np.sin(2 * np.pi * f * h * t) * np.exp(-t * (6 + 4 * h))
    x /= len(notalar)
    return filtre(x, 4500) * guc


def pad(notalar, n, guc=0.12):
    x = sum(testere(frek(nt), n, 0.005) for nt in notalar) / len(notalar)
    x = filtre(x, 1400)
    a = int(0.25 * SR)
    z = np.ones(n)
    z[:a] = np.linspace(0, 1, a)
    z[-a:] = np.linspace(1, 0, a)
    return x * z * guc


def bas_nota(nota, sure):
    n = int(sure * SR)
    t = np.arange(n) / SR
    f = frek(nota)
    x = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 2 * f * t) + 0.15 * testere(f, n)
    x = filtre(x, 700)
    z = np.minimum(1, t / 0.004) * np.exp(-t / max(0.08, sure * 0.9))
    return x * z * 0.55


# ---------- tropik house ----------

def tropik(saniye, tohum=7):
    rng = np.random.default_rng(tohum)
    vurus = 60 / TARZLAR["tropik"]["bpm"]
    on6 = vurus / 4
    olcu = 4 * vurus
    n = int(saniye * SR) + SR
    davul, bas, piyano, mel, ped = (np.zeros(n) for _ in range(5))
    pompa = np.ones(n)

    # vi - IV - I - V (La minör / Do majör): Am9 - Fadd9 - Cadd9 - G
    akorlar = [(57, "m9"), (53, "add9"), (48, "add9"), (55, "add9")]
    # marimba motifleri (on altılık konum, nota): pentatonik, akılda kalıcı
    motif_a = [(0, 76), (3, 74), (6, 72), (8, 69), (10, 72), (14, 74)]
    motif_b = [(0, 76), (3, 79), (6, 76), (8, 74), (11, 72), (14, 69)]
    # senkoplu bas (on altılık konum, kökten aralık, uzunluk)
    bas_desen = [(0, 0, 2), (3, 0, 1), (6, 12, 1), (8, 0, 2), (11, 0, 1), (14, 7, 2)]
    # piyano vuruşları: klasik house senkopu
    piyano_desen = [2, 5, 7, 10, 13]

    olcu_sayisi = int(np.ceil(saniye / olcu)) + 1
    for o in range(olcu_sayisi):
        kok, tip = akorlar[o % 4]
        notalar = [kok + i for i in ARALIKLAR[tip]]
        t0 = o * olcu
        giris = False  # Reels ilk saniyeden enerjik başlamalı
        dolgu = o % 4 == 3  # her 4 ölçünün sonunda küçük clap dolgusu

        yerlestir(ped, pad([x - 12 for x in notalar[:3]] + [notalar[3]], int(olcu * SR)), t0 * SR)

        for k in range(16):
            t = t0 + k * on6
            yerlestir(davul, shaker(rng, 0.08 if k % 2 else 0.045), t * SR)
            if giris:
                continue
            if k % 4 == 0:
                yerlestir(davul, kick(), t * SR)
                b = int(t * SR)
                e = min(n, b + int(vurus * SR))
                pompa[b:e] = np.minimum(pompa[b:e], 1 - 0.6 * np.exp(-np.arange(e - b) / SR / 0.1))
            if k in (4, 12):
                yerlestir(davul, clap(rng), t * SR)
            if k % 4 == 2:
                yerlestir(davul, acik_hat(rng), t * SR)
            if dolgu and k in (13, 14, 15):
                yerlestir(davul, clap(rng) * 0.5, t * SR)

        if not giris:
            for k, ara, uz in bas_desen:
                yerlestir(bas, bas_nota(kok - 24 + ara, uz * on6), (t0 + k * on6) * SR)
            for k in piyano_desen:
                yerlestir(piyano, piyano_vurus(notalar), (t0 + k * on6) * SR)
        if o >= 1:  # melodi ikinci ölçüde girer
            motif = motif_a if (o // 2) % 2 == 1 else motif_b
            for k, nt in motif:
                yerlestir(mel, marimba(nt, guc=0.24), (t0 + k * on6) * SR)

    ir = yanki_ir(1.5, rng)
    piyano = yanki(piyano, ir, 0.35)
    mel = yanki(mel, ir, 0.45)
    ped = yanki(ped, ir, 0.3)
    davul = davul + 0.06 * fftconvolve(davul, ir)[:n]

    karisim = davul * 0.85 + (bas + piyano + mel + ped) * pompa
    g1, g2 = int(0.011 * SR), int(0.017 * SR)
    sol, sag = karisim.copy(), karisim.copy()
    sol[g1:] += 0.18 * ((mel + piyano) * pompa)[:-g1]
    sag[g2:] += 0.18 * ((mel + piyano) * pompa)[:-g2]
    return np.stack([sol, sag], axis=1)[: int(saniye * SR)]


# ---------- diğer tarzlar ----------

def _klasik(saniye, tarz, tohum):
    s = TARZLAR[tarz]
    rng = np.random.default_rng(tohum)
    vurus = 60 / s["bpm"]
    olcu = 4 * vurus
    n = int(saniye * SR)
    davul, bas, akor, arp = (np.zeros(n) for _ in range(4))
    pompa = np.ones(n)
    for o in range(int(np.ceil(saniye / olcu))):
        kok, tip = s["akorlar"][o % len(s["akorlar"])]
        notalar = [kok + i for i in ARALIKLAR[tip]]
        t0 = o * olcu
        giris = o == 0
        m = int(olcu * SR)
        p = sum(testere(frek(nt + 12), m, 0.004) for nt in notalar) / len(notalar)
        yerlestir(akor, filtre(p, 1500) * zarf(m, 0.04, olcu * 1.5) * 0.35, t0 * SR)
        for v in range(4):
            tv = t0 + v * vurus
            if not giris:
                yerlestir(davul, kick(), tv * SR)
                b = int(tv * SR)
                e = min(n, b + int(vurus * SR))
                pompa[b:e] = np.minimum(pompa[b:e], 1 - 0.55 * np.exp(-np.arange(e - b) / SR / 0.09))
                if v in (1, 3):
                    yerlestir(davul, clap(rng), tv * SR)
                yerlestir(bas, bas_nota(kok - 24, vurus / 2), (tv + vurus / 2) * SR)
            yerlestir(davul, shaker(rng, 0.1), tv * SR)
            yerlestir(davul, acik_hat(rng), (tv + vurus / 2 + s["swing"] * vurus) * SR)
            if s["arp"] and o >= 1:
                for k16 in range(4):
                    nt = notalar[(v * 4 + k16) % len(notalar)] + 24
                    yerlestir(arp, marimba(nt, 0.2, 0.12), (tv + k16 * vurus / 4) * SR)
    karisim = davul * 0.9 + (bas + akor * 0.8 + arp) * pompa
    return np.stack([karisim, karisim], axis=1)


def uret(saniye, tarz="tropik", tohum=7):
    st = tropik(saniye, tohum) if tarz == "tropik" else _klasik(saniye, tarz, tohum)
    fi, fo = int(0.15 * SR), int(1.5 * SR)
    st[:fi] *= np.linspace(0, 1, fi)[:, None]
    st[-fo:] *= np.linspace(1, 0, fo)[:, None]
    st = np.tanh(st / np.max(np.abs(st)) * 1.6)  # yumuşak sıkıştırma, daha dolgun ses
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
    tarz = sys.argv[3] if len(sys.argv) > 3 else "tropik"
    tohum = int(sys.argv[4]) if len(sys.argv) > 4 else 7
    kaydet(uret(float(sys.argv[2]), tarz, tohum), sys.argv[1])
    print("  ", sys.argv[1])
