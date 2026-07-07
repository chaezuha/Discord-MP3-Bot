import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
DISCORD_GUILD_ID = int(os.getenv("DISCORD_GUILD_ID") or "0")
DISCORD_OPUS_PATH = os.getenv("DISCORD_OPUS_PATH", "")

_music_path = os.getenv("DISCORD_MUSIC_PATH", "")
DISCORD_MUSIC_PATH: Path | None = Path(_music_path).expanduser() if _music_path else None
