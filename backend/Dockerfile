FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
RUN python -m pip install --no-cache-dir 'pip>=26.2,<27' && python -m pip install --no-cache-dir . && useradd --create-home app
USER app
EXPOSE 8000
CMD ["uvicorn", "poker_lab.api:app", "--host", "0.0.0.0", "--port", "8000"]
