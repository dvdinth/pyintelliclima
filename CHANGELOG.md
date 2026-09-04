# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions are managed via git tags ([uv-dynamic-versioning](https://github.com/ninoseki/uv-dynamic-versioning)),
not hardcoded in this repo.

## [Unreleased]

### Added

- ECOCOMFORT 3 device discovery and status parsing through the `ECO3s` sync payload.
- `IntelliClimaEcocomfort3API` control client for power, mode, speed, and automatic sensor mode
  through the `eco3/send/` endpoint.
- `IntelliClimaECO3` model and `IntelliClimaDevices.ecocomfort3_devices` collection.
- ECOCOMFORT 3 status parsing populates the existing `voc_state`, `co2`, `aqi`, and
  `co2_thrs` fields.
- ECOCOMFORT 3 setters for temperature/humidity calibration, sensor thresholds, season,
  and free-cooling level.

## [0.4.1] - 2026-08-04

### Added

- `IntelliClimaAPI.set_filter_tracking_active()` to enable or disable filter wear tracking for a
  device (`eco/filters/`, `ACTIVATE`/`DEACTIVATE`).
- `IntelliClimaAPI.reset_filter_counter()` to reset a device's accumulated filter wear counter
  (`eco/filters/`, `RESET`).

## [0.4.0] - 2026-07-29

### Added

- `IntelliClimaAPI.get_filter_status()` and `IntelliClimaFilterStatus`/`IntelliClimaFilterStatsEntry`
  dataclasses, calling the `eco/filters/` endpoint to determine whether a device's filter needs cleaning.
- `IntelliClimaEcocomfortAPI.set_season()` for winter/summer mode (`eco/setdata/`).
- `IntelliClimaEcocomfortAPI.set_free_cooling()` for the free cooling level, summer mode only
  (`eco/freecoolset/`).
- `IntelliClimaEcocomfortAPI.set_temperature_and_humidity_offsets()` for calibration offsets. Both
  values must be provided together since they share the same device register.
- `IntelliClimaEcocomfortAPI.set_advanced_settings()` and `set_slave_rotation()` for humidity/VOC/lux
  sensor-mode thresholds and slave/satellite rotation direction, which also share one device register.
  Threshold changes were found to not reliably persist on the device during reverse-engineering; see the
  docstring caveat before building anything stateful on top of them.
- `py.typed` marker (PEP 561) so consumers can rely on this package's type hints.
- New `Season`, `FreeCoolingLevel`, `SlaveRotation`, and `ThresholdLevel` enums in `const.py`.

### Fixed

- `IntelliClimaAPI.set_house_and_device_ids()` previously only looked at the first house on the
  account (`self.house_id = list(houses.keys())[0]`), silently dropping devices belonging to any other
  house. It now merges devices from all houses. `house_id: str | None` is replaced by
  `house_ids: list[str]`.

### Changed

- Bumped minimum dependency/dev-tool versions (`aiohttp`, `pytest`, `ruff`, `basedpyright`, `rich`,
  `codespell`, `pytest-asyncio`, `pytest-cov`) to the versions currently tested against.
- Added the `Python :: 3.14` classifier.

[0.4.1]: https://github.com/dvdinth/pyintelliclima/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/dvdinth/pyintelliclima/compare/v0.3.1...v0.4.0
