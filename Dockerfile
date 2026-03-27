# Stage 1: Build the Angular UI
FROM node:22-alpine AS ui-build

WORKDIR /ui
COPY src/ascent/ui/package.json src/ascent/ui/package-lock.json* ./
RUN npm ci
COPY src/ascent/ui/ .
RUN npx ng build --configuration production

# Stage 2: Python server
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src/ src/

# Copy built UI into the server package
COPY --from=ui-build /ui/dist/ui/browser/ src/ascent/server/ui/

RUN uv sync --no-dev --frozen

EXPOSE 8000

CMD ["uv", "run", "ascent", "server", "start", "--host", "0.0.0.0"]
