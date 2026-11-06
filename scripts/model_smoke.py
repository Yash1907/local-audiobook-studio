import asyncio
import os
from pathlib import Path

os.environ.setdefault('LAS_HOME', str(Path(__file__).resolve().parents[1] / '.runtime'))

from backend.app.main import download_model, jobs
from backend.app.speech import synthesize
from backend.app.core import init_db

async def main():
    init_db()
    for name in ('kokoro_model', 'kokoro_voices'):
        jobs[name] = {'id':name,'name':name,'state':'queued','bytes':0,'total':0,'error':''}
        await download_model(name,name)
        print(name,jobs[name],flush=True)
        if jobs[name]['state'] != 'ready':
            raise RuntimeError(jobs[name]['error'])
    audio_id, duration = await synthesize('This is a real local audiobook test.', 'af_sarah')
    print('WAV',audio_id,duration,flush=True)

if __name__ == '__main__':
    asyncio.run(main())
