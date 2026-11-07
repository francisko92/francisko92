#!/usr/bin/env python3
"""Monta el vídeo largo, los Shorts y la miniatura a partir de escenas.json + audio + imágenes.

Uso:
  python3 montar.py VIDEO_DIR [--prueba] [--solo largo|short1|short2|short3|miniatura]
"""
import argparse, json, os, re, subprocess, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

FPS, XF, GAP, TAIL = 30, 0.5, 0.7, 1.5
F_TIT = "/usr/share/fonts/truetype/crosextra/Caladea-Bold.ttf"
F_CITA = "/usr/share/fonts/truetype/crosextra/Caladea-BoldItalic.ttf"
F_NOTA = "/usr/share/fonts/truetype/crosextra/Caladea-Italic.ttf"
F_UI = "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf"
FONTS_DIR = "/usr/share/fonts/opentype/inter"
GOLD = (240, 196, 90)
MOVS = ["in", "lr", "out", "up", "rl"]


def run(cmd):
    subprocess.run(cmd, check=True)


def ffdur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", p]).decode())


# ---------- audio / alineación ----------

class Escena:
    def __init__(self, adir, sid):
        self.mp3 = os.path.join(adir, sid + ".mp3")
        d = json.load(open(os.path.join(adir, sid + ".json")))
        al = d["alignment"]
        self.chars = al["characters"]
        self.st = al["character_start_times_seconds"]
        self.en = al["character_end_times_seconds"]
        self.txt = "".join(self.chars)
        self.dur = ffdur(self.mp3)
        self.words = []
        cur, s, e = "", 0, 0
        for c, a, b in zip(self.chars, self.st, self.en):
            if c.isspace():
                if cur:
                    self.words.append((cur, s, e))
                cur = ""
            else:
                if not cur:
                    s = a
                cur, e = cur + c, b
        if cur:
            self.words.append((cur, s, e))

    def t_de(self, frase, final=False):
        i = self.txt.find(frase)
        if i < 0:
            raise SystemExit(f"No encuentro «{frase}» en el audio")
        if final:
            j = i + len(frase) - 1
            return min(self.en[j] + 0.2, self.dur)
        return max(self.st[i] - 0.08, 0)


def construir_audio(piezas, tmp, total):
    """piezas: [(mp3, t0, t1, pausa_despues)] -> wav final con ambiente de mar."""
    lst = os.path.join(tmp, "piezas.txt")
    with open(lst, "w") as f:
        for k, (mp3, t0, t1, pad) in enumerate(piezas):
            w = os.path.join(tmp, f"p{k:02d}.wav")
            run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t0:.3f}", "-to", f"{t1:.3f}", "-i", mp3,
                 "-af", f"afade=t=in:d=0.02,apad=pad_dur={pad:.3f}", "-ar", "48000", "-ac", "1", w])
            f.write(f"file '{w}'\n")
    narr = os.path.join(tmp, "narr.wav")
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst,
         "-af", "loudnorm=I=-15:TP=-1.5:LRA=11", "-ar", "48000", narr])
    out = os.path.join(tmp, "audio.wav")
    amb = (f"anoisesrc=color=brown:sample_rate=48000:amplitude=0.5:duration={total:.2f},"
           "lowpass=f=420,highpass=f=40,volume='0.55+0.45*sin(2*PI*t/7.5)':eval=frame,"
           f"volume=0.05,afade=t=in:d=2,afade=t=out:st={max(total - 2.5, 0):.2f}:d=2.5")
    run(["ffmpeg", "-v", "error", "-y", "-i", narr, "-f", "lavfi", "-i", amb, "-filter_complex",
         f"[0:a]apad[n];[n][1:a]amix=inputs=2:normalize=0:duration=longest,atrim=0:{total:.2f}[a]",
         "-map", "[a]", "-ac", "2", "-ar", "48000", out])
    return out


# ---------- imágenes ----------

def viñeta(im, fuerza=0.55):
    w, h = im.size
    y, x = np.ogrid[-1:1:h * 1j, -1:1:w * 1j]
    m = 1 - fuerza * np.clip((x ** 2 + y ** 2) / 2, 0, 1) ** 1.2
    a = np.asarray(im).astype(np.float32) * m[..., None]
    return Image.fromarray(a.clip(0, 255).astype(np.uint8))


def base(img, W, H, out):
    S = 2
    W2, H2 = W * S, H * S
    im = Image.open(img).convert("RGB")
    im = ImageEnhance.Contrast(im).enhance(1.08)
    ar, tar = im.width / im.height, W / H
    vertical = H > W
    if not vertical and abs(ar - tar) / tar < 0.22:
        canvas = ImageOps.fit(im, (W2, H2), Image.LANCZOS)
    else:
        bg = ImageOps.fit(im, (W2 // 4, H2 // 4), Image.LANCZOS).filter(ImageFilter.GaussianBlur(12))
        bg = ImageEnhance.Brightness(bg.resize((W2, H2), Image.LANCZOS)).enhance(0.42)
        if vertical:
            if ar < 0.95:
                fg = ImageOps.contain(im, (W2, int(H2 * 0.62)), Image.LANCZOS)
            else:
                fg = ImageOps.fit(im, (W2, int(W2 * 1.1)), Image.LANCZOS) if ar < 2.2 else \
                    ImageOps.contain(im, (W2, H2), Image.LANCZOS)
            cy = int(H2 * 0.45)
        else:
            fg = ImageOps.contain(im, (int(W2 * 0.96), int(H2 * 0.94)), Image.LANCZOS)
            cy = H2 // 2
        bg.paste(fg, ((W2 - fg.width) // 2, cy - fg.height // 2))
        canvas = bg
    viñeta(canvas).save(out, quality=94)


def fuente(path, size):
    return ImageFont.truetype(path, int(size))


def texto_centrado(d, W, y, lineas, f, fill, sombra=True, interlineado=1.18):
    for ln in lineas:
        bb = d.textbbox((0, 0), ln, font=f)
        x = (W - (bb[2] - bb[0])) // 2
        if sombra:
            d.text((x + 3, y + 4), ln, font=f, fill=(0, 0, 0, 200))
        d.text((x, y), ln, font=f, fill=fill, stroke_width=2, stroke_fill=(0, 0, 0, 180))
        y += int(f.size * interlineado)
    return y


def envolver(d, texto, f, ancho):
    out = []
    for parrafo in texto.split("\n"):
        ln = ""
        for w in parrafo.split():
            t = (ln + " " + w).strip()
            if d.textlength(t, font=f) > ancho and ln:
                out.append(ln)
                ln = w
            else:
                ln = t
        out.append(ln)
    return out


def overlay(spec, W, H, out, cabecera=None, cta=False):
    o = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(o)
    u = H / 1080 if W > H else W / 1080
    if "titulo" in spec:
        band = Image.new("RGBA", (W, int(H * 0.42)), (0, 0, 0, 0))
        g = np.linspace(0, 1, band.height)
        alpha = (np.sin(g * np.pi) * 190).astype(np.uint8)
        band.putalpha(Image.fromarray(np.repeat(alpha[:, None], W, 1)))
        o.alpha_composite(band, (0, int(H * 0.29)))
        f = fuente(F_TIT, 92 * u)
        lineas = spec["titulo"].split("\n")
        y = int(H * 0.5 - len(lineas) * f.size * 0.6)
        texto_centrado(d, W, y, lineas, f, GOLD + (255,))
    if "cita" in spec:
        o.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 150)))
        f = fuente(F_CITA, (66 if W > H else 84) * u)
        lineas = envolver(d, spec["cita"].replace("\n", " "), f, W * 0.82)
        y = int(H * 0.47 - len(lineas) * f.size * 0.6)
        texto_centrado(d, W, y, lineas, f, (255, 255, 255, 255))
    if "etiqueta" in spec:
        f = fuente(F_UI, 34 * u)
        t = spec["etiqueta"]
        tw = d.textlength(t, font=f)
        x0, y0 = int(56 * u), int(54 * u) if W > H else int(H * 0.2)
        d.rounded_rectangle((x0, y0, x0 + tw + 52 * u, y0 + 70 * u), radius=10 * u, fill=(0, 0, 0, 170))
        d.rectangle((x0, y0, x0 + 8 * u, y0 + 70 * u), fill=GOLD + (255,))
        d.text((x0 + 30 * u, y0 + 14 * u), t, font=f, fill=(255, 255, 255, 255))
    if "nota" in spec:
        f = fuente(F_NOTA, 36 * u)
        lineas = envolver(d, spec["nota"], f, W * 0.8)
        h = len(lineas) * f.size * 1.25 + 36 * u
        y0 = int(54 * u) if W > H else int(H * 0.2)
        bw = max(d.textlength(l, font=f) for l in lineas) + 60 * u
        d.rounded_rectangle(((W - bw) / 2, y0, (W + bw) / 2, y0 + h), radius=12 * u, fill=(0, 0, 0, 175))
        texto_centrado(d, W, int(y0 + 16 * u), lineas, f, (235, 225, 200, 255), sombra=False, interlineado=1.25)
    if cabecera:
        f = fuente(F_UI, 64 * u)
        lineas = envolver(d, cabecera.upper(), f, W * 0.86)
        h = len(lineas) * f.size * 1.15 + 50 * u
        y0 = int(H * 0.075)
        d.rounded_rectangle((W * 0.04, y0, W * 0.96, y0 + h), radius=22 * u, fill=(12, 12, 12, 215))
        texto_centrado(d, W, int(y0 + 24 * u), lineas, f, GOLD + (255,), sombra=False, interlineado=1.15)
    if cta:
        f = fuente(F_UI, 52 * u)
        t = "▶  HISTORIA COMPLETA EN EL CANAL"
        tw = d.textlength(t, font=f)
        y0 = int(H * 0.63)
        d.rounded_rectangle(((W - tw) / 2 - 40 * u, y0, (W + tw) / 2 + 40 * u, y0 + 100 * u), radius=20 * u,
                            fill=(200, 30, 30, 235))
        d.text(((W - tw) / 2, y0 + 22 * u), t, font=f, fill=(255, 255, 255, 255))
    o.save(out)


def clip(base_png, ov_png, dur, W, H, mov, out):
    N = max(int(round(dur * FPS)), 2)
    Z = 0.12
    z, x, y = {
        "in": (f"1+{Z}*on/{N}", "(iw-iw/zoom)/2", "(ih-ih/zoom)/2"),
        "out": (f"{1 + Z}-{Z}*on/{N}", "(iw-iw/zoom)/2", "(ih-ih/zoom)/2"),
        "lr": (f"{1 + Z}", f"(iw-iw/zoom)*on/{N}", "(ih-ih/zoom)/2"),
        "rl": (f"{1 + Z}", f"(iw-iw/zoom)*(1-on/{N})", "(ih-ih/zoom)/2"),
        "up": (f"1+{Z}*on/{N}", "(iw-iw/zoom)/2", "(ih-ih/zoom)*0.25"),
    }[mov]
    fc = f"[0:v]zoompan=z='{z}':x='{x}':y='{y}':d={N}:s={W}x{H}:fps={FPS},setsar=1[v]"
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", base_png]
    if ov_png:
        cmd += ["-loop", "1", "-framerate", str(FPS), "-i", ov_png]
        fc += ";[1:v]format=rgba,fade=t=in:st=0.35:d=0.6:alpha=1[o];[v][o]overlay=0:0:shortest=1[v2]"
        last = "[v2]"
    else:
        last = "[v]"
    fc += f";{last}format=yuv420p[vo]"
    run(cmd + ["-filter_complex", fc, "-map", "[vo]", "-frames:v", str(N), "-c:v", "libx264",
               "-preset", "veryfast", "-crf", "17", "-r", str(FPS), out])


# ---------- subtítulos ----------

def ts(t):
    t = max(t, 0)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def trozos(words, maxw, maxc):
    out, cur = [], []
    for w in words:
        cur.append(w)
        txt = " ".join(x[0] for x in cur)
        if len(cur) >= maxw or len(txt) >= maxc or re.search(r"[.,:;?!…]$", w[0]):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def ass(words, W, H, out, short=False, silencio=()):
    if short:
        style = f"Style: S,Inter Display Black,86,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,0,0,1,6,2,2,60,60,{int(H * 0.2)},1"
        ch = trozos(words, 3, 16)
    else:
        style = f"Style: S,Inter Display Black,50,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,0,0,1,3.5,1.5,2,120,120,54,1"
        ch = trozos(words, 6, 34)
    hl = "{\\c&H5AC4F0&}"
    ev = []
    for i, c in enumerate(ch):
        t0 = c[0][1]
        t1 = ch[i + 1][0][1] if i + 1 < len(ch) else c[-1][2] + 0.4
        t1 = min(t1, c[-1][2] + 0.9)
        if any(a <= t0 < b for a, b in silencio):
            continue
        txts = [w[0].upper() if short else w[0] for w in c]
        if short:
            for k, w in enumerate(c):
                a = w[1]
                b = c[k + 1][1] if k + 1 < len(c) else t1
                line = " ".join((hl + t + "{\\c&HFFFFFF&}") if j == k else t for j, t in enumerate(txts))
                ev.append(f"Dialogue: 0,{ts(a)},{ts(b)},S,,0,0,0,,{line}")
        else:
            ev.append(f"Dialogue: 0,{ts(t0)},{ts(t1)},S,,0,0,0,,{' '.join(txts)}")
    with open(out, "w") as f:
        f.write(f"[Script Info]\nScriptType: v4.00+\nPlayResX: {W}\nPlayResY: {H}\nWrapStyle: 0\n\n"
                "[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,"
                "Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,"
                f"MarginL,MarginR,MarginV,Encoding\n{style}\n\n[Events]\n"
                "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n" + "\n".join(ev) + "\n")
    return ch


def srt(words, out):
    ch = trozos(words, 8, 42)
    def t(x):
        return f"{int(x // 3600):02d}:{int(x % 3600 // 60):02d}:{int(x % 60):02d},{int(x * 1000 % 1000):03d}"
    with open(out, "w") as f:
        for i, c in enumerate(ch, 1):
            f.write(f"{i}\n{t(c[0][1])} --> {t(c[-1][2] + 0.25)}\n{' '.join(w[0] for w in c)}\n\n")


# ---------- render ----------

def render(visuales, piezas, words, W, H, out, tmp, short=False, cabecera=None):
    """visuales: [(img_path, spec, dur, frontera_escena)]"""
    os.makedirs(tmp, exist_ok=True)
    total = sum(v[2] for v in visuales) + XF
    audio = construir_audio(piezas, tmp, total)
    clips, silencio, t = [], [], 0.0
    for k, (img, spec, d, _) in enumerate(visuales):
        b = os.path.join(tmp, f"b{k:02d}.jpg")
        base(img, W, H, b)
        ov = None
        es_ultimo = k == len(visuales) - 1
        if spec or cabecera or (short and es_ultimo):
            ov = os.path.join(tmp, f"o{k:02d}.png")
            overlay(spec or {}, W, H, ov, cabecera=cabecera, cta=short and es_ultimo)
        if spec and "cita" in spec:
            silencio.append((t, t + d))
        c = os.path.join(tmp, f"c{k:02d}.mp4")
        clip(b, ov, d + XF, W, H, MOVS[k % len(MOVS)], c)
        clips.append(c)
        t += d
        print(f"  clip {k + 1}/{len(visuales)}", flush=True)
    sub = os.path.join(tmp, "subs.ass")
    ass(words, W, H, sub, short=short, silencio=silencio)
    cmd = ["ffmpeg", "-v", "error", "-y"]
    for c in clips:
        cmd += ["-i", c]
    cmd += ["-i", audio]
    fc, prev, off = [], "[0:v]", 0.0
    for k in range(1, len(clips)):
        off += visuales[k - 1][2]
        tr = "fadeblack" if visuales[k][3] else "fade"
        fc.append(f"{prev}[{k}:v]xfade=transition={tr}:duration={XF}:offset={off:.3f}[x{k}]")
        prev = f"[x{k}]"
    fc.append(f"{prev}ass={sub}:fontsdir={FONTS_DIR},format=yuv420p[v]")
    run(cmd + ["-filter_complex", ";".join(fc), "-map", "[v]", "-map", f"{len(clips)}:a",
               "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-c:a", "aac", "-b:a", "192k",
               "-movflags", "+faststart", "-t", f"{total:.2f}", out])
    print("->", out, f"{total:.1f}s")


def img_path(vdir, n):
    return os.path.join(vdir, "imagenes", f"{n:02d}.jpg")


def largo(vdir, adir, cfg, sal, tmp):
    visuales, piezas, words, t = [], [], [], 0.0
    esc = cfg["escenas"]
    for i, e in enumerate(esc):
        E = Escena(adir, e["id"])
        span = E.dur + GAP + (TAIL if i == len(esc) - 1 else 0)
        piezas.append((E.mp3, 0, E.dur, GAP))
        words += [(w, a + t, b + t) for w, a, b in E.words]
        ims = e["imagenes"]
        for j, im in enumerate(ims):
            spec = {k: v for k, v in im.items() if k != "img"}
            visuales.append((img_path(vdir, im["img"]), spec, span / len(ims), j == 0 and i > 0))
        t += E.dur + GAP
    render(visuales, piezas, words, 1920, 1080, os.path.join(sal, "video-largo.mp4"), tmp)
    srt(words, os.path.join(sal, "subtitulos-es.srt"))


def short(vdir, adir, sh, sal, tmp):
    piezas, words, t = [], [], 0.0
    for sid, desde, hasta in sh["piezas"]:
        E = Escena(adir, sid)
        t0 = E.t_de(desde) if desde else 0
        t1 = E.t_de(hasta, final=True) if hasta else E.dur
        piezas.append((E.mp3, t0, t1, 0.35))
        words += [(w, a - t0 + t, b - t0 + t) for w, a, b in E.words if a >= t0 - 0.01 and b <= t1 + 0.01]
        t += t1 - t0 + 0.35
    total = t + TAIL
    ims = sh["imagenes"]
    visuales = []
    for im in ims:
        im = im if isinstance(im, dict) else {"img": im}
        spec = {k: v for k, v in im.items() if k != "img"}
        visuales.append((img_path(vdir, im["img"]), spec, total / len(ims), False))
    render(visuales, piezas, words, 1080, 1920, os.path.join(sal, sh["id"] + ".mp4"), tmp, short=True,
           cabecera=sh["cabecera"])


def miniatura(vdir, cfg, sal):
    m = cfg["miniatura"]
    W, H = 1280, 720
    im = Image.open(img_path(vdir, m["img"])).convert("RGB")
    im = ImageOps.fit(im, (W, H), Image.LANCZOS, centering=tuple(m.get("centro", (0.5, 0.5))))
    im = ImageEnhance.Contrast(im).enhance(1.25)
    im = ImageEnhance.Color(im).enhance(1.2)
    im = viñeta(im, 0.75).convert("RGBA")
    d = ImageDraw.Draw(im)
    g = np.linspace(0, 1, W)
    alpha = (np.clip(1.15 - g * 1.6, 0, 1) * 220).astype(np.uint8)
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shade.putalpha(Image.fromarray(np.repeat(alpha[None, :], H, 0)))
    im.alpha_composite(shade)
    f = fuente(F_UI, 132)
    y = 150
    for k, ln in enumerate(m["texto"].split("\n")):
        col = (255, 255, 255) if k == 0 else GOLD
        d.text((54, y), ln, font=f, fill=col, stroke_width=8, stroke_fill=(0, 0, 0))
        y += 150
    d.rectangle((54, y + 20, 340, y + 34), fill=(210, 30, 30))
    f2 = fuente(F_TIT, 54)
    d.text((54, y + 50), m.get("sub", ""), font=f2, fill=(255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0))
    im.convert("RGB").save(os.path.join(sal, "miniatura.jpg"), quality=92)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_dir")
    ap.add_argument("--prueba", action="store_true")
    ap.add_argument("--solo")
    a = ap.parse_args()
    vdir = os.path.abspath(a.video_dir)
    cfg = json.load(open(os.path.join(vdir, "escenas.json")))
    adir = os.path.join(vdir, "audio_prueba" if a.prueba else "audio")
    sal = os.path.join(vdir, "salida_prueba" if a.prueba else "salida")
    os.makedirs(sal, exist_ok=True)
    tmp_root = os.path.join(vdir, ".tmp")
    if a.solo in (None, "miniatura"):
        miniatura(vdir, cfg, sal)
    if a.solo in (None, "largo"):
        largo(vdir, adir, cfg, sal, os.path.join(tmp_root, "largo"))
    for sh in cfg.get("shorts", []):
        if a.solo in (None, sh["id"]):
            short(vdir, adir, sh, sal, os.path.join(tmp_root, sh["id"]))
    shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
