# Discord MP3 Bot

A Discord slash-command music bot that plays local `.mp3` files.

This version includes:
- Fuzzy song search with ranking
- Slash command autocomplete for `/play`
- Better queue/playback handling
- Configuration via a `.env` file (or plain environment variables)

## Requirements

- Python `3.10+`
- `ffmpeg` installed and available in your PATH
- Optional: explicit Opus path (if your system does not auto-detect it)

## Install

1. Clone this repository.
2. Create a virtual environment and install dependencies:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
3. Configure the bot:
```bash
cp .env.example .env
# then edit .env and fill in your values
```
The `.env` file is git-ignored, so your token stays out of version control. Plain
environment variables also work and take precedence over `.env` values.
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
- Without `DISCORD_GUILD_ID`, commands sync globally and can take up to an hour to appear.
