import asyncio
import json
import os
from pathlib import Path
import httpx
from .core import ROOT
from .normalization import PROMPT

MODEL = ROOT / 'models/lfm/LFM3-1.7B-Q4_K_M.gguf'

class LFM:
    def __init__(self):
        self.process = None
        self.port = 18987
        self.lock = asyncio.Lock()

    def available(self):
        from shutil import which
        executable=os.environ.get('LAS_LLAMA_SERVER','llama-server.exe')
        return MODEL.is_file() and MODEL.stat().st_size > 1_000_000 and (Path(executable).is_file() or which(executable) is not None)

    async def start(self):
        if self.process and self.process.returncode is None:
            return
        executable = os.environ.get('LAS_LLAMA_SERVER', 'llama-server.exe')
        if not MODEL.is_file():
            raise RuntimeError('LFM model is not installed')
        from shutil import which
        if not Path(executable).is_file() and not which(executable):
            raise RuntimeError('Set LAS_LLAMA_SERVER to a recent llama-server.exe with LFM3 support')
        self.process = await asyncio.create_subprocess_exec(executable, '-m', str(MODEL), '--host', '127.0.0.1', '--port', str(self.port), '-c', '4096', '-ngl', os.environ.get('LAS_LFM_GPU_LAYERS', '0'), '--reasoning', 'off', stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        async with httpx.AsyncClient(timeout=2) as client:
            for _ in range(100):
                if self.process.returncode is not None:
                    raise RuntimeError('llama-server exited while loading LFM')
                try:
                    if (await client.get(f'http://127.0.0.1:{self.port}/health')).status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(.3)
        raise TimeoutError('LFM load timed out')

    async def transform(self, segment_id, text, mode, citations, footnotes):
        async with self.lock:
            await self.start()
            payload = {'messages': [{'role':'system','content':PROMPT}, {'role':'user','content':json.dumps({'segment_id':segment_id,'mode':mode,'citations':citations,'footnotes':footnotes,'source_text':text})}], 'temperature':.1,'max_tokens':600,'reasoning_effort':'none','chat_template_kwargs':{'enable_thinking':False},'response_format':{'type':'json_object'}}
            async with httpx.AsyncClient(timeout=90) as client:
                response = await client.post(f'http://127.0.0.1:{self.port}/v1/chat/completions', json=payload)
                response.raise_for_status()
            choice=response.json()['choices'][0]
            content=choice['message'].get('content') or ''
            if not content.strip():
                raise ValueError(f'LFM returned empty content (finish_reason={choice.get("finish_reason")})')
            item = json.loads(content)
            if item.get('segment_id') != segment_id:
                raise ValueError('LFM returned wrong segment identifier')
            return item['normalized_text']

    async def stop(self):
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), 5)
            except TimeoutError:
                self.process.kill()

lfm = LFM()
