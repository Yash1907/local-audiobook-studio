import asyncio
import hashlib
import ipaddress
import json
import mimetypes
import os
import secrets
import socket
import subprocess
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .core import ROOT, connection, digest, init_db, rows, settings
from .extraction import extract, Extracted, paragraphs
from .lfm import lfm, MODEL as LFM_MODEL
from .normalization import normalize
from .speech import MODEL as KOKORO_MODEL, VOICES, PRESETS, installed, synthesize
from .segmentation import split_for_speech

TOKEN = secrets.token_urlsafe(32)
jobs = {}
MODEL_FILES = {
 'kokoro_model': ('https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx', KOKORO_MODEL, 300_000_000),
 'kokoro_voices': ('https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin', VOICES, 20_000_000),
 'lfm': ('https://huggingface.co/LiquidAI/LFM3-1.7B-GGUF/resolve/main/LFM3-1.7B-Q4_K_M.gguf', LFM_MODEL, 1_000_000_000)
}

@asynccontextmanager
async def lifespan(app):
    init_db()
    yield
    await lfm.stop()

app = FastAPI(title='Local Audiobook Studio', lifespan=lifespan)

@app.middleware('http')
async def security(request: Request, call_next):
    host = request.headers.get('host', '').split(':')[0]
    if host not in ('127.0.0.1','localhost','testserver'):
        return _error(403, 'Loopback access only')
    if request.url.path.startswith('/api/') and request.method not in ('GET','HEAD'):
        origin = request.headers.get('origin')
        if origin and urlparse(origin).hostname not in ('127.0.0.1','localhost'):
            return _error(403, 'Invalid origin')
        if request.headers.get('x-studio-token') != TOKEN:
            return _error(403, 'Invalid session token')
    return await call_next(request)

def _error(code, message):
    from fastapi.responses import JSONResponse
    return JSONResponse({'detail':message}, status_code=code)

def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return uuid.uuid4().hex

class SettingsPatch(BaseModel):
    voice: str | None = None
    playback_speed: float | None = Field(None, ge=.5, le=2.5)
    mode: str | None = None
    citations: str | None = None
    footnotes: str | None = None
    lfm_enabled: bool | None = None
    theme: str | None = None
    offline_only: bool | None = None

class TextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100000)
    voice: str = 'af_sarah'
    mode: str = 'balanced'
    citations: str = 'skip'
    footnotes: str = 'skip'

class GenerateRequest(BaseModel):
    segment_id: str
    voice: str = 'af_sarah'
    mode: str = 'balanced'
    citations: str = 'skip'
    footnotes: str = 'skip'

class ProgressRequest(BaseModel):
    segment_id: str
    offset: float = Field(ge=0)

class BookmarkRequest(BaseModel):
    segment_id: str
    label: str = ''

class URLRequest(BaseModel):
    url: str

class ModelRequest(BaseModel):
    name: str

async def download_model(job_id, name):
    url,path,minimum=MODEL_FILES[name]
    if path.exists() and path.stat().st_size>=minimum:
        jobs[job_id].update(state='ready',bytes=path.stat().st_size,total=path.stat().st_size)
        return
    part=path.with_suffix(path.suffix+'.part')
    jobs[job_id].update(state='downloading',bytes=part.stat().st_size if part.exists() else 0)
    try:
        start=part.stat().st_size if part.exists() else 0
        headers={'Range':f'bytes={start}-'} if start else {}
        async with httpx.AsyncClient(follow_redirects=True,timeout=httpx.Timeout(30,read=60)) as client:
            async with client.stream('GET',url,headers=headers) as response:
                response.raise_for_status()
                if start and response.status_code!=206:
                    start=0
                total=int(response.headers.get('content-length','0'))+start
                jobs[job_id]['total']=total
                with part.open('ab' if start else 'wb') as output:
                    async for chunk in response.aiter_bytes(1024*256):
                        output.write(chunk)
                        jobs[job_id]['bytes']+=len(chunk)
        if part.stat().st_size<minimum: raise ValueError('Downloaded file is incomplete')
        if name=='lfm' and part.open('rb').read(4)!=b'GGUF': raise ValueError('Invalid GGUF file')
        if name=='kokoro_model' and not part.open('rb').read(4): raise ValueError('Invalid ONNX file')
        os.replace(part,path)
        jobs[job_id]['state']='ready'
    except Exception as exc:
        jobs[job_id].update(state='failed',error=str(exc))

@app.post('/api/models/install')
async def install_model(body:ModelRequest):
    if body.name not in MODEL_FILES: raise HTTPException(422,'Unknown model')
    if settings()['offline_only']: raise HTTPException(403,'Offline-only mode is enabled')
    job_id=uid()
    jobs[job_id]={'id':job_id,'name':body.name,'state':'queued','bytes':0,'total':0,'error':''}
    asyncio.create_task(download_model(job_id,body.name))
    return jobs[job_id]

@app.get('/api/jobs/{job_id}')
def get_job(job_id:str):
    if job_id not in jobs: raise HTTPException(404,'Job not found')
    return jobs[job_id]

@app.get('/api/session')
def session(): return {'token':TOKEN}

@app.get('/api/health')
def health(): return {'ok':True}

@app.get('/api/settings')
def get_settings(): return settings()

@app.patch('/api/settings')
def patch_settings(patch:SettingsPatch):
    values = patch.model_dump(exclude_none=True)
    for key, allowed in {'voice':PRESETS,'mode':['faithful','balanced','enhanced'],'citations':['skip','natural','all'],'footnotes':['skip','end','inline'],'theme':['light','dark']}.items():
        if key in values and values[key] not in allowed: raise HTTPException(422, f'Invalid {key}')
    with connection() as db:
        for key,value in values.items(): db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(key,json.dumps(value)))
    return settings()

@app.get('/api/models')
def models():
    return {'kokoro':{'installed':installed(),'path':str(KOKORO_MODEL)},'lfm':{'installed':LFM_MODEL.is_file() and LFM_MODEL.stat().st_size > 1_000_000,'path':str(LFM_MODEL),'runtime_ready':lfm.available()},'ocr':{'installed':__import__('shutil').which('tesseract') is not None},'storage':str(ROOT)}

@app.get('/api/voices')
def voices(): return {'voices':PRESETS}

@app.get('/api/documents')
def documents():
    return rows('SELECT d.*,p.segment_id AS progress_segment FROM documents d LEFT JOIN progress p ON p.document_id=d.id ORDER BY d.imported_at DESC')

def store_extracted(result:Extracted, source_type, source_path=None, source_url=None, source_hash=None):
    doc_id = uid()
    with connection() as db:
        db.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?)',(doc_id,result.title,result.author,source_type,source_path,source_url,source_hash,now(),'ready',json.dumps(result.warnings)))
        for ci,(title,blocks) in enumerate(result.chapters):
            chapter_id=uid()
            db.execute('INSERT INTO chapters VALUES(?,?,?,?)',(chapter_id,doc_id,title,ci))
            position=0
            for text,page in blocks:
                for chunk in split_for_speech(text):
                    db.execute('INSERT INTO segments VALUES(?,?,?,?,?)',(uid(),chapter_id,position,chunk,page))
                    position+=1
    return doc_id

@app.post('/api/documents')
async def import_document(file:UploadFile=File(...)):
    data=await file.read(30_000_001)
    if len(data)>30_000_000: raise HTTPException(413,'File exceeds 30 MB')
    name=Path(file.filename or 'upload.txt').name
    try: result=await asyncio.to_thread(extract,data,name)
    except Exception as exc: raise HTTPException(422,str(exc))
    path=ROOT/'documents'/f'{uid()}{Path(name).suffix.lower()}'
    path.write_bytes(data)
    doc_id=store_extracted(result,Path(name).suffix.lower().lstrip('.'),str(path),source_hash=hashlib.sha256(data).hexdigest())
    return {'id':doc_id,'warnings':result.warnings}

def public_ip(host):
    infos=socket.getaddrinfo(host,None,type=socket.SOCK_STREAM)
    return all(ipaddress.ip_address(info[4][0]).is_global for info in infos)

@app.post('/api/articles')
async def import_article(body:URLRequest):
    if settings()['offline_only']: raise HTTPException(403,'Offline-only mode is enabled')
    parsed=urlparse(body.url)
    if parsed.scheme not in ('https','http') or not parsed.hostname or parsed.port not in (None,80,443) or not public_ip(parsed.hostname): raise HTTPException(422,'Use a public HTTP or HTTPS article URL')
    try:
        async with httpx.AsyncClient(follow_redirects=False,timeout=20) as client:
            url=body.url
            for _ in range(5):
                response=await client.get(url)
                if response.status_code in (301,302,303,307,308):
                    from urllib.parse import urljoin
                    url=urljoin(url,response.headers['location'])
                    target=urlparse(url)
                    if target.scheme not in ('http','https') or not target.hostname or target.port not in (None,80,443) or not public_ip(target.hostname): raise ValueError('Redirect to local address blocked')
                    continue
                response.raise_for_status()
                if len(response.content)>5_000_000: raise ValueError('Article exceeds 5 MB')
                break
            else: raise ValueError('Too many redirects')
        import trafilatura
        meta=trafilatura.extract(response.text,output_format='json',with_metadata=True)
        if not meta: raise ValueError('Article text not found')
        item=json.loads(meta)
        result=Extracted(item.get('title') or url,item.get('author') or '', [('Article',[(p,None) for p in paragraphs(item['text'])])])
        return {'id':store_extracted(result,'article',source_url=url)}
    except Exception as exc: raise HTTPException(422,str(exc))

@app.post('/api/ocr')
async def ocr(file:UploadFile=File(...)):
    data=await file.read(10_000_001)
    if len(data)>10_000_000: raise HTTPException(413,'Image exceeds 10 MB')
    try:
        result=await asyncio.to_thread(extract,data,file.filename or 'image.png')
        return {'text':'\n\n'.join(x for _,blocks in result.chapters for x,_ in blocks),'warnings':result.warnings}
    except Exception as exc: raise HTTPException(422,str(exc))

@app.get('/api/documents/{document_id}')
def document(document_id:str):
    matches=rows('SELECT * FROM documents WHERE id=?',(document_id,))
    if not matches: raise HTTPException(404,'Document not found')
    doc=matches[0]
    doc['chapters']=rows('SELECT * FROM chapters WHERE document_id=? ORDER BY position',(document_id,))
    doc['segments']=rows('SELECT s.*,c.title AS chapter_title,c.position AS chapter_position FROM segments s JOIN chapters c ON c.id=s.chapter_id WHERE c.document_id=? ORDER BY c.position,s.position',(document_id,))
    progress=rows('SELECT * FROM progress WHERE document_id=?',(document_id,))
    doc['progress']=progress[0] if progress else None
    doc['bookmarks']=rows('SELECT * FROM bookmarks WHERE document_id=? ORDER BY created_at',(document_id,))
    return doc

@app.delete('/api/documents/{document_id}')
def delete_document(document_id:str):
    matches=rows('SELECT source_path FROM documents WHERE id=?',(document_id,))
    if not matches: raise HTTPException(404,'Document not found')
    with connection() as db: db.execute('DELETE FROM documents WHERE id=?',(document_id,))
    if matches[0]['source_path']: Path(matches[0]['source_path']).unlink(missing_ok=True)
    return {'deleted':True}

@app.get('/api/documents/{document_id}/source')
def source(document_id:str):
    match=rows('SELECT source_path FROM documents WHERE id=?',(document_id,))
    if not match or not match[0]['source_path']: raise HTTPException(404,'Source unavailable')
    return FileResponse(match[0]['source_path'])

@app.post('/api/documents/{document_id}/progress')
def save_progress(document_id:str,body:ProgressRequest):
    match=rows('SELECT s.id FROM segments s JOIN chapters c ON c.id=s.chapter_id WHERE c.document_id=? AND s.id=?',(document_id,body.segment_id))
    if not match: raise HTTPException(404,'Segment not found')
    with connection() as db: db.execute('INSERT OR REPLACE INTO progress VALUES(?,?,?,?)',(document_id,body.segment_id,body.offset,now()))
    return {'saved':True}

@app.post('/api/documents/{document_id}/bookmarks')
def add_bookmark(document_id:str,body:BookmarkRequest):
    match=rows('SELECT s.id FROM segments s JOIN chapters c ON c.id=s.chapter_id WHERE c.document_id=? AND s.id=?',(document_id,body.segment_id))
    if not match: raise HTTPException(404,'Segment not found')
    bookmark={'id':uid(),'document_id':document_id,'segment_id':body.segment_id,'label':body.label or 'Bookmark','created_at':now()}
    with connection() as db: db.execute('INSERT INTO bookmarks VALUES(?,?,?,?,?)',tuple(bookmark.values()))
    return bookmark

@app.delete('/api/bookmarks/{bookmark_id}')
def delete_bookmark(bookmark_id:str):
    with connection() as db: db.execute('DELETE FROM bookmarks WHERE id=?',(bookmark_id,))
    return {'deleted':True}

@app.post('/api/quick-read')
async def quick_read(body:TextRequest):
    if body.voice not in PRESETS: raise HTTPException(422,'Unsupported voice')
    chunks=[part for p in paragraphs(body.text) for part in split_for_speech(p)]
    return {'segments':[{'id':digest('quick',i,part),'original_text':part} for i,part in enumerate(chunks)]}

@app.post('/api/narration/generate')
async def generate(body:GenerateRequest):
    matches=rows('SELECT original_text FROM segments WHERE id=?',(body.segment_id,))
    if not matches: raise HTTPException(404,'Segment not found')
    return await generate_text(body.segment_id,matches[0]['original_text'],body.voice,body.mode,body.citations,body.footnotes)

@app.post('/api/narration/quick-generate')
async def quick_generate(body:TextRequest):
    return await generate_text(digest(body.text),body.text,body.voice,body.mode,body.citations,body.footnotes)

async def generate_text(segment_id,text,voice,mode,citations,footnotes):
    options=settings()
    norm=await normalize(segment_id,text,mode,citations,footnotes,lfm if options['lfm_enabled'] and LFM_MODEL.is_file() else None)
    try: audio_id,duration=await synthesize(norm['text'],voice)
    except (FileNotFoundError,ValueError) as exc: raise HTTPException(409,str(exc))
    return {'audio_id':audio_id,'duration':duration,'normalized_text':norm['text'],'method':norm['method'],'warnings':norm['warnings']}

@app.get('/api/audio/{audio_id}')
def audio(audio_id:str):
    if not len(audio_id)==64 or any(c not in '0123456789abcdef' for c in audio_id): raise HTTPException(404,'Audio not found')
    path=ROOT/'audio'/f'{audio_id}.wav'
    if not path.is_file(): raise HTTPException(404,'Audio not found')
    return FileResponse(path,media_type='audio/wav')

@app.post('/api/export/{document_id}')
async def export(document_id:str, request:Request):
    voice=request.query_params.get('voice','af_sarah')
    format=request.query_params.get('format','mp3')
    if format not in ('wav','mp3'): raise HTTPException(422,'Use WAV or MP3')
    doc=document(document_id)
    if not doc['segments']: raise HTTPException(422,'Document has no text')
    files=[]
    for segment in doc['segments']:
        result=await generate_text(segment['id'],segment['original_text'],voice,settings()['mode'],settings()['citations'],settings()['footnotes'])
        files.append(ROOT/'audio'/f"{result['audio_id']}.wav")
    output=ROOT/'exports'/f'{document_id}-{voice}.{format}'
    listfile=ROOT/'exports'/f'{uid()}.txt'
    listfile.write_text(''.join("file '"+str(f).replace("'","'\\''")+"'\n" for f in files),encoding='utf-8')
    try:
        command=['ffmpeg','-y','-f','concat','-safe','0','-i',str(listfile),'-c:a','pcm_s16le' if format=='wav' else 'libmp3lame','-q:a','3',str(output)]
        result=await asyncio.to_thread(subprocess.run,command,capture_output=True,text=True,timeout=600)
        if result.returncode: raise HTTPException(500,result.stderr[-500:])
    finally: listfile.unlink(missing_ok=True)
    return {'path':str(output),'download':f'/api/exports/{output.name}'}

@app.get('/api/exports/{filename}')
def exported(filename:str):
    path=ROOT/'exports'/Path(filename).name
    if not path.is_file(): raise HTTPException(404,'Export not found')
    return FileResponse(path,filename=path.name)

FRONTEND=(Path(getattr(sys,'_MEIPASS'))/'frontend/dist') if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[2]/'frontend/dist'
mimetypes.add_type('text/javascript','.mjs')
if FRONTEND.exists(): app.mount('/',StaticFiles(directory=FRONTEND,html=True),name='frontend')
