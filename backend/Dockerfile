# backend/Dockerfile
#
# Build from the REPO ROOT, not from inside backend/:
#   docker build -f backend/Dockerfile -t elmeeda-backend .
#
# WORKDIR is the repo root and backend/ is copied in as a package so that
# `backend.main:app` resolves as a module path, matching how the app is run
# locally (`uvicorn backend.main:app --reload` from the repo root).

# ---- deps stage ----
FROM python:3.11-slim AS deps

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# ---- runtime stage ----
FROM python:3.11-slim AS runtime

WORKDIR /app

COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

COPY backend/ backend/

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
