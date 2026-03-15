FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    libfreetype6-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN pip install -r requirements.txt

CMD ["python", "bot.py"]