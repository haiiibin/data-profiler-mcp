# Container image for the data-profiler-mcp server (stdio transport).
# Used by Glama and anyone who wants to run the server in isolation.
FROM python:3.12-slim

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir .

# The server speaks MCP over stdio.
ENTRYPOINT ["data-profiler-mcp"]
