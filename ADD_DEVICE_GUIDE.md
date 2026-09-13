# Adding Support for New IntelliClima Devices

This guide explains how to investigate the official **IntelliClima+** app and validate its
cloud protocol so that new device types can be added to this library.

Start with the app's bundled code when it is readable. It can reveal endpoints, command
formats, and response transformations without setting up a proxy. Use traffic capture to
resolve questions and check what the app actually exchanges with the server. Neither method
replaces testing on a real device.

- [Inspect the app code](#inspect-the-app-code-recommended-start): useful for contributors
  comfortable reading JavaScript, including the iOS app on an Apple Silicon Mac.
- [Validate on a real device](#validate-on-a-real-device): useful for device owners, even
  without programming experience.
- [Capture Android traffic with Waydroid](#how-this-works): the existing Linux/proxy workflow,
  useful when code is unavailable or actual requests and responses are needed.

You do not need account credentials to read locally installed app assets. Live validation
requires your own device, or an owner willing to test with their paired account. Do not ask
owners to post their credentials or upload a complete app bundle.

## Inspect the App Code (Recommended Start)

### iOS App on an Apple Silicon Mac

ECOCOMFORT 3 research used the **iPhone/iOS version of IntelliClima+ running on an Apple
Silicon Mac**, not an Android APK. The inspected installation, version **3.10.50**, contains
readable JavaScript and HTML in a `www` directory inside the app bundle. This is a verified
route for that version, not a guarantee about future releases or other installation layouts.

If the iPhone/iPad app is available to you in the Mac App Store, install it from there.
In Finder, use **Show Package Contents** on the installed app. If there is a `Wrapper`
directory containing another `.app`, inspect that inner bundle too. Look for `www` and open
its files in a text editor. Read the files without modifying the installed, signed bundle.
There is no need to launch the app or log in for this inspection.

For the verified installation, these read-only Terminal commands locate the relevant assets.
Adjust the path to your installation; `rg` is [ripgrep](https://github.com/BurntSushi/ripgrep)
and must be installed separately if it is not already available:

```bash
app_bundle='/Applications/Intelliclima+.app/Wrapper/Intelliclima.app'
app_www="$app_bundle/www"
plutil -extract CFBundleShortVersionString raw "$app_bundle/Info.plist"
rg --files "$app_www" | rg '\.(js|html)$'
rg -n 'eco3Write|rhinoWrite|eco3/send/|rhino/send/' "$app_www/js/system/wifi.js"
rg -n 'sync/cronos400|convertiDatiEcoComfort' "$app_www/js/system/sync.js"
```

Useful starting points in that version are:

| Location relative to `www` | What to investigate |
| --- | --- |
| `js/route.js` | Cloud base URL and API routing |
| `js/system/wifi.js` | Discovery requests, device-specific command builders and send endpoints |
| `js/system/sync.js` | Status polling and transformations applied to responses |
| `js/controllers/ecocomfort3/` and `js/system/ecocomfort3/` | How ECOCOMFORT 3 UI actions map to commands |
| `template/ecocomfort3/` | Display labels and selectable settings |

Other model names can help locate equivalent code, but their presence in the app does not
mean those devices are already supported by this library.

### Android App Assets

The maintainer has also used extracted Android app code. If you already have an official
APK, inspect its archive contents for bundled JavaScript/HTML (for example, an `assets/www`
directory). Static asset inspection does not require an emulator or proxy. Exact paths and
readability depend on the app version; the iOS paths above are not Android instructions.
If the relevant code is unavailable or unclear, use the traffic-capture workflow below.

### Trace a Feature End to End

Follow the implementation in both directions, rather than searching for a field name alone:

1. **Discovery:** identify how the app lists homes and devices, distinguishes model types,
   and obtains the identifier used in later requests.
2. **Status:** find the polling endpoint, request parameters, and raw response. Check for
   nested JSON strings and conversions before a value reaches the screen.
3. **Commands:** start with a UI action, follow its controller into the command builder,
   and record the endpoint, payload, register, byte order, and checksum where applicable.
4. **Display:** trace raw fields through scaling, offsets, flags, lookup tables, and labels.
   Record what is observed separately from what is inferred.

For example, in iOS 3.10.50, `wifi.js` contains `eco3Write` and `rhinoWrite` with separate
`eco3/send/` and `rhino/send/` routes. `sync.js` contains `sync/cronos400` polling and the
shared `convertiDatiEcoComfort` conversion function. These are useful search targets, not
proof that the devices have identical hardware or capabilities.

Watch for these common pitfalls:

- A number shown in the UI, a decimal string, and a hexadecimal command byte are not
  interchangeable. Preserve leading zeroes and distinguish flags from the underlying value.
- A register can contain several settings. Updating one must preserve the unrelated bits.
- Shared or unused app code can mention features a particular model does not support.
- A plausible field name or matching app label does not establish the physical quantity,
  unit, or accuracy of a sensor. In particular, do not assume a field named `co2` is a
  validated CO2 measurement, or that `voc_state` is a VOC concentration. Document uncertainty.
- Commands accepted by the cloud are not necessarily applied by the device. Check a later
  status response and, where possible, the physical device.

Keep your findings as independently written protocol notes, not copied app source. Record
the app platform/version and relevant file/function names so another contributor can follow
the investigation. Do not commit proprietary bundles, extracted source trees, or credentials.

## Validate on a Real Device

If you do not own the target model, an owner can supply sanitized status data and perform
the tests. App-code research alone is enough to assess feasibility, but not to claim working
device support. You do not need to give another contributor access to your account.

1. Record the **exact model/product code**, **firmware version**, and **app platform/version**.
   A successful test on one firmware version does not establish a minimum required version.
2. Begin with read-only discovery and status. Save a sanitized example showing the original
   field names, value types, missing fields, and any nested JSON structure.
3. Record the initial settings. For each supported control, change **one setting at a time**
   in the official app and note the action, time, before/after values, and physical effect.
   Traffic capture can help associate an action with its actual request.
4. Test the independently implemented command against the same observations. Allow time for
   the normal cloud update; avoid tight polling loops or simultaneous capture/test clients
   repeatedly refreshing the account. Record failures rather than assuming rate limiting.
5. Restore the original settings after control tests. Routine protocol testing should not
   require firmware changes, factory resets, or changing device pairing.

For a contribution, include a small evidence table (feature, raw field or command, app
behavior, hardware result, remaining uncertainty), sanitized fixtures, and regression tests
for parsing and command encoding. Include relevant off/auto/manual modes and boundary values;
do not expose settings merely because they occur in shared app code. See
[development.md](development.md) for the project's development workflow.

Prefer synthetic identifiers in fixtures, preserving the response structure and value types.
If an identifier is embedded in a command frame, replace it there too and recalculate any
dependent checksum. Review URLs, headers, request bodies, and responses for secrets before
sharing; see [Step 8](#step-8-what-to-check-before-sharing-your-logs). Share only the minimum
sanitized evidence needed, not an entire account history.

---

## How This Works

The remaining sections describe the alternative **Android traffic-capture workflow**. They
require Linux and some command-line familiarity, but no programming experience.

`pyintelliclima` communicates with the IntelliClima cloud API. Watching what the official app
sends to and receives from the cloud can complement the app-code investigation above, or
provide a starting point when the code is not readable. This technique is called
**traffic interception** or a **man-in-the-middle proxy**.

The tool we use for this is [mitmproxy](https://mitmproxy.org/), a free and open-source proxy
that lets you inspect HTTPS traffic. We run the IntelliClima+ app inside
[Waydroid](https://waydro.id/), a layer that lets you run Android apps natively on Linux,
and route all app traffic through mitmproxy.

The setup used for this workflow allowed interception after installing mitmproxy's
certificate into Android's trusted store (step 5). The cloud exchanges contained readable
**JSON** inside HTTPS. App versions that use **certificate pinning** (restricting which
server certificates or keys they accept) or different payload formats may behave differently;
do not assume this setup will work unchanged with every release.

This guide is based on the blog post
[**"Use a Proxy with Waydroid"** by Julien Duponchelle](https://julien.duponchelle.info/android/use-proxy-with-waydroid/),
which explains the general setup process in detail. The steps below are adapted specifically
for capturing IntelliClima+ traffic.

---

## Prerequisites

- A computer running **Ubuntu** (22.04 or later recommended) with a **Wayland** desktop session
  (see below).
- An internet connection.
- An **IntelliClima account** with the device you want to add support for already paired in the
  official app.

### Getting a Wayland Session on Ubuntu

Waydroid requires Wayland, which is Ubuntu's modern display system. On Ubuntu 22.04 and later,
Wayland is the default, but it is easy to accidentally be on the older X11 session instead.

**Check which session you are using:**
Click the clock or the top-right system tray area, click your username or the power icon, and
look at the top of the screen after you log in. Alternatively, open a terminal and run:

```bash
echo $XDG_SESSION_TYPE
```

If the output is `wayland`, you are already on a Wayland session and can skip the rest of
this section. If it says `x11`, follow the steps below.

**Switch to a Wayland session:**

1. Log out of your current session (click the top-right system tray → your username → Log Out).
2. On the login screen, click your username but **do not enter your password yet**.
3. Look for a small **gear icon** in the bottom-right corner of the screen and click it.
4. A menu appears with options such as "Ubuntu", "Ubuntu on Wayland", and "Ubuntu on Xorg".
   Select **"Ubuntu"** or **"Ubuntu on Wayland"**.
5. Enter your password and log in. You are now on Wayland.

**If you do not see a gear icon or a Wayland option**, one of the following is likely the cause:

- **Wrong display manager.** The gear icon only appears when Ubuntu's default login manager
  (`gdm3`) is in use. Some Ubuntu variants ship with a different one (`lightdm`) that does not
  offer Wayland. Install and activate `gdm3`:
  ```bash
  sudo apt install gdm3
  ```
  During installation you may be prompted to choose a default display manager — select `gdm3`.
  Then reboot. The gear icon should now appear at the login screen.

- **Wayland is disabled in the GDM configuration.** This can happen on some systems after
  an upgrade. Open the configuration file:
  ```bash
  sudo nano /etc/gdm3/custom.conf
  ```
  Find the line that reads `#WaylandEnable=false` or `WaylandEnable=false` and change it to:
  ```ini
  WaylandEnable=true
  ```
  Save the file (`Ctrl+O`, then `Ctrl+X`), then reboot.

---

## Step 1: Install Waydroid and ADB

Waydroid lets you run Android apps on your Linux desktop. Follow the official installation
instructions for Ubuntu/Debian here:
[https://docs.waydro.id/usage/install-on-desktops#ubuntu-debian-and-derivatives](https://docs.waydro.id/usage/install-on-desktops#ubuntu-debian-and-derivatives)

After installation, search for "Waydroid" in your application menu and launch it. You will be
prompted to download an Android image. Choose the option **without** Google apps — you only
need the base Android system.

You also need **ADB** (Android Debug Bridge), a tool for sending commands to the Android
container. Install it with:

```bash
sudo apt install adb -y
```

---

## Step 2: Install mitmproxy

mitmproxy is the tool that will intercept and display the app's network requests.

> **Do not install mitmproxy with `sudo apt install mitmproxy`.** Ubuntu's package lags years
> behind (Ubuntu 24.04 ships version 8.1.1), and old versions generate certificates that current
> Android WebViews reject outright — every HTTPS request fails, with an error message that
> misleadingly blames the certificate installation. See "Every HTTPS request fails with a
> certificate error" under Troubleshooting for the full explanation.

Install a current version with [uv](https://docs.astral.sh/uv/) instead:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh     # skip if you already have uv
uv tool install mitmproxy
```

This puts `mitmproxy`, `mitmdump`, and `mitmweb` in `~/.local/bin`, which Ubuntu already has on
your `PATH`. Confirm you are running version 12 or newer:

```bash
mitmweb --version
```

If it reports version 8 or 9, an old apt copy in `/usr/bin` is taking precedence. Remove it with
`sudo apt remove mitmproxy` and check again.

---

## Step 3: Install the IntelliClima+ App in Waydroid

The easiest way is to install the app directly from the **Google Play Store** inside Waydroid.
If you chose to include Google apps when setting up Waydroid, the Play Store will already be
available. Log in with a Google account, search for **"IntelliClima+"** (by Fantini Cosmi),
and install it as you would on a phone.

If you did not include Google apps, or the Play Store is not working, you can sideload the APK
as an alternative:

1. Download the **IntelliClima+** APK from a trusted APK mirror such as
   [APKPure](https://apkpure.com) or [APKCombo](https://apkcombo.com). Search for
   "IntelliClima+" (by Fantini Cosmi).
2. Install it into Waydroid by running:
   ```bash
   waydroid app install /path/to/intelliclima.apk
   ```
   Replace `/path/to/intelliclima.apk` with the actual path to the downloaded file
   (for example `~/Downloads/intelliclima.apk`).

Once installed, launch Waydroid and verify the IntelliClima+ app appears. Do **not** log in
yet.

---

## Step 4: Find Your Waydroid Network Address

mitmproxy needs to listen on the network interface that Waydroid uses. Run:

```bash
ip address show waydroid0
```

You will see output similar to this:

```
18: waydroid0: <BROADCAST,MULTICAST,UP,LOWER_UP> ...
    inet 192.168.240.1/24 ...
```

Note the IP address after `inet` — in this example it is `192.168.240.1`. Yours may differ.
Use your actual address in the commands below wherever `192.168.240.1` appears.

---

## Step 5: Install the mitmproxy Certificate in Waydroid

The IntelliClima+ app uses HTTPS. For mitmproxy to read HTTPS traffic, Android must trust
its certificate. This is a one-time setup.

**5a.** Start mitmproxy once briefly (just to generate the certificate files):

```bash
mitmweb -p 8888 --listen-host 192.168.240.1
```

Wait a few seconds, then stop it with `Ctrl+C`.

**5b.** Get the certificate hash:

```bash
openssl x509 -subject_hash_old -in ~/.mitmproxy/mitmproxy-ca-cert.pem
```

The first line of the output is the hash, for example `a8990c1d`. Note your hash — it will
be different from this example.

**5c.** Install the certificate into Waydroid's trusted certificate store. Replace `a8990c1d`
with your actual hash from the previous step:

```bash
sudo mkdir -p /var/lib/waydroid/overlay/system/etc/security/cacerts/
sudo cp ~/.mitmproxy/mitmproxy-ca-cert.pem \
    /var/lib/waydroid/overlay/system/etc/security/cacerts/a8990c1d.0
sudo chmod 644 /var/lib/waydroid/overlay/system/etc/security/cacerts/a8990c1d.0
```

> The filename must be your hash followed by `.0` — do not change the extension.

**5d.** Restart Waydroid to apply the certificate:

```bash
sudo systemctl restart waydroid-container
```

> mitmproxy keeps its certificate authority in `~/.mitmproxy` and reuses it across versions, so
> this step is genuinely one-time. Upgrading mitmproxy later does **not** require reinstalling
> the certificate. You only need to repeat this step if you delete `~/.mitmproxy` or reinstall
> the Waydroid image (which wipes the overlay).

---

## Step 6: Start Capturing Traffic

Now you will route Waydroid's traffic through mitmproxy and use the IntelliClima+ app normally.

**6a.** Tell Waydroid to route its traffic through mitmproxy:

```bash
adb shell settings put global http_proxy "192.168.240.1:8888"
```

**6b.** Start Waydroid and mitmproxy. You can either start them together in one terminal:

```bash
waydroid & mitmweb -p 8888 --listen-host 192.168.240.1
```

Or open two terminal windows and start each separately — Waydroid from the application menu
and mitmproxy with:

```bash
mitmweb -p 8888 --listen-host 192.168.240.1
```

mitmproxy will open a web interface in your browser at `http://127.0.0.1:8081`. Keep this
tab open — this is where you will see captured requests.

> **Keep the Waydroid window visible for the whole capture.** Waydroid's default
> `suspend_action = freeze` (in `/var/lib/waydroid/waydroid.cfg`) suspends the whole Android
> container whenever no window is displayed. A frozen container stops making network requests,
> so a capture left running in the background silently records nothing.

**6c.** Launch the **IntelliClima+** app inside Waydroid and log in with your IntelliClima
credentials. Use the app normally for a few minutes. Specifically, make sure to:
- Open the device list (so the app fetches device status)
- Change the speed or mode of your device at least once
- If your device has any special features (timers, programs, sensors), interact with those too

You should see requests appearing in the mitmproxy browser tab at `http://127.0.0.1:8081`.

---

## Step 7: Export the Captured Traffic

Once you have captured a good set of interactions, export the traffic log for sharing.

**7a.** In the mitmproxy web interface (`http://127.0.0.1:8081`), click **File → Save** in the
menu bar. This saves a `.mitm` file (for example `flows.mitm`) to your Downloads folder.
This file contains the full captured traffic.

> Alternatively, you can also export individual requests as a HAR file using
> **File → Export → HAR**.

**7b.** Before sharing, open the `.mitm` file to check for sensitive information (see the
next section).

**7c.** When done, remove the proxy setting from Waydroid so normal app use is restored:

```bash
adb shell settings put global http_proxy :0
```

---

## Step 8: What to Check Before Sharing Your Logs

> **You are solely responsible for what you share.** The maintainer of this project accepts
> no responsibility for any personal or account information accidentally included in shared
> logs. Before sharing, you must review and remove all personal information yourself.

**No personal or account information should remain in the file.** This includes at minimum:

- Your **username and email address**
- Your **password hash** (the login request to `/user/login/` contains a SHA-256 hash of
  your password — remove or replace this entire request)
- Your **account ID** and **device serial numbers**
- **Authentication/session tokens, cookies, and authorization headers**, including secrets
  in URLs or nested JSON strings
- **MAC addresses, home/room names, and location information**
- Any other value that could identify you or your account

Use the mitmproxy web interface (`http://127.0.0.1:8081`) to review each captured request
before exporting. You can delete individual requests from the list by selecting them and
pressing `d`. Export only after you are satisfied nothing personal remains.

Additionally, **change your IntelliClima password** in the official app after capturing.
Do not assume that changing the password invalidates every previously issued session token;
it is not a substitute for removing secrets before sharing.

**Inspecting the exported file before sharing:**

You can re-open the exported `.mitm` file in mitmproxy at any time — without needing
Waydroid or an active proxy — to review exactly what it contains, the same way the
maintainer would when receiving it:

```bash
mitmweb -r /path/to/flows.mitm
```

This opens the mitmproxy web interface at `http://127.0.0.1:8081` with all the saved
requests loaded. Click through each request and check both the **Request** and **Response**
tabs for any personal information. If you find something that should be removed, close
mitmweb, reopen the original capture session (`mitmweb -r /path/to/flows.mitm`), delete
the offending request by clicking it and pressing `d`, then re-export with **File → Save**.

---

## Step 9: Share Your Logs with the Maintainer

Open a new GitHub issue on this repository with the minimum sanitized evidence needed.
If attaching an exported `.mitm` (or `.har`) file, complete the review in Step 8 first.
Please include the following information in the issue:

- Your **device model** (for example: IntelliClima RHINOCOMFORT 3)
- Its **product code and firmware version**, and the **IntelliClima+ app version**
- A short description of **what actions you performed** in the app while capturing
  (for example: "logged in, checked device status, set fan speed to medium, set auto mode"). Be very specific here in exactly what steps you took, and in what order. Otherwise it's very difficult to know which request corresponds to which action.
- Your **operating system** (Ubuntu version) and your **mitmproxy version**
  (`mitmweb --version`)
- Whether HTTPS traffic was successfully captured or only HTTP (if you only see HTTP requests,
  see "Every HTTPS request fails with a certificate error" in the Troubleshooting section)

The more interactions you capture (especially changing different settings and modes), the
more complete the protocol picture will be, and the easier it is to implement support.

**GitHub Issues:** [https://github.com/dvdinth/pyintelliclima/issues](https://github.com/dvdinth/pyintelliclima/issues)

---

## Troubleshooting

**mitmproxy browser tab shows no requests from IntelliClima+**
- Make sure you ran the `adb shell settings put global http_proxy` command *after* starting
  mitmproxy and *before* opening the app.
- Confirm the IP address in the `adb` command matches the one from `ip address show waydroid0`.
- Try restarting Waydroid with `sudo systemctl restart waydroid-container` and repeating
  step 6.

**Every HTTPS request fails with a certificate error**

mitmproxy logs a line like this for every connection, including
`intelliclima.fantinicosmi.it`:

```
Client TLS handshake failed. The client does not trust the proxy's certificate for
intelliclima.fantinicosmi.it (OpenSSL Error([('SSL routines', '', 'sslv3 alert
certificate unknown')]))
```

**This message is misleading.** It is mitmproxy's guess at why the client rejected the
certificate, and the most common actual cause is not trust at all — it is **certificate
lifetime**. Check first, before touching anything from step 5:

- **Is your mitmproxy too old?** Run `mitmweb --version`. Versions 8 and 9 (including Ubuntu's
  apt package) generate certificates valid for 367 days. The CA/Browser Forum limit on
  certificate lifetime dropped to **200 days** for certificates issued after **2026-03-15**,
  Chromium enforces that limit, and the Android WebView treats a CA installed into
  `/system/etc/security/cacerts` as a publicly-trusted root — so the limit applies to
  mitmproxy's certificates too. The result is a hard rejection on every request.

  This is why a setup that worked before March 2026 can break with no changes on your side.
  Fix it by installing a current mitmproxy as described in step 2. Your existing certificate
  from step 5 stays valid — there is no need to reinstall it.

  To confirm this is your problem, look for Chromium's real error code in the Android log while
  the app is running:
  ```bash
  adb logcat -d | grep "net_error"
  ```
  `net_error -213` is `ERR_CERT_VALIDITY_TOO_LONG` and confirms the lifetime issue.
  `net_error -202` (`ERR_CERT_AUTHORITY_INVALID`) is a genuine trust problem — in that case
  continue below.

- **Is the certificate actually installed?** Confirm the file exists:
  ```bash
  ls /var/lib/waydroid/overlay/system/etc/security/cacerts/
  ```
  You should see a file named `<your-hash>.0`. If not, repeat step 5. Make sure the filename
  hash matches your current certificate:
  ```bash
  openssl x509 -subject_hash_old -in ~/.mitmproxy/mitmproxy-ca-cert.pem
  ```
- **Did you restart Waydroid** after installing the certificate? The overlay is only applied at
  container start.

**Lots of failed handshakes to Google domains**

Lines like these are **expected and harmless**:

```
Client TLS handshake failed. The client does not trust the proxy's certificate for
android.googleapis.com
```

Google Play Services pins its own certificates, so mitmproxy cannot intercept
`android.googleapis.com`, `*-pa.googleapis.com`, `gstatic.com` and similar. This has nothing to
do with your setup and does not affect the IntelliClima+ capture — it is just noise, and there
is a lot of it if you installed a Waydroid image that includes Google apps. Ignore it and look
only for `intelliclima.fantinicosmi.it` requests.

A cleaner option is to tell mitmproxy to intercept **only** the IntelliClima server and pass
everything else straight through without touching it:

```bash
mitmweb -p 8888 --listen-host 192.168.240.1 --allow-hosts fantinicosmi
```

This removes the noise at the source rather than just hiding it: other hosts are forwarded
without TLS interception, so Google's pinned connections keep working normally and Android stays
happy about having a working internet connection.

**`adb` command says "no devices found"**
- Waydroid must be running before you use `adb`. Launch Waydroid from the application menu
  first, then try again.

**Waydroid does not start / says Wayland is required**
- Follow the "Getting a Wayland Session on Ubuntu" steps in the Prerequisites section above.
