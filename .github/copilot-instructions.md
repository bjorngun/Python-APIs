## Project Identity

- **Package name (PyPI):** `python-apis`
- **Import name:** `python_apis`
- **Source layout:** `src/python_apis/` (src-layout, installed via `pip install .`)
- **Python:** `>=3.10`
- **Purpose:** A collection of easy-to-use Python APIs for integrating with Active Directory (LDAP), SQL databases (SQLAlchemy), Jira, and SAP employee data. Provides data models, Pydantic schemas, and service layers for common operations.
- **Version:** see `version` in `pyproject.toml`

---

### Project Structure

```
src/
  python_apis/        # main package
    __init__.py       # public API exports (apis, models, schemas, services)
    apis/             # API connection classes (AD, SQL, Jira)
      __init__.py
      ad_api.py
      jira_api.py
      sql_api.py
    models/           # Data models (SQLAlchemy, Pydantic)
      __init__.py
      ad_group.py
      ad_ou.py
      ad_user.py
      base.py
      sap_employee.py
      jira_models/    # Jira-specific models
        __init__.py
        jira_component.py
        jira_issue.py
        ...
    schemas/          # Pydantic validation schemas
      __init__.py
      ad_group_schema.py
      ad_ou_schema.py
      ad_user_schema.py
    services/         # Business logic / service layer
      __init__.py
      ad_group_service.py
      ad_ou_service.py
      ad_user_service.py
      employee_service.py
      jira_service.py
  tests/              # all tests (unittest)
    test_apis/
    test_models/
    test_schemas/
    test_services/
```

- New API connectors go in `src/python_apis/apis/`.
- New data models go in `src/python_apis/models/` (or a sub-package for grouped models like `jira_models/`).
- New Pydantic schemas go in `src/python_apis/schemas/`.
- New service classes go in `src/python_apis/services/`.
- Public API must be exported from the relevant sub-package `__init__.py` and listed in `__all__`.

---

### Coding Standards

- **Type Hints**: Mandatory for all new code.
- **Logging**: Use `logging.getLogger(__name__)`.
- **Formatting**: No trailing whitespace, single EOF newline.
- **Docstrings**: Required for all public classes, functions, and modules.
- **Pydantic**: Use Pydantic for data validation schemas.
- **SQLAlchemy**: Use SQLAlchemy for database models and sessions.

---

### Dependencies

Key dependencies (defined in `pyproject.toml`):
- `bosos-dev-tools` — shared developer utilities (logging, decorators, etc.)
- `ldap3` — LDAP/Active Directory connectivity
- `python-dotenv` — environment variable management
- `sqlalchemy` + `pyodbc` + `cryptography` — SQL database connectivity
- `winkerberos` (Windows) / `gssapi` (Linux) — Kerberos authentication
- `unidecode` — Unicode text transliteration
- `python-dateutil` — date parsing utilities
- `pydantic` — data validation schemas
- `requests` — HTTP client for Jira API
- `pylint` + `pylint-pydantic` — linting

Do not add new dependencies without strong justification.

---

### Public API (`__all__`)

Top-level exports from `python_apis`:
- `apis` — API connection classes (`ADConnection`, `SQLConnection`, `JiraConnection`)
- `models` — Data models (`ADUser`, `ADGroup`, `ADOrganizationalUnit`, `Employee`, `JiraComponent`, `JiraIssue`, `JiraRequestType`)
- `schemas` — Pydantic validation schemas (`ADUserSchema`, `ADOrganizationalUnitSchema`, `ADGroupSchema`)
- `services` — Service layer (`ADUserService`, `ADGroupService`, `ADOrganizationalUnitService`, `EmployeeService`)

---

### Testing

- **Framework:** `unittest` (tests in `src/tests/`)
- **Run tests:** `python -m unittest discover -s src/tests -p "test_*.py"`
- **Run with coverage:** `coverage run -m unittest discover -s src/tests -p "test_*.py"` then `coverage html`
- **Naming:** `test_<module_name>.py`, test classes `Test<ClassName>`, test functions `test_<behavior>`.
- **Pattern:** Each module in `python_apis/` sub-packages should have a corresponding `test_*.py` under the matching `src/tests/test_<subpackage>/` directory.

---

### Pre-Push Checklist

**CI requires passing tests and clean linting.** Before every push, run both:

1. **Tests:** `python -m unittest discover -s src/tests -p "test_*.py"` — all tests must pass.
2. **Linting:** `pylint src/python_apis/` — must score 10/10 (CI fails on any warning or error).

Do not push until both checks pass locally.
