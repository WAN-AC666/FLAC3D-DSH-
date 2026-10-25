# FLAC3D 7.0 plugin for DeepSeek Harness

Exposes [Itasca FLAC3D 7.0](https://www.itascacg.com/software/flac3d) as agent tools in
DeepSeek Harness: the model can write a FLAC3D script, run it headlessly, read the
console log and collect the output files — without leaving the chat.

[中文说明](#中文说明)

## Tools

| Tool | Purpose |
| --- | --- |
| `mcp__flac3d__flac3d_run` | Run a `.py` / `.f3dat` script, return `status`, duration, log path and an error excerpt |
| `mcp__flac3d__flac3d_info` | Report the detected installation, executables and runner |
| `mcp__flac3d__flac3d_outputs` | List the files a run produced |

`flac3d_run` takes `script`, and optionally `gui`, `timeout_sec` and `pre`.

## Requirements

- Windows with FLAC3D 7.0 installed and licensed (auto-detected through the registry,
  or set `FLAC3D_HOME`)
- DeepSeek Harness with a profile at `%USERPROFILE%\.dsh\profiles\<name>`
- Python 3. The interpreter bundled with FLAC3D
  (`<FLAC3D_HOME>\exe64\python36\python.exe`) is enough; no extra packages are needed.

## Quick start

```powershell
git clone https://github.com/WAN-AC666/FLAC3D-DSH-.git
cd FLAC3D-DSH-
.\install.ps1 -DryRun     # preview
.\install.ps1             # copy, render patch, link, register bundle
.\verify.ps1              # solves the example model end to end
```

Then restart the harness if `mcp__flac3d__*` tools are not there yet. Other machines,
other profiles and manual installs: [docs/INSTALL.md](docs/INSTALL.md).

`install.ps1` copies the package to `%LOCALAPPDATA%\dsh-flac3d`, renders
`cordis.patch.yml` with absolute paths, links it into the profile's `node_modules`
and registers `@local/flac3d` in `dsh.profile.bundles`. Restart the harness if the
`mcp__flac3d__*` tools do not appear; the profile manifest is backed up as
`package.json.bak-flac3d`.

Manual equivalent:

1. `mklink /J %USERPROFILE%\.dsh\profiles\desktop\node_modules\@local\flac3d <install dir>`
2. replace `__PYTHON__` / `__MCP_SERVER__` in `cordis.patch.yml`
3. append `@local/flac3d` to `dsh.profile.bundles` in the profile `package.json`

## Usage

```python
flac3d_run(script="examples/cube_gravity.py", timeout_sec=600)
flac3d_run(script="examples/cube_gravity.py", gui=True)      # when the script exports plots
flac3d_run(script="model.py", pre=["model restore 'out/cube'"])   # restore before Python starts
```

`examples/cube_gravity.py` builds an 8 m Mohr-Coulomb cube under gravity, solves it and
writes `out/gridpoint_disp.csv` + `out/cube.sav`.

## How it works

- **Console build ignores stdin.** `flac3d700_console.exe` only executes commands from
  its argument list, then waits at `flac3d>`. The runner writes a two-line wrapper
  (`program call '<script>'` + `program exit`) and launches the console with it.
  Without the trailing `program exit` the process never terminates.
- **Plots need the GUI build.** `plot` commands answer
  `Warning! PLOT command not supported in console interface`, so `gui=true` switches to
  `flac3d700_gui.exe` (slower, and it flashes a window).
- **Non-ASCII paths break argument passing.** FLAC3D converts command-line arguments with
  the ANSI code page, so `G:\项目\model.py` arrives as `G:\????\model.py`. The runner
  creates an ASCII junction under `%TEMP%\flac3d-ascii\<hash>` and hands that path to
  FLAC3D; relative paths inside scripts then resolve to the real directory.
- **Errors do not terminate the process.** A failing command prints `*** ...` and returns
  to the prompt, so the runner watches stdout and kills the process on the first `***`
  line (excluding warnings), reporting the surrounding 24 lines.
- **`model new` / `model restore` reset the embedded Python namespace** (`it` becomes
  undefined, and the GUI shows `Python error: "name 'it' is not defined"`). Pass those
  commands through `pre` so they run before the Python script starts.

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| `FLAC3D not found` | set `FLAC3D_HOME`, e.g. `C:\Program Files\Itasca\FLAC3D700` |
| tools missing in the harness | check the junction and `dsh.profile.bundles`, then restart |
| `Python error: "name 'it' is not defined"` | `model new`/`model restore` inside Python; move them to `pre` |
| run ends with `timeout` | script never reached `program exit`, or the model is still cycling; raise `timeout_sec` |
| `plot ... not supported in console interface` | call with `gui=true` |
| `*** Error opening ...????...` | non-ASCII path; run through `flac3d_run` (it creates the junction) or use ASCII directories |

## Notes

- The runner is stdlib-only Python 3 and executes scripts with the Python bundled with
  FLAC3D (`<home>\exe64\python36\python.exe`), so `itasca` and `numpy` are available.
- One run = one FLAC3D process. Concurrent runs need a license that allows them.
- `toolCallTimeoutMs` is set to 900 s in the bundle patch; lower it if you prefer faster
  failures, raise it for large models.

## 中文说明

把本机 FLAC3D 7.0 接成 DSH 插件：Agent 可以直接写脚本、无界面跑模型、读日志、收结果文件。

- **工具**：`flac3d_run`（跑 `.py`/`.f3dat`，`gui=true` 出图）、`flac3d_info`（查环境）、`flac3d_outputs`（列产物）。
- **安装**：`.\install.ps1`（先 `-DryRun` 预览）。它会复制到 `%LOCALAPPDATA%\dsh-flac3d`、
  生成绝对路径的 `cordis.patch.yml`、在 profile 的 `node_modules` 下建联接并注册 bundle。
- **要点**：控制台版只认命令行参数、不读 stdin，所以运行器会补一个 `program call` + `program exit`
  的包装文件；`plot` 只有 GUI 版支持；中文路径会被 ANSI 转换破坏，运行器自动建 ASCII 联接绕开；
  脚本里不要写 `model new` / `model restore`（会清空 `it` 命名空间），改用 `pre` 传入。

## License

MIT — see [LICENSE](LICENSE). FLAC3D is commercial software of Itasca Consulting Group;
this project only automates a locally licensed installation and ships no Itasca code.
