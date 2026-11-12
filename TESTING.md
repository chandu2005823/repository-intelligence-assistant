# Testing Guide

This document describes how to run tests for the Repository Intelligence Assistant.

## Backend Testing

### Prerequisites

```bash
cd repository-intelligence-assistant/backend
pip install -r requirements.txt
```

### Running Tests

Run all tests:
```bash
pytest tests/
```

Run with verbose output:
```bash
pytest tests/ -v
```

Run specific test file:
```bash
pytest tests/test_code_analyzer.py
```

Run with coverage:
```bash
pytest tests/ --cov=app --cov-report=html
```

## Test Files

### Unit Tests

- **test_code_analyzer.py** - Tests for code analysis functionality
- **test_code_chunker.py** - Tests for code chunking logic
- **test_llm_service.py** - Tests for LLM integration
- **test_vector_store.py** - Tests for ChromaDB vector store

### Integration Tests

- **test_application_workflow.py** - End-to-end application workflow tests
- **test_conversations.py** - Conversation management tests
- **test_repository_analysis.py** - Repository analysis tests
- **test_retrieval_regressions.py** - Retrieval regression tests

## Frontend Testing

Currently no automated tests configured for frontend. Manual testing recommended:

1. Start backend: `python main.py`
2. Start frontend: `npm run dev`
3. Test each feature:
   - Repository Search
   - AI Assistant
   - Dependency Explorer
   - Code Intelligence
   - Code Review

## Manual Testing Checklist

### Repository Upload
- [ ] Upload small ZIP file
- [ ] Verify extraction
- [ ] Check indexing completes
- [ ] Repository appears in dropdown

### Repository Search
- [ ] Select repository
- [ ] Enter search query
- [ ] Verify results return
- [ ] Check source citations

### AI Assistant
- [ ] Select repository
- [ ] Ask question about code
- [ ] Verify AI response
- [ ] Check source references

### Dependencies
- [ ] Select repository
- [ ] View dependency graph
- [ ] Verify relationships shown

### Code Intelligence
- [ ] Select repository
- [ ] View code relationships
- [ ] Check impact analysis

### Code Review
- [ ] Select repository
- [ ] Trigger code review
- [ ] Verify findings displayed

## Continuous Integration

Tests can be run automatically using CI/CD tools like:
- GitHub Actions
- GitLab CI
- Jenkins
- Travis CI

Configure in `.github/workflows/tests.yml` for GitHub Actions.

## Troubleshooting

### ImportError
Ensure all dependencies are installed:
```bash
pip install -r requirements.txt
```

### Database Errors
Clear test data:
```bash
rm -rf backend/data/
```

### Test Timeout
Increase pytest timeout:
```bash
pytest tests/ --timeout=300
```

## Performance Benchmarks

Expected test execution times:

| Test Suite | Duration |
|-----------|----------|
| test_code_analyzer.py | ~2s |
| test_code_chunker.py | ~1s |
| test_llm_service.py | ~5s |
| test_vector_store.py | ~3s |
| test_conversations.py | ~2s |
| All tests | ~15-20s |

## Contributing Tests

When adding new features:

1. Write tests first (TDD)
2. Ensure all tests pass: `pytest tests/ -v`
3. Maintain >80% code coverage
4. Add test to appropriate test file
5. Update this documentation

## Support

For test-related issues:
1. Check test output for error messages
2. Review test code for expected behavior
3. Create GitHub issue with test failure details
