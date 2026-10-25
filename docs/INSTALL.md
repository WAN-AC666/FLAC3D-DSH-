# Install the plugin on another machine

Three routes, from easiest to most manual. All of them end with the agent having
`mcp__flac3d__flac3d_run`, `mcp__flac3d__flac3d_info` and `mcp__flac3d__flac3d_outputs`.

Requirements in every case:

- Windows with **FLAC3D 7.0** installed and licensed
- **DeepSeek Harness** with a profile (`%USERPROFILE%\.dsh\profiles\<name>`)
- A Python 3 interpreter. The Python bundled with FLAC3D
  (`<FLAC3D_HOME>\exe64\python36\python.exe`) is enough — the server is 3.6-compatible.

## Route A — ask your DSH agent (bundle install)

```text
Clone https://github.com/WAN-AC666/FLAC3D-DSH- to D:\tools\flac3d-dsh-plugin,
then install the bundle from plugin/ with plugin_manager install_bundle.
```

Notes for the agent (and for you):

- The bundle is the `plugin/` subdirectory, not the repository root.
- `plugin/cordis.patch.yml` contains two placeholders, `__PYTHON__` and
  `__MCP_SERVER__`. They must be replaced by an absolute Python path and the
  absolute path of `mcp_flac3d.py` **before** installing, otherwise the MCP
  client cannot start the server.
- `flac3d/runner.py` must sit next to `mcp_flac3d.py`'s parent directory
  (`plugin/../flac3d/runner.py`), or `FLAC3D_RUNNER` must point at it.

Because of those paths, Route B is usually less error-prone on Windows.

## Route B — install script (recommended)

```powershell
git clone https://github.com/WAN-AC666/FLAC3D-DSH-.git
cd FLAC3D-DSH-
.\install.ps1 -DryRun     # show what will happen
.\install.ps1             # copy to %LOCALAPPDATA%\dsh-flac3d, render patch, link, register
```

What it does:

1. copies `plugin/` + `flac3d/runner.py` to `%LOCALAPPDATA%\dsh-flac3d`
2. renders `cordis.patch.yml` with absolute paths
3. creates the junction `%USERPROFILE%\.dsh\profiles\<profile>\node_modules\@local\flac3d`
4. adds `@local/flac3d` to `dsh.profile.bundles` (backup: `package.json.bak-flac3d`)

Useful switches: `-ProfileDir`, `-InstallDir`, `-Flac3DHome`, `-Python`, `-Uninstall`,
`-RemoveFiles`.

Afterwards restart the harness if the tools do not appear, then:

```powershell
.\verify.ps1
```

## Route C — manual

```powershell
$plugin = "D:\tools\flac3d-dsh-plugin"
$install = "$env:LOCALAPPDATA\dsh-flac3d"
Copy-Item "$plugin\plugin\*" $install -Recurse
New-Item -ItemType Directory -Force "$install\flac3d" | Out-Null
Copy-Item "$plugin\flac3d\runner.py" "$install\flac3d\runner.py"
# edit $install\cordis.patch.yml: replace __PYTHON__ and __MCP_SERVER__
# add @local/flac3d to dsh.profile.bundles in the profile package.json
mklink /J "%USERPROFILE%\.dsh\profiles\desktop\node_modules\@local\flac3d" "%install%"
```

## Verifying

| Check | Expected |
| --- | --- |
| `.\verify.ps1` | every line `[ok]`, example solved in a few seconds |
| agent calls `flac3d_info` | `runner_present: true`, `present` all true |
| agent calls `flac3d_run` on `examples/cube_gravity.py` | `status: ok`, `out/gridpoint_disp.csv` created |

If the tools are missing, inspect the profile:

```powershell
Get-Content "$env:USERPROFILE\.dsh\profiles\desktop\package.json"
Get-Item "$env:USERPROFILE\.dsh\profiles\desktop\node_modules\@local\flac3d"
```

## Environment variables

| Variable | Purpose |
| --- | --- |
| `FLAC3D_HOME` | installation root when auto-detection fails, e.g. `D:\Itasca\FLAC3D700` |
| `FLAC3D_CONSOLE` / `FLAC3D_GUI` | override the executables |
| `FLAC3D_PYTHON` | Python shipped with FLAC3D |
| `FLAC3D_RUNNER` | absolute path of `runner.py` (MCP server looks next to `plugin/` by default) |

## Updating / uninstalling

```powershell
git pull
.\install.ps1                 # re-renders the patch and refreshes the copy
.\install.ps1 -Uninstall      # remove link + bundle entry
.\install.ps1 -Uninstall -RemoveFiles   # also delete %LOCALAPPDATA%\dsh-flac3d
```
