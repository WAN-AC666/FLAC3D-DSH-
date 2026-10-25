# Changelog

## 1.0.0 — 2026-10-25

First public release.

### Added

- MCP server (`plugin/mcp_flac3d.py`) exposing `flac3d_run`, `flac3d_info` and
  `flac3d_outputs` over stdio, compatible with Python 3.6+ (FLAC3D's bundled
  interpreter is enough).
- Headless runner (`flac3d/runner.py`):
  - console build with a generated `program call` + `program exit` wrapper
  - GUI build for plot export (`gui=True`)
  - automatic ASCII junction for non-ASCII script paths
  - `***` error detection with context, wall-clock timeout, log capture
  - FLAC3D discovery through `FLAC3D_HOME`, the registry, or common paths
- Cordis bundle manifest, localized metadata (en/zh) and icon.
- `install.ps1` (copy → render patch → junction → register bundle, `-DryRun`,
  `-Uninstall`) and `verify.ps1` (static checks + example solve).
- Example model `examples/cube_gravity.py` and MCP protocol smoke test.
- Documentation: `README.md`, `docs/INSTALL.md` (three install routes).

### Fixed

- Runner path resolution now works both from the repository layout
  (`plugin/../flac3d`) and from an installed copy (`<pkg>/flac3d`).
