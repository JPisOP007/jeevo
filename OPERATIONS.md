# Operations Guide

Operational runbooks, monitoring procedures, and troubleshooting guides.

## 1. Startup Procedures

### 1.1 Pre-Startup Checklist

```bash
#!/bin/bash
echo "=== Pre-Startup Checklist ==="

# 1. Check system resources
echo "✓ Checking system resources..."
free -h | head -n 2
df -h / | tail -n 1

# 2. Check services
echo "✓ Checking PostgreSQL..."
pg_isready -h DATABASE_HOST -p 5432

echo "✓ Checking Redis..."
redis-cli -h REDIS_HOST ping

# 3. Check configuration
echo "✓ Checking .env file..."
[ -f .env ] && echo "✓ .env exists" || echo "✗ .env missing"

# 4. Check database connectivity
echo "✓ Testing database..."
python -c "import asyncpg; asyncio.run(test_db())"

# 5. Verify medical RAG
echo "✓ Verifying medical RAG..."
python -c "from medical_rag.vector_store import MedicalVectorStore; vs = MedicalVectorStore(); print(f'✓ {vs.collection.count()} chunks loaded')"

echo "=== All checks passed ==="
```

### 1.2 Startup Sequence

```bash
# 1. Start infrastructure
docker-compose up -d postgres redis

# 2. Wait for services
sleep 10
pg_isready -h localhost -p 5432
redis-cli ping

# 3. Run migrations
alembic upgrade head

# 4. Clear cache
redis-cli FLUSHDB

# 5. Start application
gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 app.main:app

# 6. Verify startup
curl http://localhost:8000/health/
```

### 1.3 Shutdown Sequence

```bash
# 1. Stop accepting new requests
# Set maintenance mode flag

# 2. Wait for in-flight requests
sleep 30

# 3. Shutdown application gracefully
# Send SIGTERM, wait max 20 seconds

# 4. Stop services
docker-compose down --timeout 10

# 5. Verify all stopped
docker-compose ps
ps aux | grep gunicorn
```

## 2. Monitoring & Health Checks

### 2.1 Health Check Endpoint

```python
# GET /health/
# Returns application and dependency health status

{
    "status": "healthy",
    "version": "1.0.0",
    "timestamp": "2024-01-01T12:00:00Z",
    "components": {
        "database": {
            "status": "connected",
            "pool_size": 20,
            "active_connections": 5
        },
        "redis": {
            "status": "connected",
            "memory_used_mb": 245
        },
        "rag_system": {
            "status": "active",
            "chunks_loaded": 6565,
            "last_update": "2024-01-01T00:00:00Z"
        }
    }
}
```

### 2.2 Key Metrics to Monitor

**Response Times:**
- Webhook endpoint: <1 second (median)
- Medical query response: <3 seconds (median)
- Vector search: <500ms (median)
- Database queries: <100ms (median)

**Error Rates:**
- Overall error rate: <0.1%
- Database errors: <0.05%
- Timeout errors: <0.01%
- API limit errors: <0.02%

**Resource Usage:**
- Memory: <80% utilization
- CPU: <70% average
- Disk: <80% filled
- Database connections: <80% of pool

**RAG System:**
- Vector DB response: <500ms
- Confidence scores: >0.6 (median)
- Source citations: 100% present
- Knowledge base freshness: <7 days

### 2.3 Prometheus Metrics

```python
# In app/main.py
from prometheus_client import Counter, Histogram, Gauge

# Counters
medical_queries_total = Counter('medical_queries_total', 'Total medical queries')
validation_errors_total = Counter('validation_errors_total', 'Total validation errors')

# Histograms
query_duration_seconds = Histogram('query_duration_seconds', 'Query duration')
vector_search_duration_seconds = Histogram('vector_search_duration_seconds', 'Vector search duration')

# Gauges
active_connections = Gauge('active_connections', 'Active database connections')
vector_db_chunks = Gauge('vector_db_chunks', 'Chunks in vector DB')

# Usage
with query_duration_seconds.time():
    response = await process_query(message)
```

### 2.4 Monitoring Stack

```yaml
# docker-compose.yml additions
services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-storage:/var/lib/grafana
    depends_on:
      - prometheus

volumes:
  grafana-storage:
```

## 3. Logging Strategy

### 3.1 Log Levels

```python
# DEBUG: Detailed diagnostic information
logger.debug(f"Processing message from {user_id}")

# INFO: General informational messages
logger.info(f"Medical query detected: {query_type}")

# WARNING: Warning messages for potentially problematic situations
logger.warning(f"Low confidence response: {confidence_score}")

# ERROR: Error messages for serious problems
logger.error(f"Database connection failed: {error}")

# CRITICAL: Critical messages for system failures
logger.critical("Redis unavailable, system may be unstable")
```

### 3.2 Structured Logging

```python
import json
import logging

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "extra": {
                k: v for k, v in record.__dict__.items()
                if k not in ['name', 'msg', 'args', 'created', 'filename', 'funcName', 'levelname', 'levelno', 'lineno', 'module', 'msecs', 'message', 'pathname', 'process', 'processName', 'relativeCreated', 'thread', 'threadName']
            }
        }
        return json.dumps(log_data)

# Configure
handler = logging.FileHandler('/var/log/jeevo/app.json')
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)
```

### 3.3 Log Aggregation

```bash
# Elasticsearch, Kibana setup (optional)
# Aggregate all logs for centralized monitoring

# Basic ELK docker-compose:
version: '3'
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.0.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
  
  filebeat:
    image: docker.elastic.co/beats/filebeat:8.0.0
    volumes:
      - /var/log/jeevo:/var/log/jeevo:ro
      - ./filebeat.yml:/usr/share/filebeat/filebeat.yml
  
  kibana:
    image: docker.elastic.co/kibana/kibana:8.0.0
    ports:
      - "5601:5601"
```

## 4. Backup & Recovery

### 4.1 Backup Schedule

```bash
#!/bin/bash
# /usr/local/bin/backup-jeevo.sh

BACKUP_DIR="/backup/jeevo"
RETENTION_DAYS=30

# Database backup
echo "Backing up PostgreSQL..."
pg_dump -U jeevo_app -d jeevo | gzip > $BACKUP_DIR/db_$(date +%Y%m%d_%H%M%S).sql.gz

# Vector database backup
echo "Backing up Vector DB..."
tar -czf $BACKUP_DIR/vector_db_$(date +%Y%m%d_%H%M%S).tar.gz medical_rag/vector_db/

# Configuration backup
echo "Backing up configuration..."
tar -czf $BACKUP_DIR/config_$(date +%Y%m%d_%H%M%S).tar.gz \
  .env.production prometheus.yml grafana-dashboards/

# Cleanup old backups
find $BACKUP_DIR -name "db_*.sql.gz" -mtime +$RETENTION_DAYS -delete
find $BACKUP_DIR -name "vector_db_*.tar.gz" -mtime +$RETENTION_DAYS -delete
find $BACKUP_DIR -name "config_*.tar.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed"
```

### 4.2 Backup Automation

```bash
# Add to crontab (crontab -e)
# Daily backup at 2 AM
0 2 * * * /usr/local/bin/backup-jeevo.sh >> /var/log/backups.log 2>&1

# Weekly full backup
0 3 * * 0 /usr/local/bin/backup-jeevo-full.sh >> /var/log/backups.log 2>&1
```

### 4.3 Recovery Procedures

**Database Recovery:**
```bash
# Stop application
systemctl stop jeevo

# Restore from backup
gunzip -c /backup/jeevo/db_20240101_020000.sql.gz | psql -U jeevo_app -d jeevo

# Verify
psql -U jeevo_app -d jeevo -c "SELECT COUNT(*) FROM messages;"

# Start application
systemctl start jeevo
```

**Vector Database Recovery:**
```bash
# Stop application
systemctl stop jeevo

# Remove corrupted database
rm -rf medical_rag/vector_db

# Restore backup
tar -xzf /backup/jeevo/vector_db_20240101_020000.tar.gz -C medical_rag/

# Verify
python -c "from medical_rag.vector_store import MedicalVectorStore; vs = MedicalVectorStore(); print(f'{vs.collection.count()} chunks')"

# Start application
systemctl start jeevo
```

## 5. Performance Tuning

### 5.1 Database Query Optimization

```bash
# Identify slow queries
psql -U jeevo_app -d jeevo

# Enable query analysis
SET log_min_duration_statement = 1000;  -- Log queries > 1 second

# Check query plans
EXPLAIN ANALYZE SELECT * FROM messages WHERE user_id = 'abc123';
```

### 5.2 Index Management

```sql
-- Create optimal indexes
CREATE INDEX CONCURRENTLY idx_messages_user_created 
  ON messages(user_id, created_at DESC);

CREATE INDEX CONCURRENTLY idx_sessions_active 
  ON sessions(user_id) WHERE end_time IS NULL;

-- Monitor index usage
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
```

### 5.3 Redis Optimization

```bash
# Monitor Redis
redis-cli
> INFO stats
> INFO memory
> DBSIZE

# Clear old cache entries
SCAN 0 MATCH "*" COUNT 1000

# Set appropriate expiration
EXPIRE key_name 3600  # 1 hour TTL
```

## 6. Troubleshooting Runbook

### 6.1 High Response Times

```bash
# 1. Check system resources
free -m
df -h /
top -b -n 1 | head -20

# 2. Check database
psql -U jeevo_app -d jeevo
SELECT count(*) FROM pg_stat_activity;
SELECT query, mean_time FROM pg_stat_statements ORDER BY mean_time DESC;

# 3. Check Redis
redis-cli INFO stats
redis-cli --latency-history

# 4. Check vector DB size
ls -lh medical_rag/vector_db/

# 5. Profile slow queries
EXPLAIN ANALYZE SELECT ...;
```

### 6.2 High Error Rate

```bash
# 1. Check application logs
tail -f /var/log/jeevo/app.log | grep ERROR

# 2. Check error distribution
grep "ERROR" /var/log/jeevo/app.log | awk '{print $NF}' | sort | uniq -c | sort -rn

# 3. Check external services
curl -s https://api.groq.com/health
curl -s https://api.whatsapp.com/health
pg_isready -h DATABASE_HOST -p 5432

# 4. Check recent deployments
git log --oneline -10

# 5. Rollback if needed
docker pull jeevo:previous-version
docker-compose up -d
```

### 6.3 Database Connection Issues

```bash
# 1. Check connection pool
psql -U jeevo_app -d jeevo -c "SELECT count(*) FROM pg_stat_activity;"

# 2. Check for long-running queries
SELECT pid, usename, state, query 
FROM pg_stat_activity 
WHERE state != 'idle' 
ORDER BY query_start ASC;

# 3. Terminate stuck connections (careful!)
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE pid <> pg_backend_pid() AND state = 'idle in transaction'
AND query_start < NOW() - INTERVAL '1 hour';

# 4. Check credentials
psql -U jeevo_app -h DATABASE_HOST -d jeevo -c "SELECT 1;"
```

### 6.4 Memory Leaks

```python
# Monitor memory usage over time
import psutil
import asyncio

async def memory_monitor():
    process = psutil.Process()
    while True:
        mem = process.memory_info().rss / 1024 / 1024  # MB
        print(f"Memory: {mem:.2f} MB")
        await asyncio.sleep(60)

# Run in background
asyncio.create_task(memory_monitor())
```

## 7. Incident Management

### 7.1 Incident Severity Levels

**Severity 1 (Critical)**
- Complete service outage
- Data corruption
- Security breach
- All users affected

**Severity 2 (High)**
- Partial service degradation
- Medical responses failing
- Performance <500ms degraded
- >10% users affected

**Severity 3 (Medium)**
- Minor feature issues
- Performance slightly degraded
- <5% users affected

**Severity 4 (Low)**
- UI/UX issues
- Non-critical features down
- Single user affected

### 7.2 Response Procedures

```
INCIDENT DECLARED
        ↓
[5 min] Acknowledge incident
        ↓
[10 min] Identify severity level
        ↓
[15 min] Activate incident commander
        ↓
[20 min] Begin mitigation
        ↓
[Post-Incident] Root cause analysis + prevention
```

### 7.3 Communication Template

```
🚨 INCIDENT ALERT

Service: Jeevo Medical Bot
Status: INVESTIGATING

Last Known Status: [timestamp]
Affected Users: [count/percentage]
Current Action: [mitigation steps]
ETA Resolution: [time estimate]

Updates every 15 minutes.
Subscribe: incidents@example.com
```

## 8. Maintenance Windows

### 8.1 Scheduled Maintenance

```
Maintenance Window: Every 3rd Sunday, 2:00 AM - 4:00 AM UTC
Estimated Downtime: 30 minutes
Services Affected: Medical queries (WhatsApp temporarily unavailable)
```

### 8.2 Pre-Maintenance Checklist

- [ ] Notify users 48 hours in advance
- [ ] Create full system backup
- [ ] Test rollback procedure
- [ ] Have on-call team ready
- [ ] Update status page
- [ ] Prepare rollback plan

### 8.3 Post-Maintenance Checklist

- [ ] Run health checks
- [ ] Verify all services
- [ ] Check error logs
- [ ] Confirm metrics normal
- [ ] Update documentation
- [ ] Notify users completion

## 9. Disaster Recovery Plan

### 9.1 RTO & RPO

- **RTO** (Recovery Time Objective): 1 hour
- **RPO** (Recovery Point Objective): 15 minutes

### 9.2 Failover Procedure

```bash
# 1. Assess damage (5 min)
# 2. Activate backup system (10 min)
# 3. Verify data integrity (15 min)
# 4. Route traffic to backup (5 min)
# 5. Monitor closely (ongoing)

# Total RTO: ~35 minutes
```

### 9.3 Data Recovery

```bash
# Restore from latest backup
/usr/local/bin/restore-jeevo.sh backup_timestamp

# Verify
python -c "
from app.models import Message
from app.database.base import db
count = db.query(Message).count()
print(f'✓ {count} messages restored')
"
```

---

**Document Version**: 1.0  
**Last Updated**: [Date]  
**Next Review**: [Date]  
**Maintainer**: DevOps Team
