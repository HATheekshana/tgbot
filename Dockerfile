FROM python:3.10-slim

# Install system tools for image processing
RUN apt-get update && apt-get install -y \
    libfreetype6-dev \
    libjpeg-dev \
    zlib1g-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install the library directly to ensure it exists
RUN pip install --no-cache-dir aioenkanetworkcard aiogram motor python-dotenv

COPY requirements.txt .

# 3. THIS IS THE INSTALL LINE
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]