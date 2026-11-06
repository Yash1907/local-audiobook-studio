import multiprocessing
import os
import socket
import sys
import threading
import time
import webbrowser
import uvicorn
from backend.app.main import app

if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

PORT=8765
def server(): uvicorn.run(app,host='127.0.0.1',port=PORT,log_level='warning')
def wait_ready():
    for _ in range(100):
        try:
            with socket.create_connection(('127.0.0.1',PORT),timeout=.2): return
        except OSError: time.sleep(.1)
    raise RuntimeError('Backend failed to start')
if __name__=='__main__':
    multiprocessing.freeze_support()
    process=multiprocessing.Process(target=server)
    process.start()
    try:
        wait_ready()
        if os.environ.get('LAS_SMOKE_MODE') == '1':
            from urllib.request import urlopen
            with urlopen(f'http://127.0.0.1:{PORT}/api/health', timeout=5) as response:
                if response.status != 200: raise RuntimeError('Backend health check failed')
            raise SystemExit(0)
        try:
            import webview
            webview.create_window('Local Audiobook Studio',f'http://127.0.0.1:{PORT}',width=1260,height=840,min_size=(850,600))
            webview.start(gui='edgechromium')
        except ImportError:
            webbrowser.open(f'http://127.0.0.1:{PORT}')
            input('Press Enter to stop the studio...')
    finally:
        process.terminate();process.join(timeout=5)
        if process.is_alive(): process.kill()
