# Local SearXNG Setup & Operational Evaluation

## 1. Executive Summary & Zero-Cost Philosophy

NumberShield / ClearNum is designed around an inviolable principle: **Zero Mandatory Cost and Zero Mandatory Infrastructure**.

- **No Docker required**: The application functions out-of-the-box with direct, lawful, zero-cost public discovery providers:
  - **DuckDuckGo HTML Search**: Direct public search with polite backoff.
  - **Wikipedia / Wikimedia MediaWiki API**: Direct public page, revision, and discussion search.
  - **Hacker News Algolia API**: Direct public comments, hiring threads, and resume query API.
  - **Internet Archive Wayback CDX API**: Historical snapshot index searching archived pastes and directories.
  - **Manual Search Dorks**: Curated dork queries for major commercial search engines without third-party API costs.
  - **Offline Local Parsers**: MBOX email archives and Android SMS XML backups analyzed entirely on the local machine.

Operating a local SearXNG meta-search instance is an **entirely optional capability** for advanced privacy engineers who wish to aggregate broad search results across multiple engines without relying on commercial API keys.

---

## 2. Operational Evaluation & Trade-offs

| Dimension | Direct Public Providers (Default) | Local SearXNG Container (Optional) |
| :--- | :--- | :--- |
| **Setup Cost** | **$0** (zero commands or configuration needed) | Docker required; ~5 minutes setup |
| **Resource Usage** | **~0 MB RAM overhead** | **250MB–500MB RAM**, background CPU |
| **Upstream IP Reliability** | **High** (Official APIs from Wikimedia, Algolia, Internet Archive do not block residential IPs) | **Low to Moderate** (Google and Bing rapidly block or challenge residential IPs querying through meta-search scrapers) |
| **Maintenance** | **None** (ClearNum maintains adapters) | User must maintain Docker container, engine configurations, and bot-evasion settings |
| **Network Security** | Strictly outbound HTTPS with SSRF connection pinning | Bound strictly to `127.0.0.1:8888` on local interface |

### Why ClearNum Does Not Depend on Public SearXNG Instances
Public SearXNG instances found on public lists are notoriously unstable:
1. They are frequently overloaded and return HTTP 429 (Rate Limited) or HTTP 503 (Unavailable).
2. Many disable the JSON search API format (`format=json`) to prevent bot abuse.
3. Using public instances routes search queries through third-party servers.

Therefore, ClearNum's primary automated discovery engine uses dedicated, unauthenticated official APIs (MediaWiki, Algolia, Wayback CDX) and only uses SearXNG when explicitly enabled or when a local instance is configured by the user.

---

## 3. How to Run Local SearXNG (Optional)

If you have Docker installed and wish to run a dedicated local SearXNG instance:

### Step 1: Start the Local SearXNG Container
From the repository root, start the provided compose file:
```bash
docker compose -f docker-compose.searxng.yml up -d
```

### Step 2: Verify Strict Localhost Binding
Ensure the container binds **exclusively to 127.0.0.1** and is never exposed to your local network (`0.0.0.0`):
```bash
# Verify port binding in docker ps
docker ps --filter "name=numbershield-searxng" --format "{{.Ports}}"
# Expected output: 127.0.0.1:8888->8080/tcp
```

### Step 3: Configure ClearNum
Set the instance URL in your local environment or `.env` file:
```bash
SEARXNG_INSTANCE_URL=http://127.0.0.1:8888
```

ClearNum's SSRF protection will recognize that `SEARXNG_INSTANCE_URL` is an explicitly configured operator endpoint on `127.0.0.1` and permit communication over port 8888 while preserving strict blocking against cloud metadata (`169.254.169.254`) and unauthorized internal subnets (`10.0.0.0/8`, `192.168.0.0/16`).

### Step 4: Tear Down
When finished, stop the container with:
```bash
docker compose -f docker-compose.searxng.yml down
```
ClearNum will continue functioning seamlessly without it.
