# Diagnosing MCP process leaks on macOS

ZCode can use user-scoped `stdio` MCP servers in every workspace. When a
workspace or session is created repeatedly, each session may start another MCP
process tree. If old trees are not terminated, process count, compressed memory,
and swap can grow until macOS becomes unresponsive.

This guide provides a privacy-preserving way to collect evidence for that
failure mode. It complements the reports in issues
[#25](https://github.com/zai-org/feedback/issues/25) and
[#104](https://github.com/zai-org/feedback/issues/104).

## Collect a sanitized report

Run the collector on the affected Mac before restarting ZCode, if the machine is
still responsive:

```bash
python3 tools/collect_macos_mcp_leak_debug.py > zcode-mcp-leak-debug.md
```

Review the generated Markdown file before sharing it. The collector reports:

- macOS, hardware model, physical memory, and ZCode version;
- memory pressure, compressed memory, and swap usage;
- process counts and ZCode descendant RSS using process names only;
- configured/enabled MCP counts without server names or configuration values;
- an anonymized `session/create` timeline;
- allow-listed summary fields from the latest Jetsam and kernel panic reports.

Its allow-listed output schema does **not** include command arguments,
environment variables, headers, tokens, API URLs, workspace paths, usernames,
hostnames, IP addresses, session IDs, conversation content, UUIDs, PIDs, or raw
core files. Unknown transport values and malformed count fields are reduced to
fixed labels rather than copied into the report.

Raw `.panic`, Jetsam, and kernel core files can contain sensitive information.
Do not attach them publicly without reviewing them first.

## Signals that indicate a process leak

The following combination is stronger evidence than a single high-memory
renderer process:

1. The same anonymized workspace has repeated `session/create` entries.
2. Each create starts the full user-scoped MCP set.
3. `zcode-cli` has dozens of direct children and a much larger descendant tree.
4. Closing a session or ZCode does not return Node, npm, Python, or uv processes
   to their baseline within 60 seconds.
5. Jetsam shows an active ZCode group plus a ZCode-helper group without a live
   ZCode root.
6. Process count, compressed memory, or swap continues to rise while the app is
   idle.

## Safe temporary mitigation

1. Save work and quit ZCode normally.
2. Capture the ZCode root and descendants before force-terminating anything.
3. If cleanup is required, terminate only the captured tree and re-check process
   identity before sending a signal. Never use broad commands such as
   `killall node`, `pkill python`, or `pkill -f mcp`.
4. Back up `~/.zcode/cli/config.json` with permissions restricted to the current
   user.
5. Disable user-scoped `stdio` MCP servers while preserving their definitions.
6. Re-enable only the servers needed by one workspace, in small batches.
7. Restart one workspace and verify that process count returns to baseline after
   each session closes.

Where possible, prefer workspace-scoped MCP configuration over making every
local `stdio` server available to every workspace.

## Product-side fix proposal

The durable fix belongs in ZCode's session and MCP lifecycle implementation:

- Make `session/create` idempotent for a workspace/session identity.
- Give every MCP process tree an explicit owner and lifecycle state.
- Reuse one healthy MCP instance per intended scope instead of spawning a new
  set on every reconnect.
- Start local MCP trees in an isolated process group.
- On session close, replacement, app quit, and startup reconciliation, send a
  graceful shutdown and then terminate the entire owned process group after a
  bounded timeout.
- Give MCP children a parent-death signal, pipe, or heartbeat so they self-exit
  if the supervisor disappears.
- Reconcile and terminate orphaned MCP groups before restoring workspaces after
  a crash.
- Record spawn/stop events with an owner ID and process count, without logging
  credentials.

## Suggested regression tests

1. Call `session/create` twice for the same workspace and assert that MCP process
   count does not increase the second time.
2. Create and close ten sessions and assert that the process count returns to
   baseline (within `+5` processes or `+10%`) after every cycle.
3. Crash the session supervisor and assert that all owned MCP children exit
   within 60 seconds.
4. Restore multiple workspaces after a simulated app crash and assert that no
   orphan group survives reconciliation.
5. Run a two-hour soak test and assert bounded RSS, compressed memory, and swap.

For a 24 GiB Mac, stop the test if one idle ZCode workspace exceeds 6 GiB,
creates more than 100 new processes in ten minutes, or keeps memory pressure in
yellow/red for more than 30 seconds.
