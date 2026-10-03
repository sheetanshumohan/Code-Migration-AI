# Code Migration AI — Benchmark Suite

This directory contains the automated performance benchmarking harness for the Code Migration AI application.

## Prerequisites
1. **FastAPI Backend Server**: Running on `http://127.0.0.1:8000`
2. **Celery Worker**: Running with solo pool listening to `migration_jobs,ast_indexing,validation_sandbox`
3. **Docker Engine**: Running with Linux container support
4. **PostgreSQL & Redis**: Connected and accessible
5. **Groq API Key**: Set in `.env` (`GROQ_API_KEY`)

## Directory Structure
- `config.json`: Configuration for the benchmark (model, provider, runs, target repo)
- `fixture_repo/`: Standardized multi-file Python repository used for all benchmark runs
- `setup_repo.py`: Initializes the test user, organization, project, and repository records in PostgreSQL
- `run_benchmark.py`: Runs warm-up and measured benchmark iterations, collecting real timing and resource metrics
- `generate_reports.py`: Computes summary statistics, generates markdown reports, and renders visualizations
- `results/`: Contains raw metrics (`results.json`), summary (`summary.json`), charts (`latency.png`, `stage_latency.png`, `token_usage.png`), and markdown reports

## Running the Benchmark
```bash
# 1. Setup fixture repository in database
python benchmark/setup_repo.py

# 2. Execute benchmark suite
python benchmark/run_benchmark.py

# 3. Generate summary reports
python benchmark/generate_reports.py
```
