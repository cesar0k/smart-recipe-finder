# builder
FROM python:3.11 as builder

WORKDIR /app

RUN python -m venv /opt/venv

ENV PATH="/opt/venv/bin/:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# final image
FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

COPY ./app .