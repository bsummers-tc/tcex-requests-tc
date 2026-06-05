# tcex-requests-tc

A [TcEx](https://github.com/ThreatConnect-Inc/tcex) submodule providing the authenticated
`requests` session layer for communicating with the ThreatConnect REST API, including HMAC and
token authentication, automatic retries, proxy support, and curl-command logging.

## Overview

All HTTP communication between a TcEx App and the ThreatConnect platform flows through this
submodule. It provides two `requests.auth.AuthBase` implementations (HMAC-SHA256 and token),
a combined auth class that selects the appropriate strategy at construction time, and a
`requests.Session` subclass that ties everything together with retry logic, 401 recovery,
base-URL resolution, and debug logging.

## Authentication

### `HmacAuth`

Implements the ThreatConnect HMAC-SHA256 signature scheme. On each request it constructs the
signature string `{path_url}:{method}:{timestamp}`, signs it with the App's secret key using
`hmac.new(..., digestmod=sha256)`, and sets:

```
Authorization: TC {access_id}:{base64_signature}
Timestamp: {unix_epoch}
```

The secret key is held as a `Sensitive` type so it is never inadvertently logged or serialized.

### `TokenAuth`

Implements TC-Token authorization. Accepts the token in three forms:

| Form | Use case |
|---|---|
| `str` | Static token (no renewal) |
| `Sensitive` | Static token wrapped for safe handling |
| `Callable[..., str \| Sensitive]` | Dynamic token — called on every request to support platform-managed token renewal |

Sets:

```
Authorization: TC-Token {token}
Timestamp: {unix_epoch}
```

### `TcAuth`

Combines `HmacAuth` and `TokenAuth` via multiple inheritance and selects the active strategy
at construction time:

- Provide `tc_api_access_id` + `tc_api_secret_key` → HMAC mode
- Provide `tc_token` → Token mode
- Provide neither → raises `RuntimeError`

This is the auth class used by `TcSession` in normal App operation.

## Session

### `TcSession`

A `requests.Session` subclass pre-configured for the TC API.

**Construction parameters:**

| Parameter | Default | Purpose |
|---|---|---|
| `auth` | required | Any of `HmacAuth`, `TokenAuth`, or `TcAuth` |
| `base_url` | `None` | Prepended to relative URLs passed to `request()` |
| `log_curl` | `False` | Log all requests as curl commands (always logs on non-2xx) |
| `proxies` | `None` | Proxy dict (`{'http': '...', 'https': '...'}`) |
| `proxies_enabled` | `False` | Apply `proxies` only when `True` |
| `user_agent` | `None` | Additional headers merged into the session (e.g., `User-Agent`) |
| `verify` | `True` | SSL certificate verification; accepts a CA bundle path |

**Key behaviors:**

- **Base-URL resolution** — `url()` prefixes any path not starting with `https` with `base_url`,
  so callers can pass either `/v3/indicators` or `https://app.threatconnect.com/v3/indicators`.
- **Automatic retry** — mounts an `HTTPAdapter` with `urllib3.Retry` (3 total retries, 0.3s
  backoff factor, retries on 500/502/504). Configurable via `retry()`.
- **401 recovery** — automatically replays a 401 response once, to handle token-renewal race
  conditions where the platform rotates a token between signing and receipt.
- **Curl logging** — on non-2xx responses (or always when `log_curl=True`) converts the prepared
  request to an equivalent `curl` command and logs it at `DEBUG` level via `RequestsToCurl`.
- **Per-request debug logging** — logs method, resolved URL, status code, and elapsed time after
  every request.
- **`InsecureRequestWarning` suppression** — `urllib3`'s SSL warning is silenced at import time
  for environments where `verify=False` is intentional.

### `RequestsTc`

Factory and session manager; the entry point used by the framework at App startup.

| Property / method | Description |
|---|---|
| `session` (`scoped_property`) | Returns a per-thread `TcSession` built from the App's input model. Each thread gets its own session, and forked processes get a fresh one. |
| `get_session(**overrides)` | Returns a new `TcSession` with any parameter overridden. Useful when an App needs to connect to a second TC instance. |
| `proxies` (`cached_property`) | Proxy dict assembled from `tc_proxy_host`, `tc_proxy_port`, `tc_proxy_username`, `tc_proxy_password` inputs. |

**Token priority in `get_session()`:**

1. `registry.app.token.get_token` — callable from the in-platform token module (enables automatic
   renewal; only available in `tcex`, not in `tcex-app-testing` or `tcex-cli`).
2. `model.tc_token` — static token from the input model (no renewal).
3. `model.tc_api_access_id` + `model.tc_api_secret_key` — HMAC credentials.

## Module Layout

```
requests_tc/
├── auth/
│   ├── hmac_auth.py      # HmacAuth — HMAC-SHA256 requests.auth.AuthBase
│   ├── token_auth.py     # TokenAuth — TC-Token requests.auth.AuthBase
│   └── tc_auth.py        # TcAuth — combined strategy selector
├── tc_session.py         # TcSession — requests.Session subclass
└── requests_tc.py        # RequestsTc — factory and scoped session manager
```

## Project Structure Note — No `pyproject.toml` or `.pre-commit-config.yaml`

This submodule intentionally ships **without** a `pyproject.toml` or `.pre-commit-config.yaml`.
All linting (`ruff`), type-checking (`ty`), and pre-commit hooks are configured in the **parent
projects** (`tcex`, `tcex-app-testing`, `tcex-cli`), each of which scans this submodule as part
of its own workspace. Running `pre-commit run --all-files` or `ty check` from the parent repo
root covers this code automatically — there is no need for (and no benefit to) duplicating that
configuration here.

## Used By

- [tcex](https://github.com/ThreatConnect-Inc/tcex) — all TC API calls from running Apps
- [tcex-app-testing](https://github.com/ThreatConnect-Inc/tcex-app-testing) — session fixtures for integration tests
- [tcex-cli](https://github.com/ThreatConnect-Inc/tcex-cli) — API calls during `package`, `validate`, and `deploy` commands

## License

Apache 2.0 — see the `LICENSE` file in this repository.
