FROM python:3.13-slim

WORKDIR /app

# Install runtime deps
RUN pip install --no-cache-dir uv

COPY pyproject.toml /app/pyproject.toml
# If you have uv.lock, copy it too:
# COPY uv.lock /app/uv.lock

RUN uv pip install --system --no-cache -r <(uv pip compile pyproject.toml)

COPY src/ /app/src/

ENV PYTHONPATH=/app/src

# kopf CLI is installed as part of kopf dependency
CMD ["kopf", "run", "-m", "cf_ddns_operator.operator", "--verbose"]
