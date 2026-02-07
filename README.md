# Jeevo Health Platform - Backend & Database Setup


What's Been Built (Tasks 2 & 9)

**Task #2: Backend Development** - FastAPI server with WhatsApp webhook integration  
**Task #9: Database & Caching** - PostgreSQL database and Redis cache setup

---

## 🌟 Overview

**Jeevo** is a healthcare platform that works entirely within WhatsApp, making medical assistance accessible to rural and semi-urban communities in India. This initial phase establishes the backend infrastructure and data layer.




## 🛠️ Tech Stack

### Backend (Task 2)
- **FastAPI** - Modern Python web framework
- **Python 3.10+** - Programming language
- **Uvicorn** - ASGI server
- **httpx** - Async HTTP client for WhatsApp API

### Database & Caching (Task 9)
- **PostgreSQL 15** - Primary database
- **SQLAlchemy 2.0** - ORM with async support
- **Redis 7** - Session management and caching
- **asyncpg** - Async PostgreSQL driver

---

## 📦 Prerequisites

### Required Software

1. **Python 3.10 or higher**
   - Download: https://www.python.org/downloads/

2. **PostgreSQL 15**
   - Download: https://www.postgresql.org/download/

3. **Redis 7**
   - Windows: https://github.com/microsoftarchive/redis/releases
   - Or use Docker: `docker run --name jeevo-redis -p 6379:6379 -d redis:7-alpine`

4. **Git** (optional, for cloning)
   - Download: https://git-scm.com/downloads

### System Requirements
- **RAM:** Minimum 4GB (8GB recommended)
- **Disk Space:** 2GB free space
- **OS:** Windows 10+, macOS 10.15+, or Linux

---

## 🚀 Installation

### Step 1: Clone or Download the Project

```bash
# If using Git:
git clone https://github.com/yourusername/jeevo-backend.git
cd jeevo-backend

# Or download and extract the ZIP file
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate it
# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

**Dependencies installed:**
```txt
fastapi==0.104.1          # Web framework
uvicorn[standard]==0.24.0 # ASGI server
pydantic==2.5.0           # Data validation
python-dotenv==1.0.0      # Environment variables
httpx==0.25.1             # HTTP client
pydantic-settings==2.1.0  # Settings management
sqlalchemy==2.0.23        # Database ORM
asyncpg==0.29.0           # Async PostgreSQL driver
psycopg2-binary==2.9.9    # PostgreSQL adapter
alembic==1.12.1           # Database migrations
redis==5.0.1              # Redis client
aioredis==2.0.1           # Async Redis
```

---

## ⚙️ Configuration

### Step 1: Create Environment File

Create a file named `.env` in the project root:

```bash
# Create the file
touch .env  # On Linux/Mac
# Or manually create .env file on Windows
```

### Step 2: Add Configuration

Copy this into your `.env` file:

```env
# Server Configuration
APP_NAME=Jeevo Health Platform
HOST=0.0.0.0
PORT=8000
DEBUG=True

# WhatsApp Cloud API Configuration
WHATSAPP_API_URL=https://graph.facebook.com/v18.0
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id_here
WHATSAPP_ACCESS_TOKEN=your_access_token_here
WHATSAPP_VERIFY_TOKEN=your_custom_verify_token_here

# Webhook Configuration
WEBHOOK_VERIFY_TOKEN=jeevo_secure_token_2024

# Database Configuration
DATABASE_URL=postgresql+asyncpg://postgres:your_password@localhost:5432/jeevo_db
DATABASE_ECHO=True

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REDIS_TTL=3600

# Session Configuration
SESSION_EXPIRE_MINUTES=60
```

### Step 3: Update Your Credentials

Replace these values:
- `your_password` - Your PostgreSQL password
- `your_phone_number_id_here` - From Meta (when you set up WhatsApp)
- `your_access_token_here` - From Meta (when you set up WhatsApp)

---

## 🗄️ Database Setup (Task 9)

### Option 1: Using pgAdmin (Recommended for Windows)

1. **Open pgAdmin**
   - Press Windows Key → Type "pgAdmin" → Open it

2. **Connect to Server**
   - Expand "Servers" → Click "PostgreSQL 15"
   - Enter your password when prompted

3. **Create Database**
   - Right-click "Databases" → "Create" → "Database..."
   - **Database name:** `jeevo_db`
   - **Owner:** `postgres`
   - Click "Save"

4. **Verify Creation**
   - You should see `jeevo_db` in the database list ✅

### Option 2: Using Command Line

```bash
# Open terminal and connect to PostgreSQL
psql -U postgres

# Enter your password when prompted

# Create the database
CREATE DATABASE jeevo_db;

# Verify it was created
\l

# Exit
\q
```

### Option 3: Using Python Script

Create a file `create_db.py`:

```python
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Update with your password
DB_PASSWORD = "your_password_here"

try:
    conn = psycopg2.connect(
        host="localhost",
        port="5432",
        user="postgres",
        password=DB_PASSWORD,
        database="postgres"
    )
    
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    # Check if database exists
    cursor.execute("SELECT 1 FROM pg_database WHERE datname='jeevo_db'")
    exists = cursor.fetchone()
    
    if not exists:
        cursor.execute("CREATE DATABASE jeevo_db")
        print("✅ Database 'jeevo_db' created successfully!")
    else:
        print("ℹ️  Database 'jeevo_db' already exists")
    
    cursor.close()
    conn.close()

except Exception as e:
    print(f"❌ Error: {e}")
```

Run it:
```bash
python create_db.py
```

---

## 🏃 Running the Application

### Step 1: Start Redis

**Using Docker (Recommended):**
```bash
docker run --name jeevo-redis -p 6379:6379 -d redis:7-alpine
```

**Or if installed locally:**
```bash
redis-server
```

### Step 2: Start PostgreSQL

PostgreSQL usually starts automatically when your computer boots.

**To verify it's running:**
- **Windows:** Services → look for "postgresql-x64-15" → should say "Running"
- **macOS:** `brew services list | grep postgresql`
- **Linux:** `sudo systemctl status postgresql`

### Step 3: Start the Backend Server

```bash
# Make sure you're in the project directory with venv activated
python -m app.main
```

**Expected output:**
```
==================================================
🚀 Starting Jeevo Health Platform
📱 WhatsApp Phone Number ID: your_phone_number_id_here
🔧 Debug Mode: True
==================================================
📊 Initializing PostgreSQL database...
✅ Database initialized successfully
🔴 Connecting to Redis...
✅ Redis connected - Keys: 0
==================================================
✅ All services started successfully!
==================================================
INFO:     Uvicorn running on http://0.0.0.0:8000
```

If you see this, **everything is working!** ✅

---

## 🧪 Testing the Setup

### Test 1: Health Check Endpoint

Open your browser and visit:
```
http://localhost:8000/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "app": "Jeevo Health Platform",
  "version": "1.0.0",
  "database": "connected",
  "redis": {
    "connected": true,
    "used_memory": "1.2M",
    "total_keys": 0,
    "uptime_seconds": 123
  }
}
```

### Test 2: Interactive API Documentation

Visit:
```
http://localhost:8000/docs
```

You should see Swagger UI with all available endpoints:
- `GET /` - Root endpoint
- `GET /health` - Health check
- `GET /webhook` - Webhook verification
- `POST /webhook` - Receive messages

### Test 3: Database Tables

1. Open **pgAdmin**
2. Navigate to: **Servers → PostgreSQL 15 → Databases → jeevo_db → Schemas → public → Tables**

You should see **6 tables**:
- ✅ `users`
- ✅ `conversations`
- ✅ `reminders`
- ✅ `local_risk_levels`
- ✅ `health_alerts`
- ✅ `sessions`

**All tables are empty initially** - they'll populate when WhatsApp messages arrive.

---

## 📚 Database Schema 

### Tables Overview

#### 1. **users** - User Profiles
```sql
- id (Primary Key)
- phone_number (Unique) - WhatsApp number
- name - User's name
- language - Preferred language (enum)
- city, state, pincode - Location data
- latitude, longitude - Coordinates
- voice_enabled - Voice feature flag
- alerts_enabled - Alerts feature flag
- created_at - Registration timestamp
- last_active - Last interaction
- is_active - Account status
```

#### 2. **conversations** - Message History
```sql
- id (Primary Key)
- user_id (Foreign Key → users)
- message_id (Unique) - WhatsApp message ID
- message_type - text/audio/image/video/document
- user_message - User's message content
- bot_response - Bot's reply
- media_url - Media file URL
- media_id - WhatsApp media ID
- created_at - Message timestamp
- response_time_ms - Response latency
```

#### 3. **reminders** - Medical Reminders
```sql
- id (Primary Key)
- user_id (Foreign Key → users)
- reminder_type - immunization/checkup/medication/test/followup
- title - Reminder title
- description - Reminder details
- scheduled_time - When to send
- sent_at - When actually sent
- is_sent - Sent status
- is_completed - Completion status
- is_recurring - Recurring flag
- recurrence_pattern - daily/weekly/monthly
- created_at, updated_at - Timestamps
```

#### 4. **local_risk_levels** - Health Risk Data
```sql
- id (Primary Key)
- pincode - Area code
- city, state - Location
- risk_level - green/yellow/red (enum)
- risk_factors - JSON array of factors
- active_diseases - JSON array of diseases
- pollution_level - Air quality
- weather_alerts - JSON weather data
- last_updated - Data freshness
- data_source - Source API
```

#### 5. **health_alerts** - Public Announcements
```sql
- id (Primary Key)
- alert_type - outbreak/immunization/weather/safety
- title - Alert headline
- message - Alert content
- target_pincodes - JSON array
- target_cities - JSON array
- target_states - JSON array
- audio_url - Voice announcement URL
- is_active - Active status
- priority - 1=low, 2=medium, 3=high
- created_at - Creation time
- expires_at - Expiration time
- sent_count - Delivery counter
```

#### 6. **sessions** - User Sessions
```sql
- id (Primary Key)
- session_id (Unique) - Session identifier
- phone_number - User's number
- context - JSON conversation context
- state - Current conversation state
- created_at - Session start
- last_accessed - Last activity
- expires_at - Session expiration
```

### Enums (Custom Types)

1. **languageenum** - Supported languages
   - `en` (English), `hi` (Hindi), `mr` (Marathi)
   - `gu` (Gujarati), `bn` (Bengali), `ta` (Tamil)
   - `te` (Telugu), `kn` (Kannada), `ml` (Malayalam), `pa` (Punjabi)

2. **remindertype** - Reminder categories
   - `immunization`, `checkup`, `medication`, `test`, `followup`

3. **risklevel** - Risk indicators
   - `green` (Low), `yellow` (Medium), `red` (High)

---

## 📁 Project Structure

```
jeevo-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app entry point
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py            # Environment configuration
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── base.py                # Database connection
│   │   ├── models.py              # 6 tables + 3 enums
│   │   └── repositories.py        # Data access layer (5 repositories)
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   └── webhook.py             # WhatsApp webhook endpoints
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── whatsapp_service.py    # WhatsApp API integration
│   │   └── cache_service.py       # Redis cache operations
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── message.py             # Pydantic models
│   │
│   └── utils/
│       ├── __init__.py
│       └── helpers.py             # Utility functions
│
├── venv/                          # Virtual environment
├── .env                           # Environment variables
├── .gitignore                     # Git ignore rules
├── requirements.txt               # Dependencies
└── README.md                      # This file
```

---

## 🔧 API Endpoints (Task 2)

### 1. Root Endpoint
```http
GET /
```

**Response:**
```json
{
  "app": "Jeevo Health Platform",
  "status": "running",
  "message": "Jeevo WhatsApp Health Platform API is active"
}
```

### 2. Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "app": "Jeevo Health Platform",
  "version": "1.0.0",
  "database": "connected",
  "redis": {
    "connected": true,
    "used_memory": "1.2M",
    "total_keys": 0,
    "uptime_seconds": 123
  }
}
```

### 3. Webhook Verification (WhatsApp Setup)
```http
GET /webhook?hub.mode=subscribe&hub.verify_token=TOKEN&hub.challenge=CHALLENGE
```

**Response:** Returns the challenge string (for Meta verification)

### 4. Receive Messages (WhatsApp Webhook)
```http
POST /webhook
```

**Request:** WhatsApp webhook payload (JSON)  
**Response:** `{"status": "ok"}`

**What happens when a message arrives:**
1. Message is parsed
2. User is fetched or created
3. Message is marked as read
4. Conversation is saved to database
5. User context is cached in Redis
6. Response is sent back to WhatsApp

---

## 🔍 How It Works

### Message Flow

```
1. User sends WhatsApp message
   ↓
2. Meta WhatsApp Cloud API receives it
   ↓
3. POST /webhook is called on your server
   ↓
4. Message is parsed (text/audio/image/etc.)
   ↓
5. User is fetched from PostgreSQL (or created if new)
   ↓
6. Message is marked as read
   ↓
7. Response is generated (currently echo/welcome)
   ↓
8. Conversation is saved to PostgreSQL
   ↓
9. User context is cached in Redis
   ↓
10. Response is sent via WhatsApp API
```

### Data Flow

**PostgreSQL:**
- Stores users permanently
- Stores all conversation history
- Stores reminders (for future use)
- Stores risk levels (for future use)
- Stores health alerts (for future use)

**Redis:**
- Caches user sessions (60 min expiry)
- Caches conversation context (30 min expiry)
- Caches risk levels (1 hour expiry)
- Provides fast access to recent data

---

Backend infrastructure and database layer are fully functional and ready for AI integration.

---

**Made with ❤️ for rural India's healthcare accessibility**
