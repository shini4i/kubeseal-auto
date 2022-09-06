# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.4] - 2022-09-06
### Fixed
- Corner case when SealedSecrets controller has a different name

## [0.4.3] - 2022-09-06
### Changed
- Fallback to the default kubeseal binary if the specific version can't be downloaded
### Fixed
- Correct exit code if the required version of kubeseal was not found on github

## [0.4.2] - 2022-07-21
### Fixed
- Correct download link for amd64
- Exit 1 if unsupported architecture or OS is detected

## [0.4.1] - 2022-07-15
### Changed
- Print controller version on a separated line
### Fixed
- Removed code duplication

## [0.4.0] - 2022-07-05
### Added
- kubeseal-auto now downloads the same version of kubeseal binary as the version of sealed-secret controller (only in non-detached mode)

## [0.3.1] - 2022-07-04
### Fixed
- TypeError: argument of type 'NoneType' is not iterable in _find_sealed_secrets_controller

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
