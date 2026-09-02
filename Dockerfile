FROM python:3.12-slim

WORKDIR /app

COPY data/schema.sql data/seed_games.json data/owned_games_sample.csv /app/data/
COPY frontend/ /app/frontend/
COPY service/ /app/service/
COPY tools/ /app/tools/
COPY README.md /app/README.md

ENV CATALOG_HOST=0.0.0.0
ENV CATALOG_PORT=8000

EXPOSE 8000

CMD ["python", "service/api.py"]
