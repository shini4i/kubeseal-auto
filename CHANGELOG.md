# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2022-07-01
### Added
- Support for SealedSecrets controller encryption secret backup
### Changed
- Improved SealedSecrets controller searching

## [0.2.3] - 2022-06-14
### Added
- Support for re-encrypting all SealedSecret files in a provided directory

## [0.2.2] - 2022-05-07
### Added
- Support for selecting kubeconfig context
### Changed
- Separated Kubeseal logic into two classes for easier maintainability

## [0.2.1] - 2022-04-19
### Changed
- Added README to pypi published package

## [0.2.0] - 2022-04-19
### Added
- Support for editing secret in a detached mode
### Changed
- Script was completely rewritten to python

## [0.1.0] - 2022-03-06
### Added
- Initial bash version
