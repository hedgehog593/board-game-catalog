# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/playwright/python:v1.63.0-noble AS tests
WORKDIR /app
COPY tests/requirements.txt /app/tests/requirements.txt
RUN pip install --no-cache-dir -r tests/requirements.txt
COPY data/schema.sql data/seed_games.json /app/data/
COPY frontend/ /app/frontend/
COPY service/ /app/service/
COPY tests/ /app/tests/
RUN python -m unittest discover -s tests -p "test_*.py" -v
ARG RUN_LIVE_BGG_TESTS=0
RUN --mount=type=secret,id=bgg_api_token \
    if [ "$RUN_LIVE_BGG_TESTS" = "1" ]; then \
      BGG_TEST_TOKEN_FILE=/run/secrets/bgg_api_token python tests/live_bgg.py; \
    fi
RUN touch /app/tests-passed

FROM python:3.12-slim AS runtime

WORKDIR /app
COPY --from=tests /app/tests-passed /app/tests-passed

COPY data/schema.sql data/seed_games.json data/owned_games_sample.csv /app/data/
COPY frontend/ /app/frontend/
COPY service/ /app/service/
COPY tools/ /app/tools/
COPY README.md /app/README.md

ENV CATALOG_HOST=0.0.0.0
ENV CATALOG_PORT=8000

EXPOSE 8000

CMD ["python", "service/api.py"]
