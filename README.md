# YouTube: el juego

Partida para hacer crecer el canal, nivel a nivel.

| Nivel | Misión | Estado |
|---|---|---|
| 1 | Elegir el nicho | ✅ **Historias reales increíbles**, en español, sin salir en cámara, voz de ElevenLabs |
| 2 | Primer vídeo | ✅ Montado: vídeo largo + 3 Shorts + miniatura. Falta que lo subas ([texto para YouTube](canal/video-01/descripcion-youtube.md)) |
| 3 | Jefe final: el Algoritmo | 🔒 Ganchos en el primer segundo y retención |
| 4 | Modo constancia | 🔒 Calendario de guiones para varias semanas |

## Reglas de la partida

- **Tiempo:** 2 horas por semana.
- **Ritmo:** 1 vídeo largo al mes + 2–3 Shorts por semana, sacados del mismo guion.
- **Idioma:** primero español; los guiones que funcionen se traducen al inglés más adelante.
- **Voz:** ElevenLabs (plan gratuito). En los primeros vídeos se cita a ElevenLabs en la descripción. **Antes de pedir la monetización:** contratar un plan de pago (Starter o superior) y volver a generar la voz de los vídeos publicados con ese plan.
- **Toque humano:** guiones propios, investigados y con fuentes, para no chocar con la política de contenido «inauthentic» de YouTube.
- **Meta de monetización:** 1.000 suscriptores + 4.000 horas de visualización en 12 meses (o 10 M de visualizaciones de Shorts en 90 días).

## Herramientas

- `canal/herramientas/tts.py`: locución con ElevenLabs a partir de `escenas.json`.
- `canal/herramientas/montar.py`: monta el vídeo largo, los Shorts, la miniatura, los subtítulos y los capítulos.
- `.claude/skills/yt-*`: las 11 skills de [youtube-agent-skill](https://github.com/Jakeschincariol/youtube-agent-skill) (MIT), disponibles en las sesiones de Claude Code que se abran en este repositorio.
