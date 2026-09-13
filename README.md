# pyintelliclima

<div align="center">

[![Python versions](https://img.shields.io/pypi/pyversions/pyintelliclima)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/pyintelliclima.svg)](https://pypi.org/project/pyintelliclima/)
[![Status](https://img.shields.io/pypi/status/pyintelliclima.svg)](https://pypi.org/project/pyintelliclima/)
[![License](https://img.shields.io/pypi/l/pyintelliclima)](https://github.com/dvdinth/pyintelliclima/blob/main/LICENSE)

</div>

* * *

This is a Python module for communicating with IntelliClima ECOCOMFORT 2.0 and
ECOCOMFORT 3 devices.
Its main use is for my corresponding [HomeAssistant IntelliClima integration](https://www.home-assistant.io/integrations/intelliclima/).

ECOCOMFORT 3 support is community-contributed and is not tested by me - I own only the
ECOCOMFORT 2.0. It can be extended to include other devices from IntelliClima in the future,
but not without help from device owners. I've made a
[guide for adding new devices](ADD_DEVICE_GUIDE.md). If you own another device type, it's
highly appreciated if you could take a look at the guide and see if you can add a PR for your
device(s), or share the logs as described so I can add them.

This API was made by reverse engineering the cloud API, through the use of an android emulator and proxy to catch the Intelliclima+ app traffic. As such, no public API exists and the functionality of this module breaks if the API changes. This module is provided as-is, with no guarantees of correctness, stability, or continued functionality. Use it at your own risk.

### ECOCOMFORT 3 air-quality values

ECOCOMFORT 3 status responses populate the existing `voc_state`, `co2`, `aqi`, and `co2_thrs`
fields. All values are returned as strings.

`voc_state` carries the **eCO2 estimate in ppm**, despite the field name. The device manual
describes the sensor as measuring eCO2, with air-quality thresholds at 500/750/1000 ppm, and a
device owner confirmed that `voc_state` matches the value the vendor app charts as CO2. It is a
VOC-derived estimate anchored to a 400 ppm baseline, not an NDIR measurement, so it responds to
solvents and cooking as well as to occupancy.

`co2` is the odd one out: field observations found physically implausible values there. Treat it
as unverified raw data.

### Reading the current mode and speed

`mode_set` and `speed_set` hold the last *commanded* values, which is not necessarily what the
unit is doing - the vendor app never displays them. Read `device.fan_state` instead, which
decodes the reported `mode_state`/`speed_state` registers into the running direction, speed,
preset, and the boost/night/profiled/advanced flags.

One exception: when a write needs to preserve "the current speed", keep reading `speed_set`.
The running speed may be a boost or night-profile override, and commanding that back would
make a temporary override permanent. `FanSpeedState.boost` has no `FanSpeed` counterpart at
all - boost is device-driven and lasts three minutes.

## Credits

This was highly inspired by: https://github.com/ruizmarc/homebridge-intelliclima

Partial credit for the reverse engineering process of the API goes to them.

ECOCOMFORT 3 support, and the observation that the IntelliClima+ app ships as plain JavaScript
and can therefore be read directly, are thanks to [@rbressers](https://github.com/rbressers).

* * *

## Project Docs

For how to install uv and Python, see [installation.md](installation.md).

For development workflows, see [development.md](development.md).

* * *

*This project was built from
[simple-modern-uv](https://github.com/jlevy/simple-modern-uv).*
