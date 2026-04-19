#!/bin/bash
# Run all integration tests for the Nifty 50 Dashboard

set -e

echo "=== Running Integration Tests ==="

source venv/bin/activate
pytest tests/integration/ -v --tb=short

echo "=== All Integration Tests Completed ==="
