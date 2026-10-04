FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first so this layer is cached until requirements change.
ARG INSTALL_DEV=false
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && if [ "$INSTALL_DEV" = "true" ]; then \
         pip install --no-cache-dir -r requirements-dev.txt; \
       fi

COPY . .

# Run as an unprivileged user. The data and cache directories are created
# here, owned by that user, so the named volumes Compose mounts on them are
# writable (Docker copies a directory's ownership into a new, empty volume).
#   /data/chroma        ChromaDB storage
#   ~/.cache            downloaded embedding model
RUN useradd --create-home appuser \
    && mkdir -p /data/chroma /home/appuser/.cache \
    && chown -R appuser /app /data /home/appuser/.cache
USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]