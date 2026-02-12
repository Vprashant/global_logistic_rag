# Global Logistics Intelligence Hub

A production-grade RAG-based AI assistant for 1,000+ supply chain managers to query shipment delays, vendor contracts, and real-time IoT sensor data.

## 🏗️ Architecture Overview

This solution implements a scalable, secure, and multimodal RAG system with:

- **Unified Ingestion Layer**: Handles PDFs, Excel files, databases, Kafka streams, and external APIs
- **Advanced Processing**: Context-aware chunking, semantic splitting, and multimodal embeddings
- **Vector Database**: Hybrid search (BM25 + Semantic) with metadata filtering
- **Security & Governance**: PII masking, RBAC, and data lineage tracking
- **Scalability**: Designed for 1000+ concurrent users with caching and optimization

## 📁 Project Structure

```
global-logistics-rag/
├── ingestion/                      # Data Ingestion Module
│   ├── connectors/                 # Source connectors
│   │   ├── s3_connector.py
│   │   ├── sharepoint_connector.py
│   │   ├── database_connector.py
│   │   ├── kafka_connector.py
│   │   └── api_connector.py
│   ├── parsers/                    # Format-specific parsers
│   │   ├── pdf_parser.py
│   │   ├── excel_parser.py
│   │   ├── image_parser.py
│   │   └── text_parser.py
│   ├── processors/                 # Data processing
│   │   ├── chunking.py
│   │   ├── normalization.py
│   │   ├── masking.py
│   │   └── embedding.py
│   ├── pipeline.py                 # Main ingestion pipeline
│   └── config.py                   # Ingestion configuration
│
├── generation/                     # Generation/Retrieval Module
│   ├── retriever.py                # Hybrid retrieval engine
│   ├── generator.py                # LLM-based response generation
│   ├── cache.py                    # Query caching layer
│   ├── reranker.py                 # Result reranking
│   └── config.py                   # Generation configuration
│
├── common/                         # Shared utilities
│   ├── database/
│   │   ├── vector_db.py           # Vector database client
│   │   ├── metadata_db.py         # Metadata/lineage database
│   │   └── cache_db.py            # Cache database (Redis)
│   ├── security/
│   │   ├── rbac.py                # Role-based access control
│   │   ├── masking.py             # PII/PHI masking
│   │   └── auth.py                # Authentication
│   ├── monitoring/
│   │   ├── lineage.py             # Data lineage tracking
│   │   ├── metrics.py             # Performance metrics
│   │   └── logging.py             # Centralized logging
│   ├── models/
│   │   ├── document.py            # Document models
│   │   ├── chunk.py               # Chunk models
│   │   └── schema.py              # Data schemas
│   └── utils/
│       ├── config.py              # Global configuration
│       └── helpers.py             # Helper functions
│
├── api/                            # API Layer
│   ├── main.py                     # FastAPI application
│   ├── routes/
│   │   ├── query.py
│   │   ├── ingest.py
│   │   └── admin.py
│   └── middleware/
│       ├── auth.py
│       └── rate_limit.py
│
├── tests/                          # Test suite
│   ├── test_ingestion/
│   ├── test_generation/
│   └── test_integration/
│
├── docker/                         # Docker configuration
│   ├── Dockerfile.ingestion
│   ├── Dockerfile.api
│   └── docker-compose.yml
│
├── scripts/                        # Utility scripts
│   ├── setup_vector_db.py
│   ├── migrate_data.py
│   └── benchmark.py
│
├── config/                         # Configuration files
│   ├── dev.yaml
│   ├── prod.yaml
│   └── schema_mappings.yaml
│
├── requirements.txt
├── pyproject.toml
├── .env.example
├── .gitignore
└── README.md
```

## 🚀 Features

### 1. Data Ingestion & Source Diversity
- ✅ PDF contracts and bills of lading from S3/SharePoint
- ✅ Shipment logs from SAP/Oracle databases
- ✅ Real-time IoT streams via Kafka/Flink
- ✅ External APIs (port congestion, weather forecasts)

### 2. Advanced Processing
- ✅ Context-aware chunking (recursive, semantic, parent-child)
- ✅ Schema normalization across disparate sources
- ✅ Multimodal processing (text, tables, images)
- ✅ Table-aware parsing with Markdown/HTML conversion

### 3. Data Lineage & Governance
- ✅ Automatic lineage tracking from source to embedding
- ✅ Versioned document index for auditability
- ✅ Metadata-enriched chunks with provenance info

### 4. Security & Data Masking
- ✅ PII/PHI masking before vector storage
- ✅ Role-Based Access Control (RBAC)
- ✅ Field-level security for sensitive data

### 5. Scaling for 1000+ Users
- ✅ Scalable vector database (Pinecone/Milvus/Weaviate)
- ✅ Hybrid search (BM25 + Semantic)
- ✅ Redis caching for frequent queries
- ✅ Async processing and connection pooling

### 6. Multimodal Processing
- ✅ Vision-Language Models for image understanding
- ✅ Cross-modal embeddings (CLIP/ImageBind)
- ✅ Late interaction models (ColBERT) for precision
- ✅ Semantic chunking with similarity-based splitting

## 📋 Prerequisites

- Python 3.10+
- Docker & Docker Compose
- PostgreSQL (for metadata)
- Redis (for caching)
- Vector Database (Pinecone/Milvus/Weaviate)
- API Keys: OpenAI/Anthropic, AWS, etc.

## 🔧 Installation

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/global-logistics-rag.git
cd global-logistics-rag
```

### 2. Set up Python environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment variables
```bash
cp .env.example .env
# Edit .env with your credentials
```

### 4. Initialize databases
```bash
python scripts/setup_vector_db.py
```

### 5. Run with Docker Compose
```bash
docker-compose up -d
```

## 🎯 Usage

### Ingestion Pipeline

```python
from ingestion.pipeline import IngestionPipeline

pipeline = IngestionPipeline()

# Ingest PDF from S3
pipeline.ingest_s3_documents(bucket="contracts", prefix="2024/")

# Ingest from database
pipeline.ingest_database_records(query="SELECT * FROM shipments WHERE date >= '2024-01-01'")

# Stream from Kafka
pipeline.ingest_kafka_stream(topic="iot-sensors")
```

### Query Interface

```python
from generation.retriever import HybridRetriever
from generation.generator import ResponseGenerator

retriever = HybridRetriever()
generator = ResponseGenerator()

# Query with RBAC
results = retriever.search(
    query="Show me all shipments delayed in Q1 2024",
    user_role="supply_chain_manager",
    filters={"region": "APAC"}
)

response = generator.generate(query, results)
```

### API Usage

```bash
# Start API server
uvicorn api.main:app --host 0.0.0.0 --port 8000

# Query endpoint
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the current port delays in Singapore?",
    "filters": {"source_type": "api", "region": "APAC"}
  }'
```

## 🔐 Security

- **Authentication**: JWT-based token authentication
- **Authorization**: Role-Based Access Control (RBAC)
- **Data Masking**: Automatic PII/PHI redaction
- **Encryption**: TLS for data in transit, AES-256 for data at rest
- **Audit Logs**: Complete lineage tracking and access logs

## 📊 Performance

- **Latency**: <200ms for cached queries, <2s for complex searches
- **Throughput**: 1000+ concurrent users
- **Scalability**: Horizontal scaling with Kubernetes
- **Caching**: 70%+ cache hit rate for common queries

## 🧪 Testing

```bash
# Run unit tests
pytest tests/test_ingestion/

# Run integration tests
pytest tests/test_integration/

# Run with coverage
pytest --cov=ingestion --cov=generation tests/
```

## 📈 Monitoring

- **Metrics**: Prometheus + Grafana dashboards
- **Logging**: Centralized logging with ELK stack
- **Tracing**: OpenTelemetry for distributed tracing
- **Lineage**: Full data provenance tracking

## 🛠️ Technology Stack

- **Vector Database**: Pinecone / Milvus / Weaviate
- **Embeddings**: OpenAI text-embedding-3-large, CLIP (images)
- **LLM**: GPT-4 / Claude 3.5 Sonnet
- **Framework**: LangChain / LlamaIndex
- **API**: FastAPI
- **Caching**: Redis
- **Database**: PostgreSQL (metadata)
- **Message Queue**: Apache Kafka
- **Monitoring**: Prometheus, Grafana, ELK

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines.

## 📄 License

MIT License - see LICENSE file for details

## 📧 Contact

For questions or support, please contact the development team.
