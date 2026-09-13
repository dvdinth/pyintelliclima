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
- `IntelliClimaVMCBase.fan_state`, decoding the device's own `mode_state`/`speed_state`
  registers so consumers never have to pair the two by hand. `mode_set`/`speed_set` remain the
  right source for a write that wants to preserve the current speed.
- `decode_fan_state()`, returning a `FanState` with the running direction, speed, preset and
  the profiled/advanced/boost/night flags, plus the `FanSpeedState` and `FanPreset` enums.
  `mode_set`/`speed_set` are the last *commanded* values and are not what the unit is doing;
  the vendor app displays `mode_state`/`speed_state`, and `speed_state` is a bitfield that was
  not previously decoded at all.
- The protocol enums (`FanMode`, `FanSpeed`, `FanSpeedState`, `FanPreset`, `Season`,
  `FreeCoolingLevel`, `ThresholdLevel`, `SatelliteRotation`) and `IntelliClimaFilterStatus` are
  exported from the package root. They are argument and return types of the public client
  methods, so importing them from `pyintelliclima.const` was an avoidable detour.
- `decode_threshold()` and `ThresholdSetting`, plus `humidity_threshold` and
  `luminosity_threshold` on `IntelliClimaVMCBase`, `voc_threshold` on `IntelliClimaECO2` and
  `co2_threshold` on `IntelliClimaECO3`. `rh_thrs`, `voc_thrs` and `co2_thrs` carry the "advanced
  control" flag in bit 7 on top of the level, so a threshold with that flag on read back as
  `129`-`131` and was not a valid `ThresholdLevel` at all. The library already encoded that bit
  on write; decoding it on read is what makes a partial write to the shared threshold register
  safe. `lux_thrs` has no such flag on either generation and stays a bare `ThresholdLevel`.

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
- **Breaking:** `IntelliClimaAPI.device_id_types` is replaced by `ecocomfort2_ids: list[str]`
  and `ecocomfort3_ids: list[str]`. Device discovery now reads the `ecoIDs`/`eco3IDs` arrays
  that `casa/elenco3` returns, and `_parse_device()` picks the dataclass from each status
  entry's own `model.modello`. Both are what the vendor app uses; the per-device `tipo` we
  read before is a field no vendor code touches, and it was the only thing routing a device
  to `IntelliClimaECO3`. Devices of families this library does not implement are now
  rejected on `modello` - previously a RHINOCOMFORT 3 would very likely have been accepted
  as an ECOCOMFORT 2.0, since it shares most of this schema.
- **Breaking:** `SlaveRotation` is renamed to `SatelliteRotation`, `set_slave_rotation()` to
  `set_satellite_rotation()`, and the `slave_rotation` keyword to `satellite_rotation`, following
  the Home Assistant guidance against master/slave terminology. "Satellite unit" is the vendor
  app's own English wording for these devices. The `role`, `slv_rot` and `slv_addr` status fields
  keep their names: they are the server's JSON keys, which dacite matches verbatim.
- README: the air-quality fields are now documented per generation. `voc_state` is the field to
  read on both, but carries VOC in ppm on ECOCOMFORT 2.0 and an eCO2 estimate in ppm on
  ECOCOMFORT 3, so each needs its own Home Assistant device class. `co2` and `aqi` exist only on
  ECOCOMFORT 3; `co2` disagrees with a reference NDIR monitor and should not be used.
- **Breaking:** `set_house_and_device_ids()` no longer swallows its own failures, and
  `authenticate()` no longer runs it inside the handler that turns transport errors into
  `IntelliClimaAuthError`. A failed lookup used to leave every ID list empty and return
  success, which a caller could not tell apart from an account that owns no supported device.
- README: documents the "no reading" sentinel for every sensor, not just the air-quality ones.
  `tamb` reports `327.67` and `rh` reports `143` when the probe has no value, which a consumer
  would otherwise publish as a measurement.
- `IntelliClimaVMCBase.dev_state` is documented as ECOCOMFORT 3's filter-change flag, which is
  the only filter signal that generation has - the vendor app never asks `eco3/filters/` to
  calculate wear the way it does for ECOCOMFORT 2.0.
- `create_advanced_settings_command()` documents that the register's trailing main-unit address
  has no preserve marker, so any threshold write clears `slv_addr` on a satellite unit. The
  vendor app's cloud path has the same hole; only its Bluetooth path can rewrite the address.
- `IntelliClimaGetDeviceBody` now matches the request actually sent and is what builds it, so
  the two cannot drift apart again. It had declared `C900s`/`RHINOs` and their `includi_*`
  flags, which `get_all_device_status()` has never sent.

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
- `set_season()` now clears free cooling when switching to winter, as the vendor app does.
  Free cooling is summer-only and the app's UI merely hides a stale level out of season, so
  nothing else ever cleared the device's own register.
- Login now sends the `TOKEN` header the vendor app sends on its unauthenticated requests:
  SHA-256 of today's date as `DDMMYYYY`. The server does not appear to enforce it today, but
  login had no token at all, so it would break outright if that changed.
- `create_advanced_settings_command()` no longer accepts a `lux_threshold_advanced` flag. The
  "advanced" bit is only ever set on the humidity and VOC/CO2 threshold bytes; neither
  generation sets it on the luminosity byte.
- Rejected credentials now raise `IntelliClimaAuthError` rather than a bare
  `IntelliClimaAPIError`. The server answers a bad login with an HTTP 200 whose body carries a
  non-`OK` `status` and an `error` of `NO_USERNAME`/`NO_PASSWORD`, so `post_to_session()` raised
  on the status before `authenticate()` could read the reason - making the `NO_PASSWORD` branch
  unreachable and leaving a consumer unable to distinguish a changed password from an outage.
- `get_all_device_status()` no longer drops a device whose nested `model` or `config` arrives as
  JSON `null`. `json.loads(None)` raises `TypeError`, which the surrounding handler did not
  catch, so one null field cost that device every reading on it. `config` is no longer parsed at
  all: no VMC dataclass has the field and the vendor app never reads it for an ECOCOMFORT.
- The command builders no longer left-pad an odd-length serial. A serial is always four bytes,
  and each frame's length field is hardcoded for that, so padding produced a frame the device
  would misread; such a serial now fails loudly instead.

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
