FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System deps for mysqlclient and image processing libs
RUN apt-get update && apt-get install -y --no-install-recommends \
	build-essential \
	default-libmysqlclient-dev \
	pkg-config \
	libjpeg62-turbo-dev \
	zlib1g-dev \
	libwebp-dev \
	&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
	pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8002

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uwsgi", "--http-socket", "0.0.0.0:8002", "--module", "web_bulonera.wsgi:application", "--master", "--processes", "4", "--threads", "2", "--enable-threads", "--harakiri", "180", "--max-requests", "5000", "--buffer-size", "65536"]
