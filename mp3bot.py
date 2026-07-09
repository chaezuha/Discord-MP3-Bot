import asyncio
import logging
import re
from collections import deque
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from config import DISCORD_GUILD_ID, DISCORD_MUSIC_PATH, DISCORD_OPUS_PATH, DISCORD_TOKEN


def normalize_text(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return " ".join(cleaned.split())


@dataclass(slots=True)
class Song:
    path: Path
    title: str


@dataclass
class GuildPlayer:
    queue: deque[Song] = field(default_factory=deque)
    current_song: Song | None = None
    voice_client: discord.VoiceClient | None = None
    text_channel: discord.abc.Messageable | None = None


log = logging.getLogger("mp3bot")


class MP3Bot(commands.Bot):
    async def setup_hook(self) -> None:
        # Sync commands here rather than in on_ready: setup_hook runs exactly once,
        # while on_ready fires again on every reconnect.
        if DISCORD_GUILD_ID:
            guild = discord.Object(id=DISCORD_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info("Synced %d command(s) to guild %d.", len(synced), DISCORD_GUILD_ID)
        else:
            synced = await self.tree.sync()
            log.info("Synced %d global command(s).", len(synced))


intents = discord.Intents(guilds=True, voice_states=True)
# Only slash commands are registered; when_mentioned avoids needing the
# message-content intent that a text prefix would warn about.
bot = MP3Bot(command_prefix=commands.when_mentioned, intents=intents)

players: dict[int, GuildPlayer] = {}


def get_player(guild_id: int) -> GuildPlayer:
    return players.setdefault(guild_id, GuildPlayer())


_catalog_cache: tuple[float, list[Song]] | None = None


def get_catalog() -> list[Song]:
    global _catalog_cache

    if DISCORD_MUSIC_PATH is None or not DISCORD_MUSIC_PATH.is_dir():
        return []

    # Cache on the folder's mtime so autocomplete doesn't re-scan the disk on
    # every keystroke; adding/removing files bumps the mtime and refreshes it.
    mtime = DISCORD_MUSIC_PATH.stat().st_mtime
    if _catalog_cache is not None and _catalog_cache[0] == mtime:
        return _catalog_cache[1]

    files = sorted(DISCORD_MUSIC_PATH.glob("*.mp3"), key=lambda item: item.name.lower())
    catalog = [Song(path=path, title=path.stem) for path in files]
    _catalog_cache = (mtime, catalog)
    return catalog


def score_song(song: Song, query: str) -> int:
    normalized_query = normalize_text(query)
    normalized_title = normalize_text(song.title)
    query_tokens = set(normalized_query.split())
    title_tokens = set(normalized_title.split())

    if normalized_query == normalized_title:
        return 100
    if normalized_title.startswith(normalized_query):
        return 95
    if normalized_query in normalized_title:
        return 88

    similarity = SequenceMatcher(None, normalized_query, normalized_title).ratio()
    overlap = (len(query_tokens & title_tokens) / len(query_tokens)) if query_tokens else 0.0

    score = int(max(similarity * 75, overlap * 70))
    if query_tokens and query_tokens.issubset(title_tokens):
        score = min(99, score + 15)
    return score


def search_songs(query: str, *, limit: int = 10) -> list[tuple[Song, int]]:
    catalog = get_catalog()
    if not catalog:
        return []

    normalized_query = normalize_text(query)
    if not normalized_query:
        return [(song, 0) for song in catalog[:limit]]

    ranked: list[tuple[Song, int]] = []
    for song in catalog:
        score = score_song(song, normalized_query)
        if score >= 35:
            ranked.append((song, score))

    ranked.sort(key=lambda item: (-item[1], item[0].title.lower()))
    return ranked[:limit]


async def ensure_voice(interaction: discord.Interaction, player: GuildPlayer) -> discord.VoiceClient | None:
    if interaction.guild is None:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return None

    if interaction.user.voice is None or interaction.user.voice.channel is None:
        await interaction.response.send_message(
            "You need to be in a voice channel to use this command.",
            ephemeral=True,
        )
        return None

    voice_channel = interaction.user.voice.channel

    try:
        if player.voice_client is None or not player.voice_client.is_connected():
            player.voice_client = await voice_channel.connect(timeout=15)
        elif player.voice_client.channel != voice_channel:
            await player.voice_client.move_to(voice_channel)
    except (asyncio.TimeoutError, discord.ClientException, discord.opus.OpusNotLoaded) as exc:
        log.warning("Could not connect to voice channel %s: %s", voice_channel, exc)
        await interaction.response.send_message(
            "Could not connect to your voice channel. Please try again.",
            ephemeral=True,
        )
        return None

    return player.voice_client


def start_playback(guild_id: int, song: Song) -> bool:
    player = get_player(guild_id)
    voice_client = player.voice_client
    if voice_client is None or not voice_client.is_connected():
        player.current_song = None
        return False

    try:
        source = discord.FFmpegPCMAudio(str(song.path), before_options="-nostdin", options="-vn")
    except discord.ClientException as exc:
        # Most commonly: ffmpeg is not installed / not in PATH.
        log.error("Could not create audio source for %s: %s", song.path, exc)
        player.current_song = None
        return False

    player.current_song = song

    def after_playback(error: Exception | None) -> None:
        # Runs in the audio thread; hand the coroutine back to the event loop.
        asyncio.run_coroutine_threadsafe(handle_song_end(guild_id, error), bot.loop)

    voice_client.play(source, after=after_playback)
    return True


async def play_next_song(guild_id: int, *, announce: bool = False) -> None:
    player = get_player(guild_id)
    if not player.queue:
        player.current_song = None
        return

    next_song = player.queue.popleft()
    if not start_playback(guild_id, next_song):
        return

    if announce and player.text_channel is not None:
        await player.text_channel.send(f"Now playing: **{next_song.title}**")


async def handle_song_end(guild_id: int, error: Exception | None) -> None:
    player = get_player(guild_id)

    if error:
        log.error("Playback error in guild %d: %s", guild_id, error)
        if player.text_channel is not None:
            await player.text_channel.send(f"Playback error: `{error}`")

    player.current_song = None
    await play_next_song(guild_id, announce=True)


@bot.event
async def on_ready() -> None:
    log.info("Bot is ready as %s", bot.user)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    command_name = interaction.command.name if interaction.command else "unknown"
    log.error("Error in /%s command", command_name, exc_info=error)

    message = "Something went wrong while running that command."
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="play", description="Play the best matching MP3 from your local library.")
@app_commands.describe(query="Song title, partial title, or keywords")
async def play_command(interaction: discord.Interaction, query: str) -> None:
    if interaction.guild is None:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return

    guild_id = interaction.guild.id
    player = get_player(guild_id)

    if interaction.channel is not None:
        player.text_channel = interaction.channel

    matches = search_songs(query, limit=5)
    if not matches:
        await interaction.response.send_message("No matching songs found.", ephemeral=True)
        return

    top_song, top_score = matches[0]
    second_score = matches[1][1] if len(matches) > 1 else 0
    ambiguous = len(matches) > 1 and top_score < 90 and (top_score - second_score) < 10
    if ambiguous:
        suggestions = "\n".join(
            f"{index + 1}. {song.title} ({score}%)" for index, (song, score) in enumerate(matches)
        )
        await interaction.response.send_message(
            f"Search is ambiguous. Try a more specific title.\nTop matches:\n{suggestions}",
            ephemeral=True,
        )
        return

    voice_client = await ensure_voice(interaction, player)
    if voice_client is None:
        return

    if player.current_song is None and not voice_client.is_playing() and not voice_client.is_paused():
        if start_playback(guild_id, top_song):
            await interaction.response.send_message(f"Now playing: **{top_song.title}**")
        else:
            await interaction.response.send_message("Could not start playback.", ephemeral=True)
    else:
        player.queue.append(top_song)
        await interaction.response.send_message(f"Added **{top_song.title}** to the queue.")


@play_command.autocomplete("query")
async def play_autocomplete(_: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    if current.strip():
        results = search_songs(current, limit=25)
    else:
        results = [(song, 0) for song in get_catalog()[:25]]

    return [app_commands.Choice(name=song.title[:100], value=song.title[:100]) for song, _ in results]


@bot.tree.command(name="search", description="Search your local MP3 library with fuzzy ranking.")
@app_commands.describe(query="Song title, partial title, or keywords")
async def search_command(interaction: discord.Interaction, query: str) -> None:
    matches = search_songs(query, limit=10)
    if not matches:
        await interaction.response.send_message("No matching songs found.", ephemeral=True)
        return

    lines = [f"{index + 1}. {song.title} ({score}%)" for index, (song, score) in enumerate(matches)]
    await interaction.response.send_message("Top matches:\n" + "\n".join(lines))


@bot.tree.command(name="queue", description="Show the current and upcoming songs.")
async def queue_command(interaction: discord.Interaction) -> None:
    if interaction.guild is None:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return

    player = get_player(interaction.guild.id)

    lines: list[str] = []
    if player.current_song is not None:
        lines.append(f"Now playing: **{player.current_song.title}**")

    if player.queue:
        for index, song in enumerate(player.queue, start=1):
            lines.append(f"{index}. {song.title}")

    if not lines:
        await interaction.response.send_message("The queue is currently empty.")
        return

    await interaction.response.send_message("\n".join(lines))


@bot.tree.command(name="skip", description="Skip the current song.")
async def skip_command(interaction: discord.Interaction) -> None:
    if interaction.guild is None:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return

    player = get_player(interaction.guild.id)
    voice_client = player.voice_client
    if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
        voice_client.stop()
        await interaction.response.send_message("Skipped current song.")
    else:
        await interaction.response.send_message("No song is currently playing.")


@bot.tree.command(name="pause", description="Pause the current song.")
async def pause_command(interaction: discord.Interaction) -> None:
    if interaction.guild is None:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return

    player = get_player(interaction.guild.id)
    voice_client = player.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        await interaction.response.send_message("Paused the current song.")
    else:
        await interaction.response.send_message("No song is currently playing.")


@bot.tree.command(name="resume", description="Resume the paused song.")
async def resume_command(interaction: discord.Interaction) -> None:
    if interaction.guild is None:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return

    player = get_player(interaction.guild.id)
    voice_client = player.voice_client
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        await interaction.response.send_message("Resumed the current song.")
    else:
        await interaction.response.send_message("No song is currently paused.")


@bot.tree.command(name="stop", description="Stop playback, clear queue, and disconnect.")
async def stop_command(interaction: discord.Interaction) -> None:
    if interaction.guild is None:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return

    player = get_player(interaction.guild.id)
    voice_client = player.voice_client
    if voice_client and voice_client.is_connected():
        player.queue.clear()
        player.current_song = None
        await voice_client.disconnect()
        players.pop(interaction.guild.id, None)
        await interaction.response.send_message("Stopped playback and left the voice channel.")
    else:
        players.pop(interaction.guild.id, None)
        await interaction.response.send_message("The bot is not connected to a voice channel.")


@bot.tree.command(name="list", description="List songs in the local MP3 library.")
@app_commands.describe(query="Optional filter for song names")
async def list_command(interaction: discord.Interaction, query: str | None = None) -> None:
    if query:
        matches = search_songs(query, limit=50)
        songs = [song for song, _ in matches]
    else:
        songs = get_catalog()

    if not songs:
        await interaction.response.send_message("No MP3 files found.")
        return

    max_items = 50
    shown = songs[:max_items]
    lines = [f"{index + 1}. {song.title}" for index, song in enumerate(shown)]
    remainder = len(songs) - len(shown)

    message = "Library:\n" + "\n".join(lines)
    if remainder > 0:
        message += f"\n...and {remainder} more."

    await interaction.response.send_message(message)


def main() -> None:
    if not DISCORD_TOKEN:
        raise SystemExit("DISCORD_TOKEN is not set. Copy .env.example to .env and fill in your bot token.")

    if DISCORD_MUSIC_PATH is None:
        log.warning("DISCORD_MUSIC_PATH is not set; the bot will not find any songs.")
    elif not DISCORD_MUSIC_PATH.is_dir():
        log.warning("Music folder %s does not exist; the bot will not find any songs.", DISCORD_MUSIC_PATH)

    if DISCORD_OPUS_PATH:
        discord.opus.load_opus(DISCORD_OPUS_PATH)

    bot.run(DISCORD_TOKEN, root_logger=True)


if __name__ == "__main__":
    main()
