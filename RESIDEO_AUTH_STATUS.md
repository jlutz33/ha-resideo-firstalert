# Resideo Auth Investigation — Status

Last updated 2026-08-28. Original investigation notes from 2026-08-06 are preserved below the update.

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
