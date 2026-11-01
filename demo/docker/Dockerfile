FROM python:3.13-bookworm@sha256:3856e3e7bf4d0ba061501a84ed2eb0d429663307c0f54f191dc4de03c7081c3e
RUN apt-get update && apt-get install -y --no-install-recommends chromium xvfb x11-utils xauth openbox \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 demo
# Debian ships Chromium's sandbox separately; keep it enabled in the test runner.
RUN apt-get update && apt-get install -y --no-install-recommends chromium-sandbox \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /demo
COPY scripts/mctl-display scripts/mctl-display
COPY demo/fixtures demo/fixtures
COPY demo/tests demo/tests
USER demo
ENV PYTHONDONTWRITEBYTECODE=1
CMD ["xvfb-run", "-a", "-s", "-screen 0 1280x720x24", "python3", "-m", "unittest", "discover", "-s", "demo/tests", "-v"]
