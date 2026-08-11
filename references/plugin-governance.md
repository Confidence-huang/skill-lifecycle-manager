# Plugin Governance

`skill plugins` observes Codex plugin inventory through the documented machine-readable CLI. It is
a zero-write evidence command, not a plugin repair or runtime test.

## Command

```text
skill plugins
skill plugins --available
skill plugins --codex-command /exact/path/to/codex
```

Use `--codex-command` when several Codex installations exist. This is especially important on
Windows: a global CLI and the CLI associated with the current Desktop package can expose different
marketplace or plugin state. The command records the resolved executable and its reported version.

The adapter invokes only:

```text
codex --version
codex plugin list --json
codex plugin list --available --json
codex plugin marketplace list --json
```

It never invokes `add`, `remove`, `upgrade`, connector login, plugin refresh, enable/disable actions,
Computer Use, or a runtime tool.

## Evidence layers

| Layer | v5.3 evidence | Meaning |
|---|---|---|
| CLI identity | observed | Exact executable selection and version text returned by Codex. |
| Installation metadata | observed | Plugin ID, name, marketplace, version, installed/enabled state, and policies. |
| Local source topology | observed | A declared local source exists and is lexically below its observed marketplace root. Plugin contents and links are not traversed. |
| Connector authentication | `UNKNOWN` or `NOT_CONFIGURED` | `authPolicy` describes setup policy; it does not prove a live authorized connection. |
| Runtime injection | `NOT_RUN` | Installed/enabled metadata does not prove that a new task receives skills, MCP tools, browser controls, or Computer Use. |
| Representative behavior | `NOT_RUN` | No task, connector action, browser action, or desktop action is executed. |

The command-level `status: PASS` means the requested CLI observations completed and their JSON
contracts were valid. Each plugin has a separate `evidenceStatus`; missing paths, absent
marketplaces, incomplete required fields, or topology drift produce `UNKNOWN` with exact issues.

## Why plugins stay outside the Skill Registry

A plugin can package Skills, connectors/MCP servers, browser extensions, hooks, scheduled-task
templates, or several of these together. Its availability, connector authorization, source-system
permissions, and active-host runtime policy are separate controls. Folding a plugin row into the
Skill Registry would incorrectly equate a package with each capability it may contribute.

v5.3 therefore adds a separate observation module and result document. Future plugin mutation work
must define preview, exact target identity, approval, rollback, cache ownership, connector effects,
and post-restart runtime probes before any `--apply` command is introduced.

## Official contract references

- [Codex CLI plugin commands](https://learn.chatgpt.com/docs/developer-commands?surface=cli#cli-codex-plugin)
- [Plugins](https://learn.chatgpt.com/docs/plugins)
- [Plugin architecture](https://developers.openai.com/plugins/concepts/plugins)
- [Package your plugin](https://developers.openai.com/plugins/build/plugins)
- [Computer Use](https://learn.chatgpt.com/docs/computer-use)
