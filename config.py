import os
from pathlib import Path

# Preferred environment variable configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "Insert Token")
DISCORD_GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "0"))
DISCORD_OPUS_PATH = os.getenv("DISCORD_OPUS_PATH", "")
DISCORD_MUSIC_PATH = Path(os.getenv("DISCORD_MUSIC_PATH", "File Path Location")).expanduser()

# Backward-compatible aliases for older code
TOKEN = DISCORD_TOKEN
guildId = DISCORD_GUILD_ID
opusLoc = DISCORD_OPUS_PATH
filePath = str(DISCORD_MUSIC_PATH)
