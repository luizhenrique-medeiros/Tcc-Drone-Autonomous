FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --system gateway \
    && useradd --system --gid gateway --create-home gateway \
    && mkdir -p /var/lib/drone-gateway \
    && chown gateway:gateway /var/lib/drone-gateway
WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app
RUN python -m pip install --upgrade pip && python -m pip install .

USER gateway
CMD ["python", "-m", "app.main"]
