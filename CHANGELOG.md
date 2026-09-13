# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions are managed via git tags ([uv-dynamic-versioning](https://github.com/ninoseki/uv-dynamic-versioning)),
not hardcoded in this repo.

## [Unreleased]

ECOCOMFORT 3 support is contributed by [@rbressers](https://github.com/rbressers), who also
pointed out that the IntelliClima+ app ships as plain JavaScript - which is what made the
protocol corrections below possible. ECOCOMFORT 3 is untested by the maintainer, who owns only
an ECOCOMFORT 2.0.

### Added

- ECOCOMFORT 3 device discovery and status parsing through the `ECO3s` sync payload.
- `IntelliClimaEcocomfort3API` control client for power, mode, speed, and automatic sensor mode
  through the `eco3/send/` endpoint.
- `IntelliClimaECO3` model and `IntelliClimaDevices.ecocomfort3_devices` collection.
- ECOCOMFORT 3 status parsing populates the existing `voc_state`, `co2`, `aqi`, and
  `co2_thrs` fields.
- ECOCOMFORT 3 setters for temperature/humidity calibration, sensor thresholds, season,
  and free-cooling level.
- ECOCOMFORT 3 filter wear tracking through `eco3/filters/`. `reset_filter_counter()`
  additionally sends the `0x26` reset command frame, which the ECOCOMFORT 2.0 reset does
  not need. Only `RESET` is reachable in the vendor app's ECOCOMFORT 3 UI, so the other
  three actions are unverified against a real device.
- `decode_fan_state()`, returning a `FanState` with the running direction, speed, preset and
  the profiled/advanced/boost/night flags, plus the `FanSpeedState` and `FanPreset` enums.
  `mode_set`/`speed_set` are the last *commanded* values and are not what the unit is doing;
  the vendor app displays `mode_state`/`speed_state`, and `speed_state` is a bitfield that was
  not previously decoded at all.

### Changed

- **Breaking:** `IntelliClimaEcocomfortAPI` is renamed to `IntelliClimaEcocomfort2API` and the
  `IntelliClimaAPI.ecocomfort` attribute to `.ecocomfort2`, so both generations name themselves
  explicitly alongside `IntelliClimaEcocomfort3API` / `.ecocomfort3`.
- **Breaking:** `IntelliClimaECO` is renamed to `IntelliClimaECO2`. It and `IntelliClimaECO3` are
  now empty siblings on a shared `IntelliClimaVMCBase` rather than one subclassing the other, so
  `isinstance` is exact in both directions - previously `isinstance(eco3, IntelliClimaECO)` was
  `True` and a downstream ECOCOMFORT 2.0 branch would silently swallow ECOCOMFORT 3 devices.
- **Breaking:** `FanSpeed.auto_get` and `FanSpeed.auto_set` are replaced by a single
  `FanSpeed.auto`. They were never two values: both are register byte `0x10`. Enum values are now
  the register byte in decimal throughout, matching what the device reports, and the command
  builder formats them as hex. The wire bytes are unchanged for every existing value.
- **Breaking:** `get_filter_status()`, `set_filter_tracking_active()` and
  `reset_filter_counter()` moved from `IntelliClimaAPI` onto the per-family device
  clients, since the endpoint prefix differs. Call `api.ecocomfort2.get_filter_status(sn)`
  or `api.ecocomfort3.get_filter_status(sn)` instead of `api.get_filter_status(sn)`.
  Previously an ECOCOMFORT 3 serial was silently posted to the ECOCOMFORT 2.0 endpoint.
- **Breaking:** `SlaveRotation` is renamed to `SatelliteRotation`, `set_slave_rotation()` to
  `set_satellite_rotation()`, and the `slave_rotation` keyword to `satellite_rotation`, following
  the Home Assistant guidance against master/slave terminology. "Satellite unit" is the vendor
  app's own English wording for these devices. The `role`, `slv_rot` and `slv_addr` status fields
  keep their names: they are the server's JSON keys, which dacite matches verbatim.
- README: `voc_state` is the eCO2 estimate in ppm, confirmed against the device manual and a
  device owner's measurement. `co2` remains unverified.

### Fixed

- `IntelliClimaEcocomfort2API.set_season()` and `set_free_cooling()` never reached the
  device. They posted only to `eco/setdata/` / `eco/freecoolset/`, which update the
  cloud-side record; the vendor app sends the `conf_ts` command frame first. The new
  value therefore read back correctly from a status poll while the unit kept running its
  old setting.
- `get_all_device_status()` no longer loses every device's data when one device fails to
  parse. Enum and dacite errors were raised straight out of the polling loop, so a single
  unexpected value from one device (for example an ECOCOMFORT 3 on an account that also
  has ECOCOMFORT 2.0 units) took down the whole poll. Such a device is now logged and
  skipped.
- Login now sends the `TOKEN` header the vendor app sends on its unauthenticated requests:
  SHA-256 of today's date as `DDMMYYYY`. The server does not appear to enforce it today, but
  login had no token at all, so it would break outright if that changed.
- `create_advanced_settings_command()` no longer accepts a `lux_threshold_advanced` flag. The
  "advanced" bit is only ever set on the humidity and VOC/CO2 threshold bytes; neither
  generation sets it on the luminosity byte.

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
