# Implementation notes

The FastAPI service owns SQLite metadata, extraction, normalization, inference, model downloads, and audio files. React owns navigation, text editing, and playback. No document content is sent to a remote inference service. Article import and user initiated model downloads are the only intentional network paths.

Each imported source is copied to local storage. Chapters and speech segments carry source text separately from normalized text and cached audio. Speech uses a single Kokoro instance behind an async lock. LFM starts lazily and remains loaded until shutdown. Generated WAV files use atomic replacement and content hashes.

The UI asks for the next segment while the current one plays. Audio generation is a blocking API call performed off the event loop; a future job queue would allow broader prefetching and cancellation. Progress and bookmarks are stored in SQLite. The frontend stores the active segment and intra-segment offset for resume.

API security uses a random process session token, origin and Host checks, upload limits, and path-safe IDs. Article fetching checks public DNS addresses and redirects, but does not pin the resolved IP across the connection; hardening this is required before exposing article retrieval beyond the local single-user application.
