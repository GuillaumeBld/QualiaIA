# Contributing to QualiaIA

Thank you for your interest in contributing to QualiaIA!

## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/GuillaumeBld/QualiaIA.git
cd QualiaIA
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
pip install -e .  # Install in development mode
```

4. Set up pre-commit hooks:
```bash
pip install pre-commit
pre-commit install
```

## Code Style

- We use `black` for formatting
- We use `ruff` for linting
- We use `mypy` for type checking

Run checks:
```bash
black src/ tests/
ruff check src/ tests/
mypy src/
```

## Testing

Run tests:
```bash
pytest tests/ -v
```

With coverage:
```bash
pytest tests/ -v --cov=src --cov-report=html
```

## Pull Request Process

1. Create a feature branch from `develop`
2. Make your changes
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a PR to `develop`

## Areas for Contribution

- [ ] x402 EIP-712 signing implementation
- [ ] Market scanner agents
- [ ] Legal entity API integrations
- [ ] Additional communication channels
- [ ] Improved test coverage
- [ ] Documentation improvements
