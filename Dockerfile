# Use uv's Python 3.13 image for deterministic, fast installs
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# Set working directory
WORKDIR /app

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies using the lockfile into a local virtualenv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Ensure the virtualenv is used at runtime
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

# Copy application code
COPY . .

# Expose port (Fly.io typically sets PORT=8080)
EXPOSE 8080

# Run the FastMCP server
CMD ["python", "main.py"]