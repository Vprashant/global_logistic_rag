# Quick Start Guide

Get the Global Logistics Intelligence Hub up and running in 5 minutes!

## 🚀 Quick Setup

### Prerequisites
- Docker & Docker Compose
- Python 3.10+ (for local development)

### 1. Clone and Configure

```bash
git clone https://github.com/yourusername/global-logistics-rag.git
cd global-logistics-rag

# Copy environment file
cp .env.example .env
```

### 2. Add Your API Keys

Edit `.env` and add:
```bash
OPENAI_API_KEY=sk-your-key-here  # Required
PINECONE_API_KEY=your-key-here   # Optional - uses Milvus if not provided
```

### 3. Start Services

```bash
# Start all services with Docker Compose
docker-compose up -d

# Wait for services to be ready (30 seconds)
sleep 30

# Check health
curl http://localhost:8000/health
```

### 4. Test the API

```bash
# Access the interactive API docs
open http://localhost:8000/docs

# Or test with curl
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-token" \
  -d '{
    "query": "What caused shipment delays in Q1 2024?",
    "top_k": 5
  }'
```

## 📊 Access Dashboards

- **API Documentation**: http://localhost:8000/docs
- **Grafana Monitoring**: http://localhost:3000 (admin/admin)
- **Milvus Dashboard**: http://localhost:9091
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin)

## 🔄 Data Ingestion

### Upload a Document

```bash
curl -X POST http://localhost:8000/api/v1/upload \
  -H "Authorization: Bearer test-token" \
  -F "file=@your-document.pdf"
```

### Ingest from Python

```python
from ingestion.pipeline import IngestionPipeline

pipeline = IngestionPipeline()

# Ingest from S3
pipeline.ingest_s3_documents(
    bucket="your-bucket",
    prefix="documents/"
)

# Ingest from database
pipeline.ingest_database_records(
    query="SELECT * FROM shipments",
    query_name="shipments",
    connection_string="postgresql://user:pass@host/db"
)
```

## 🧪 Sample Queries

Once data is ingested, try these queries:

```bash
# Query 1: Shipment delays
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-token" \
  -d '{"query": "Show me shipments delayed by more than 5 days"}'

# Query 2: Port congestion
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-token" \
  -d '{"query": "What is the current port congestion in Singapore?"}'

# Query 3: Vendor contracts
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-token" \
  -d '{"query": "Find all active vendor contracts"}'
```

## 📝 Key Features Demo

### 1. Multimodal Search (Text + Images)

```python
from ingestion.parsers.image_parser import ImageParser

parser = ImageParser(vlm_provider="openai", api_key="your-key")

# Parse warehouse image
with open("warehouse.jpg", "rb") as f:
    result = parser.parse_cargo_image(f.read())
    print(result['description'])
```

### 2. Advanced Chunking

```python
from ingestion.processors.chunking import get_chunker

# Semantic chunking
chunker = get_chunker("semantic", similarity_threshold=0.7)
chunks = chunker.chunk(your_text)

# Parent-child chunking
chunker = get_chunker("parent_child", child_chunk_size=400)
chunks = chunker.chunk(your_text)
```

### 3. PII Masking

```python
from common.security.masking import PIIMasker

masker = PIIMasker()
result = masker.mask_text("Contact John at john@example.com or 555-1234")
print(result['masked_text'])
# Output: "Contact John at ********@example.com or ****-1234"
```

### 4. Hybrid Search

```python
from generation.retriever import HybridRetriever

retriever = HybridRetriever(
    vector_db_client=your_vector_db,
    semantic_weight=0.7,
    bm25_weight=0.3
)

results = retriever.search(
    query="delayed shipments",
    user_role="supply_chain_manager",
    top_k=5
)
```

## 🛠️ Development Mode

For local development without Docker:

```bash
# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL and Redis locally
# macOS: brew services start postgresql redis
# Ubuntu: sudo systemctl start postgresql redis

# Run API server
uvicorn api.main:app --reload --port 8000

# Run ingestion pipeline
python -m ingestion.pipeline
```

## 🔍 Monitoring

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api

# Last 100 lines
docker-compose logs --tail=100 api
```

### Check Service Health

```bash
# API health
curl http://localhost:8000/health

# System stats
curl http://localhost:8000/api/v1/stats

# Prometheus metrics
curl http://localhost:9090/metrics
```

## 🛑 Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

## 📚 Next Steps

1. **Load Sample Data**: See [SETUP.md](SETUP.md) for data loading examples
2. **Configure Vector DB**: Set up Pinecone or use local Milvus
3. **Set up Authentication**: Implement JWT token generation
4. **Deploy to Production**: Follow deployment guide in [SETUP.md](SETUP.md)

## 🆘 Troubleshooting

### Services won't start?
```bash
# Check Docker is running
docker ps

# Check logs
docker-compose logs

# Restart services
docker-compose restart
```

### API returns errors?
```bash
# Check environment variables
cat .env

# Verify services are healthy
docker-compose ps

# Check API logs
docker-compose logs api
```

### Database connection issues?
```bash
# Check PostgreSQL is ready
docker-compose exec postgres pg_isready

# Check Redis is ready
docker-compose exec redis redis-cli ping
```

## 💡 Tips

1. **First time?** Start with the interactive docs at http://localhost:8000/docs
2. **Need data?** Use the sample data loading script
3. **Testing?** Use the mock endpoints that don't require real data
4. **Production?** Review security settings in [SETUP.md](SETUP.md)

## 📞 Support

- **Documentation**: See [README.md](README.md) and [SETUP.md](SETUP.md)
- **Issues**: Open a GitHub issue
- **Questions**: Check existing issues or discussions

---

**Ready to process 1000+ logistics documents?** Let's go! 🚢📦
