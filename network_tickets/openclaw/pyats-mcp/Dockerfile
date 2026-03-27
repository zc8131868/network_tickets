FROM python:3.10-slim

LABEL description="pyATS MCP Server - SSE transport for OpenClaw"

RUN apt-get update && apt-get install --no-install-recommends -y \
        openssh-client \
        build-essential \
        libssl-dev \
        libffi-dev \
        libxml2-dev \
        libxslt1-dev \
        zlib1g-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

RUN pip install --no-cache-dir \
        backports.ssl \
        backports.ssl-match-hostname \
        tftpy \
        ncclient \
        f5-icontrol-rest

RUN pip install --no-cache-dir \
        pydantic \
        python-dotenv \
        "mcp[cli]" \
        pyats[full]==25.2.0

# pyATS Cython 扩展依赖 pkg_resources（setuptools>=74 已移除独立包）
RUN pip install --no-cache-dir "setuptools==67.8.0"

COPY pyats_sse_server.py .
COPY testbed.yaml .

EXPOSE 8765

ENTRYPOINT ["python", "pyats_sse_server.py"]
