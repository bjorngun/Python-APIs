"""
Package initialization for the 'python_apis' package.

This package provides a collection of modules that include APIs, data models, schemas, and services
used throughout the application.

Available submodules:
- **apis**: Contains API interfaces and implementations for interacting with external systems or
    services.
- **models**: Defines the data models representing the structure of the application's data.
- **schemas**: Provides data validation schemas, often using libraries like Pydantic, to ensure
    data integrity.
- **services**: Offers service classes that encapsulate business logic and orchestrate interactions
    between APIs and models.
- **discovery**: Machine-readable registry of modern AD capabilities plus compatibility-mode
    introspection and a quick-reference summary.
- **deprecation**: Structured ``warn_legacy`` helper that emits actionable migration hints.
- **migration_examples**: Connection-free before/after code snippets for adopting modern APIs.

By importing this package, these main submodules are made available for convenient access and use
in other parts of the application.
"""

from python_apis import (
    apis,
    deprecation,
    discovery,
    migration_examples,
    models,
    schemas,
    services,
)

__all__ = [
    "apis",
    "deprecation",
    "discovery",
    "migration_examples",
    "models",
    "schemas",
    "services",
]
