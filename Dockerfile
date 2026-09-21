# syntax=docker/dockerfile:1

# The backend container for Render (docs/ROADMAP.md 3c; render.yaml points at
# this file and at this context). The build context is the repository root
# because two things live above `backend/`: the demo inbox at `demo_data/`, and
# the sys.path entry that makes `backend.api.main` importable.
#
# Nothing in here bakes in a secret. OPENAI_API_KEY arrives from Render's
# environment at run time (render.yaml marks it `sync: false`), and `.env` is
# excluded by .dockerignore so a developer's local key cannot ride along in a
# layer — where it would survive every later `rm` and be readable by anyone who
# can pull the image.

# ---------------------------------------------------------------------------
# Stage 1 — resolve and install the dependency tree
# ---------------------------------------------------------------------------
# 3.10 is the interpreter every score in docs/SCORING.md was measured on
# (`.venv/Scripts/python.exe --version` reports 3.10.11), so the deployed
# behaviour is the measured behaviour. The minor version matters more than it
# looks: pydantic-core, rapidfuzz, pypdfium2, pillow and uvicorn's [standard]
# extras all ship as compiled wheels tagged per interpreter version, and on a
# version with no matching wheel pip silently falls back to building from
# source — which in this image is not a slow success but a failure, because no
# compiler is installed here on purpose. A missing wheel should stop the build
# loudly rather than quietly adding a toolchain to the runtime image.
FROM python:3.10-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

# A virtualenv rather than the system site-packages, so the runtime stage can
# take the whole dependency tree in a single COPY and leave pip, setuptools and
# their build metadata behind in this stage.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# The requirements file is copied alone, ahead of any source, so that editing a
# Python file does not invalidate the install layer. Installing is the
# expensive step and source edits are the frequent one; with the deadline three
# days out, the difference between a 15-second rebuild and a four-minute one is
# several iterations.
#
# requirements-api.txt, not requirements.txt: the deployed image drops
# markitdown and the onnxruntime/pandas/numpy/sympy tree behind it — roughly
# 357 MB of installed packages that this image can never reach. That file's
# header carries the measurement, its limits (docker is not installed on the
# machine this was written on, so no image size here is a measured one), and
# exactly which capability is given up and how the code behaves without it.
COPY backend/requirements-api.txt ./requirements-api.txt
RUN pip install --no-cache-dir -r requirements-api.txt

# ---------------------------------------------------------------------------
# Stage 2 — the runtime image
# ---------------------------------------------------------------------------
FROM python:3.10-slim-bookworm

ENV PATH="/opt/venv/bin:$PATH" \
    # Render's log viewer shows nothing during a failing start-up unless Python
    # stops buffering — the one moment the logs are worth reading.
    PYTHONUNBUFFERED=1 \
    # /app is owned by root and the process is not, so every import would
    # otherwise attempt a .pyc write that cannot succeed.
    PYTHONDONTWRITEBYTECODE=1 \
    # `backend/` has no __init__.py: it is an implicit namespace package, so
    # `backend.api.main` resolves only with the repository root on sys.path.
    # uvicorn does insert its --app-dir (default ".") for us, but stating it
    # here means `docker exec ... python -c "import backend.api.main"` and a
    # one-off `python backend/run.py` behave the same as the server does.
    PYTHONPATH=/app \
    # Defaults for a local `docker run` with no flags. On Render every one of
    # these is set again by render.yaml, and $PORT is injected per deploy.
    PORT=8000 \
    SENTINEL_DATA_ROOT=/app/demo_data \
    SENTINEL_CORS_ORIGINS=*

# Non-root, because this container parses documents a stranger uploaded: POST
# /compare hands judge-supplied bytes straight to pdfplumber, python-docx and
# openpyxl. A parser bug in that path should not be reached as root. The uid is
# fixed rather than auto-assigned so the ownership below is predictable.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin sentinel

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Source, then data. Both change far more often than the dependency tree above,
# which is why they are the last layers.
COPY --chown=sentinel:sentinel backend/ backend/

# Render builds from git and `/data/` is git-ignored, so the participant bundle
# has to be committed somewhere that is not ignored for the deployed demo to
# have an inbox at all; `demo_data/` is that path (render.yaml sets
# SENTINEL_DATA_ROOT to it). Only the participant bundle may go there — the
# organisers' package in data/_grader/ never enters this image, and
# .dockerignore is written as an allow-list so that it cannot.
COPY --chown=sentinel:sentinel demo_data/ demo_data/

# The full participant inbox, 520 emails and 251 attachments, 3.2 MB. This is
# what SENTINEL_DATA_ROOT points at, so a judge pressing "Start a run" watches
# the whole graded inbox go through rather than a sample of it. `demo_data/`
# stays for a faster run. Only the participant bundle is ever copied here --
# `bundle_data/README.md` and `.dockerignore` both say why, and the answer key
# has no path into this image.
COPY --chown=sentinel:sentinel bundle_data/ bundle_data/

# backend/sdoc/llm/cache.py writes model responses under `.cache/llm` relative
# to the working directory, and swallows OSError on the way out ("a cache that
# cannot write is not a failure"). That swallow is correct and it is also why
# this line exists: without a writable directory the cache degrades to a
# permanent zero hit rate with nothing in the logs, and the cache is what makes
# a demo re-run answer identically rather than merely similarly.
RUN install -d -o sentinel -g sentinel /app/.cache

USER sentinel

# Documentation only — Render routes to $PORT regardless, and $PORT is not
# expanded in an EXPOSE.
EXPOSE 8000

# Render runs its own check against healthCheckPath and ignores this one; it is
# here for `docker run` and for anyone bringing the container up locally.
# Python rather than curl because the slim base ships no curl, and adding one
# for a health check would be a package installed to run three lines of code.
# `/` is the only route in backend/api/main.py that does not touch the
# pipeline; there is no /health route to point at.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/').read()"

# `sh -c` because $PORT has to be expanded at run time and the exec form does
# no shell expansion — a container that hardcodes 8000 builds cleanly, starts
# cleanly, and then fails Render's health check with no useful error. `exec` so
# that uvicorn replaces the shell as PID 1 and receives SIGTERM directly;
# without it sh swallows the signal and every redeploy waits out the kill
# timeout.
#
# One worker, deliberately. backend/api/store.py is "a single process's
# memory": with two workers, a POST /runs served by worker A returns a run_id
# that GET /runs/{run_id} on worker B answers with 404, intermittently and only
# under load — the worst failure to debug in front of a judge. Scaling this
# service means giving the store a database first (ARCHITECTURE.md section 5).
CMD ["sh", "-c", "exec uvicorn backend.api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
