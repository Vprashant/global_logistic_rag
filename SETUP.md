# Setup Guide - Global Logistics Intelligence Hub

This guide will help you set up and run the Global Logistics RAG system.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Database Setup](#database-setup)
5. [Running the Application](#running-the-application)
6. [Testing](#testing)
7. [Deployment](#deployment)

## Prerequisites

### Required Software
- Python 3.10 or higher
- PostgreSQL 14+
- Redis 6+
- Docker & Docker Compose (recommended)

### Required Accounts
- OpenAI API key (for embeddings and LLM)
- Anthropic API key (optional, for Claude)
- Pinecone account (or alternative vector DB)
- AWS account (for S3 access)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/global-logistics-rag.git
cd global-logistics-rag
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Additional System Dependencies

For PDF processing:
```bash
# macOS
brew install poppler

# Ubuntu/Debian
sudo apt-get install poppler-utils

# Windows
# Download from: https://github.com/oschwartz10612/poppler-windows/releases
```

## Configuration

### 1. Environment Variables

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` and fill in your credentials:

```bash
# Critical settings to configure:
OPENAI_API_KEY=sk-your-key-here
PINECONE_API_KEY=your-pinecone-key
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret

POSTGRES_HOST=localhost
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-password
POSTGRES_DB=logistics_metadata

REDIS_HOST=localhost
REDIS_PORT=6379
```

### 2. Vector Database Setup

#### Option A: Pinecone (Recommended for Production)

1. Sign up at [pinecone.io](https://www.pinecone.io/)
2. Create an index:
   - Name: `logistics-rag`
   - Dimensions: `3072` (for text-embedding-3-large)
   - Metric: `cosine`
3. Add credentials to `.env`

#### Option B: Milvus (Self-hosted)

```bash
# Using Docker
docker-compose up -d milvus
```

#### Option C: Weaviate (Self-hosted)

```bash
# Using Docker
docker-compose up -d weaviate
```

## Database Setup

### 1. PostgreSQL Setup

Create the metadata database:

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE logistics_metadata;

# Create user
CREATE USER rag_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE logistics_metadata TO rag_user;
```

### 2. Run Migrations

```bash
python scripts/setup_vector_db.py
```

### 3. Redis Setup

Start Redis:
```bash
# Using Docker
docker run -d -p 6379:6379 redis:latest

# Or install locally
# macOS: brew install redis && redis-server
# Ubuntu: sudo apt-get install redis-server && redis-server
```

## Running the Application

### Option 1: Docker Compose (Recommended)

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Option 2: Manual Start

#### Start API Server

```bash
cd global-logistics-rag
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Access the API:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health Check: http://localhost:8000/health

#### Run Ingestion Pipeline

```bash
python -m ingestion.pipeline
```

#### Start Background Workers (Optional)

```bash
# Start Celery worker
celery -A ingestion.tasks worker --loglevel=info

# Start Celery beat (scheduler)
celery -A ingestion.tasks beat --loglevel=info

# Flower (monitoring)
celery -A ingestion.tasks flower --port=5555
```

## Testing

### Run Unit Tests

```bash
pytest tests/test_ingestion/
pytest tests/test_generation/
```

### Run Integration Tests

```bash
pytest tests/test_integration/ -v
```

### Run with Coverage

```bash
pytest --cov=ingestion --cov=generation --cov=common tests/
```

### Manual Testing

Test the API with curl:

```bash
# Health check
curl http://localhost:8000/health

# Query endpoint
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token" \
  -d '{
    "query": "What are the current port delays?",
    "top_k": 5,
    "user_role": "supply_chain_manager"
  }'

# Upload file
curl -X POST http://localhost:8000/api/v1/upload \
  -H "Authorization: Bearer your-token" \
  -F "file=@contract.pdf"
```

## Data Ingestion Examples

### Ingest from S3

```python
from ingestion.pipeline import IngestionPipeline

pipeline = IngestionPipeline()

# Ingest contracts from S3
stats = pipeline.ingest_s3_documents(
    bucket="logistics-contracts",
    prefix="2024/",
    batch_size=10
)
print(f"Ingested: {stats['successful']} documents")
```

### Ingest from Database

```python
# Ingest shipment logs
stats = pipeline.ingest_database_records(
    query="SELECT * FROM shipments WHERE date >= '2024-01-01'",
    query_name="shipments_2024",
    connection_string="postgresql://user:pass@localhost/db"
)
```

### Ingest from Kafka

```python
# Stream IoT sensor data
stats = pipeline.ingest_kafka_stream(
    topic="iot-sensors",
    batch_size=50,
    max_batches=100
)
```

### Ingest from APIs

```python
# Ingest port congestion data
stats = pipeline.ingest_api_data(
    api_type="port_congestion",
    port_codes=['SGSIN', 'USNYC', 'NLRTM']
)
```

## Deployment

### Docker Deployment

```bash
# Build images
docker-compose build

# Push to registry
docker tag global-logistics-rag:latest your-registry/global-logistics-rag:latest
docker push your-registry/global-logistics-rag:latest

# Deploy
docker-compose -f docker-compose.prod.yml up -d
```

### Kubernetes Deployment

```bash
# Apply configurations
kubectl apply -f k8s/

# Check status
kubectl get pods -n logistics-rag
kubectl get services -n logistics-rag

# View logs
kubectl logs -f deployment/api-server -n logistics-rag
```

### Cloud Deployment (AWS)

1. **ECS/EKS for containers**
2. **RDS for PostgreSQL**
3. **ElastiCache for Redis**
4. **S3 for document storage**
5. **MSK for Kafka**
6. **CloudWatch for monitoring**

## Monitoring

### Prometheus + Grafana

Access Grafana:
- URL: http://localhost:3000
- Default credentials: admin/admin

Import dashboards:
- API performance
- Ingestion metrics
- Vector DB statistics
- Cache hit rates

### Logs

View application logs:
```bash
# Docker
docker-compose logs -f api

# Kubernetes
kubectl logs -f deployment/api-server

# Local
tail -f logs/app.log
```

## Troubleshooting

### Common Issues

#### 1. Import Errors

```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

#### 2. Database Connection Errors

```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432

# Check credentials in .env
cat .env | grep POSTGRES
```

#### 3. Vector DB Connection Errors

```bash
# Test Pinecone connection
python -c "import pinecone; pinecone.init(api_key='your-key')"

# Check Milvus/Weaviate is running
docker ps | grep milvus
```

#### 4. Out of Memory Errors

Reduce batch sizes in configuration:
```python
# In config
BATCH_SIZE=5  # Reduce from 10
MAX_CONCURRENT_INGESTIONS=2  # Reduce from 5
```

### Getting Help

- Check logs: `docker-compose logs -f`
- GitHub Issues: https://github.com/yourusername/global-logistics-rag/issues
- Documentation: See README.md

## Performance Tuning

### Vector Database

- Enable caching for frequent queries
- Use hybrid search for better accuracy
- Tune similarity thresholds
- Implement query result caching

### API Server

- Increase worker count: `--workers 4`
- Enable response caching
- Use connection pooling
- Implement rate limiting

### Ingestion Pipeline

- Adjust batch sizes based on memory
- Use parallel processing
- Enable incremental updates
- Schedule off-peak ingestion

## Security Checklist

- [ ] Change default passwords
- [ ] Enable HTTPS/TLS
- [ ] Configure firewall rules
- [ ] Set up JWT authentication
- [ ] Enable PII masking
- [ ] Configure RBAC
- [ ] Regular security updates
- [ ] Enable audit logging
- [ ] Backup strategy in place

## Next Steps

1. Load sample data: `python scripts/load_sample_data.py`
2. Run benchmark tests: `python scripts/benchmark.py`
3. Configure monitoring dashboards
4. Set up automated backups
5. Implement CI/CD pipeline

For more information, see the main [README.md](README.md).
