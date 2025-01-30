# Simple Management Protocol (SMP) Manager

`smpmgr` is a CLI application for interacting with device firmware over a
**serial (UART or USB)**, **Bluetooth (BLE)**, or **UDP**, connection.  It can be used as a
reference implementation of the [smp](https://github.com/JPHutchins/smp) and
[smpclient](https://github.com/intercreate/smpclient) libraries when developing your own SMP
application.

The SMP specification can be found
[here](https://docs.zephyrproject.org/latest/services/device_mgmt/smp_protocol.html).

## Install

You can download a portable executable for Windows or Linux from the
[latest releases page](https://github.com/intercreate/smpmgr/releases/latest).

`smpmgr` is also [distributed by PyPI](https://pypi.org/project/smpmgr/).  If you already have a
Python environment setup, then it is **strongly recommended** to install `smpmgr` with
[pipx](https://github.com/pypa/pipx) instead of `pip`.

## Development Quickstart

> Assumes that you've already [setup your development environment](#development-environment-setup).

1. activate [envr](https://github.com/JPhutchins/envr), the environment manager for **bash**, **zsh**, and **PS**:
   ```
   . ./envr.ps1
   ```
2. run `poetry install` when pulling in new changes
3. run `lint` after making changes
4. run `test` after making changes
5. run `build` to build a portable executable bundle at `dist/smpmgr-<git tag>`.  Refer to `portably.py` for details.
6. add library dependencies with `poetry`:
   ```
   poetry add <my_new_dependency>
   ```
7. add test or other development dependencies using [poetry groups](https://python-poetry.org/docs/managing-dependencies#dependency-groups):
   ```
   poetry add -G dev <my_dev_dependency>
   ```

## Development Environment Setup

### Install Dependencies

- poetry==1.8.5: https://python-poetry.org/docs/#installation

### Create the venv

```
poetry install
```

The `venv` should be installed to `.venv`.

### Activate envr

> [envr](https://github.com/JPhutchins/envr) supports **bash**, **zsh**, and **PS** in Linux, MacOS, and Windows.  If you are using an unsupported shell, you can activate the `.venv` environment manually, use `poetry run` and `poetry shell`, and refer to `envr-default` for useful aliases.

```
. ./envr.ps1
```

### Verify Your Setup

To verify the installation, make sure that all of the tests are passing using these envr aliases:

```
lint
test
```

### Enable the githooks

> The pre-commit hook will run the linters but not the unit tests.

```
git config core.hooksPath .githooks
```
