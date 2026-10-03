# IncidentIQ

IncidentIQ is a real-time crisis intelligence pipeline that ingests public news, classifies potential incidents with a locally hosted language model, stores structured and semantic representations, and exposes the results through an interactive dashboard.

The goal is to turn a noisy stream of public information into structured, searchable signals that make emerging incidents easier to identify and investigate.

## Demo

IncidentIQ provides two main views:

### Live Incident Feed

The dashboard displays recently detected incidents alongside:

- AI-generated crisis classifications
- source and timestamp information
- incident distribution by category
- incident volume over time
- a 24-hour activity heatmap

### Semantic Search

IncidentIQ also supports semantic search over previously processed incidents.

Instead of requiring exact keyword matches, a query is embedded using Sentence Transformers and compared against stored vectors in Qdrant.

For example:

```text
political unrest in Europe
```

can retrieve semantically related incidents even when the exact phrase does not appear in the original article.

---

## Architecture

```text
                   ┌──────────────────┐
                   │ Google News RSS  │
                   └────────┬─────────┘
                            │
                            ▼
                      ┌──────────┐
                      │  Kafka   │
                      └────┬─────┘
                           │
                           ▼
               ┌──────────────────────┐
               │ Spark Structured     │
               │ Streaming            │
               └──────────┬───────────┘
                          │
                          ▼
                ┌──────────────────┐
                │ FastAPI +        │
                │ FLAN-T5          │
                │ Classifier       │
                └────────┬─────────┘
                         │
             ┌───────────┴───────────┐
             ▼                       ▼
       ┌─────────────┐          ┌─────────────┐
       │  MongoDB    │          │   Qdrant    │
       │ structured  │          │ embeddings  │
       │ records     │          │ + search    │
       └──────┬──────┘          └──────┬──────┘
              │                        │
              └───────────┬────────────┘
                          ▼
                 ┌─────────────────┐
                 │ Dash Dashboard  │
                 └─────────────────┘
```

---

## How It Works

### 1. Ingestion

Public news articles are pulled from Google News RSS and published to Kafka.

The architecture also contains ingestion modules for additional sources such as Reddit and Bluesky.

### 2. Streaming Processing

Apache Spark Structured Streaming consumes incoming Kafka events and coordinates downstream processing.

Kafka decouples ingestion from processing so producers do not need to know how downstream consumers classify or persist the data.

### 3. AI Classification

Incoming text is sent to a FastAPI service backed by a locally hosted FLAN-T5 model.

The model classifies relevant content into crisis categories such as:

- War
- Pandemic
- Cyberattack
- Terrorist Attack
- Natural Disaster
- Civil Unrest
- Crime
- Financial Crisis
- Infrastructure Failure
- Environmental Crisis

Keeping the model behind an API boundary allows the classifier to be changed independently from the streaming pipeline.

### 4. Persistence

Processed incidents are stored in MongoDB for structured retrieval and dashboard analytics.

### 5. Semantic Search

Incident text is embedded using `all-MiniLM-L6-v2`.

The resulting vectors are stored in Qdrant and used to retrieve semantically related incidents from natural-language queries.

---

## Tech Stack

### Backend and Data

- Python
- Apache Kafka
- Apache Spark / PySpark
- FastAPI
- MongoDB
- Qdrant

### AI / ML

- Hugging Face Transformers
- FLAN-T5
- Sentence Transformers
- `all-MiniLM-L6-v2`

### Frontend

- Dash
- Plotly
- Dash Bootstrap Components

### Infrastructure

- Docker
- Docker Compose

---

## Project Structure

```text
IncidentIQ/
├── classification/
│   ├── download_model_once.py
│   ├── fastapi_model.py
│   └── models/
│
├── consumer/
│   └── general.consumer.py
│
├── dashboard/
│   └── app.py
│
├── ingestion/
│   ├── bluesky_ingest.py
│   ├── google_ingest.py
│   ├── reddit_ingest.py
│   └── unified_ingest.py
│
├── processing/
│   └── spark_kafka_consumer.py
│
├── tests/
│   ├── qdrant_test.py
│   ├── test_llm.py
│   └── test_spark.py
│
├── utils/
│   └── search_qdrant.py
│
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

# Running IncidentIQ Locally

## 1. Create the Python environment

Python 3.11 is recommended.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 2. Download the local classifier

```bash
python classification/download_model_once.py
```

The model is stored locally under:

```text
classification/models/
```

Model files are intentionally excluded from Git.

---

## 3. Start the infrastructure

```bash
docker compose up -d
```

Docker Compose starts the infrastructure required by the pipeline, including:

- Kafka
- ZooKeeper
- MongoDB
- Qdrant
- Spark services

MongoDB is exposed locally at:

```text
mongodb://localhost:27017/
```

Qdrant is exposed at:

```text
http://localhost:6333
```

Kafka brokers are available through:

```text
localhost:9095
localhost:9096
localhost:9097
```

---

## 4. Create Kafka Topics

On a fresh Docker environment, create the ingestion topics:

```bash
docker exec incidentiq-kafka1-1 kafka-topics \
  --bootstrap-server kafka1:29092 \
  --create --if-not-exists \
  --topic reddit_posts \
  --partitions 3 \
  --replication-factor 3
```

```bash
docker exec incidentiq-kafka1-1 kafka-topics \
  --bootstrap-server kafka1:29092 \
  --create --if-not-exists \
  --topic bluesky_posts \
  --partitions 3 \
  --replication-factor 3
```

```bash
docker exec incidentiq-kafka1-1 kafka-topics \
  --bootstrap-server kafka1:29092 \
  --create --if-not-exists \
  --topic google_news_posts \
  --partitions 3 \
  --replication-factor 3
```

Verify:

```bash
docker exec incidentiq-kafka1-1 kafka-topics \
  --bootstrap-server kafka1:29092 \
  --list
```

---

## 5. Start the Classification API

From the `classification` directory:

```bash
cd classification
source ../.venv/bin/activate

python -m uvicorn fastapi_model:app \
  --host 0.0.0.0 \
  --port 8000
```

Verify:

```bash
curl http://127.0.0.1:8000/
```

---

## 6. Start Spark Streaming

From the project root:

```bash
source .venv/bin/activate

spark-submit \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3 \
  processing/spark_kafka_consumer.py
```

---

## 7. Start Google News Ingestion

In another terminal:

```bash
source .venv/bin/activate
python ingestion/google_ingest.py
```

Incoming articles will begin flowing through Kafka and Spark into the classification and persistence layers.

---

## 8. Start the Dashboard

```bash
source .venv/bin/activate
python dashboard/app.py
```

Open:

```text
http://127.0.0.1:4567
```

---

## Verify Processed Records

To inspect how many incidents have reached MongoDB:

```bash
docker exec incidentiq-mongodb mongosh --quiet --eval \
'db.getSiblingDB("incidentiq").unified_posts.countDocuments({})'
```

---

## Current Limitations

The current classifier can occasionally force unrelated news into the closest available crisis category.

For example, entertainment or general business stories may sometimes receive a crisis label despite not describing a genuine incident.

A production version would add:

- an explicit crisis vs. non-crisis relevance stage
- confidence or abstention thresholds
- a labeled evaluation dataset
- per-category precision and recall measurement
- stronger deduplication and source-quality controls

These improvements would allow classification quality to be measured systematically rather than relying only on individual examples.

---

## Design Decisions

### Why Kafka?

Kafka separates data producers from downstream processing. New sources can publish events without needing to know how classification, storage, or analytics are implemented.

### Why Spark Structured Streaming?

Spark provides a streaming processing layer capable of consuming Kafka events and coordinating downstream transformations and model calls.

### Why keep the model behind FastAPI?

The streaming pipeline depends on a classification interface rather than a specific model implementation. This makes it possible to replace or upgrade the model independently.

### Why MongoDB and Qdrant?

MongoDB stores structured incident records used by the dashboard and analytics.

Qdrant stores vector embeddings used for semantic retrieval.

The two databases therefore serve different access patterns.

---

## Future Work

Potential extensions include:

- crisis relevance filtering before classification
- systematic classifier evaluation
- additional live data sources
- entity and location extraction
- clustering duplicate reports describing the same real-world event
- incident severity scoring
- geographic visualization
- alerting for high-confidence emerging incidents
- improved vector-search ranking

---

## Status

IncidentIQ is an experimental local prototype intended to explore real-time event ingestion, AI-assisted classification, streaming data processing, and semantic retrieval.