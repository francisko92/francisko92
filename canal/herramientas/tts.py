#!/usr/bin/env python3
"""Genera la locución de cada escena con ElevenLabs (con marcas de tiempo por carácter).

Uso:
  python3 tts.py VIDEO_DIR --voz VOICE_ID [--modelo eleven_multilingual_v2]
  python3 tts.py VIDEO_DIR --prueba        # audio mudo de prueba, no gasta créditos

Las escenas ya generadas no se vuelven a pedir (para no gastar créditos dos veces).
La clave de la API la inyecta el proxy del entorno en la cabecera xi-api-key.
"""
import argparse, base64, json, os, subprocess, sys, urllib.request, urllib.error

API = "https://api.elevenlabs.io/v1"


def tts(voz, modelo, texto, prev, nxt):
    body = {
        "text": texto,
        "model_id": modelo,
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.25, "use_speaker_boost": True},
    }
    if prev:
        body["previous_text"] = prev
    if nxt:
        body["next_text"] = nxt
    req = urllib.request.Request(
        f"{API}/text-to-speech/{voz}/with-timestamps?output_format=mp3_44100_128",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "xi-api-key": os.environ.get("ELEVENLABS_API_KEY", "sk_proxy")},
    )
    try:
        return json.load(urllib.request.urlopen(req, timeout=300))
    except urllib.error.HTTPError as e:
        sys.exit(f"ElevenLabs respondió {e.code}: {e.read()[:500]!r}")


def prueba(texto, mp3):
    """Audio mudo con una duración realista y alineación uniforme."""
    dur = len(texto) * 0.068
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                    "-t", f"{dur:.2f}", "-b:a", "128k", mp3], check=True)
    step = dur / len(texto)
    return {"characters": list(texto),
            "character_start_times_seconds": [i * step for i in range(len(texto))],
            "character_end_times_seconds": [(i + 1) * step for i in range(len(texto))]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_dir")
    ap.add_argument("--voz")
    ap.add_argument("--modelo", default="eleven_multilingual_v2")
    ap.add_argument("--prueba", action="store_true")
    ap.add_argument("--solo", help="id de una escena concreta")
    a = ap.parse_args()
    cfg = json.load(open(os.path.join(a.video_dir, "escenas.json")))
    esc = cfg["escenas"] + cfg.get("extras", [])
    out = os.path.join(a.video_dir, "audio_prueba" if a.prueba else "audio")
    os.makedirs(out, exist_ok=True)
    total = 0
    for i, e in enumerate(esc):
        if a.solo and e["id"] != a.solo:
            continue
        mp3, js = os.path.join(out, e["id"] + ".mp3"), os.path.join(out, e["id"] + ".json")
        if os.path.exists(mp3) and os.path.exists(js):
            continue
        if a.prueba:
            al = prueba(e["texto"], mp3)
        else:
            if not a.voz:
                sys.exit("Falta --voz")
            prev = esc[i - 1]["texto"] if i and i < len(cfg["escenas"]) else None
            nxt = esc[i + 1]["texto"] if i + 1 < len(cfg["escenas"]) else None
            r = tts(a.voz, a.modelo, e["texto"], prev, nxt)
            open(mp3, "wb").write(base64.b64decode(r["audio_base64"]))
            al = r.get("alignment") or r["normalized_alignment"]
        json.dump({"texto": e["texto"], "alignment": al}, open(js, "w"), ensure_ascii=False)
        total += len(e["texto"])
        print(f"{e['id']}: {len(e['texto'])} caracteres", flush=True)
    print(f"Total pedido: {total} caracteres")


if __name__ == "__main__":
    main()
