import asyncio
import os
import zipfile
from pathlib import Path

import httpx

os.environ.setdefault('LAS_HOME', str(Path(__file__).resolve().parents[1] / '.runtime'))

from backend.app.core import ROOT, init_db
from backend.app.main import download_model, jobs
from backend.app.lfm import lfm

async def main():
    init_db()
    jobs['lfm']={'id':'lfm','name':'lfm','state':'queued','bytes':0,'total':0,'error':''}
    await download_model('lfm','lfm')
    print('model',jobs['lfm'],flush=True)
    if jobs['lfm']['state']!='ready': raise RuntimeError(jobs['lfm']['error'])
    release='b12177'
    url=f'https://github.com/ggml-org/llama.cpp/releases/download/{release}/llama-{release}-bin-win-cpu-x64.zip'
    archive=ROOT/'models'/'llama.zip'
    if not archive.exists():
        async with httpx.AsyncClient(follow_redirects=True,timeout=120) as client:
            response=await client.get(url)
            response.raise_for_status()
            archive.write_bytes(response.content)
    destination=ROOT/'models'/'llama'
    destination.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as package:
        for item in package.infolist():
            if item.filename.endswith('llama-server.exe') or item.filename.lower().endswith('.dll'):
                target=destination/Path(item.filename).name
                target.write_bytes(package.read(item))
    executable=destination/'llama-server.exe'
    os.environ['LAS_LLAMA_SERVER']=str(executable)
    print('runtime',executable,executable.exists(),flush=True)
    try:
        result=await lfm.transform('smoke-1','The correlation was significant (p < 0.01).','balanced','skip','skip')
        print('normalized',result,flush=True)
    finally:
        await lfm.stop()

if __name__=='__main__': asyncio.run(main())
