# syntax=docker/dockerfile:1.7
#
# Multi-target Dockerfile for Ascent.
#
# Targets:
#   base       — Python + ascent package. Shared foundation for every
#                other target. No CMD.
#   ui-build   — Angular build stage. Produces the static bundle the
#                server ships.
#   server     — FastAPI + built UI. Image for the `server` compose
#                service.
#   runtime    — Thin base for trading services. Dev compose mounts the
#                user script in; no script is baked in here.
#   exchange /
#   feed /
#   strategy   — Production targets: extend runtime and COPY the
#                corresponding root-level script in so the image is
#                self-contained and reproducible. Used by the prod
#                compose override.
#
# Build examples:
#   docker build --target server   -t ascent-server   .
#   docker build --target exchange -t ascent-exchange .
#   docker build --target feed     -t ascent-feed     .
#   docker build --target strategy -t ascent-strategy .


# ----------------------------------------------------------------------
# base: Python + ascent package.
# ----------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS base

WORKDIR /app

# Install the ascent package first so this expensive layer caches across
# every downstream target unless pyproject.toml / uv.lock / src/ change.
COPY pyproject.toml uv.lock README.md ./
COPY src/ src/

RUN uv sync --no-dev --frozen

# Directory convention for user-authored scripts. Extended targets (prod
# exchange/feed/strategy) COPY into this path; the dev compose mounts
# individual files on top of it.
RUN mkdir -p /app/user


# ----------------------------------------------------------------------
# ui-build: Angular → static bundle.
# ----------------------------------------------------------------------
FROM node:22-alpine AS ui-build

WORKDIR /ui
COPY src/ascent/ui/package.json src/ascent/ui/package-lock.json* ./
RUN npm ci
COPY src/ascent/ui/ .
RUN npx ng build --configuration production


# ----------------------------------------------------------------------
# server: FastAPI + served UI.
# ----------------------------------------------------------------------
FROM base AS server

COPY --from=ui-build /ui/dist/ui/browser/ src/ascent/server/ui/

EXPOSE 8000

CMD ["uv", "run", "ascent", "server", "start", "--host", "0.0.0.0"]


# ----------------------------------------------------------------------
# runtime: thin base for trading services. No UI build (nothing to
# serve), no fixed CMD (the extending target decides what to run). Used
# directly by the dev compose with a bind-mounted script.
# ----------------------------------------------------------------------
FROM base AS runtime

# The dev compose provides the script via bind mount; in that mode the
# compose service overrides `command:` to point at the mounted file.
# We set a default CMD that errors loudly if someone forgets both —
# easier to diagnose than a silent "ImportError: No module".
CMD ["sh", "-c", "echo 'ascent-runtime: set a command or COPY a script into /app/user/'; exit 1"]


# ----------------------------------------------------------------------
# exchange / feed / strategy: production targets.
#
# Each bakes the corresponding root-level script into the image so a
# deployed container is byte-identical to what we built. The dev
# compose continues to bind-mount source; the prod compose override
# switches to these targets.
# ----------------------------------------------------------------------
FROM runtime AS exchange
COPY exchange.py /app/user/exchange.py
CMD ["uv", "run", "python", "/app/user/exchange.py"]


FROM runtime AS feed
COPY feed.py /app/user/feed.py
CMD ["uv", "run", "python", "/app/user/feed.py"]


FROM runtime AS strategy
COPY strategy.py /app/user/strategy.py
CMD ["uv", "run", "python", "/app/user/strategy.py"]
