FROM python:3.14.3-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHON_DOTENV_DISABLED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 \
    && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 app
# Explicit runtime allowlist: no tests, environment files, or dependency overrides.
COPY backend/main.py backend/config.py backend/input_validation.py backend/operations.py backend/provider.py backend/schemas.py backend/analysis_request.py ./
COPY backend/tokenizer_data/o200k_base.tiktoken.gz backend/tokenizer_data/LICENSE ./tokenizer_data/
USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--timeout-graceful-shutdown", "135"]
