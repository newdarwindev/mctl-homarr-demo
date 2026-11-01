# Modification and attribution notice

This is an isolated demonstration fork of [LiamDroog/mctl](https://github.com/LiamDroog/mctl),
upstream commit `bf7072fdf1080fec6890a9889531e78297e491eb` (version 0.1.1).
The spacecraft display, native renderer, assets, original documentation and history are upstream work.
Their attribution, asset licenses, third-party notices and full GPL text are preserved.

**Modified by newdarwindev on 2026-11-01**, under GPL-3.0-or-later:

- Added `scripts/mctl-display`, an explicit foreground mode selector and external fullscreen Homarr browser launcher.
- Added synthetic board-route fixtures, Docker-only tests and a bounded pull-request workflow.
- Added a demo introduction to README. Native Rust source, dependencies and behavior are unchanged.
- Replaced active upstream CI/release workflows with demo-only CI; originals are retained in
  `demo/upstream-workflows/*.txt`. This demo has no schedule, release publication or deployment workflow.

This software comes with **NO WARRANTY**. You may redistribute and modify it under the GNU General Public
License version 3 or any later version; see [LICENSE](../LICENSE).
The upstream README asks users not to sell the project and to contact its author before use in published
media. This demo does not sell anything or publish promotional media. It is not endorsed by upstream or Homarr.
