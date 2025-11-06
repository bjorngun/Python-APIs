# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

<!-- insertion marker -->
## Unreleased

### Added

- rename_user_cn functionality to ADUserService for renaming user common names
- Python 3.14 support and optimized CI/CD workflows  
- Comprehensive test coverage (100% function coverage with 48 tests)

### Fixed

- CI pipeline shell compatibility issues for cross-platform builds
- Auto-changelog integration conflicts

### Changed

- Optimized GitHub Actions workflow from 8 to 5 jobs for better efficiency
- Updated Python version matrix to support 3.10-3.14

## [v0.4.9](https://github.com/bjorngun/Python-APIs/releases/tag/v0.4.9) - 2025-10-27

- Added carLicence field to user fetch functionality

## [v0.4.8](https://github.com/bjorngun/Python-APIs/releases/tag/v0.4.8) - 2025-10-27

- Added carLicence field to user model

## [v0.4.5](https://github.com/bjorngun/Python-APIs/releases/tag/v0.4.5) - 2025-10-22

- Added enable_user functionality to ADUserService

## [v0.4.4](https://github.com/bjorngun/Python-APIs/releases/tag/v0.4.4) - 2025-10-22

- Added set_password function to ADUserService

## [v0.4.3](https://github.com/bjorngun/Python-APIs/releases/tag/v0.4.3) - 2025-10-16

- Added functionality to get all SAM account names
- Fixed linting issues

## [v0.4.2](https://github.com/bjorngun/Python-APIs/releases/tag/v0.4.2) - 2025-10-14

- Added move_user_to_ou function for moving users between organizational units

## [v0.4.1](https://github.com/bjorngun/Python-APIs/releases/tag/v0.4.1) - 2025-08-12

- Internal improvements and maintenance

## [v0.3.9](https://github.com/bjorngun/Python-APIs/releases/tag/v0.3.9) - 2025-08-11

- Internal improvements and maintenance

## [v0.3.8](https://github.com/bjorngun/Python-APIs/releases/tag/v0.3.8) - 2025-06-20

- Internal improvements and maintenance

## [v0.3.7](https://github.com/bjorngun/Python-APIs/releases/tag/v0.3.7) - 2025-06-04

- Added status badges to README

## [v0.3.6](https://github.com/bjorngun/Python-APIs/releases/tag/v0.3.6) - 2025-06-04

- Fixed bug in bump-version file for handling quotes in pyproject.toml

## [v0.3.5](https://github.com/bjorngun/Python-APIs/releases/tag/v0.3.5) - 2025-06-04

Major release with comprehensive improvements:

### Added

- Linux compatibility and Ubuntu-specific dependencies
- GitHub Actions automation and LDAP3 logging options
- SAP employee model and service with MainJob field
- Schema validation system
- Comprehensive README documentation

### Fixed

- OS-dependent GitHub Actions bugs
- OU service attributes with comprehensive tests
- Various linting issues throughout codebase
- README content and formatting

### Changed

- Updated version detection regex for pyproject.toml
- Migrated from Ruby to Node.js for changelog generation
- Improved OS-dependent dependency management
- Enhanced LDAP connection with OS-specific SASL packages
- Updated PyPI authentication to use tokens instead of username/password
- Added Linux compatibility for Active Directory connections
- Standardized logging and return values for modify_user function

## [v0.1.0](https://github.com/bjorngun/Python-APIs/releases/tag/v0.1.0) - 2022-11-07

- Initial project setup with core configuration files
- Basic project structure and packaging configuration
