
# Discord-MP3-Bot

A Discord bot for playing MP3 files. This effectively works like a discord music bot, but it streams your own mp3 files instead of music found online.
 It offers basic functionality to manage and play songs in a voice channel.

This was mainly made for personal use for my needs so it may not work as expected for you.

## Requirements

- `discord.py` library
- Opus library installed


## Installation 
1. Install all required libraries
2. Clone the repo somewhere on your computer
3. Substitute your own values in "config.py"
4. Run mp3bot.py

## Bot Commands

### /play
Plays an MP3 file by its title.
- **Usage:** `/play <title>`
- **Example:** `/play songname`

### /queue
Shows the current song queue.
- **Usage:** `/queue`

### /skip
Skips the current song.
- **Usage:** `/skip`

### /pause
Pauses the current song.
- **Usage:** `/pause`

### /resume
Resumes the paused song.
- **Usage:** `/resume`

### /stop
Stops the bot and makes it leave the voice channel.
- **Usage:** `/stop`

### /list
Lists available songs.
- **Usage:** `/list`

## Permissions List

### Scopes
- bot
- applications.commands

### Bot Permissions
#### General Permissions
- Read Messages/View Channels

#### Text Permissions
- Use Slash Commands

#### Voice Permissions
- Connect
- Speak
- Use Voice Activity

Feel free to reach out if you encounter any issues or have suggestions for improvements. This was just a quick project for a need of mine so I don't really expect everything to be perfect.