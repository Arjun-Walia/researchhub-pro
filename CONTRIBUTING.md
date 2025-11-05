# Contributing to ResearchHub Pro

Thank you for considering contributing to ResearchHub Pro! This document outlines the process for contributing to this project.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for everyone.

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in [Issues](https://github.com/yourusername/researchhub-pro/issues)
2. If not, create a new issue with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python version, etc.)
   - Screenshots if applicable

### Suggesting Features

1. Check existing issues and discussions
2. Create a new issue with the "enhancement" label
3. Clearly describe:
   - The problem you're trying to solve
   - Your proposed solution
   - Alternative solutions considered
   - Additional context

### Pull Requests

1. Fork the repository
2. Create a new branch (`git checkout -b feature/AmazingFeature`)
3. Make your changes
4. Write or update tests
5. Ensure all tests pass (`pytest`)
6. Run linting (`black app && isort app && flake8 app`)
7. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
8. Push to the branch (`git push origin feature/AmazingFeature`)
9. Open a Pull Request

### Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/researchhub-pro.git
   cd researchhub-pro
   ```

2. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. Initialize database:
   ```bash
   flask db upgrade
   flask seed-db
   ```

6. Run tests:
   ```bash
   pytest
   ```

### Coding Standards

- Follow PEP 8 style guide
- Use type hints where possible
- Write docstrings for all functions/classes
- Keep functions small and focused
- Write meaningful variable names
- Add comments for complex logic

### Commit Message Guidelines

Use conventional commits format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Example:
```
feat(search): add AI query enhancement

Implemented automatic query enhancement using OpenAI GPT-4
to improve search result relevance.

Closes #123
```

### Testing

- Write unit tests for new features
- Maintain test coverage above 80%
- Test both success and error cases
- Use fixtures for test data
- Mock external API calls

### Documentation

- Update README.md if needed
- Add docstrings to new functions/classes
- Update API documentation
- Include examples for new features

## Questions?

Feel free to open an issue with the "question" label or reach out to the maintainers.

Thank you for contributing! 🎉
