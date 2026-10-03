# Code Migration AI — Comprehensive Local Engineering Benchmark Report

**Execution Timestamp (UTC):** 2026-10-03T16:13:48.415924+00:00  
**Host Environment:** Windows Host (Python 3.12 / FastAPI Uvicorn + Celery Worker Solo Pool)  
**Persistence Tier:** PostgreSQL (Neon Serverless SSL / AsyncPg NullPool), Redis (Upstash Serverless Cloud SSL)  
**AI / LLM Model:** Groq High-Speed API (`openai/gpt-oss-120b`)  

---

## 1. Tree-sitter AST Engine Performance

High-resolution performance of the AST parser and symbol extraction pipeline across 10 measured runs:

| Metric | Measured Value | Unit |
| :--- | :--- | :--- |
| **Total Files Analyzed** | 7 | files |
| **Python Files Parsed** | 6 | files |
| **Total Symbols Extracted** | 24 | symbols |
| **Total Lines of Code (LOC)** | 139 | lines |
| **Mean Parse Duration** | 14.84 | ms |
| **Median Parse Duration** | 14.06 | ms |
| **P95 Parse Duration** | 15.0865 | ms |
| **Minimum Parse Duration** | 12.89 | ms |
| **Maximum Parse Duration** | 20.31 | ms |
| **Throughput (Files/sec)** | **404.33** | files/sec |
| **Throughput (Symbols/sec)** | **1617.34** | symbols/sec |

---

## 2. Infrastructure Latency Breakdown

Measured round-trip latencies across external cloud services and persistent stores (10 iterations each):

| Service | Infrastructure Component | Mean Latency | Median | P95 | Min | Max |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Redis** | Upstash Serverless SSL Task Queue | **877.02 ms** | 483.4725 ms | 478.8231 ms | 477.62 ms | 2457.43 ms |
| **PostgreSQL** | Neon Cloud AsyncPg Connection Pool | **1585.06 ms** | 273.7379 ms | 270.6492 ms | 268.92 ms | 6842.18 ms |
| **Sandbox** | Hermetic Compileall Validation | **208.72 ms** | - | - | 190.31 ms | 233.86 ms |
| **Qdrant** | Cloud Vector Index | NOT MEASURED | - | - | - | - |
| **Neo4j** | Graph DB Aura Free | NOT MEASURED (Driver unreachable: 844bde8d.databases.neo4j.io:7687) | - | - | - | - |

---

## 3. Concurrency Protection & Conflict Prevention

Live test verifying multi-tenant isolation and queue collision avoidance:

### 2 Simultaneous Submissions
- **Requests Dispatched:** 2 simultaneous requests
- **Dispatch Duration:** 8623.24 ms
- **Status Codes Received:** [200, 200]
- **Accepted Workflows (HTTP 200):** 2
- **Rejected Conflicts (HTTP 409):** 0
- **Conflict Prevention Rate:** 0.0%

### 5 Simultaneous Submissions
- **Requests Dispatched:** 5 simultaneous requests
- **Dispatch Duration:** 3394.17 ms
- **Status Codes Received:** [409, 409, 409, 409, 409]
- **Accepted Workflows (HTTP 200):** 0
- **Rejected Conflicts (HTTP 409):** 5
- **Conflict Prevention Rate:** 100.0%

---

## 4. End-to-End Migration & LLM Resource Utilization

Telemetric records extracted from PostgreSQL persistent state:

- **Total Workflows Ingested:** 20
- **Median Workflow Latency:** 484.009 sec
- **P95 Workflow Latency:** 6604.2246 sec
- **Mean Total Tokens per Workflow:** 13542.2
- **Mean Cost per Workflow:** $0.004396
- **Validation Pass Rate:** 100.0%

---

## 5. LangGraph State Machine Stage Breakdown

The pipeline orchestrates 7 specialized LangGraph agent nodes:
1. `repo_analyst`: Tree-sitter AST parsing, language/framework detection, symbol tree assembly
2. `prompt_validator`: Goal heuristic guardrails and verification
3. `planner`: Autonomous migration DAG generation with LLM
4. `refactor`: Unified code diff transformation adhering to target framework conventions
5. `test_generator`: Automated regression and unit test suite synthesis
6. `validator`: Compileall / pytest sandbox execution
7. `reviewer`: Summary report, cryptographic audit trail, and Pull Request delivery
