# fit-render CLI image. The future API worker runs renders with this image:
#   docker run --rm -v "$PWD:/work" fit-render render ride.fit --start 1:00 --end 1:30 -o out.mov
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.0 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH

WORKDIR /app
# Dependencies first (cached layer), then the project itself.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

# ffmpeg comes from the imageio-ffmpeg wheel (static build with prores_ks and
# libvpx-vp9); set FFMPEG_PATH to use a different binary.
RUN fit-render --version && python -c "from fit_render.encode import find_ffmpeg; print(find_ffmpeg())"

RUN useradd --create-home --uid 1000 app
USER app
WORKDIR /work
ENTRYPOINT ["fit-render"]
CMD ["--help"]
