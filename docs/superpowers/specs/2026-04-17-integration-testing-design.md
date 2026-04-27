# Integration Testing Design for Nifty 50 Investment Monitoring Dashboard

## Overview
This document outlines the integration testing strategy for the Nifty 50 Investment Monitoring Dashboard, focusing on verifying data flow from ingestion through storage to API endpoints. The design follows a layered approach with comprehensive coverage of critical paths, organized by feature (dashboard views).

## Goals
- Verify data flow from ingestion → storage → API layers
- Ensure data integrity and correctness throughout the pipeline
- Validate API endpoint contracts and response shapes
- Provide comprehensive coverage of critical user paths

## Test Organization
Integration tests will be organized by feature, corresponding to the seven dashboard views specified in the project specification:
1. Market Overview
2. Movers & Extremes
3. Drawdown Scanner
4. Breakout Monitor
5. Volume Anomaly Monitor
6. Corporate Events Tracker
7. Watchlist Builder

## Layered Testing Approach

### 1. Ingestion Layer Tests
**Focus:** CSV parsing → database loading
**Test Data:** Synthetic/mock NSE CSV samples (Bhavcopy, 52-week, corporate actions)
**Key Tests:**
- CSV header validation (TODO-001)
- Idempotent loading (ON CONFLICT DO UPDATE)
- Rate limiting behavior
- Local file fallback mechanism
- Download validation (checksum/row-count comparison)
- Data type correctness (NUMERIC(12,2) for prices, BIGINT for volume)
- Date column storage as DATE type

### 2. Storage Layer Tests
**Focus:** Database constraints, relationships, data integrity
**Test Data:** Loaded test data from ingestion layer
**Key Tests:**
- Foreign key relationships between tables
- Composite primary key constraints (trade_date, symbol)
- Idempotency across all ingestion scripts (TODO-003)
- Proper indexing on fact/mart tables
- Data validation (no NULLs in non-nullable columns for current Nifty 50 members)
- Ingestion log table population
- Table row counts and integrity checks

### 3. API Layer Tests
**Focus:** Endpoint contracts, response shapes, error handling
**Test Data:** Pre-loaded test database with known datasets
**Key Tests:**
- Health endpoint (/health) - DB connectivity and table status
- All endpoint response shapes match Pydantic models
- Pagination (limit/offset) on list endpoints
- Error response format standardization
- Input validation (symbol case handling, date ranges)
- Performance benchmarks for critical endpoints
- Standard error shape: {"error": "message", "code": "ERROR_CODE", "details": {}}

### 4. End-to-End Flow Tests
**Focus:** Complete data pipelines from ingestion to API response
**Test Data:** Realistic synthetic datasets covering various scenarios
**Key Tests:**
- Bhavcopy ingestion → fact_eod_price → API price endpoints
- 52-week calculation → fact_52wk → drawdown/breakout signals
- Volume ratios → mart_stock_signals → volume anomaly detection
- Signal calculation pipeline → mart_stock_signals → dashboard views
- End-to-end data flow for each of the seven dashboard views
- Edge cases: empty data, single row, threshold boundary conditions

## Test Data Strategy
- **Primary:** Synthetic/mock data for controlled, predictable outcomes
- **Rationale:** Enables deterministic test results and edge case testing
- **Approach:** Parameterized tests with multiple data sets including boundary values
- **Fixtures:** Centralized test data generation utilities in tests/fixtures/

## Coverage Criteria
- **Critical Paths:** All data flows powering the seven dashboard views
- **Edge Cases:** Empty datasets, single records, exact threshold values
- **Error Conditions:** Invalid CSV formats, missing columns, database connection failures
- **Performance:** Basic performance benchmarks for critical API endpoints
- **Idempotency:** Re-running ingestion scripts produces consistent results

## Implementation Plan
1. Create tests/integration/ directory structure
2. Establish test fixtures and utilities for synthetic data generation
3. Implement ingestion layer tests for each pipeline component
4. Develop storage layer tests for schema validation and constraints
5. Build API layer tests using TestClient with test database
6. Create end-to-end flow tests for each dashboard view
7. Configure CI/CD to run integration tests on pull requests
8. Establish baseline performance metrics for regression detection

## Success Criteria
- All integration tests pass consistently
- Test suite completes within reasonable time (< 5 minutes for critical paths)
- Test coverage meets or exceeds 80% for integrated components
- Performance benchmarks established and monitored
- Tests catch regressions in data flow and API contracts

## Dependencies
- pytest for test framework
- pytest-fixtures for test data management
- Factory Boy or similar for synthetic data generation
- httpx.AsyncClient for API testing (already used in unit tests)
- Test database isolation (separate test schema or transaction rollback)

## Maintenance
- Tests will be updated as schema changes occur via Alembic migrations
- New features will include corresponding integration tests
- Regular review to remove brittle tests and update synthetic data generators
- Performance benchmarks updated periodically as optimizations are made