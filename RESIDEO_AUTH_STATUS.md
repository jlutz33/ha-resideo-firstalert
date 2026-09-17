# Resideo Auth Investigation — Status

Last updated 2026-09-17 (closing update). Earlier updates are preserved below, most recent first.

## 2026-09-17 closing update: PR #1 merged, resolved end to end, docs cleaned up

**`rheeloaded/ha-resideo-firstalert#1` is merged** (2026-09-17T21:00:43Z, merged directly by `rheeloaded`, no formal review left). It carries the full arc: the host-migration fix, the browser-login redirect improvement, device-type filtering, the `exchange_code_for_tokens` network-error fix (`v1.5.1`), and the `AbortFlow`/token-refresh-on-reconfigure fix (`v1.5.2`/`v1.5.3`).

**`almoney`'s case fully resolved** — turned out to be neither bug we chased: they'd disabled their existing config entry at some point (to avoid lockout noise) and forgot. Re-enabling it fixed things immediately. The two real bugs we found and fixed along the way (`exchange_code_for_tokens` swallowing network errors, `AbortFlow` getting caught by a bare `except Exception`) are still genuine, worthwhile fixes — just not what was actually wrong for `almoney` specifically. Good example of chasing a report to a real root cause even when it isn't the one that started the investigation.

**Independent confirmation from `pjschaffer`** on the original PR #14 thread: updated, confirmed working, and — as an unprompted bonus — confirmed the `"dc": "DC Power"` translation fix too (a battery-powered detector now shows the correct label instead of an error).

**`zackwag`** (a separate, independently-built integration — not a fork of this one, first commit 2026-07-19) already had the host-migration fix by the time we checked (commit `31bd8c8`, `2026-09-16T21:33:00Z`) — but the timing (35 minutes after our own PR #14 announcement, on a thread they were actively watching) suggests they picked it up from us rather than found it independently. Flagged them on PR #14 pointing at PR #1's later fixes (`AbortFlow`, token-refresh-on-reconfigure) in case the same patterns apply to their own `config_flow.py`, since they might not otherwise see activity on a different repo's PR.

**Documentation pass**: `README.md`, `manifest.json` (`documentation`/`issue_tracker` links), and the in-UI `docs_url` links in `config_flow.py`/`application_credentials.py` were all still pointing at the dead `aidenmitchell/ha-resideo-firstalert` repo — fixed to point at this fork. Also fixed two real staleness bugs in `README.md` itself: the documented `API Base URL` still said the old host, and the Power Source sensor table didn't list `dc` as a valid value (the PR #9 fix). Left `manifest.json`'s `codeowners` (`@aidenmitchell`) alone — that's an attribution call, not a documentation-accuracy one.

**Current state**: `main` is at `v1.5.3`, confirmed working end-to-end on this fork's own install and independently by two other users. PR #1 upstream is merged. Nothing outstanding.

## 2026-09-17 update: PR upstreamed, real bug found and fixed (v1.5.1)

Opened three PRs against `rheeloaded/ha-resideo-firstalert`'s `browser-assisted-login` branch (the maintainer situation settled: `rheeloaded` is taking over as maintainer given the depth of their work on the captcha/rotation/filtering fixes, this fork continuing as a contributor rather than a competing fork):

- [#1](https://github.com/rheeloaded/ha-resideo-firstalert/pull/1) — the host-migration fix (`api.ha.resideo.com`), scoped narrowly to just that plus the legacy-auth nonce/challenge fix. Left out the `dc` sensor option and brand icons (unrelated, already have their own open PRs against the original repo) and this status doc (personal notes, not a contribution).
- [#2](https://github.com/rheeloaded/ha-resideo-firstalert/pull/2) / [#3](https://github.com/rheeloaded/ha-resideo-firstalert/pull/3) — the `dc` sensor option and brand icons, opened separately against the same branch so they're not stuck forever on the dead original repo.

`almoney` reported "An unknown error occurred" pasting the browser-login code on PR #1. Root cause: `auth.py::exchange_code_for_tokens` was the one network call in the whole codebase that didn't wrap `aiohttp.ClientError` into a domain exception — every other request (`api.py::_request`) does. A transient connection hiccup during the token-exchange POST to `login.resideo.com` (exactly the kind of thing hit repeatedly against GitHub's API this same day) would propagate as a raw aiohttp exception, which `config_flow.py`'s except chain doesn't specifically handle, so it fell into the generic "unknown error" catch-all instead of a real message. Fixed on both `main` and the PR #1 branch. Shipped as `v1.5.1`, confirmed working end-to-end on a real account (delete + re-add, browser login, succeeded cleanly).

Also caught and fixed in passing: the earlier `v1.5.0-beta3` merge had force-replaced `strings.json`/`translations/en.json` wholesale with `rheeloaded`'s versions, which silently dropped the `"dc": "DC Power"` translation label from PR #9 — `sensor.py`'s options list still included `"dc"` as valid, just with no label. Restored on `main`.

Set up a recurring check (every 30 min, session-local) watching PR #1 for review activity.

## 2026-09-16 update #2: the "outage" was actually a host migration — fixed

Same-day follow-up to the update directly below, which had concluded the REST outage was purely Resideo's problem with nothing for us to do. That conclusion was wrong, or at least incomplete: **`api.resideo.com` isn't down, it's retired.** Resideo migrated the entire consumer API to a new host, `api.ha.resideo.com`, and the old host's canned 503 "planned maintenance" body is permanent, not transient.

Found via `sfcodes/ha-resideo` (a separate, more mature reverse-engineering project covering Resideo's thermostat/leak-detector devices via this same consumer API), whose [v0.3.0 release](https://github.com/sfcodes/ha-resideo/releases/tag/v0.3.0) diagnosed and fixed the identical 503 on 2026-09-11. Their `const.py`/`client.py` are extensively documented, reverse-engineered-and-verified-live reference material — not speculation. Independently confirmed ourselves (not just trusted their word) via direct `curl`:

- `https://api.ha.resideo.com/ris-public-api/api/v1/accounts` → `401` (not 503/404 — route exists, live, enforcing auth)
- `https://api.ha.resideo.com/ris-public-api/api/v2/devices/smokeDetectors/{id}/state` → `401` — our exact smoke-detector endpoint, specifically, also confirmed alive at the new host (sfcodes' project only covers thermostats, so this needed separate verification)
- Old host (`api.resideo.com`) still `503` on the same accounts call, same moment — direct side-by-side confirmation this is a host move, not a flaky endpoint recovering/failing intermittently

Two extra headers are mandatory on every call at the new host (confirmed via sfcodes' `client.py`, which sends both unconditionally on every request, not just writes): `Ocp-Apim-Subscription-Key: b60885e8a9b44680a29ea1f03452878a` (Azure API Management key) and `User-Agent: First Alert/2440 CFNetwork/3860.600.12 Darwin/25.5.0` (the real app's UA — our client previously sent no UA on API calls at all, only on the Auth0 login flow in `auth.py`).

**Fixed in this fork**: `const.py`'s `API_BASE_URL` now points at the new host, `API_SUBSCRIPTION_KEY`/`API_USER_AGENT` added, and `api.py::_request` now sends both new headers on every call (persists through the existing 401-retry path automatically, since that path mutates the same headers dict rather than rebuilding it). `RESIDEO_API.md` updated to match. Auth0 (`login.resideo.com`) is untouched by any of this — it was never part of the outage, only the REST data layer moved.

**Not yet done, deliberately out of scope for now**: `sfcodes`'s client also documents a working Azure SignalR real-time push channel (separate from this REST fix) that also moved hosts alongside the REST API — noted here in case push-based updates are worth adding later, but the REST fix alone should be sufficient to restore normal polling.

**Confirmed end-to-end**: shipped as `v1.5.0` on this fork, installed via HACS on a real instance with an existing config entry, restarted — sensors resumed updating with no re-login needed (the stored refresh token was still valid the whole time, since only the REST data host moved, not Auth0). The fix works in practice, not just in probes.

## 2026-09-16 update: Resideo's backend itself is down, and the login flow got a real upgrade

**Blocking issue, not ours to fix:** Resideo's consumer REST API (`ris-public-api` on `api.resideo.com`, and a second internal service called `devsrv`) has been returning `503 "The API is temporarily down for planned maintenance"` continuously since ~2026-09-09, confirmed still down as of this update (direct `curl` to the accounts endpoint returns 503 right now). This is **not** a real maintenance window — `rheeloaded` (upstream PR #14 thread) confirmed Resideo's own status page shows all-green/no incidents, their actual announced maintenance window closed hours before this outage started, and automated overnight monitoring (72 checks over 12 hours) got 503 every single time with zero variation. The First Alert app *looks* like it still works, but that's misleading: it's running on a still-live Azure SignalR push channel plus a cached device list, not fresh REST reads — the app can't do live pulls right now either. A separate contributor (`zackwag`) has forked off exploring whether this is an actual deprecation tied to a long-standing "coming soon...a new app" banner in the First Alert app, but that's speculative, not confirmed. **Nothing in this integration can fix this — it's entirely on Resideo's side.** Re-check with a direct `curl` to `https://api.resideo.com/ris-public-api/api/v1/accounts` before assuming any login failure is a code problem.

**Merged `rheeloaded`'s newer fixes** (`v1.5.0-beta3` tag / `filter-non-smoke-devices` branch, the current cumulative head of their work) into this fork's `main`, superseding the `v1.4.0-beta1` web-client approach merged on 2026-08-28:

- **Better browser-login redirect**: the earlier merge used a separate Auth0 "web client" (`dN6PdXbUwMAYGRuh8vQX8BfIry6oge1E` / `myid.resideo.com`) to get the code into the browser's address bar. `rheeloaded` found something simpler and more robust — the **same app client**, but its `https://login.resideo.com/ios/com.resideo.firstalert/callback` redirect (as opposed to the `com.resideo.firstalert://...` custom-scheme one) is *also* registered with Auth0, and lands on a plain "Not found." page with the code sitting in the address bar. No DevTools, no second client to track, no separate refresh-client-id bookkeeping. **This merge removed the old web-client code entirely** (`WEB_CLIENT_ID`, `WEB_REDIRECT_URI`, `CONF_CLIENT_ID`, the `browser_web`/`reauth_browser_web` config-flow steps) since its own author had already abandoned it upstream — it was dead, untested code sitting in our fork. `config_flow.py`'s menu is back to a clean `["browser", "login", "manual"]`.
- **Device-type filtering fix** (real bug, found by a user with a water leak detector + thermostat also on their Resideo account): the integration wasn't filtering devices by type at all, so anything non-smoke-detector on the account got pulled in, mislabeled as a smoke detector, and polled every cycle forever — generating a failed API call and a log warning every 60 seconds for each unsupported device. Now filters on `productFamily` in `api.py::get_devices`, skipping anything that isn't `PRODUCT_FAMILY_SMOKE_DETECTOR`.
- **503 handling fix**: server errors (like the current outage) used to fall into a generic "unknown error" in the config flow, which misled people into thinking their *login* was broken during this exact outage and sent them needlessly deleting/re-adding their integration. Now reported as a clear "service temporarily unavailable" without triggering a bogus reauth prompt.

Merge was a real 3-way merge (not a rebase/force-push) since `main` already had public history from the first merge — resolved conflicts in `auth.py`/`manifest.json` by hand, then force-replaced `config_flow.py`/`const.py`/`api.py`/`strings.json`/`translations/en.json` with `rheeloaded`'s authoritative versions (since our old web-client additions there were the abandoned approach), and manually stripped the matching dead code from `__init__.py` (not touched by their commits, so it auto-merged "successfully" but stayed stale). Confirmed zero remaining references to the removed symbols, `py_compile` and JSON validation both clean.

**Still true:** the underlying scripted-login captcha wall (see below) is unchanged and still has no fix. **Newly true:** even once someone completes the browser-assisted login successfully, Resideo's backend being down means the integration still can't actually fetch device data right now — that's expected and will resolve itself whenever Resideo's outage clears, no code change needed on our end.

## 2026-08-28 update: merged community fix for the captcha wall

## Current state: resolved, via community fix merged into this fork

Upstream (`aidenmitchell/ha-resideo-firstalert`) has had no commits since 2025-12-20 and hasn't reviewed any open PR in that time (confirmed the maintainer is still active on GitHub generally, just not on this repo). Rather than keep waiting, `merge/browser-login-fork` in this fork reconciles:

- **This repo's own pending fixes**: PR #9 (`dc` power source sensor option) and PR #10 (inline brand icons for HA 2026.3+), both otherwise stuck unmerged upstream.
- **`rheeloaded/ha-resideo-firstalert`'s `web-client-login` branch** (their PR #14 upstream, plus one further commit not yet in the PR): adds a browser-assisted login flow that sidesteps the Auth0 captcha entirely by having a human complete the login in a real browser and paste back the resulting authorization code, and fixes the refresh-token rotation bug (see "Root cause, fully understood now" below) more completely than our own earlier attempt at the same fix.
- **This fork's own nonce/challenge-detection fix** to the legacy scripted `ResideoAuth` class, layered on top (see below) — kept as a diagnostic/fallback, not the primary fix.

### Root cause, fully understood now

Scripted email/password login (`ResideoAuth.authenticate` in `auth.py`) fails because Auth0 gates `/usernamepassword/login` behind a bot-detection challenge (`/usernamepassword/challenge` returns `{"required": true}`) that a headless HTTP client cannot satisfy — confirmed independently by us and by `rheeloaded` (PR #14). This is a deliberate server-side wall, not a fixable protocol mismatch; a missing `nonce` param and stale `Auth0-Client` version fingerprints were real bugs fixed along the way, but they were not the actual blocker. **No scripted login fix is possible** without either TLS-fingerprint impersonation (not attempted — flagged as more invasive than warranted) or a real browser completing the challenge.

Separately, **Auth0 rotates the refresh token on every use**, and the original code only ever read `access_token` out of a refresh response, discarding the rotated `refresh_token`. This meant even a successfully-bootstrapped token would silently die within about an hour. Both our fork and `rheeloaded` independently found and fixed this (this is the shared root cause behind upstream issues #8, #12, #13). `rheeloaded`'s fix is the more complete one: it also catches the case where **verifying** a freshly-entered token (during initial config flow / manual token entry / reauth) itself rotates it — every config-flow step that calls `get_accounts()` to validate a token now re-reads `client.refresh_token` afterward and persists the post-rotation value, instead of the stale pre-rotation string the user typed in. Our own earlier fix only covered the background coordinator refresh loop, not this initial-validation path.

### The actual working solution: browser-assisted login

`config_flow.py` now offers, in order: **"Sign in with your browser"** (two variants — a web-client one where the auth code lands directly in the browser's address bar, and an app-client fallback that needs DevTools to find the code), then email/password (kept, but will reliably fail with a clear captcha-detected error), then manual refresh token entry.

Flow for the user: Home Assistant shows an authorize URL → open it in a real browser and log in normally (any challenge renders and is solved by a human) → the page tries to redirect to a URL Home Assistant can't automatically catch → copy that URL (or just the `code` param) back into the HA form → HA exchanges it for tokens itself. This is the same technique we improvised by hand earlier in this investigation (see "Current working state" in the original notes below), now built into the integration properly instead of requiring a human to walk through it each time.

Refresh tokens obtained this way now persist correctly across rotations (see above), so this should only need to be repeated roughly every 30 days when the underlying refresh token itself expires, not every time an access token expires.

### What's left

- **Not yet tested end-to-end on this fork's actual merged branch** (`merge/browser-login-fork`) against a real account/device. `rheeloaded`'s underlying commits were validated by multiple users on their own fork before merging, and our earlier improvised version of the same technique worked when we did it by hand — but the reconciled branch itself hasn't been run against live devices yet.
- **HACS distribution**: to actually use this without manually copying files, point HACS at this fork (`jlutz33/ha-resideo-firstalert`) as a custom repository, on whichever branch/tag ends up hosting this merged work — mirrors how `rheeloaded`'s testers consumed their fork.
- **Web-client login variant is still labeled experimental upstream** (`rheeloaded` couldn't test it end-to-end himself, no Resideo account) but was confirmed working by real testers in the PR #14 thread, including surviving reconnects without reauth.
- Consider commenting on upstream issues #8/#11/#12/#13 and/or PR #14 noting this fork now carries a merged, working version, in case that unblocks anything upstream or helps other people hitting the same wall.
- The dead-end browser **OAuth-via-HA-redirect** path (`AbstractOAuth2FlowHandler`'s automatic external-step flow, as opposed to the manual-paste flow above) remains structurally impossible — Resideo's Auth0 client only allow-lists the app's own custom URL scheme as a redirect target, confirmed via direct testing. Not revisited; the manual-paste approach above is the correct workaround, not a stopgap for this.
- Official Resideo/Honeywell Home developer API still does not cover smoke/CO alarms (confirmed against the live endpoint reference, not just docs) — not a path forward for this device regardless of developer account registration.
- No local control path exists for the SC5 (cloud-only, AWS IoT Shadow architecture, no Zigbee/Z-Wave/Matter/Thread) — going fully local would require different hardware (e.g. First Alert ZCOMBO/SMCO410, Z-Wave, natively supported by HA), not reverse-engineering the device currently owned.

---

## Original investigation notes (2026-08-06)

Everything below is preserved as-written from the original session for reference — some of it (e.g. "possible next steps") has since been resolved by the merge described above.

### What broke

Home Assistant logs showed `Authentication failed: Login failed with status 401` from the scripted email/password login (`auth.py`), which reproduces Resideo's Auth0 login flow via raw HTTP calls (not a real browser). Captured real app traffic (via Proxyman/MITM) and diffed it against `auth.py`. Found real protocol drift:

1. **Missing `nonce`** — the real `/authorize` call and the `/usernamepassword/login` POST both include a `nonce` param that `auth.py` never generated or sent. Almost certainly the direct cause of the original 401.
2. **Stale `Auth0-Client` fingerprints** — login-widget version was pinned to `9.13.2`, real app is on `9.32.0`; the `auth0-flutter` app fingerprint was similarly stale (`1.14.0`/iOS 26.1 vs `2.3.0`/iOS 26.5).
3. **New step**: the real flow calls `POST /usernamepassword/challenge` before submitting credentials — an Auth0 bot-detection pre-check that returns `{"required": true/false}`.

All three were fixed in `auth.py`. This got the scripted flow further, but then hit a **hard wall**: `/usernamepassword/challenge` started returning `{"required": true}` for the scripted attempt specifically (never for the real app, tested side-by-side on the same account). Three separate attempts, spread over real time, including a full detour through setting up the OAuth browser flow in between (so not just rapid retries triggering rate limiting) — all hit the same captcha requirement.

### Other things tried and why they didn't pan out

- **Browser-based OAuth flow** (`config_entry_oauth2_flow` / Application Credentials): built out and wired into the config flow menu, but Auth0 rejects Home Assistant's redirect URI outright (`Callback URL mismatch`). The `client_id` used throughout (`SRmiA7CaYi1JgivDZdzzoZu4X5VBogGt`) belongs to Resideo's own mobile app and is allow-listed only for its custom URL scheme (`com.resideo.firstalert://...`) — not something we control or can register against. **Confirmed dead end for this client_id.**
- **MITM-captured refresh token via Proxyman**: worked for the login-page portion (rendered in the app's webview, which trusts the system cert store), but the final native `POST /oauth/token` call is certificate-pinned and fails under MITM with a TLS trust error. Did not pursue defeating cert pinning (jailbreak/Frida-class tooling) — too invasive for the payoff, and risky to poke at on a life-safety device's firmware/app.
- **Official Resideo developer API**: doesn't cover this device category at all.
- **Direct local device access**: SC5 device state has the unmistakable shape of an **AWS IoT Device Shadow** (`deviceState: {desired, reported}`), meaning the device talks MQTT/TLS directly to AWS IoT Core, not a local hub or LAN API.

### Current working state (how login was actually happening, before the merge above)

Because scripted login is blocked but a *human* logging in via a real browser is not, the integration was bootstrapped as follows:

1. Generated our own PKCE `code_verifier`/`code_challenge` + `state` + `nonce` locally (not via the app).
2. Built the same `/authorize` URL the app uses and had the user open it in a real desktop browser and log in normally (any challenge/captcha solved by a human, so it never triggered).
3. The browser's attempted redirect to `com.resideo.firstalert://...?code=...&state=...` fails (no app registered for that scheme on desktop), but the URL — containing the real authorization code — is visible in DevTools/address bar.
4. That code + our own `code_verifier` were used to complete the token exchange directly via a plain HTTPS POST (`curl`) to `/oauth/token` — no proxy, no pinning issue, since this is a normal outbound request, not something the device or app has to trust.
5. The resulting `refresh_token` was pasted into HA's "Enter refresh token manually" config flow option.

This is exactly the technique now built into the config flow properly (see "The actual working solution" above), so this manual dance shouldn't be necessary again.

### Code changes made in the original session

All in `custom_components/resideo_firstalert/`:

- **`auth.py`** — nonce generation/threading through the flow, updated Auth0 client version fingerprints, added `_step2b_check_challenge` (surfaces a clear error if Auth0 ever requires a captcha, instead of a bare 401). *Preserved in the merge, reapplied on top of `rheeloaded`'s untouched `ResideoAuth` class.*
- **`api.py`** — `_refresh_access_token` now treats HTTP 403 the same as 401, captures and threads through a rotated `refresh_token`, `test_connection` no longer swallows `ResideoAuthError`. *Superseded by `rheeloaded`'s more complete version of the same fix (see "Root cause" above) — not carried forward as-is.*
- **`__init__.py`** — wires a callback to persist a rotated refresh token back into the config entry. *Superseded, same reason.*
- **`manifest.json`** — added `application_credentials` dependency for the (ultimately dead-end) HA-native OAuth flow. *Not carried forward — not needed by the manual-paste browser flow that replaced it.*
- **`config_flow.py`**, **`strings.json`**, **`translations/en.json`** — OAuth menu entries added then removed again once confirmed non-functional. *Superseded by `rheeloaded`'s working `browser`/`browser_web` menu entries.*

### Confirmed root causes behind related upstream GitHub issues

Checked `aidenmitchell/ha-resideo-firstalert` issues #8, #11, #12 mid-session:

- **#11** ("getting login error") — same symptom we hit.
- **#12** — independently confirmed Auth0 refresh-token rotation is enabled on this tenant and paired with reuse-detection (replaying a stale token revokes the whole token family).
- **#8** — root cause of #12's rotation finding: refresh responses were never checked for a rotated `refresh_token`.

(As of this update, issue #13 also exists upstream, opened by a PR #14 tester, describing the same short-lived-token symptom — same root cause, now fixed via the merge above.)

### Official developer API — confirmed does not cover this device

Fetched the live API reference directly (`developer.honeywellhome.com/api-methods`). Full set of device-typed endpoints: `thermostats`, `cameras`, `waterLeakDetectors`, `dhw`, `shutoffvalve`. **No smoke/CO/alarm endpoints exist in the published reference.** Consistent with the Acceptable Use Policy's explicit ban on "High Risk Activities" (life-support-type systems where failure could cause death/injury).

Read the full Resideo Developer License Agreement. Notable points if registering anyway:

- API access is free; SDK access may have separate fees (not relevant here).
- Rate limit: 250 calls/hour without written approval for more.
- The reverse-engineering prohibition (Section 3.7) applies only to their official **DevTools** — not to the separate consumer-app API this integration already reverse-engineers. Not legal advice; just a plain reading.
- Registration may require a credit card even for the free tier, and ties a "Developer ID" to your actual Resideo account.
