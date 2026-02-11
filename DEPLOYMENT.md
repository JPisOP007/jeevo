# Production Deployment Guide

Complete guide for deploying Jeevo Health Assistant to production.

## Pre-Deployment Checklist

### Infrastructure
- [ ] PostgreSQL database configured
- [ ] Redis instance running
- [ ] Server with 8GB+ RAM, 50GB storage
- [ ] SSL certificate for HTTPS
- [ ] Domain configured with DNS

### Credentials & API Keys
- [ ] Groq API key obtained (free tier sufficient)
- [ ] WhatsApp Business Account setup
- [ ] WhatsApp webhook TOKEN generated
- [ ] Database credentials secured
- [ ] Redis password configured (if needed)

### Code Preparation
- [ ] All tests passing (10/10)
- [ ] Environment variables configured (.env)
- [ ] Requirements installed (pip install -r requirements.txt)
- [ ] No debug code enabled (DEBUG=False)

## Step 1: Environment Setup

### 1.1 Create Production .env File

```bash
# Copy template
cp .env.example .env

# Edit with production values
nano .env
```

**Critical configurations:**
```bash
# Application
ENVIRONMENT=production
DEBUG=False
HOST=0.0.0.0
PORT=8000

# Database
DATABASE_URL=postgresql+asyncpg://user:password@db.host:5432/jeevo
DATABASE_ECHO=False

# Redis
REDIS_HOST=cache.host
REDIS_PORT=6379
REDIS_PASSWORD=your_password
REDIS_TTL=3600

# Groq API
GROQ_API_KEY=add_your_key_here
USE_GROQ=true

# WhatsApp
WHATSAPP_ACCESS_TOKEN=your_access_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_id
WHATSAPP_VERIFY_TOKEN=your_verify_token

# Medical RAG
MEDICAL_RAG_ENABLED=true
ENABLE_MEDICAL_VALIDATION=true
```

### 1.2 Secure Sensitive Data

```bash
# Change file permissions
chmod 600 .env

# Use vault or secrets manager for production
# Never commit .env to git
# Ensure .gitignore excludes .env
```

## Step 2: Database Setup

### 2.1 Create PostgreSQL Database

```sql
-- Connect as admin
psql -U postgres

-- Create database
CREATE DATABASE jeevo;

-- Create user with privileges
CREATE USER jeevo_app WITH PASSWORD 'strong_password_here';
ALTER ROLE jeevo_app CREATEDB;
GRANT ALL PRIVILEGES ON DATABASE jeevo TO jeevo_app;

-- Switch to database
\c jeevo

-- Set permissions
GRANT ALL ON SCHEMA public TO jeevo_app;
GRANT ALL ON ALL TABLES IN SCHEMA public TO jeevo_app;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO jeevo_app;
```

### 2.2 Verify Connection

```bash
# Test connection
python -c "
import asyncpg
import asyncio

async def test():
    conn = await asyncpg.connect('postgresql://jeevo_app:password@localhost/jeevo')
    result = await conn.fetchval('SELECT 1')
    await conn.close()
    print('✅ Database connection successful')

asyncio.run(test())
"
```

## Step 3: Redis Setup

### 3.1 Install & Configure Redis

```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# Configure
sudo nano /etc/redis/redis.conf

# Set password
requirepass your_redis_password
maxmemory 2gb
maxmemory-policy allkeys-lru
```

### 3.2 Start Redis Service

```bash
# Start service
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Verify
redis-cli -h localhost -p 6379 -a password ping
# Should return: PONG
```

## Step 4: Medical RAG Setup

### 4.1 Pre-built Vector Database

```bash
# The vector database comes pre-built with:
# - 6,565 medical knowledge chunks
# - Sentence-transformers embeddings (all-MiniLM-L6-v2)
# - Groq LLM integration ready

# Verify database
python -c "
from medical_rag.vector_store import MedicalVectorStore
vs = MedicalVectorStore()
print(f'✅ Vector DB loaded: {vs.collection.count()} chunks')
"
```

### 4.2 Test RAG System

```bash
# Run test suite
python test_medical_rag_integration.py

# Expected output: All 10/10 tests passing
```

## Step 5: Application Deployment

### 5.1 Using Uvicorn (Simple)

```bash
# Install gunicorn for production
pip install gunicorn

# Run with gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 app.main:app
```

### 5.2 Using Docker (Recommended)

```bash
# Build image
docker build -t jeevo:latest .

# Run container
docker run -d \
  --name jeevo \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/medical_rag/vector_db:/app/medical_rag/vector_db \
  jeevo:latest

# Check logs
docker logs -f jeevo
```

### 5.3 Using Docker Compose (Full Stack)

```bash
# Copy compose file
docker-compose -f docker-compose.yml up -d

# Verify all services
docker-compose ps
```

## Step 6: WhatsApp Webhook Configuration

### 6.1 Configure Webhook URL

In WhatsApp Business Dashboard:
1. Settings → API Setup
2. Webhook URL: `https://your-domain.com/webhook/`
3. Verify Token: Set in .env as WHATSAPP_VERIFY_TOKEN

### 6.2 Test Webhook

```bash
# Test endpoint response
curl -X GET "https://your-domain.com/webhook/" \
  -H "hub.mode=subscribe" \
  -H "hub.verify_token=your_verify_token" \
  -H "hub.challenge=test_challenge"
```

## Step 7: SSL/HTTPS Configuration

### 7.1 Using Let's Encrypt with Nginx

```nginx
# /etc/nginx/sites-available/jeevo
server {
    listen 80;
    server_name your-domain.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    # Certificate paths (from certbot)
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    
    # Proxy to Jeevo
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 7.2 Enable SSL Certificate

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Generate certificate
sudo certbot certonly --nginx -d your-domain.com

# Enable nginx site
sudo ln -s /etc/nginx/sites-available/jeevo /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## Step 8: Monitoring & Logging

### 8.1 Configure Logging

```python
# Add to app/main.py or settings
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/jeevo/app.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
```

### 8.2 Log Rotation

```bash
# Install logrotate configuration
sudo nano /etc/logrotate.d/jeevo
```

```
/var/log/jeevo/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
    sharedscripts
    postrotate
        systemctl reload jeevo > /dev/null 2>&1 || true
    endscript
}
```

### 8.3 Health Check Endpoint

```bash
# Test health endpoint
curl https://your-domain.com/health/

# Expected response
{
    "status": "healthy",
    "version": "1.0.0",
    "database": "connected",
    "redis": "connected",
    "rag_system": "active"
}
```

## Step 9: Performance Tuning

### 9.1 Database Optimization

```sql
-- Create indexes
CREATE INDEX idx_messages_user_id ON messages(user_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);
CREATE INDEX idx_sessions_user_id ON sessions(user_id);

-- Analyze tables
ANALYZE messages;
ANALYZE sessions;
```

### 9.2 Redis Configuration

```bash
# Optimize for cache
redis-cli CONFIG SET maxmemory-policy allkeys-lru
redis-cli CONFIG SET timeout 0
redis-cli CONFIG REWRITE
```

### 9.3 Connection Pooling

```python
# In app/main.py - verify settings
DATABASE_POOL_SIZE = 20
DATABASE_MAX_OVERFLOW = 10
REDIS_POOL_SIZE = 10
```

## Step 10: Security Hardening

### 10.1 Firewall Rules

```bash
# Allow only necessary ports
sudo ufw default deny incoming
sudo ufw allow 22/tcp     # SSH
sudo ufw allow 80/tcp     # HTTP
sudo ufw allow 443/tcp    # HTTPS
sudo ufw enable
```

### 10.2 Rate Limiting

```python
# Configured in app/routes/webhook.py
MAX_REQUESTS_PER_MINUTE = 100
MAX_REQUESTS_PER_HOUR = 10000
```

### 10.3 API Key Rotation

```bash
# Store API keys in secure vault
# Rotate every 90 days
# Monitor key usage
```

## Post-Deployment Verification

### Checklist

```bash
# 1. Health check
curl https://your-domain.com/health/

# 2. Database connectivity
python -c "from app.main import app; print('✅ App loaded')"

# 3. Redis connectivity
redis-cli -a password ping

# 4. Vector DB
python test_medical_rag_integration.py

# 5. WhatsApp webhook
# Send test message to your bot phone number

# 6. Logs
tail -f /var/log/jeevo/app.log

# 7. System resources
free -m        # Memory
df -h          # Disk
top            # CPU
```

## Monitoring Dashboard

### Key Metrics to Track

- **Response Time**: <3 seconds for medical queries
- **Error Rate**: <0.1%
- **Vector Search Latency**: <500ms
- **Database Connection Pool**: <80% utilization
- **Redis Hit Rate**: >90%
- **Uptime**: >99.9%

### Recommended Tools

- **Monitoring**: Prometheus + Grafana
- **Logs**: ELK Stack or CloudWatch
- **Alerts**: PagerDuty or Opsgenie
- **APM**: DataDog or New Relic

## Troubleshooting Production Issues

### High Response Times

```bash
# Check vector DB performance
SELECT COUNT(*) FROM chroma_embeddings;

# Verify Redis cache
redis-cli INFO stats

# Check database slow queries
SELECT * FROM pg_stat_statements WHERE mean_time > 1000;
```

### Database Connection Issues

```bash
# Check connection pool
SELECT count(*) FROM pg_stat_activity;

# Verify credentials
psql -U jeevo_app -d jeevo -c "SELECT 1"
```

### RAG System Issues

```bash
# Test RAG directly
python -c "
from app.services.medical_rag_service import get_medical_rag_service
svc = get_medical_rag_service()
print(f'Available: {svc.is_available()}')
"
```

## Backup & Recovery

### Database Backup

```bash
# Daily backup
pg_dump -U jeevo_app -d jeevo > /backup/jeevo_$(date +%Y%m%d).sql

# Automatic backup schedule
0 2 * * * pg_dump -U jeevo_app -d jeevo | gzip > /backup/jeevo_$(date +\%Y\%m\%d).sql.gz
```

### Vector DB Backup

```bash
# Backup ChromaDB
tar -czf /backup/vector_db_$(date +%Y%m%d).tar.gz medical_rag/vector_db/

# Restore if needed
tar -xzf /backup/vector_db_YYYYMMDD.tar.gz -C medical_rag/
```

## Maintenance Schedule

- **Weekly**: Review logs, check metrics
- **Monthly**: Update dependencies, security audit
- **Quarterly**: Database optimization, backup verification
- **Annually**: Full system audit, capacity planning

---

**Deployment Date**: [Fill in]  
**Next Review Date**: [Fill in]  
**Status**: [Production Ready]
