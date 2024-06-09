import discord
from discord import app_commands
from config import TOKEN, guildId

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

@client.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=guildId))
    print(f'Bot is starting. Logged in as {client.user}')

@tree.command(
    name="play",
    description="Plays mp3 files in order",
    guild=discord.Object(id=guildId)
)
async def play_command(interaction):
    print(f'Running play command')
    await interaction.response.send_message("play test")

@tree.command(
    name="queue",
    description="Adds mp3 files to the queue",
    guild=discord.Object(id=guildId)
)
async def queue_command(interaction):
    print(f'Running queue command')
    await interaction.response.send_message("queue test")

@tree.command(
    name="skip",
    description="Skips the current song",
    guild=discord.Object(id=guildId)
)
async def skip_command(interaction):
    print(f'Running skip command')
    await interaction.response.send_message("skip test")

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

client.run(TOKEN)
