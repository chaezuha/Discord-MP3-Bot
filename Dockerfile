FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libopus0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py mp3bot.py ./

# Compose/`docker run` mount the host music folder here.
ENV DISCORD_MUSIC_PATH=/music

RUN useradd --create-home bot
USER bot

CMD ["python", "mp3bot.py"]
