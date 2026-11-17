FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first (better layer caching).
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY prompts ./prompts
COPY data ./data

RUN pip install --upgrade pip && pip install -e ".[postgres]"

EXPOSE 8000

# DATABASE_URL and DOCPIPE_PROFILE come from the environment (see docker-compose.yml).
CMD ["python", "-m", "docpipe", "serve", "--host", "0.0.0.0", "--port", "8000"]
