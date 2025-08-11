# Python APIs for Active Directory and SQL Integration

[![Python Versions](https://img.shields.io/pypi/pyversions/python-apis.svg?logo=python&logoColor=white)](https://pypi.org/project/python-apis/#files)
[![Platform](https://img.shields.io/badge/platform-linux%20%7C%20windows-lightgrey)](https://pypi.org/project/python-apis/#files)
[![PyPI Version](https://img.shields.io/pypi/v/python-apis)](https://pypi.org/project/python-apis/#history)
[![PyPI status](https://img.shields.io/pypi/status/python-apis.svg)](https://pypi.python.org/pypi/python-apis/)
[![Github Actions Test and Publish Status](https://github.com/bjorngun/Python-APIs/actions/workflows/Test%20and%20publish.yml/badge.svg)](https://github.com/bjorngun/Python-APIs/actions)
[![codecov](https://codecov.io/gh/bjorngun/Python-APIs/graph/badge.svg)](https://codecov.io/gh/bjorngun/Python-APIs)
[![License](https://img.shields.io/pypi/l/python-apis)](LICENSE)

Welcome to the **Python APIs for Active Directory and SQL Integration** project. This repository provides a set of Python modules and classes designed to interact with Active Directory (AD) and SQL databases seamlessly. It facilitates operations such as querying AD users, managing SQL database connections, and synchronizing data between AD and SQL.

## Table of Contents

- [Python APIs for Active Directory and SQL Integration](#python-apis-for-active-directory-and-sql-integration)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
  - [Features](#features)
  - [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
  - [Usage](#usage)
    - [Configuration](#configuration)
    - [Connecting to Active Directory](#connecting-to-active-directory)
    - [Connecting to SQL Database](#connecting-to-sql-database)
    - [Working with AD Users](#working-with-ad-users)
  - [Running Tests](#running-tests)
  - [Linting and Code Quality](#linting-and-code-quality)
  - [Project Structure](#project-structure)
  - [Contributing](#contributing)
  - [License](#license)

## Overview

This project aims to simplify the integration between Python applications, Active Directory services, and SQL databases. It provides:

- Classes for connecting to and interacting with Active Directory using LDAP.
- Classes for managing SQL database connections and performing CRUD operations using SQLAlchemy.
- Data models representing AD users and their attributes.
- Utility functions and services for common tasks like updating user information, handling group memberships, and more.
- Comprehensive unit tests to ensure code reliability and correctness.
- Linting configurations to maintain code quality and adherence to PEP 8 standards.

## Features

- **Active Directory Integration**: Query and manipulate AD users and groups using LDAP.
- **SQL Database Connectivity**: Manage database connections and perform operations using SQLAlchemy.
- **Data Models**: Represent AD users with a Python class that maps to a SQL database schema.
- **Services Layer**: Provides business logic and utility functions for higher-level operations.
- **Unit Testing**: Includes tests with mocking to validate functionality without requiring actual connections.
- **Linting and Code Quality**: Configured with Pylint for maintaining code standards and conventions.

## Getting Started

### Prerequisites

- **Python 3.10 or higher**
- **Virtual Environment**: Recommended to use a virtual environment to manage dependencies.
- **Active Directory Access**: Necessary permissions to interact with your organization's AD.
- **SQL Server Access**: Access to a SQL Server database if you plan to use the SQL functionalities.

### Installation

1. **Clone the Repository**

   ```bash
   git clone https://github.com/bjorngun/python-apis.git
   cd python-apis
   ```

2. **Create and Activate a Virtual Environment on Windows**

   ```bash
   python -m venv venv
   venv/Scripts/activate
   ```

3. **Upgrade pip**

   ```bash
   python -m pip install --upgrade pip
   ```

4. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

   **Note**: The `requirements.txt` file includes all necessary dependencies, some of which are platform-specific.

## Usage

### Configuration

The project uses environment variables for configuration. Create a `.env` file in the project root or set the environment variables in your system.

Example `.env` file:

```ini
# Active Directory Configuration
LDAP_SERVER_LIST=ldap://server1 ldap://server2
SEARCH_BASE=dc=example,dc=com

# SQL Database Configuration
ADUSER_DB_SERVER=your_db_server
ADUSER_DB_NAME=your_db_name
ADUSER_SQL_DRIVER=ODBC Driver 17 for SQL Server
```

### Connecting to Active Directory

```python
from src.apis import ADConnection

# Initialize ADConnection
ad_connection = ADConnection(
    servers=['ldap://server1', 'ldap://server2'],
    base_dn='dc=example,dc=com'
)

# Search for users
users = ad_connection.search('(objectClass=user)')
```

### Connecting to SQL Database

```python
from src.apis import SQLConnection

# Initialize SQLConnection
sql_connection = SQLConnection(
    server='your_db_server',
    database='your_db_name',
    driver='ODBC Driver 17 for SQL Server'
)

# Access the session
session = sql_connection.session

# Query the database
from src.models.ad_user import ADUser

ad_users = session.query(ADUser).all()
```

### Working with AD Users

```python
from src.services.ad_user_service import ADUserService

# Initialize the service
service = ADUserService()

# Get users from the SQL database
sql_users = service.get_users()

# Get users from Active Directory
ad_users = service.get_users_from_ad()

# Add a user to a group
user = sql_users[0]
group_dn = 'CN=GroupName,OU=Groups,DC=example,DC=com'
service.add_member(user, group_dn)

# Modify a user's attributes
changes = [('displayName', 'New Display Name')]
service.modify(user, changes)
```

## Running Tests

The project includes unit tests located in the `src/tests` directory.

1. **Install Test Dependencies**

   ```bash
   pip install -r requirements-dev.txt
   ```

2. **Run Tests**

   ```bash
   python -m unittest discover -s src/tests -p 'test_*.py'
   ```

   **Note**: Ensure that your `PYTHONPATH` includes the project root so that tests can locate the modules correctly.

## Linting and Code Quality

We use `pylint` to maintain code quality and adherence to PEP 8 standards.

1. **Install Pylint**

   ```bash
   pip install pylint
   ```

2. **Run Linting**

   ```bash
   pylint src/apis/ src/models/ src/services/
   ```

   This command lints only the specified directories.

3. **Configuration**

   You can adjust linting rules by modifying the `.pylintrc` file in the project root.

## Project Structure

```md
python-apis/
├── src/
│   ├── apis/
│   │   ├── __init__.py
│   │   ├── ad_api.py
│   │   └── sql_api.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── ad_user.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── ad_user_service.py
│   └── tests/
│       ├── __init__.py
│       ├── test_apis/
│       │   └── test_ad_api.py
│       ├── test_models/
│       │   └── test_ad_user.py
│       └── test_services/
│           └── test_ad_user_service.py
├── .env.example
├── .gitignore
├── README.md
├── pyproject.toml
└── .pylintrc
```

- **src/apis/**: Contains classes for connecting to external APIs like AD and SQL.
- **src/models/**: Data models representing database schemas.
- **src/services/**: Business logic and utility functions.
- **src/tests/**: Unit tests for the codebase.
- **pyproject.toml**: Package configuration file.

## Contributing

We welcome contributions! Please follow these guidelines:

1. **Fork the Repository**: Create a personal fork of the project.

2. **Create a Feature Branch**: Work on your changes in a new branch.

   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Write Tests**: Ensure that your code is covered by unit tests.

4. **Run Linting**: Verify that your code passes linting checks.

5. **Commit Changes**: Write clear and concise commit messages.

6. **Push and Open a Pull Request**: Push your branch to your fork and open a PR against the main repository.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

**Note**: Replace placeholder text like `your-username`, `your_db_server`, and `your_db_name` with actual values relevant to your environment.

If you have any questions or need assistance, feel free to open an issue or contact the project maintainers.

---

This README provides an overview of the project, instructions on how to set it up, and guidance on how to use its features. It is intended to help users and contributors understand the purpose of the project and how to work with it.
