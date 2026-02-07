# Jeevo - WhatsApp Health Platform Backend

## Setup

1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables in `.env`:
- Add your WhatsApp Cloud API credentials
- Set a secure WEBHOOK_VERIFY_TOKEN

4. Run the server:
```bash
python -m app.main
```

Or using uvicorn directly:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Testing

Visit: http://localhost:8000/docs for interactive API documentation

## Endpoints

- `GET /` - Health check
- `GET /health` - Detailed health status
- `GET /webhook` - WhatsApp webhook verification
- `POST /webhook` - Receive WhatsApp messages