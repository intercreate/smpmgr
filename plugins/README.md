# Plugins

If you would like to use a custom SMP group that cannot be upstreamed to
[smp](https://github.com/jphutchins/smp)/[smpclient](https://github.com/intercreate/smpclient)/smpmgr,
you can instead create a plugin for your group.

> [!CAUTION]
> Do not use plugin path(s) or file(s) from an untrusted source. It is your
> responsibility to inspect the Python file(s) that will be executed upon import
> and usage of smpmgr.
>
> If you are providing your plugins to a third-party, provide careful
> instructions about how to load your plugins in order to avoid accidental
> execution of malicious code.
>
> Always place plugin group(s) in their own folders without unrelated files.

## Usage

Provide 1 or more absolute or relative paths to a folder containing the plugins
that you would like to load, using the `--plugin-path` argument:
```
smpmgr --plugin-path=plugins --help
smpmgr --plugin-path=plugins example --help
```

To load plugins from multiple paths, reuse the `--plugin-path` argument:
```
smpmgr --plugin-path=plugins --plugin-path=plugins/another --help
smpmgr --plugin-path=plugins --plugin-path=plugins/another another --help
```

## Requirements

1. The Python source file(s) must end in `_group.py` in order to be discovered
   by `smpmgr`.
2. There can only be one group per file.
3. `smpmgr` searches for the custom group CLI implementation by looking for a
   `typer.Typer` named `app`.

## Examples

Example implementation is provided in this folder. To try these out in your
installation, download this folder and provide it as the plugin path for smpmgr.