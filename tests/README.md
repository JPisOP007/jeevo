# Test Suite

This directory contains the test suites for the medical validation system.

## Test Files

### 1. `test_medical_validation.py`
Comprehensive test suite for the medical validation system (16 tests):
- Medical sources and conditions loading
- Symptom and treatment verification
- Claim extraction and semantic validation
- Full validation pipeline with risk assessment
- Emergency and high-risk keyword detection
- Legacy validation compatibility

**Run:** `python tests/test_medical_validation.py`

### 2. `test_whatsapp_integration.py`
End-to-end WhatsApp integration test (5 tests):
- WhatsApp message ingestion and parsing
- LLM processing and response generation
- Medical validation and risk assessment
- Escalation logic
- TTS audio generation
- WhatsApp response formatting

**Run:** `python tests/test_whatsapp_integration.py`

## Test Results

Both test suites should show 100% pass rate:
- Medical Validation: ✅ 16/16 tests passing
- WhatsApp Integration: ✅ 5/5 tests passing

## Database Setup

Before running medical validation tests, initialize the database:
```bash
python setup_validation_db.py
```

This loads:
- 6 authoritative medical sources (WHO, ICMR, MOH India, etc.)
- 10 medical conditions with symptoms, treatments, and contraindications

## Production Notes

- Tests use SQLite for speed
- Production should use PostgreSQL (set `DATABASE_URL` environment variable)
- All medical validation logic is production-ready
- WhatsApp integration test uses mocks - replace with actual API calls in production
