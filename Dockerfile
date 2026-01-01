FROM python:3.13-slim

WORKDIR /app

# Install runtime deps
RUN pip install --no-cache-dir uv

COPY pyproject.toml /app/pyproject.toml

COPY README.md /app/README.md

COPY uv.lock /app/uv.lock

COPY src/ /app/src/

RUN pip install .

ENV PYTHONPATH=/app/src

# kopf CLI is installed as part of kopf dependency
CMD ["kopf", "run", "-m", "cf_ddns_operator.operator", "--verbose", "--namespace=networking", "--standalone"]
