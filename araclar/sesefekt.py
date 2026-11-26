#!/usr/bin/env python3
"""Belgesel kurgusu için kodla sentezlenen ses efektleri (sample yok, telif sorunu yok).

Her fonksiyon stereo (n, 2) float dizi döndürür, tepe değeri ~1.
  whoosh   geçiş sesi (süpürülen filtreli gürültü, soldan sağa)
  darbe    derin sinematik vuruş (boom): alt frekans düşüşü + gövde + uzun yankı
  riser    gerilim yükselişi; bittiği an bir darbeye/kesmeye denk getirilir
  tik      sayaç tıkı
  daktilo  tek daktilo tuşu (her çağrıda biraz farklı)
  ruzgar   uzun, yavaş dalgalanan rüzgar/ortam yatağı
  drone    düşük, gergin uğultu (soğuk açılış altı)
  nefes    yumuşak, kısa hava sesi (yazı belirirken)
"""
import numpy as np
from scipy.signal import butter, fftconvolve, lfilter, sosfilt

SR = 44100


def _bp(x, lo, hi, derece=2):
    sos = butter(derece, [lo / (SR / 2), hi / (SR / 2)], btype="band", output="sos")
    return sosfilt(sos, x)


def _lp(x, f, derece=2):
    sos = butter(derece, f / (SR / 2), output="sos")
    return sosfilt(sos, x)


def _hp(x, f, derece=2):
    sos = butter(derece, f / (SR / 2), btype="high", output="sos")
    return sosfilt(sos, x)


def _norm(x, tepe=1.0):
    m = np.max(np.abs(x)) or 1.0
    return x / m * tepe


def _stereo(m, pan=0.0):
    sol = np.sqrt(0.5 * (1 - pan))
    sag = np.sqrt(0.5 * (1 + pan))
    return np.stack([m * sol, m * sag], axis=1)


def _yanki(m, sure, oran, rng, parlaklik=4000):
    n = int(sure * SR)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / SR / (sure / 5))
    ir = _lp(ir, parlaklik)
    ir /= np.sqrt(np.sum(ir ** 2))
    return m + oran * fftconvolve(m, ir)[: len(m)]


def _degisken_filtre(x, merkezler, genislik=1.6, blok=512):
    """Zamanla kayan bant geçiren filtre (blok blok; durum korunur)."""
    out = np.zeros_like(x)
    zi = None
    for i in range(0, len(x), blok):
        fc = float(merkezler[min(i, len(merkezler) - 1)])
        lo, hi = max(40, fc / genislik), min(SR / 2 - 200, fc * genislik)
        b, a = butter(2, [lo / (SR / 2), hi / (SR / 2)], btype="band")
        if zi is None or len(zi) != max(len(a), len(b)) - 1:
            zi = np.zeros(max(len(a), len(b)) - 1)
        out[i:i + blok], zi = lfilter(b, a, x[i:i + blok], zi=zi)
    return out


def whoosh(sure=0.9, tohum=1, parlak=1.0):
    rng = np.random.default_rng(tohum)
    n = int(sure * SR)
    t = np.linspace(0, 1, n)
    zarf = np.sin(np.pi * t ** 0.7) ** 2.2
    merkez = 250 + 2600 * parlak * np.sin(np.pi * t ** 0.8) ** 1.5
    g = _degisken_filtre(rng.standard_normal(n), merkez, 1.8)
    m = _norm(g * zarf)
    m = _yanki(m, 0.6, 0.25, rng)
    pan = np.linspace(-0.7, 0.7, n)
    st = np.stack([m * np.sqrt(0.5 * (1 - pan)), m * np.sqrt(0.5 * (1 + pan))], axis=1)
    return _norm(st, 0.9)


def darbe(sure=3.2, tohum=2, derin=1.0):
    rng = np.random.default_rng(tohum)
    n = int(sure * SR)
    t = np.arange(n) / SR
    # alt frekans: 70 Hz'den 32 Hz'e kayan sinüs
    f = 32 + 38 * np.exp(-t * 6)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.6) * derin
    # gövde: kısa, alçak geçirilmiş gürültü patlaması
    govde = _lp(rng.standard_normal(n), 900) * np.exp(-t * 14)
    # vuruş anı: çok kısa tık
    tik = _hp(rng.standard_normal(n), 2500) * np.exp(-t * 90) * 0.35
    m = sub * 1.0 + _norm(govde) * 0.55 + tik
    m = _yanki(m, 2.8, 0.55, rng, 2500)
    m = np.tanh(_norm(m) * 1.4)
    st = _stereo(m)
    # biraz genişlik: sağ kanal yankısı farklı
    st[:, 1] = 0.85 * st[:, 1] + 0.15 * np.roll(st[:, 1], int(0.011 * SR))
    return _norm(st, 1.0)


def riser(sure=2.2, tohum=3):
    rng = np.random.default_rng(tohum)
    n = int(sure * SR)
    t = np.linspace(0, 1, n)
    zarf = t ** 2.4
    merkez = 300 + 5500 * t ** 2
    g = _norm(_degisken_filtre(rng.standard_normal(n), merkez, 1.5))
    f = 110 * 2 ** (t * 2.0)
    ton = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.5 * np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR)
    m = (g * 0.8 + ton * 0.25) * zarf
    m = _yanki(m, 1.2, 0.3, rng)
    m[-int(0.01 * SR):] *= np.linspace(1, 0, int(0.01 * SR))  # sonda keskin kesme
    return _norm(_stereo(m), 0.8)


def tik(tohum=4, ton=3200):
    rng = np.random.default_rng(tohum)
    n = int(0.035 * SR)
    t = np.arange(n) / SR
    m = np.sin(2 * np.pi * ton * t) * np.exp(-t * 260) + 0.3 * _hp(rng.standard_normal(n), 4000) * np.exp(-t * 400)
    return _norm(_stereo(m), 0.6)


def daktilo(tohum=5):
    rng = np.random.default_rng(tohum)
    n = int(0.09 * SR)
    t = np.arange(n) / SR
    vurus = _bp(rng.standard_normal(n), 1800 + rng.uniform(-300, 300), 5200) * np.exp(-t * 180)
    govde = np.sin(2 * np.pi * (180 + rng.uniform(-20, 20)) * t) * np.exp(-t * 70) * 0.5
    geri = np.zeros(n)
    k = int(rng.uniform(0.028, 0.04) * SR)
    geri[k:] = _bp(rng.standard_normal(n - k), 2500, 7000) * np.exp(-np.arange(n - k) / SR * 300) * 0.35
    m = vurus + govde + geri
    return _norm(_stereo(m, rng.uniform(-0.15, 0.15)), rng.uniform(0.45, 0.6))


def ruzgar(sure, tohum=6):
    rng = np.random.default_rng(tohum)
    n = int(sure * SR)
    beyaz = rng.standard_normal(n + SR)
    kahve = np.cumsum(beyaz)
    kahve = _hp(kahve, 25)[SR:]
    kahve = _norm(kahve)
    t = np.arange(n) / SR
    # yavaş dalgalanma (esintiler)
    lfo = 0.55 + 0.25 * np.sin(2 * np.pi * 0.07 * t + 1.3) + 0.2 * np.sin(2 * np.pi * 0.19 * t)
    merkez = 380 + 260 * np.sin(2 * np.pi * 0.05 * t) + 180 * np.sin(2 * np.pi * 0.13 * t + 2)
    islik = _degisken_filtre(rng.standard_normal(n), merkez, 1.25, blok=1024)
    m = _lp(kahve, 700) * 0.7 + _norm(islik) * 0.35
    m = _norm(m * lfo)
    sol = m
    sag = np.roll(m, int(0.37 * SR))
    st = np.stack([sol, sag], axis=1)
    k = int(1.5 * SR)
    st[:k] *= np.linspace(0, 1, k)[:, None]
    st[-k:] *= np.linspace(1, 0, k)[:, None]
    return _norm(st, 0.9)


def drone(sure, tohum=7, nota=38):
    rng = np.random.default_rng(tohum)
    n = int(sure * SR)
    t = np.arange(n) / SR
    f = 440 * 2 ** ((nota - 69) / 12)
    m = np.zeros(n)
    for c, g in ((1, 1.0), (2, 0.35), (3, 0.2), (1.5, 0.18)):
        for d in (-0.003, 0.003):
            m += g * np.sin(2 * np.pi * f * c * (1 + d) * t + rng.uniform(0, 6.28))
    m = _lp(m, 900) * (0.75 + 0.25 * np.sin(2 * np.pi * 0.21 * t))
    zarf = np.minimum(1, t / (sure * 0.6)) ** 1.5
    zarf[-int(0.3 * SR):] *= np.linspace(1, 0, int(0.3 * SR))
    return _norm(_stereo(m * zarf), 0.7)


def nefes(sure=0.6, tohum=8):
    rng = np.random.default_rng(tohum)
    n = int(sure * SR)
    t = np.linspace(0, 1, n)
    m = _bp(rng.standard_normal(n), 600, 3500) * np.sin(np.pi * t) ** 2
    return _norm(_stereo(m), 0.5)


def ekle(iz, ses, zaman, kazanc=1.0):
    """iz: (N,2) stereo; ses (n,2); zaman saniye."""
    bas = int(round(zaman * SR))
    if bas < 0:
        ses = ses[-bas:]
        bas = 0
    son = min(len(iz), bas + len(ses))
    if son > bas:
        iz[bas:son] += ses[: son - bas] * kazanc
