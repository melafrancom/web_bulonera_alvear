FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System deps for mysqlclient, image processing libs, and Node.js
RUN apt-get update && apt-get install -y --no-install-recommends \
	build-essential \
	default-libmysqlclient-dev \
	pkg-config \
	libjpeg62-turbo-dev \
	zlib1g-dev \
	libwebp-dev \
	curl \
	&& curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
	&& apt-get install -y nodejs \
	&& rm -rf /var/lib/apt/lists/*

# Copy package files and install Node dependencies
COPY package.json package-lock.json* ./
RUN npm install

# Copy Tailwind config and input CSS
COPY tailwind.config.js ./
COPY static/css/input.css ./static/css/

# Copy Python requirements and install
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
	pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY . /app

# Build Tailwind CSS for production
RUN npm run build:css

# Make entrypoint executable
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8002

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uwsgi", "--http-socket", "0.0.0.0:8002", "--module", "web_bulonera.wsgi:application", "--master", "--processes", "4", "--threads", "2", "--enable-threads", "--harakiri", "180", "--max-requests", "5000", "--buffer-size", "65536", "--static-map", "/static=/app/staticfiles", "--static-map", "/media=/app/media"]
