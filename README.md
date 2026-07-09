# Discord-MP3-Bot

[![CI](https://github.com/chaezuha/Discord-MP3-Bot/actions/workflows/ci.yml/badge.svg)](https://github.com/chaezuha/Discord-MP3-Bot/actions/workflows/ci.yml)

A self-hostable Discord bot that plays **your own local MP3 library** into
voice channels using **ffmpeg**. Point it at a folder of `.mp3` files and play
them by name — fuzzy search handles partial titles and typos.

## Features

- `/play` with fuzzy matching and slash-command autocomplete — partial titles,
  keywords, and misspellings all work
- `/search` shows the top matches with confidence scores
- Per-server queue with add, view, and skip
- Library auto-refreshes when you add or remove files (no restart needed)
- Slash commands, no privileged intents required

## Commands

| Command           | What it does                                                                                |
| ----------------- | ------------------------------------------------------------------------------------------- |
| `/play <query>`   | Play the best-matching MP3, or queue it if something is already playing. Asks you to narrow the query if matches are too close. |
| `/search <query>` | Show the top 10 fuzzy matches with confidence scores.                                       |
| `/queue`          | Show the current track and upcoming queue.                                                  |
| `/skip`           | Skip the current track.                                                                     |
| `/pause`          | Pause playback (stays connected).                                                           |
| `/resume`         | Resume paused playback.                                                                     |
| `/stop`           | Stop everything: clears the queue and disconnects.                                          |
| `/list [query]`   | List the library (up to 50 songs), optionally filtered.                                     |

## Setup

### 1. Create the Discord application

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create a **New Application**.
2. Under **Bot**, click **Reset Token** and copy the token (you'll need it for `.env`). No privileged intents are needed.
3. Invite the bot to your server with this URL (replace `YOUR_CLIENT_ID` with the Application ID from **General Information**):

   ```
   https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&scope=bot%20applications.commands&permissions=3165184
   ```

   (That permission set is: View Channels, Send Messages, Embed Links, Connect, Speak.)

### 2. Run with Docker Compose (recommended)

No clone needed — the prebuilt image ships with ffmpeg and everything else
included. Put [`compose.yaml`](compose.yaml) and a `.env` (see
[`.env.example`](.env.example)) in a folder, then in `.env` paste your bot
token and set `DISCORD_MUSIC_PATH` to the folder on your machine that holds
your `.mp3` files (compose mounts it into the container read-only), then:

```sh
docker compose up -d          # pulls the prebuilt GHCR image
docker compose logs -f        # follow logs
```

The compose file sets `restart: unless-stopped`, so the bot comes back on its
own after crashes and reboots.

To update, just run `up` again — the compose file pulls the latest image on
every start:

```sh
docker compose up -d
```

### Alternative: plain Docker

Same image, without Compose (again with your token in `.env`):

```sh
docker run --env-file .env \
  -e DISCORD_MUSIC_PATH=/music \
  -v "/path/to/your/mp3s:/music:ro" \
  ghcr.io/chaezuha/discord-mp3-bot:latest
```

Or build it yourself from a clone:

```sh
docker build -t discord-mp3-bot .
docker run --env-file .env \
  -e DISCORD_MUSIC_PATH=/music \
  -v "/path/to/your/mp3s:/music:ro" \
  discord-mp3-bot
```

### Alternative: run directly with Python

You'll need:

- Python 3.10+
- ffmpeg on your PATH:
  - macOS: `brew install ffmpeg`
  - Debian/Ubuntu: `sudo apt install ffmpeg`
  - Windows: `winget install ffmpeg` (or [download](https://ffmpeg.org/download.html))

Then install, configure, and run:

```sh
git clone https://github.com/chaezuha/Discord-MP3-Bot.git
cd Discord-MP3-Bot
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # then edit .env: bot token + music folder path
python mp3bot.py
```

### Slash-command sync

Whichever way you run it, slash commands sync automatically on startup. Global
sync can take up to an hour to show up in Discord — set `DISCORD_GUILD_ID` in
`.env` to your server's ID for instant sync while testing.

## Configuration (`.env`)

| Variable             | Required | Description                                                                                     |
| -------------------- | -------- | ------------------------------------------------------------------------------------------------ |
| `DISCORD_TOKEN`      | yes      | Bot token from the Developer Portal.                                                            |
| `DISCORD_MUSIC_PATH` | yes      | Absolute path to your `.mp3` folder. Under Docker Compose this is the host folder to mount.     |
| `DISCORD_GUILD_ID`   | no       | Server ID for instant slash-command sync during development.                                    |
| `DISCORD_OPUS_PATH`  | no       | Explicit path to libopus if your system doesn't auto-detect it (Python installs only).          |

## Development

```sh
pip install -r requirements-dev.txt
pytest            # search/catalog unit tests (no network needed)
ruff check .      # lint
ruff format .     # format
```

CI runs lint, the test suite on Python 3.10/3.12/3.14, and a Docker build
check on every push and PR. Pushes to `main` and `v*` tags publish the image
to GHCR.

## Notes

- Search ranks exact titles highest, then prefix and substring matches, then
  fuzzy/token similarity — if the top matches are too close, `/play` asks for
  a more specific query instead of guessing.
- The library is cached on the folder's modification time, so adding or
  removing files is picked up automatically without restarting the bot.
- Filenames become titles: `Bohemian Rhapsody.mp3` shows up as
  "Bohemian Rhapsody".
