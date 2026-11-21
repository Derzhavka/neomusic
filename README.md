# NEO MUSIC 🎧

Telegram-only AI music bot. No Mini App or website.

Features: AI DJ mood-to-track mixes, Deezer search, 30-second previews, favorites, saved AI playlists, mood presets, daily mix and profile.

## Environment
- BOT_TOKEN — Telegram bot token
- HMS_API_KEY — AI provider key (OpenAI-compatible)
- DEEPSEEK_BASE_URL — defaults to https://100milionseek.top/v1
- DEEPSEEK_MODEL — defaults to deepseek-v4.1-flash-free
- DATABASE_PATH — defaults to /data/neomusic.sqlite3

Tracks are discovered via Deezer's public API; previews and links are provided, no full tracks are hosted.

Run: pip install -r requirements.txt && python main.py
