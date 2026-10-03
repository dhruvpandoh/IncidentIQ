# IncidentIQ 🛰️

IncidentIQ is a real-time crisis detection and monitoring system that ingests social media and news data, classifies emerging incidents using a locally hosted language model, and visualizes detected events through an interactive dashboard.

## Overview

IncidentIQ continuously collects data from multiple live sources and processes it through a streaming pipeline to identify crisis-related events such as:

- Natural disasters
- Civil unrest
- Cyberattacks
- Terrorist attacks
- Pandemics
- Wars
- Financial crises
- Infrastructure failures
- Environmental crises
- Crime

The system combines real-time streaming, distributed processing, transformer-based classification, vector search, and interactive visualization.

## Architecture

```text
Reddit ───────┐
Bluesky ──────┼──> Kafka ──> Spark Structured Streaming
Google News ──┘                    │
                                   ▼
                          FastAPI Classification
                              Local LLM
                                   │
                     ┌─────────────┴─────────────┐
                     ▼                           ▼
                  MongoDB                     Qdrant
              Structured event data       Vector embeddings
                     │                           │
                     └─────────────┬─────────────┘
                                   ▼
                            Interactive Dashboard
```

## Tech Stack

- **Apache Kafka** — real-time event ingestion and streaming
- **Apache Spark / PySpark** — distributed stream processing
- **FastAPI** — model inference API
- **Hugging Face Transformers** — transformer-based crisis classification
- **Sentence Transformers** — semantic embeddings
- **Qdrant** — vector storage and similarity search
- **MongoDB** — structured post and event storage
- **Dash / Plotly** — interactive monitoring dashboard
- **Docker Compose** — local infrastructure orchestration

## Data Sources

IncidentIQ currently supports:

- Reddit
- Bluesky
- Google News

Each ingestion service publishes incoming content into Kafka for downstream processing.

## Processing Pipeline

1. Live posts and news articles are collected from supported data sources.
2. Events are published to Kafka.
3. Spark Structured Streaming consumes incoming messages.
4. Text is sent to the FastAPI classification service.
5. The local language model assigns a crisis category.
6. Processed events are stored in MongoDB.
7. Semantic embeddings are generated and stored in Qdrant.
8. The dashboard queries processed data and visualizes detected incidents.

## Crisis Categories

```text
natural_disaster
terrorist_attack
cyberattack
pandemic
war
financial_crisis
civil_unrest
infrastructure_failure
environmental_crisis
crime
none
```

## Project Structure

```text
IncidentIQ/
├── classification/
│   ├── download_model_once.py
│   └── fastapi_model.py
├── consumer/
│   └── general.consumer.py
├── dashboard/
│   └── app.py
├── ingestion/
│   ├── bluesky_ingest.py
│   ├── google_ingest.py
│   ├── reddit_ingest.py
│   └── unified_ingest.py
├── processing/
│   └── spark_kafka_consumer.py
├── tests/
│   ├── qdrant_test.py
│   ├── test_llm.py
│   └── test_spark.py
├── utils/
│   └── search_qdrant.py
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/dhruvpandoh/IncidentIQ.git
cd IncidentIQ
```

### 2. Create a Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Start the infrastructure

```bash
docker compose up -d
```

MongoDB must also be available locally at:

```text
mongodb://localhost:27017/
```

### 4. Download the classification model

```bash
python classification/download_model_once.py
```

### 5. Start the classification API

```bash
cd classification
uvicorn fastapi_model:app --host 0.0.0.0 --port 8000 --reload
cd ..
```

### 6. Start data ingestion

```bash
python ingestion/unified_ingest.py
```

### 7. Start Spark processing

```bash
spark-submit \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.3.2 \
  processing/spark_kafka_consumer.py
```

### 8. Start the dashboard

```bash
python dashboard/app.py
```

## Vector Search

IncidentIQ generates semantic embeddings and stores them in Qdrant for similarity-based retrieval of related crisis reports.

This supports context-aware analysis of emerging incidents and provides the retrieval layer used by the system’s semantic search functionality.

## Testing

The repository includes tests for:

- Local model classification
- Spark configuration
- Qdrant connectivity

Tests are located in:

```text
tests/
```

## Current Status

IncidentIQ is a local development project focused on real-time crisis detection, event classification, semantic retrieval, and monitoring.

The system demonstrates an end-to-end streaming architecture spanning ingestion, distributed processing, machine learning inference, structured storage, vector search, and visualization.