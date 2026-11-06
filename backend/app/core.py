import hashlib
import json
import os
import sqlite3
from pathlib import Path

ROOT = Path(os.environ.get('LAS_HOME') or Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'LocalAudiobookStudio')
for name in ('documents', 'audio', 'models/kokoro', 'models/lfm', 'exports'):
    (ROOT / name).mkdir(parents=True, exist_ok=True)
DB = ROOT / 'studio.sqlite3'

DEFAULTS = {'voice': 'af_sarah', 'playback_speed': 1.0, 'mode': 'balanced', 'citations': 'skip', 'footnotes': 'skip', 'lfm_enabled': True, 'theme': 'light', 'offline_only': False}

def connection():
    db = sqlite3.connect(DB, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db

def init_db():
    with connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,title TEXT NOT NULL,author TEXT,source_type TEXT NOT NULL,source_path TEXT,source_url TEXT,source_hash TEXT,imported_at TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'ready',warnings TEXT NOT NULL DEFAULT '[]');
        CREATE TABLE IF NOT EXISTS chapters(id TEXT PRIMARY KEY,document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,title TEXT NOT NULL,position INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS segments(id TEXT PRIMARY KEY,chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,position INTEGER NOT NULL,original_text TEXT NOT NULL,page_number INTEGER);
        CREATE TABLE IF NOT EXISTS normalization(cache_key TEXT PRIMARY KEY,text TEXT NOT NULL,method TEXT NOT NULL,warnings TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audio(cache_key TEXT PRIMARY KEY,path TEXT NOT NULL,duration REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS progress(document_id TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,segment_id TEXT,offset REAL NOT NULL DEFAULT 0,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS bookmarks(id TEXT PRIMARY KEY,document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,segment_id TEXT NOT NULL,label TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        ''')

def settings():
    with connection() as db:
        return {**DEFAULTS, **{r['key']: json.loads(r['value']) for r in db.execute('SELECT * FROM settings')}}

def digest(*parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

def rows(sql, args=()):
    with connection() as db:
        return [dict(r) for r in db.execute(sql, args)]
