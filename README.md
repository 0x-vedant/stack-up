# stack-up

## Agent / MCP Server Architecture

This project explicitly enforces a zero-code agent boundary to ensure compatibility with our internal Docker orchestration and tracing pipelines. 

To deploy an agent or MCP server, your uploaded repository archive **MUST** contain the following exact files at the root level:

1. `src/main.py` - The explicit entry point for your agent or FastAPI server.
2. `Dockerfile` - Container instructions required for runtime deployment.
3. `docker-compose.yml` (or `.yaml`) - Composition files to orchestrate your agent against the internal LLM gateway and Litellm proxies.

Uploads bypassing this strict requirement will be rejected during ingestion with an `HTTP 422 MissingStructureError`.