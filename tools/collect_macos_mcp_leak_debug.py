#!/usr/bin/env python3
"""Collect a privacy-preserving ZCode MCP process-leak report on macOS.

The report intentionally excludes command arguments, environment variables,
absolute paths, network addresses, UUIDs, session IDs, conversation content,
and raw crash/core files. It uses only the Python standard library.
"""

import collections
import datetime as dt
import ipaddress
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys


HOME = str(Path.home())
UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
HEX_RE = re.compile(r"\b0x[0-9a-fA-F]{8,}\b")
LONG_TOKEN_RE = re.compile(r"\b[A-Za-z0-9_\-]{48,}\b")
ABSOLUTE_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:[^\s`|]+)")
IPV6_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:[0-9a-fA-F]{0,4}:){2,}"
    r"[0-9a-fA-F]{0,4}(?:%[A-Za-z0-9_.-]+)?(?![A-Za-z0-9])"
)
SAFE_TRANSPORTS = {"stdio", "sse", "http", "streamable-http", "websocket"}


def redact_ipv6(match):
    candidate = match.group(0)
    address = candidate.split("%", 1)[0]
    try:
        ipaddress.ip_address(address)
    except ValueError:
        return candidate
    return "<ip>"


def redact(value):
    text = str(value)
    if HOME:
        text = text.replace(HOME, "<home>")
    text = UUID_RE.sub("<uuid>", text)
    text = IPV4_RE.sub("<ip>", text)
    text = IPV6_RE.sub(redact_ipv6, text)
    text = HEX_RE.sub("<hex>", text)
    text = LONG_TOKEN_RE.sub("<redacted-token>", text)
    text = ABSOLUTE_PATH_RE.sub("<absolute-path>", text)
    return text


class Report:
    def __init__(self):
        self.lines = []

    def add(self, value=""):
        self.lines.append(redact(value))

    def section(self, title):
        self.add()
        self.add("## " + title)

    def render(self):
        return "\n".join(self.lines).rstrip() + "\n"


def run(args):
    try:
        result = subprocess.run(
            args,
            check=False,
            text=True,
            capture_output=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip()


def plist_value(path, key):
    try:
        with open(path, "rb") as handle:
            return plistlib.load(handle).get(key, "unknown")
    except (OSError, plistlib.InvalidFileException):
        return "unavailable"


def gib(value):
    return float(value) / (1024.0 ** 3)


def system_summary(report):
    report.section("Environment")
    model = run(["sysctl", "-n", "hw.model"]) or "unavailable"
    memory = run(["sysctl", "-n", "hw.memsize"])
    version = run(["sw_vers", "-productVersion"]) or "unavailable"
    build = run(["sw_vers", "-buildVersion"]) or "unavailable"
    zcode_version = plist_value(
        "/Applications/ZCode.app/Contents/Info.plist",
        "CFBundleShortVersionString",
    )
    report.add("| Field | Value |")
    report.add("|---|---|")
    report.add("| Hardware model | `{}` |".format(model))
    if memory.isdigit():
        report.add("| Physical memory | `{:.2f} GiB` |".format(gib(int(memory))))
    else:
        report.add("| Physical memory | `unavailable` |")
    report.add("| macOS | `{}` (`{}`) |".format(version, build))
    report.add("| ZCode | `{}` |".format(zcode_version))
    report.add("| Collected at | `{}` |".format(dt.datetime.now().astimezone().isoformat(timespec="seconds")))


def memory_summary(report):
    report.section("Current memory pressure")
    swap = run(["sysctl", "vm.swapusage"]) or "unavailable"
    pressure = run(["memory_pressure", "-Q"]) or "unavailable"
    top = run(["top", "-l", "1", "-n", "0"])
    selected = []
    for line in top.splitlines():
        if line.startswith("PhysMem:") or line.startswith("VM:") or line.startswith("Processes:"):
            selected.append(line)
    report.add("```text")
    report.add(swap)
    for line in pressure.splitlines():
        if "System-wide memory free percentage" in line:
            report.add(line)
    for line in selected:
        report.add(line)
    report.add("```")


def process_snapshot():
    output = run(["ps", "-axo", "pid=,ppid=,rss=,etime=,ucomm="])
    processes = {}
    children = collections.defaultdict(list)
    for line in output.splitlines():
        parts = line.strip().split(None, 4)
        if len(parts) != 5:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
            rss_kib = int(parts[2])
        except ValueError:
            continue
        processes[pid] = {
            "ppid": ppid,
            "rss_kib": rss_kib,
            "etime": parts[3],
            "name": parts[4].strip(),
        }
        children[ppid].append(pid)
    return processes, children


def descendants(root, children):
    seen = set()
    stack = list(children.get(root, []))
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        stack.extend(children.get(pid, []))
    return seen


def process_category(name):
    lowered = name.lower()
    if lowered.startswith("zcode helper"):
        return "ZCode Helper"
    if lowered == "zcode-cli":
        return "zcode-cli"
    if lowered.startswith("zcode-host"):
        return "zcode-host"
    if lowered == "node":
        return "node"
    if lowered in ("npm", "npx"):
        return lowered
    if lowered.startswith("python"):
        return "python"
    if lowered in ("uv", "uvx"):
        return lowered
    if lowered == "codex":
        return "codex"
    if lowered.startswith("chatgpt"):
        return "ChatGPT"
    return "other"


def process_summary(report):
    report.section("Process summary (names only; no command arguments)")
    processes, children = process_snapshot()
    counts = collections.Counter(process_category(item["name"]) for item in processes.values())
    interesting = ("ZCode Helper", "zcode-cli", "zcode-host", "node", "npm", "npx", "python", "uv", "uvx", "codex", "ChatGPT")
    report.add("- Total processes: `{}`".format(len(processes)))
    report.add("- Selected process counts: `{}`".format(
        ", ".join("{}={}".format(name, counts.get(name, 0)) for name in interesting)
    ))

    roots = []
    for pid, item in processes.items():
        if item["name"] in ("ZCode", "zcode-cli", "ChatGPT", "codex"):
            roots.append((pid, item))

    report.add()
    report.add("| Root name | Elapsed | Direct children | Descendants | Descendant RSS | Top descendant types |")
    report.add("|---|---:|---:|---:|---:|---|")
    for pid, item in sorted(roots, key=lambda row: (row[1]["name"], row[0])):
        tree = descendants(pid, children)
        if not tree and item["name"] not in ("ZCode", "ChatGPT"):
            continue
        rss_kib = sum(processes[child]["rss_kib"] for child in tree if child in processes)
        tree_counts = collections.Counter(
            process_category(processes[child]["name"])
            for child in tree
            if child in processes
        )
        top_types = ", ".join(
            "{}x{}".format(name, count)
            for name, count in tree_counts.most_common(8)
            if name != "other"
        ) or "none"
        report.add(
            "| `{}` | `{}` | {} | {} | `{:.2f} GiB` | {} |".format(
                item["name"],
                item["etime"],
                len(children.get(pid, [])),
                len(tree),
                rss_kib / (1024.0 ** 2),
                top_types,
            )
        )


def zcode_config_summary(report):
    report.section("ZCode MCP configuration summary")
    path = Path.home() / ".zcode" / "cli" / "config.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        servers = data.get("mcp", {}).get("servers", {})
    except (OSError, ValueError, AttributeError):
        report.add("Configuration could not be parsed.")
        return
    if not isinstance(servers, dict):
        report.add("Configuration does not contain a valid MCP server map.")
        return
    valid = [value for value in servers.values() if isinstance(value, dict)]
    enabled = [value for value in valid if value.get("enabled", True) is True]
    transports = collections.Counter()
    for value in valid:
        raw_transport = value.get("type", "unspecified")
        transport = raw_transport.lower() if isinstance(raw_transport, str) else "other"
        transports[transport if transport in SAFE_TRANSPORTS else "other"] += 1
    report.add("- Configured MCP servers: `{}`".format(len(servers)))
    report.add("- Enabled MCP servers: `{}`".format(len(enabled)))
    if len(valid) != len(servers):
        report.add("- Invalid server entries: `{}`".format(len(servers) - len(valid)))
    report.add("- Transport counts: `{}`".format(dict(sorted(transports.items()))))
    report.add("- Server names, commands, arguments, environment variables, and credentials are intentionally omitted.")


def session_create_summary(report):
    report.section("Sanitized session/create timeline")
    log_path = Path.home() / ".zcode" / "v2" / "logs" / (dt.date.today().isoformat() + ".log")
    workspace_labels = {}
    events = []
    try:
        lines = log_path.open("r", encoding="utf-8", errors="replace")
    except OSError:
        report.add("No readable ZCode log was found for today.")
        return
    with lines:
        for line in lines:
            if "session/create" not in line or '"hasInitialModel"' not in line:
                continue
            start = line.find("{")
            if start < 0:
                continue
            try:
                payload = json.loads(line[start:])
            except ValueError:
                continue
            workspace = payload.get("workspacePath") or payload.get("workspaceKey") or "unknown"
            if workspace not in workspace_labels:
                workspace_labels[workspace] = "workspace-{}".format(len(workspace_labels) + 1)
            timestamp_match = re.search(r"\[(\d{4}-\d{2}-\d{2} [0-9:.]+)\]", line)
            events.append(
                (
                    timestamp_match.group(1) if timestamp_match else "unknown",
                    workspace_labels[workspace],
                    (
                        payload.get("mcpServerCount")
                        if isinstance(payload.get("mcpServerCount"), int)
                        and not isinstance(payload.get("mcpServerCount"), bool)
                        else "unknown"
                    ),
                )
            )
    report.add("- Session-create requests today: `{}` across `{}` anonymized workspaces.".format(
        len(events), len(workspace_labels)
    ))
    report.add()
    report.add("| Timestamp | Workspace label | MCP server count |")
    report.add("|---|---|---:|")
    for timestamp, workspace, count in events[-30:]:
        report.add("| `{}` | `{}` | {} |".format(timestamp, workspace, count))
    report.add()
    report.add("Workspace paths, model/provider details, URLs, trace IDs, and session IDs are omitted.")


def split_json_report(path):
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        handle.readline()
        return json.load(handle)


def report_candidates(pattern):
    root = Path("/Library/Logs/DiagnosticReports")
    candidates = []
    try:
        candidates.extend(root.glob(pattern))
        candidates.extend((root / "Retired").glob(pattern))
    except OSError:
        return []
    readable = []
    for path in candidates:
        try:
            readable.append((path.stat().st_mtime, path))
        except OSError:
            continue
    return [path for _mtime, path in sorted(readable, reverse=True)]


def latest_report(pattern):
    candidates = report_candidates(pattern)
    return candidates[0] if candidates else None


def jetsam_summary(report):
    path = latest_report("JetsamEvent*.ips")
    if path is None:
        return
    try:
        data = split_json_report(path)
    except (OSError, ValueError):
        return
    report.section("Latest Jetsam snapshot (sanitized)")
    try:
        page_size = int(data.get("memoryStatus", {}).get("pageSize", 16384))
    except (TypeError, ValueError):
        page_size = 16384
    processes = data.get("processes", [])
    active = [item for item in processes if "active" in item.get("states", [])]
    report.add("- Snapshot time: `{}`".format(data.get("date", "unknown")))
    report.add("- Active process records: `{}`".format(len(active)))
    largest = process_category(data.get("largestProcess", ""))
    if largest == "other":
        largest = "other (name omitted)"
    report.add("- Largest process class: `{}`".format(largest))

    aggregates = collections.defaultdict(lambda: [0, 0])
    for item in active:
        name = item.get("name", "")
        label = None
        if name == "node":
            label = "node"
        elif name.startswith("python"):
            label = "python"
        elif name in ("uv", "uvx", "npm", "npx", "codex", "ChatGPT", "ZCode"):
            label = name
        elif name.startswith("ZCode Helper"):
            label = "ZCode Helper"
        if label:
            aggregates[label][0] += 1
            try:
                aggregates[label][1] += int(item.get("rpages") or 0)
            except (TypeError, ValueError):
                pass

    report.add()
    report.add("| Process class | Count | Aggregate footprint |")
    report.add("|---|---:|---:|")
    for name, (count, pages) in sorted(aggregates.items(), key=lambda row: row[1][1], reverse=True):
        report.add("| `{}` | {} | `{:.2f} GiB` |".format(name, count, gib(pages * page_size)))

    coalitions = collections.defaultdict(list)
    for item in active:
        coalitions[item.get("coalition")].append(item)
    app_groups = []
    for members in coalitions.values():
        names = [item.get("name", "") for item in members]
        label = None
        if "ZCode" in names:
            label = "ZCode current group"
        elif any(name.startswith("ZCode Helper") for name in names):
            label = "ZCode orphan candidate"
        elif "ChatGPT" in names:
            label = "ChatGPT/Codex group"
        if label:
            pages = 0
            for item in members:
                try:
                    pages += int(item.get("rpages") or 0)
                except (TypeError, ValueError):
                    pass
            app_groups.append((label, len(members), pages))
    if app_groups:
        report.add()
        report.add("| Anonymized app group | Active processes | Aggregate footprint |")
        report.add("|---|---:|---:|")
        for label, count, pages in sorted(app_groups, key=lambda row: row[2], reverse=True):
            report.add("| {} | {} | `{:.2f} GiB` |".format(label, count, gib(pages * page_size)))


def panic_summary(report):
    data = None
    for path in report_candidates("*.panic"):
        try:
            candidate = split_json_report(path)
        except (OSError, ValueError):
            continue
        if candidate.get("panicString"):
            data = candidate
            break
    if data is None:
        return
    panic = data.get("panicString", "")
    watchdog = re.search(
        r"watchdog timeout: no checkins from watchdogd in \d+ seconds",
        panic,
    )
    compressor = re.search(
        r"Compressor Info: \d+% of compressed pages limit \([A-Z]+\) and "
        r"\d+% of segments limit \([A-Z]+\) with \d+ swapfiles and "
        r"[A-Z]+ swap space",
        panic,
    )
    calendar = re.search(r"Calendar:\s+0x([0-9a-fA-F]+)", panic)
    report.section("Latest kernel panic (sanitized)")
    if calendar:
        try:
            timestamp = dt.datetime.fromtimestamp(int(calendar.group(1), 16)).astimezone()
            report.add("- Panic time: `{}`".format(timestamp.isoformat(timespec="seconds")))
        except (OverflowError, OSError, ValueError):
            pass
    if watchdog:
        report.add("- `{}`".format(watchdog.group(0)))
    if compressor:
        report.add("- `{}`".format(compressor.group(0)))
    report.add("- Kernel addresses, UUIDs, incident IDs, crash reporter keys, and raw core data are omitted.")


def privacy_note(report):
    report.section("Privacy boundary")
    report.add("This report does not contain:")
    report.add("- usernames, hostnames, IP addresses, or absolute home/workspace paths;")
    report.add("- MCP names, commands, arguments, environment variables, headers, tokens, or API URLs;")
    report.add("- conversation titles/content, session IDs, trace IDs, UUIDs, PIDs, or raw crash/core data.")


def main():
    if sys.platform != "darwin":
        print("This collector is intended for macOS.", file=sys.stderr)
        return 2
    report = Report()
    report.add("# Sanitized ZCode MCP process-leak debug report")
    report.add()
    report.add("Generated locally. Review the output before posting it publicly.")
    system_summary(report)
    memory_summary(report)
    process_summary(report)
    zcode_config_summary(report)
    session_create_summary(report)
    jetsam_summary(report)
    panic_summary(report)
    privacy_note(report)
    sys.stdout.write(report.render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
