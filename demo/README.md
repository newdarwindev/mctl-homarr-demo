# Fullscreen Homarr demo

This fork adds a **companion launcher**, not a native WebView or a Homarr API renderer. Homarr runs in its
own real Chromium/Chrome window, opened directly at your board URL in fullscreen kiosk mode. The native
wgpu/egui spacecraft UI and its existing `--fullscreen` behavior remain intact. No CRT filter is applied
to the Homarr page. This distinction is intentional: the upstream renderer has no embedded web engine.

Requires Python 3.10+ and an already-installed Chromium or Google Chrome on Linux or macOS, with an active
graphical display. The launcher installs nothing. Windows lifecycle support is not implemented.

```sh
python3 scripts/mctl-display homarr --url https://homarr.example/boards/your-board
# Or keep the URL out of shell history using a locally configured HOMARR_BOARD_URL:
python3 scripts/mctl-display homarr --browser /usr/bin/chromium

# Native mode uses your explicitly built upstream binary; flags pass through unchanged:
python3 scripts/mctl-display native --binary ./target/release/mctl -- --offline --fullscreen
```

Replace the example URL with your installation's actual board URL. The browser loads that URL as a
top-level page; there is no iframe, proxy, header rewrite or content injection. Homarr authentication,
permissions, TLS and visibility stay under your control. Log in interactively if required; the new
temporary browser profile does not import existing cookies. Private boards do not need to become public.
This demo has not connected to any private Homarr installation.

URLs must use HTTP(S), have a host and optional valid port, and contain no userinfo, query or fragment.
Use an ordinary board path, not a password/token URL. The launcher does not print the URL or browser
output, but browsers and the OS can expose URLs in process listings and on screen. Do not put secrets
anywhere in the URL. Browser executable configuration is a single trusted file, not a shell command.

The launcher stays in the foreground and waits. Close the browser window (Alt-F4 on Linux, Cmd-Q on
macOS), press Ctrl-C in the terminal, or send SIGTERM to the launcher to stop. It terminates only its own
browser process group and removes its temporary profile. Authentication/cookies are discarded; it never
touches your regular browser profile. There is no restart, background service, startup registration,
schedule or system-setting change. Force-killing the launcher with SIGKILL cannot run cleanup; use the
normal stop controls. On a crash, inspect and remove any leftover temporary profile locally.

## Local synthetic board

`demo/fixtures/serve.py` serves only `/boards/demo` from the checked-in synthetic HTML fixture, on
loopback, and exits when interrupted. The route and ordinary HTML response exercise the same top-level
board-URL contract as a Homarr installation. It is **not Homarr**, an API mock, or proof of private
Homarr authentication. It contains no remote assets, credentials or real metrics.

```sh
python3 demo/fixtures/serve.py          # foreground, loopback:8765 only; Ctrl-C stops
python3 scripts/mctl-display homarr --url http://127.0.0.1:8765/boards/demo
```

## Verification (Docker only)

```sh
docker build -f demo/docker/Dockerfile -t mctl-homarr-tests .
docker run --rm --init --network none --shm-size=256m mctl-homarr-tests
```

Tests cover URL rejection/redaction, argument boundaries, missing/non-executable browsers, native flag
dispatch, foreground waiting, normal close, SIGINT/SIGTERM, descendant cleanup, browser failure and
temporary-profile removal. A real Chromium kiosk under Xvfb loads the synthetic board and checks its
window geometry. The container runs as an unprivileged user with Chromium's sandbox enabled. No host
display, Docker socket, personal directories or credentials are mounted.

Native Rust/GPU rendering, real monitors/macOS Chrome and actual private Homarr URL/auth are **unrun**.
The CI workflow only builds and runs this ephemeral test container. Upstream Rust source is unchanged;
its original build/test instructions remain below the demo introduction in the root README.
