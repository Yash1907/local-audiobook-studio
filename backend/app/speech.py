import asyncio
import os
from pathlib import Path
from .core import ROOT, connection, digest

MODEL = ROOT / 'models/kokoro/kokoro-v1.0.onnx'
VOICES = ROOT / 'models/kokoro/voices-v1.0.bin'
PRESETS = ['af_sarah','af_heart','af_bella','af_nicole','af_sky','am_adam','am_michael','bf_emma','bm_george']
_engine = None
_lock = asyncio.Lock()

def installed():
    return MODEL.is_file() and MODEL.stat().st_size > 1_000_000 and VOICES.is_file() and VOICES.stat().st_size > 1_000_000

def _create(text, voice, path):
    global _engine
    from kokoro_onnx import Kokoro
    import soundfile as sf
    if _engine is None:
        _engine = Kokoro(str(MODEL), str(VOICES))
    samples, sample_rate = _engine.create(text, voice=voice, speed=1.0, lang='en-us' if voice[0] == 'a' else 'en-gb')
    temporary = path.with_suffix('.tmp.wav')
    sf.write(temporary, samples, sample_rate)
    os.replace(temporary, path)
    return len(samples) / sample_rate

async def synthesize(text, voice):
    if not installed():
        raise FileNotFoundError('Kokoro model and voices are required. Install them in Settings.')
    if voice not in PRESETS:
        raise ValueError('Unsupported voice')
    key = digest('kokoro-v1.0', text, voice, 1.0)
    path = ROOT / 'audio' / f'{key}.wav'
    with connection() as db:
        row = db.execute('SELECT duration FROM audio WHERE cache_key=?', (key,)).fetchone()
    if row and path.exists():
        return key, row['duration']
    async with _lock:
        if path.exists() and row:
            return key, row['duration']
        duration = await asyncio.to_thread(_create, text, voice, path)
        with connection() as db:
            db.execute('INSERT OR REPLACE INTO audio VALUES(?,?,?)', (key, str(path), duration))
        return key, duration
