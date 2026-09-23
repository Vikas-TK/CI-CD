# Contributing to Hospital Management System (MediCare HMS)

Thank you for contributing to the Hospital Management System project. This guide outlines the development standards, Git workflow, testing requirements, and quality checks.

---

## 1. Development Principles & Code Standards

- **Modular MVC Architecture**: Maintain clear separation between Models (`app/models/`), Services/Business Logic (`app/services/`), Controllers/Blueprints (`app/controllers/`), and Templates (`app/templates/`).
- **Zero Redundancy**: Credentials, core authentication attributes, names, and contact info belong exclusively in `users`. Domain profile models (`patients`, `doctors`, etc.) reference `users.user_id` via 1-to-1 foreign keys.
- **Server-Side Authorization**: Always enforce role-based access control on routes using decorators (`@admin_required`, `@doctor_required`, `@patient_required`, `@staff_required`, `@role_required`).
- **Privacy by Design**: Sensitive data (such as Aadhaar numbers) must be masked in list views and search responses (`XXXX-XXXX-1234`).
- **PEP 8 & Flake8 Standards**:
  - Maximum line length: 127 characters.
  - Maximum cyclomatic complexity: 10 (`--max-complexity=10`).
  - No trailing blank lines or unused imports.

---

## 2. Git Branching Model

We follow a structured Git branching model:

- **`main`**: Production release branch. Only fast-forward or squash merged from `develop` after CI/CD validation.
- **`develop`**: Central integration branch for tested feature modules.
- **`feature/<module-name>`**: Dedicated branch for developing specific modules or isolated capabilities.

### Branch Workflow:
```bash
# 1. Create a feature branch from develop
git checkout develop
git pull origin develop
git checkout -b feature/module-X-feature-name

# 2. Make atomic commits with conventional messages
git add .
git commit -m "feat(module-X): implement feature description"

# 3. Push feature branch and open a Pull Request to develop
git push -u origin feature/module-X-feature-name
```

---

## 3. Automated Testing & Quality Verification

Before committing and opening a Pull Request, run the local verification suite:

```bash
# Run pytest with code coverage and JUnit XML report
pytest -v --junitxml=test-results/junit.xml --cov=app --cov-report=term-missing

# Run Flake8 linter (must return 0 errors)
flake8 . --count --max-complexity=10 --max-line-length=127 --statistics
```

---

## 4. Continuous Integration & Deployment (GitHub Actions)

Every push and Pull Request triggers GitHub Actions:
- **CI Workflow (`ci.yml`)**: Executes Python matrix tests (3.10, 3.11), Flake8 linting, pytest test suite, and SonarCloud analysis.
- **CD Staging Workflow (`cd-staging.yml`)**: Builds Docker image `medicare-hms:staging` and performs `/health` endpoint verification.

> **Note**: Jenkins is not used in this repository. All automation is handled exclusively via GitHub Actions.
