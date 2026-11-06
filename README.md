# Local Audiobook Studio

A local Windows reading and listening app. It extracts real text from PDFs, EPUBs, images, articles, and plain text, prepares it for speech, and generates WAV audio with Kokoro ONNX. LFM3 is optional for complex narration cleanup. Source documents, models, metadata, and generated audio stay on the PC.

## Requirements

- Windows 10/11, Python 3.13, Node.js 24, FFmpeg on `PATH`
- WebView2 runtime for desktop mode (browser mode needs no WebView2)
- Tesseract on `PATH` for image and scanned PDF OCR
- A recent `llama-server.exe` with LFM3 support for optional LFM normalization

## Install and run

```powershell
cd C:\Code\tts
.\scripts\setup.ps1
.\scripts\browser.ps1
```

Open `http://127.0.0.1:8765` if the browser does not open automatically. For a native window after building the frontend:

```powershell
.\scripts\launch.ps1
```

For development hot reload, run `scripts\dev.ps1` and open `http://127.0.0.1:5173`. To build a portable directory:

```powershell
.\scripts\build.ps1
```

The build appears in `dist\LocalAudiobookStudio`. The directory build completed in the development environment at 197.3 MiB, without models. The packaged executable passed a backend startup and health-check smoke test. A visible desktop window and clean Windows machine have not yet been validated.

## Models

Open Settings to download the [Kokoro ONNX model and voice bundle](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1), about 354 MB together. Both files are required. The same screen can download the official [Liquid AI LFM3 Q4_K_M GGUF](https://huggingface.co/LiquidAI/LFM3-1.7B-GGUF), about 1.1 GB. Review the [LFM Open License v1.0](https://huggingface.co/LiquidAI/LFM3-1.7B-GGUF/blob/main/LICENSE) before installing it. Model downloads are initiated only by the user.

For LFM, download a current Windows x64 CPU release of [llama.cpp](https://github.com/ggml-org/llama.cpp/releases) and set `LAS_LLAMA_SERVER` to the full path of `llama-server.exe`. Build b12177 was used for a real local inference check. The LFM model runs in a persistent local process; `LAS_LFM_GPU_LAYERS` optionally sets GPU offload (default `0`). If the runtime or model is missing, rule normalization still works.

Data defaults to `%LOCALAPPDATA%\LocalAudiobookStudio`. Set `LAS_HOME` before launch to choose another location. Models are kept outside the executable. Generated audio is cached by text and voice. Export uses FFmpeg.

## What works

- Quick Read with pasted text, clipboard image OCR, voice selection, and real WAV playback
- PDF, EPUB, TXT, Markdown, image, and explicit public article URL import
- Persistent library, chapters, paragraph read along, bookmarks, and resume location
- Rule normalization with conservative optional LFM fallback
- Progressive segment synthesis with one segment of lookahead, audio caching, and MP3/WAV export API
- Local session token and loopback binding

## Current limits

- PDF extraction uses a basic two-column heuristic; unusual scientific layouts and tables may need manual cleanup.
- Text highlighting is at paragraph or segment level. PDF viewing uses the browser's PDF viewer rather than PDF.js.
- Model downloads verify minimum size and GGUF signature; they do not yet verify published SHA-256 hashes.
- Export UI currently chooses MP3 and runs synchronously; WAV is available through the API. M4B and cancellable export jobs are not implemented.
- Only a bounded one-segment lookahead is implemented. Seeking far ahead starts generation on demand and may buffer.
- Tesseract and FFmpeg are external tools. They are not bundled in the portable build.
- The LFM fidelity validator is deliberately conservative but cannot prove semantic equivalence.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
cd frontend; npm run build
```

The optional real model smoke scripts are `python -m scripts.model_smoke` and `python -m scripts.lfm_smoke`. They download models into `.runtime` in the repository and generate real outputs. The `.runtime` directory is ignored by Git.

Verified here on Windows 11 with Python 3.13.5 and Node 24.4.1: six backend tests passed; the React production build passed; Quick Read generated a real 3.48 second Kokoro WAV through the API and played it in the browser; LFM returned structured text using llama.cpp b12177; a complex academic passage took the LFM normalization path. PDF extraction was tested with a generated real PDF, and EPUB spine ordering with a generated ebook. The packaged executable passed a backend startup smoke check. OCR, article import, visible desktop window startup, and a clean machine portable launch remain unverified.

Observed model files: Kokoro ONNX 325,505,369 bytes; Kokoro voices 28,214,398 bytes; LFM Q4_K_M GGUF 1,099,627,808 bytes. Together with the 197.3 MiB directory build, the installed footprint is about 1.65 GiB before generated audio, FFmpeg, Tesseract, and the separate llama.cpp runtime.
