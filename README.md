# Nasiko MCP Platform

Nasiko is an AI-agent registry and orchestration platform designed to run LLM workloads efficiently across distributed toolsets.

## Architecture Tracks

The Nasiko architecture is rigidly split across boundaries targeting zero-code LLM inference hooks.

- **R1 (Ingestion):** Handles standard user CLI workloads fetching `.zip` files of LangChain or CrewAI agents. 
- **R2 (Bridge & Kong):** Serves as an MCP JSON-RPC 2.0 translation proxy linking standard STDIO agent environments securely over network boundaries into Kong API Services automatically natively discovering random free OS ports.
- **R3 (Manifest Generator):** Synthesizes LLM payloads utilizing parsing tools executing complex local AST derivations identifying hidden user Tools dynamically securely.
- **R4 (Orchestrator):** The brain mapping dynamically injected LiteLLM dependencies. Injects proxy tokens avoiding native token blocks locally mapped to `http://llm-gateway:4000`.
- **R5 (Observability):** Phoenix Arize integration dumping W3C traceparents securely avoiding duplication mappings logging JSON payloads directly through OpenTelemetry boundaries securely.

## Quickstart
Deploy the framework utilizing docker configs safely targeting native components locally.

```bash
docker-compose up --build
```