import discord
import os
import glob
from discord import app_commands
from config import TOKEN, guildId, opusLoc, filePath
from collections import deque

def mp3Files(directory = filePath):
    return glob.glob(os.path.join(directory, '*.mp3'))

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

discord.opus.load_opus(opusLoc)

song_queue = deque()
current_song = None
voice_client = None

async def ensure_voice(interaction):
    global voice_client
    if interaction.user.voice is None:
        await interaction.response.send_message("You are not in a voice channel.")
        return None

    voice_channel = interaction.user.voice.channel
    if voice_client is None:
        voice_client = await voice_channel.connect()
    elif voice_client.channel != voice_channel:
        await voice_client.move_to(voice_channel)

    return voice_client

def play_next(interaction):
    global current_song
    if song_queue:
        next_song, song_name = song_queue.popleft()
        current_song = song_name
        voice_client.play(discord.FFmpegPCMAudio(source=next_song), after=lambda e: play_next(interaction))
        client.loop.create_task(interaction.followup.send(f'Now playing: {song_name}'))
    else:
        current_song = None

@client.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=guildId))
    print(f'Bot is starting. Logged in as {client.user}')

@tree.command(
    name="play",
    description="Plays an mp3 file",
    guild=discord.Object(id=guildId)
)
async def play_command(interaction, title: str):
    global song_queue
    print (f'Running play command')

    if interaction.user.voice is None:
        await interaction.response.send_message("You need to be in a voice channel to use this command.")
        return

    mp3_files = mp3Files()
    file_names = [os.path.splitext(os.path.basename(file))[0] for file in mp3_files]
    title_lower = title.lower()

    matches = [file for file in file_names if title_lower in file.lower()]

    if not matches:
        print(f'Failed: No matches found')
        await interaction.response.send_message('No matches found')
        return
    elif len(matches) == 1:
        song_file = mp3_files[file_names.index(matches[0])]
        song_name = matches[0]
    else:
        match_list = '\n'.join(matches)
        print(f'Multiple matches found: {match_list}')
        await interaction.response.send_message(f'Multiple matches found:\n{match_list}\nPlease refine your search.')
        return

    voice_client = await ensure_voice(interaction)
    if voice_client is None:
        return

    if not song_queue and not voice_client.is_playing():
        song_queue.append((song_file, song_name))
        play_next(interaction)
        await interaction.response.send_message(f'Now playing: {song_name}')
    else:
        song_queue.append((song_file, song_name))
        await interaction.response.send_message(f'Added {song_name} to the queue.')

@tree.command(
    name="queue",
    description="Shows the current song queue",
    guild=discord.Object(id=guildId)
)
async def queue_command(interaction):
    print(f'Running queue command')
    if song_queue:
        queue_list = [f"{index + 1}. {name}" for index, (_, name) in enumerate(song_queue)]
        await interaction.response.send_message("Current queue:\n" + "\n".join(queue_list))
    else:
        await interaction.response.send_message("The queue is currently empty.")

@tree.command(
    name="skip",
    description="Skips the current song",
    guild=discord.Object(id=guildId)
)
async def skip_command(interaction):
    global voice_client
    print(f'Running skip command')

    if interaction.user.voice is None:
        await interaction.response.send_message("You need to be in a voice channel to use this command.")
        return

    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await interaction.response.send_message("Skipped current song.")
        play_next(interaction)
    else:
        await interaction.response.send_message("No song is currently playing.")

@tree.command(
    name="pause",
    description="Pauses the song!",
    guild=discord.Object(id=guildId)
)
async def pause_command(interaction):
    print(f'Running pause command')
    await interaction.response.send_message("pause test")

@tree.command(
    name="resume",
    description="Resumes the song",
    guild=discord.Object(id=guildId)
)
async def resume_command(interaction):
    print(f'Running resume command')
    await interaction.response.send_message("resume test")

@tree.command(
    name="stop",
    description="Stops the bot and makes it leave",
    guild=discord.Object(id=guildId)
)
async def stop_command(interaction):
    print(f'Running stop command')
    await interaction.response.send_message("stop test!")

@tree.command(
    name="list",
    description="Lists avaliable songs",
    guild=discord.Object(id=guildId)
)
async def list_command(interaction):
    print(f'Running list command')
    mp3_files = mp3Files()
    if mp3_files:
        file_names = [os.path.splitext(os.path.basename(file))[0] for file in mp3_files]
        numbered_files = [f"{name}" for index, name in enumerate(file_names)]
        await interaction.response.send_message('\n'.join(numbered_files))
    else:
        await interaction.response.send_message('No mp3 files found')


client.run(TOKEN)
