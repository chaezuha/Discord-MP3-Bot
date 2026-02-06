import asyncio
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


intents = discord.Intents(guilds=True, voice_states=True)
bot = commands.Bot(command_prefix="!", intents=intents)

players: dict[int, GuildPlayer] = {}


def get_player(guild_id: int) -> GuildPlayer:
    return players.setdefault(guild_id, GuildPlayer())


def get_catalog() -> list[Song]:
    if not DISCORD_MUSIC_PATH.exists():
        return []

    files = sorted(DISCORD_MUSIC_PATH.glob("*.mp3"), key=lambda item: item.name.lower())
    return [Song(path=path, title=path.stem) for path in files]


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

    if player.voice_client is None or not player.voice_client.is_connected():
        player.voice_client = await voice_channel.connect()
    elif player.voice_client.channel != voice_channel:
        await player.voice_client.move_to(voice_channel)

    return player.voice_client


def start_playback(guild_id: int, song: Song) -> bool:
    player = get_player(guild_id)
    voice_client = player.voice_client
    if voice_client is None or not voice_client.is_connected():
        player.current_song = None
        return False

    player.current_song = song
    source = discord.FFmpegPCMAudio(str(song.path), before_options="-nostdin", options="-vn")

    def after_playback(error: Exception | None) -> None:
        bot.loop.call_soon_threadsafe(
            asyncio.create_task,
            handle_song_end(guild_id, error),
        )

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

    if error and player.text_channel is not None:
        await player.text_channel.send(f"Playback error: `{error}`")

    player.current_song = None
    await play_next_song(guild_id, announce=True)


@bot.event
async def on_ready() -> None:
    if DISCORD_GUILD_ID:
        guild = discord.Object(id=DISCORD_GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        print(f"Synced {len(synced)} command(s) to guild {DISCORD_GUILD_ID}.")
    else:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} global command(s).")

    print(f"Bot is ready as {bot.user}")


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
            "Search is ambiguous. Try a more specific title.\n"
            f"Top matches:\n{suggestions}",
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
        player.voice_client = None
        await interaction.response.send_message("Stopped playback and left the voice channel.")
    else:
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


if DISCORD_OPUS_PATH:
    discord.opus.load_opus(DISCORD_OPUS_PATH)

if DISCORD_TOKEN == "Insert Token":
    raise RuntimeError("Set DISCORD_TOKEN before starting the bot.")

bot.run(DISCORD_TOKEN)
