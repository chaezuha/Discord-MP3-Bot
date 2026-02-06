# Discord MP3 Bot

A Discord slash-command music bot that plays local `.mp3` files.

This version includes:
- Fuzzy song search with ranking
- Slash command autocomplete for `/play`
- Better queue/playback handling
- Environment-variable configuration (with backward-compatible `config.py` aliases)

## Requirements

- Python `3.10+`
- `ffmpeg` installed and available in your PATH
- `discord.py` with voice support
- Optional: explicit Opus path (if your system does not auto-detect it)

## Install

1. Install dependencies:
```bash
pip install -U "discord.py[voice]"
```
2. Clone this repository.
3. Set environment variables:
```bash
export DISCORD_TOKEN="your_bot_token"
export DISCORD_GUILD_ID="your_guild_id"      # optional, but recommended for fast slash sync
export DISCORD_MUSIC_PATH="/absolute/path/to/your/mp3/folder"
export DISCORD_OPUS_PATH="/absolute/path/to/libopus"  # optional
```
4. Run:
```bash
python mp3bot.py
```

## Commands

- `/play <query>`: Finds the best match and plays/queues it.
- `/search <query>`: Shows top fuzzy matches with confidence scores.
- `/queue`: Shows current song + queued songs.
- `/skip`: Skips current song.
- `/pause`: Pauses playback.
- `/resume`: Resumes playback.
- `/stop`: Clears queue and disconnects.
- `/list [query]`: Lists songs, optionally filtered by query.

## Search behavior

- Exact title matches rank highest.
- Prefix and substring matches are prioritized.
- Token overlap + fuzzy similarity help rank partial/misspelled queries.
- If matches are too close, `/play` asks for a more specific query.

## Discord OAuth setup

### Scopes
- `bot`
- `applications.commands`

### Bot permissions
- View Channels
- Send Messages
- Use Application Commands
- Connect
- Speak

## Notes

- Guild sync is used automatically when `DISCORD_GUILD_ID` is set (faster command updates).
- Existing `config.py` placeholders still work as aliases, but env vars are preferred.
