#!/bin/bash
cd /app

echo "Running PyTest"
pytest tests/test_crud.py
pytest tests/test_did.py
pytest tests/test_endpoints.py
pytest tests/test_maintenance.py
pytest tests/test_onboarding.py
pytest tests/test_pairwise.py
pytest tests/test_redis.py
pytest tests/test_repo.py
pytest tests/test_bus.py
pytest tests/test_pickup.py
pytest tests/test_storage.py
