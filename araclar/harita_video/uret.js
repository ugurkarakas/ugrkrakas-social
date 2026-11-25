#!/usr/bin/env node
// Harita rehberi videosu: icerik/<slug>.json -> reels/<slug>.mp4 (1080x1920, 30 fps)
//   node araclar/harita_video/uret.js icerik/amsterdam-harita.json            tam video
//   node araclar/harita_video/uret.js icerik/amsterdam-harita.json --kare 2,6  önizleme kareleri (saniye)
//   --bas 10 --bit 20  sadece bir aralığı üret (parça olarak)
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const fs = require('fs'), path = require('path');

const KOK = path.resolve(__dirname, '../..');
const args = process.argv.slice(2);
const json = path.resolve(args[0]);
const opt = (k) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : null; };
const veri = JSON.parse(fs.readFileSync(json, 'utf8'));
const FPS = 30;
const STIL_URL = 'https://tiles.openfreemap.org/styles/positron';

(async () => {
  let stil;
  try { stil = await (await fetch(STIL_URL)).json(); }
  catch { stil = JSON.parse(fs.readFileSync(path.join(__dirname, 'stil_kaynak.json'), 'utf8')); }
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--allow-file-access-from-files', '--disable-web-security'] });
  const p = await b.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  p.on('pageerror', e => console.error('sayfa hatası:', e.message));
  await p.addInitScript(([v, s]) => { window.VERI = v; window.STIL = s; }, [veri, stil]);
  await p.goto('file://' + path.join(__dirname, 'sablon.html'));
  await p.evaluate(() => window.basla());
  const toplam = await p.evaluate(() => window.TOPLAM);
  console.log('süre', toplam.toFixed(2), 'sn');

  const kareler = opt('--kare');
  if (kareler) {
    const out = path.join(KOK, '..', 'onizleme');
    for (const t of kareler.split(',').map(Number)) {
      await p.evaluate(t => window.kare(t), t);
      const yol = opt('--cikis') ? path.join(opt('--cikis'), `k${t}.jpg`) : `/tmp/k${t}.jpg`;
      await p.screenshot({ path: yol, type: 'jpeg', quality: 92 });
      console.log(yol);
    }
    await b.close(); return;
  }
  const bas = Number(opt('--bas') || 0), bit = Math.min(toplam, Number(opt('--bit') || toplam));
  const cikis = opt('--video') || path.join(KOK, 'reels', `${veri.slug}-sessiz.mp4`);
  const ff = spawn('ffmpeg', ['-y', '-v', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '14', '-pix_fmt', 'yuv420p', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', cikis],
    { stdio: ['pipe', 'inherit', 'inherit'] });
  const n0 = Math.round(bas * FPS), n1 = Math.round(bit * FPS);
  const t0 = Date.now();
  for (let n = n0; n < n1; n++) {
    await p.evaluate(t => window.kare(t), n / FPS);
    const buf = await p.screenshot({ type: 'jpeg', quality: 95 });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (n % 60 === 0) console.log(`kare ${n}/${n1} (${((Date.now() - t0) / 1000).toFixed(0)} sn)`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
  await b.close();
  console.log(cikis);
})();
