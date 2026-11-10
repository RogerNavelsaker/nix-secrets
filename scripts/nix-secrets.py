#!/usr/bin/env python3
"""Safe lifecycle commands for SOPS-encrypted files and recipient rules."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable


class CliError(Exception):
    pass


ROOT = Path(os.environ.get("NIX_SECRETS_ROOT", Path(__file__).resolve().parent.parent)).resolve()
SOPS_CONFIG = ROOT / ".sops.yaml"
AGE_RE = re.compile(r"^age1[023456789acdefghjklmnpqrstuvwxyz]{58}$")
PGP_RE = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
INDEX_RE = re.compile(r'^(?:\["(?:[^"\\]|\\.)*"\]|\[\d+\])+$')
KEY_LINE_RE = re.compile(
    r"^(?P<indent>\s*-\s*&(?P<alias>[a-z][a-z0-9_-]*)\s+)"
    r"(?P<recipient>\S+)(?P<trailing>\s*(?:#.*)?)$"
)
RULE_RE = re.compile(r"^  - path_regex:\s*(?P<regex>.+?)\s*$")
ALIAS_REF_RE = re.compile(
    r"^(?P<indent>\s*-\s*)\*(?P<alias>[a-z][a-z0-9_-]*)"
    r"(?P<trailing>\s*(?:#.*)?)$"
)
TYPE_HEADER_RE = re.compile(r"^(?P<indent>\s*)(?P<group>-\s*)?(?P<kind>age|pgp):\s*$")
ENTITY_PREFIX = {
    "host": "host",
    "agent": "host_agent",
    "vessel": "host_agent",
    "user": "user",
}
RECOVERY_AGE = "host_roger-aio"
RECOVERY_PGP = "user_rona"


def fail(message: str) -> None:
    raise CliError(message)


def repository_root() -> Path:
    if SOPS_CONFIG.is_symlink() or not SOPS_CONFIG.is_file():
        fail("Could not find a regular nix-secrets repository config; run from the repository root.")
    return ROOT


def safe_relative(raw: str) -> tuple[str, Path]:
    if not raw or "\\" in raw or raw.startswith("/") or raw.startswith("~"):
        fail(f"Expected a repository-relative path: {raw}")
    parts = raw.split("/")
    if (
        len(parts) < 2
        or parts[0] not in {"hosts", "users", "agents", "vessels", "clankers", "keys"}
        or any(part in ("", ".", "..") for part in parts)
        or not re.fullmatch(r"secrets\.(yaml|yml|json|env|ini)", parts[-1])
    ):
        fail(f"Expected a repository-relative secrets file path: {raw}")
    root = repository_root()
    candidate = root.joinpath(*parts)
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            fail(f"Refusing symlink path: {raw}")
    try:
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(root)
    except (OSError, ValueError):
        fail(f"Refusing path outside repository: {raw}")
    return "/".join(parts), resolved


def require_encrypted(relative: str, target: Path) -> None:
    if target.is_symlink() or not target.is_file():
        fail(f"Expected a regular secret file: {relative}")
    result = subprocess.run(
        ["sops", "filestatus", str(target)],
        cwd=repository_root(),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        text=True,
    )
    try:
        encrypted = result.returncode == 0 and json.loads(result.stdout).get("encrypted") is True
    except (json.JSONDecodeError, AttributeError):
        encrypted = False
    if not encrypted:
        fail(f"Refusing operation on a file that is not confirmed SOPS-encrypted: {relative}")


def confirm(expected: str) -> bool:
    try:
        supplied = input(f"Type {expected!r} to confirm: ")
    except EOFError:
        return False
    return supplied == expected


def file_add(raw: str) -> None:
    relative, target = safe_relative(raw)
    if Path(relative).suffix.lower() not in (".yaml", ".yml"):
        fail("file add supports YAML only (.yaml or .yml).")
    if target.exists() or target.is_symlink():
        fail(f"Refusing to overwrite existing file: {relative}")
    target.parent.mkdir(parents=True, exist_ok=True)
    relative, target = safe_relative(relative)
    if target.exists() or target.is_symlink():
        fail(f"Refusing to overwrite existing file: {relative}")

    fd, temp_name = tempfile.mkstemp(prefix=".nix-secrets-", suffix=target.suffix, dir=target.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as output:
            result = subprocess.run(
                [
                    "sops",
                    "--encrypt",
                    "--input-type",
                    "yaml",
                    "--output-type",
                    "yaml",
                    "--filename-override",
                    relative,
                    "/dev/stdin",
                ],
                cwd=repository_root(),
                input=b"{}\n",
                stdout=output,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            output.flush()
            if result.returncode:
                fail(f"SOPS encryption failed for {relative}; no file was created.")
            os.fsync(output.fileno())
        os.chmod(temp, 0o600)
        require_encrypted(relative, temp)
        try:
            os.link(temp, target)
        except FileExistsError:
            fail(f"Refusing to overwrite existing file: {relative}")
        print(f"Created encrypted empty secret file: {relative}")
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def file_edit(raw: str) -> None:
    relative, target = safe_relative(raw)
    require_encrypted(relative, target)
    result = subprocess.run(["sops", str(target)], cwd=repository_root(), check=False)
    if result.returncode:
        fail(f"SOPS edit failed for {relative}.")


def file_remove(raw: str) -> None:
    relative, target = safe_relative(raw)
    require_encrypted(relative, target)
    if not confirm(f"REMOVE {relative}"):
        fail("Removal not confirmed; file was left unchanged.")
    target.unlink()
    print(f"Removed local encrypted file: {relative} (Git history is unchanged).")


def validate_index(index: str) -> None:
    if not INDEX_RE.fullmatch(index):
        fail('SOPS index must use bracket notation, e.g. ["api"]["token"].')


def value_exists(target: Path, index: str) -> bool:
    result = subprocess.run(
        ["sops", "--decrypt", "--extract", index, str(target)],
        cwd=repository_root(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
    )
    if result.returncode == 0:
        return True
    if "not found" in result.stderr.lower():
        return False
    fail("SOPS could not inspect the requested entry; check the path and decryption access.")


def read_json_value() -> bytes:
    if sys.stdin.isatty():
        try:
            value = getpass.getpass("Secret value as JSON (input hidden): ")
        except (EOFError, KeyboardInterrupt):
            fail("No secret value supplied.")
        raw = (value + "\n").encode("utf-8")
    else:
        raw = sys.stdin.buffer.read()
    if not raw.strip():
        fail("A JSON value is required; no secret value was supplied.")
    try:
        json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        fail("Secret value must be valid JSON; value was not passed to SOPS.")
    return raw


def entry_mutate(operation: str, raw_file: str, index: str) -> None:
    relative, target = safe_relative(raw_file)
    require_encrypted(relative, target)
    validate_index(index)
    exists = value_exists(target, index)
    if operation == "add" and exists:
        fail("Entry already exists; use entry update.")
    if operation in ("update", "remove") and not exists:
        fail("Entry does not exist; no change was made.")
    if operation == "remove":
        if not confirm(f"REMOVE {relative} {index}"):
            fail("Removal not confirmed; entry was left unchanged.")
        result = subprocess.run(
            ["sops", "unset", str(target), index],
            cwd=repository_root(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        value = read_json_value()
        result = subprocess.run(
            ["sops", "set", "--value-stdin", str(target), index],
            cwd=repository_root(),
            input=value,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    if result.returncode:
        fail(f"SOPS {operation} failed for {relative}; encrypted file was not verified.")
    require_encrypted(relative, target)
    print(f"SOPS entry {operation} completed: {relative} {index}")


def entity_alias(kind: str, name: str) -> str:
    if kind not in ENTITY_PREFIX:
        fail("Entity kind must be host, vessel, user, or agent.")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
        fail("Entity name must contain lowercase letters, digits, and hyphens only.")
    if kind == "host" and name == "roger-aio":
        return RECOVERY_AGE
    return f"{ENTITY_PREFIX[kind]}_{name.replace('-', '_')}"


def default_path_regex(kind: str, name: str) -> str:
    directory = {"host": "hosts", "vessel": "vessels", "agent": "agents", "user": "users"}[kind]
    return rf"^{directory}/{re.escape(name)}/secrets\.(yaml|yml|json|env|ini)$"


def validate_path_regex(value: str) -> str:
    if value != value.strip() or "\n" in value or "\r" in value or ".." in value or not value.startswith("^") or not value.endswith("$"):
        fail("Path regex must be a single repository-relative expression anchored with ^ and $.")
    try:
        re.compile(value)
    except re.error:
        fail("Path regex is invalid.")
    if not value.startswith(("^hosts/", "^users/", "^agents/", "^vessels/", "^keys/")) or "/secrets" not in value:
        fail("Path regex must target a scoped secrets file under hosts, users, agents, vessels, or keys.")
    if any(char in value for char in (":", "#", "'")):
        fail("Path regex contains YAML-unsafe characters.")
    return value


def parse_keys(lines: list[str]) -> tuple[int, int, dict[str, tuple[int, str, str]]]:
    keys_start = next((i for i, line in enumerate(lines) if line.strip() == "keys:"), -1)
    rules_start = next((i for i, line in enumerate(lines) if line.strip() == "creation_rules:"), -1)
    if keys_start < 0 or rules_start <= keys_start:
        fail("Unsupported .sops.yaml structure: expected top-level keys and creation_rules.")
    keys: dict[str, tuple[int, str, str]] = {}
    for i in range(keys_start + 1, rules_start):
        match = KEY_LINE_RE.fullmatch(lines[i].rstrip("\n"))
        if match:
            alias = match.group("alias")
            if alias in keys:
                fail(f"Duplicate SOPS key alias in .sops.yaml: {alias}")
            recipient = match.group("recipient")
            kind = "age" if AGE_RE.fullmatch(recipient) else "pgp" if PGP_RE.fullmatch(recipient) else "unknown"
            keys[alias] = (i, recipient, kind)
    return keys_start, rules_start, keys


def parse_rules(lines: list[str], start: int) -> list[tuple[int, int, str]]:
    rules: list[tuple[int, int, str]] = []
    current_start = -1
    current_regex = ""
    for i in range(start + 1, len(lines)):
        match = RULE_RE.fullmatch(lines[i].rstrip("\n"))
        if match:
            if current_start >= 0:
                rules.append((current_start, i, current_regex))
            current_start = i
            current_regex = match.group("regex")
    if current_start >= 0:
        rules.append((current_start, len(lines), current_regex))
    if not rules:
        fail("Unsupported .sops.yaml structure: no creation_rules found.")
    return rules


def insert_anchor(lines: list[str], rules_start: int, alias: str, recipient: str) -> None:
    insertion = rules_start
    while insertion > 0 and not lines[insertion - 1].strip():
        insertion -= 1
    lines.insert(insertion, f"  - &{alias} {recipient}\n")


def rule_block(lines: list[str], rule: tuple[int, int, str]) -> list[str]:
    start, end, _ = rule
    return lines[start:end]


def type_sections(block: list[str]) -> list[tuple[int, int, str, int]]:
    headers: list[tuple[int, str, int]] = []
    for i, line in enumerate(block):
        match = TYPE_HEADER_RE.fullmatch(line.rstrip("\n"))
        if match:
            header_indent = len(match.group("indent"))
            item_indent = header_indent + 2 if match.group("group") else header_indent
            headers.append((i, match.group("kind"), item_indent))
    sections = []
    for position, (header, kind, indent) in enumerate(headers):
        end = headers[position + 1][0] if position + 1 < len(headers) else len(block)
        sections.append((header, end, kind, indent))
    return sections


def section_aliases(block: list[str], start: int, end: int) -> list[tuple[int, str]]:
    found = []
    for i in range(start + 1, end):
        match = ALIAS_REF_RE.fullmatch(block[i].rstrip("\n"))
        if match:
            found.append((i, match.group("alias")))
    return found


def modify_rule(
    block: list[str],
    alias: str,
    key_kind: str,
    *,
    add: bool,
    replacement: str | None = None,
) -> list[str]:
    if not any(line.strip() == "key_groups:" for line in block):
        fail("Unsupported SOPS rule; expected key_groups.")
    sections = type_sections(block)
    if len(sections) > 2 or len({section[2] for section in sections}) != len(sections):
        fail("Unsupported SOPS rule shape; expected at most one age and one pgp group.")
    matching = [section for section in sections if section[2] == key_kind]
    if add:
        if matching:
            header, end, _, indent = matching[0]
            aliases = section_aliases(block, header, end)
            if any(value == alias for _, value in aliases):
                return block
            insertion = aliases[-1][0] + 1 if aliases else header + 1
            block.insert(insertion, f"{' ' * indent}- *{alias}\n")
            return block
        if len(sections) == 0:
            fail("Unsupported SOPS rule; no key groups.")
        indent = sections[0][3]
        insert = sections[-1][1]
        block[insert:insert] = [f"{' ' * indent}{key_kind}:\n", f"{' ' * indent}- *{alias}\n"]
        return block

    section = matching[0] if matching else None
    if section is None:
        fail(f"Recipient is not associated with this rule: {alias}")
    header, end, _, indent = section
    aliases = section_aliases(block, header, end)
    matches = [(i, value) for i, value in aliases if value == alias]
    if not matches:
        fail(f"Recipient is not associated with this rule: {alias}")
    if replacement is not None:
        existing = {value for _, value in aliases}
        for i, value in reversed(matches):
            if replacement in existing:
                del block[i]
            else:
                block[i] = block[i].replace(f"*{value}", f"*{replacement}", 1)
                existing.add(replacement)
        return block
    if len(aliases) == len(matches):
        fail(f"Unlinking {alias} would leave an empty {key_kind} group; supply --replace-with.")
    for i, _ in reversed(matches):
        del block[i]
    return block


def add_rule(lines: list[str], path_regex: str, alias: str, key_kind: str, keys: dict[str, tuple[int, str, str]]) -> list[str]:
    age_aliases: list[str] = []
    pgp_aliases: list[str] = []
    if key_kind == "age":
        age_aliases.append(alias)
        if RECOVERY_AGE in keys and keys[RECOVERY_AGE][2] == "age":
            age_aliases.append(RECOVERY_AGE)
        if RECOVERY_PGP in keys and keys[RECOVERY_PGP][2] == "pgp":
            pgp_aliases.append(RECOVERY_PGP)
    else:
        if RECOVERY_AGE in keys and keys[RECOVERY_AGE][2] == "age":
            age_aliases.append(RECOVERY_AGE)
        pgp_aliases.append(alias)
        if RECOVERY_PGP in keys and keys[RECOVERY_PGP][2] == "pgp":
            pgp_aliases.append(RECOVERY_PGP)

    block = [
        f"  - path_regex: {path_regex}\n",
        "    key_groups:\n",
    ]
    if age_aliases:
        block.extend(["      - age:\n", *[f"        - *{name}\n" for name in age_aliases]])
    if pgp_aliases:
        if age_aliases:
            block.extend(["        pgp:\n", *[f"        - *{name}\n" for name in pgp_aliases]])
        else:
            block.extend(["      - pgp:\n", *[f"        - *{name}\n" for name in pgp_aliases]])
    if lines and lines[-1].strip():
        lines.append("\n")
    lines.extend(block)
    return lines


def link_in_text(text: str, alias: str, key_kind: str, path_regex: str, *, add: bool) -> str:
    lines = text.splitlines(keepends=True)
    _, rules_start, keys = parse_keys(lines)
    rules = parse_rules(lines, rules_start)
    matches = [rule for rule in rules if rule[2] == path_regex]
    if len(matches) > 1:
        fail(f"Duplicate creation rule for path regex: {path_regex}")
    if matches:
        rule = matches[0]
        block = rule_block(lines, rule)
        modified = modify_rule(block, alias, key_kind, add=add)
        lines[rule[0]:rule[1]] = modified
    elif add:
        add_rule(lines, path_regex, alias, key_kind, keys)
    else:
        fail(f"No creation rule matches path regex: {path_regex}")
    return "".join(lines)


def recipient_value(args: argparse.Namespace) -> tuple[str, str]:
    if args.ssh_public_key:
        path = Path(args.ssh_public_key)
        if path.is_symlink() or not path.is_file() or not os.access(path, os.R_OK):
            fail("SSH public key is not a readable regular file.")
        with path.open("rb") as source:
            first_line = source.readline().split(None, 1)
            if not first_line or first_line[0] != b"ssh-ed25519":
                fail("Expected an SSH Ed25519 public key file, not a private key.")
            source.seek(0)
            result = subprocess.run(
                ["ssh-to-age"],
                stdin=source,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
                text=True,
            )
        if result.returncode:
            fail("Could not convert SSH public key to an age recipient.")
        recipient = result.stdout.strip()
        if not AGE_RE.fullmatch(recipient):
            fail("ssh-to-age returned an invalid age recipient.")
        return recipient, "age"
    if args.age_recipient:
        if not AGE_RE.fullmatch(args.age_recipient):
            fail("Invalid age recipient.")
        return args.age_recipient, "age"
    if args.pgp_fingerprint:
        fingerprint = args.pgp_fingerprint.replace(" ", "").upper()
        if not PGP_RE.fullmatch(fingerprint):
            fail("PGP fingerprint must be 40 or 64 hexadecimal characters.")
        return fingerprint, "pgp"
    fail("Specify one key source.")


def validate_config_text(text: str) -> None:
    lines = text.splitlines(keepends=True)
    _, rules_start, keys = parse_keys(lines)
    rules = parse_rules(lines, rules_start)
    for rule in rules:
        block = rule_block(lines, rule)
        if not any(line.strip() == "key_groups:" for line in block):
            fail(f"Unsupported creation rule for {rule[2]}; expected key_groups.")
        sections = type_sections(block)
        if not sections or len(sections) > 2 or len({section[2] for section in sections}) != len(sections):
            fail(f"Invalid key groups for creation rule {rule[2]}.")
        for header, end, key_kind, _ in sections:
            aliases = section_aliases(block, header, end)
            if not aliases:
                fail(f"Creation rule {rule[2]} contains an empty key group.")
            for _, alias in aliases:
                if alias not in keys:
                    fail(f"Creation rule {rule[2]} references a missing key alias.")
                if keys[alias][2] != key_kind:
                    fail(f"Creation rule {rule[2]} places {alias} in the wrong key group.")
        for line in block:
            match = ALIAS_REF_RE.fullmatch(line.rstrip("\n"))
            if match and match.group("alias") not in keys:
                fail(f"Creation rule {rule[2]} references a missing key alias.")


def save_config(text: str, expected_original: str) -> None:
    validate_config_text(text)
    path = repository_root() / ".sops.yaml"
    current = path.read_text(encoding="utf-8")
    if current != expected_original:
        fail(".sops.yaml changed during the operation; refusing to overwrite concurrent edits.")
    mode = path.stat().st_mode & 0o777
    fd, temp_name = tempfile.mkstemp(prefix=".sops-config-", dir=path.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as output:
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def recipient_add_or_update(args: argparse.Namespace) -> None:
    repository_root()
    alias = entity_alias(args.kind, args.name)
    recipient, key_kind = recipient_value(args)
    original = SOPS_CONFIG.read_text(encoding="utf-8")
    text = original
    lines = text.splitlines(keepends=True)
    _, rules_start, keys = parse_keys(lines)
    if args.action == "add":
        if alias in keys:
            fail(f"Recipient already exists; use recipient update: {alias}")
        insert_anchor(lines, rules_start, alias, recipient)
        text = "".join(lines)
        paths = args.path_regex or [default_path_regex(args.kind, args.name)]
        for path_regex in paths:
            text = link_in_text(text, alias, key_kind, validate_path_regex(path_regex), add=True)
    else:
        if alias not in keys:
            fail(f"Recipient does not exist: {alias}")
        old_kind = keys[alias][2]
        if old_kind != key_kind:
            fail("Recipient update must keep the same key type; remove/add with replacement instead.")
        if not confirm(f"UPDATE {alias}"):
            fail("Recipient update not confirmed; .sops.yaml was left unchanged.")
        pattern = re.compile(
            rf"^(?P<prefix>\s*-\s*&{re.escape(alias)}\s+)(?P<old>\S+)(?P<tail>\s*(?:#.*)?)$"
        )
        count = 0
        updated = []
        for line in lines:
            if pattern.fullmatch(line.rstrip("\n")):
                line = pattern.sub(rf"\g<prefix>{recipient}\g<tail>", line.rstrip("\n")) + ("\n" if line.endswith("\n") else "")
                count += 1
            updated.append(line)
        if count != 1:
            fail(f"Expected one key anchor for {alias}; config was not changed.")
        text = "".join(updated)
    save_config(text, original)
    print(f"Recipient {args.action} complete: {alias} ({key_kind}).")
    print("Existing encrypted files are unchanged; use recipient sync on affected files while old recipients remain available.")


def recipient_link(args: argparse.Namespace) -> None:
    repository_root()
    alias = entity_alias(args.kind, args.name)
    text = SOPS_CONFIG.read_text(encoding="utf-8")
    _, _, keys = parse_keys(text.splitlines(keepends=True))
    if alias not in keys:
        fail(f"Recipient does not exist: {alias}")
    if keys[alias][2] not in ("age", "pgp"):
        fail(f"Recipient has an unsupported key format: {alias}")
    path_regex = validate_path_regex(args.path_regex)
    if args.action == "unlink" and not confirm(f"REMOVE LINK {alias} {path_regex}"):
        fail("Recipient unlink not confirmed; .sops.yaml was left unchanged.")
    updated = link_in_text(text, alias, keys[alias][2], path_regex, add=args.action == "link")
    if updated != text:
        save_config(updated, text)
        print(f"Recipient {args.action} complete: {alias}.")
        print("Existing encrypted files are unchanged; use recipient sync on affected files.")
    else:
        print(f"Recipient already linked: {alias}.")


def recipient_remove(args: argparse.Namespace) -> None:
    repository_root()
    alias = entity_alias(args.kind, args.name)
    original = SOPS_CONFIG.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    _, rules_start, keys = parse_keys(lines)
    if alias not in keys:
        fail(f"Recipient does not exist: {alias}")
    key_kind = keys[alias][2]
    if key_kind not in ("age", "pgp"):
        fail(f"Recipient has an unsupported key format: {alias}")
    replacement = args.replace_with
    if replacement == alias:
        fail("Replacement recipient must differ from the recipient being removed.")
    if replacement is not None:
        if replacement not in keys:
            fail(f"Replacement recipient does not exist: {replacement}")
        if keys[replacement][2] != key_kind:
            fail("Replacement recipient must have the same key type.")
    rules = parse_rules(lines, rules_start)
    for rule in reversed(rules):
        block = rule_block(lines, rule)
        if any(match.group("alias") == alias for line in block if (match := ALIAS_REF_RE.fullmatch(line.rstrip("\n")))):
            modified = modify_rule(block, alias, key_kind, add=False, replacement=replacement)
            lines[rule[0]:rule[1]] = modified
    key_line = keys[alias][0]
    del lines[key_line]
    proposed = "".join(lines)
    validate_config_text(proposed)
    if not confirm(f"REMOVE {alias}"):
        fail("Removal not confirmed; .sops.yaml was left unchanged.")
    save_config(proposed, original)
    print(f"Recipient removed from .sops.yaml: {alias}.")
    print("Existing encrypted files are unchanged; use recipient sync on affected files while old recipients remain available.")


def recipient_list() -> None:
    repository_root()
    lines = SOPS_CONFIG.read_text(encoding="utf-8").splitlines()
    _, _, keys = parse_keys(lines)
    for alias, (_, _, key_kind) in keys.items():
        print(f"{alias}\t{key_kind}")


def recipient_sync(raw_files: Iterable[str]) -> None:
    targets = [safe_relative(raw) for raw in raw_files]
    if len({relative for relative, _ in targets}) != len(targets):
        fail("Recipient sync paths must be unique.")
    for relative, target in targets:
        require_encrypted(relative, target)
    for relative, target in targets:
        result = subprocess.run(
            ["sops", "updatekeys", str(target)],
            cwd=repository_root(),
            check=False,
        )
        if result.returncode:
            fail(f"SOPS recipient sync failed for {relative}; retry after restoring decryption access.")
        print(f"Recipient sync complete: {relative}")


def key_source_options(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ssh-public-key")
    group.add_argument("--age-recipient")
    group.add_argument("--pgp-fingerprint")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nix-secrets",
        description="Safely manage SOPS-encrypted files, entries, and recipient associations.",
    )
    top = parser.add_subparsers(dest="group")

    files = top.add_parser("file", help="add, edit, or remove an encrypted secret file")
    file_ops = files.add_subparsers(dest="action")
    add = file_ops.add_parser("add", help="create an encrypted empty YAML file")
    add.add_argument("file")
    edit = file_ops.add_parser("edit", help="edit an encrypted file with SOPS")
    edit.add_argument("file")
    remove = file_ops.add_parser("remove", help="remove an encrypted file locally")
    remove.add_argument("file")

    entries = top.add_parser("entry", help="add, update, or remove an entry in an encrypted file")
    entry_ops = entries.add_subparsers(dest="action")
    for action in ("add", "update", "remove"):
        command = entry_ops.add_parser(action)
        command.add_argument("file")
        command.add_argument("index")
        command.set_defaults(func=lambda args, action=action: entry_mutate(action, args.file, args.index))

    recipients = top.add_parser("recipient", help="manage SOPS key recipients and creation-rule links")
    recipient_ops = recipients.add_subparsers(dest="action")
    for action in ("add", "update"):
        command = recipient_ops.add_parser(action)
        command.add_argument("kind", choices=tuple(ENTITY_PREFIX))
        command.add_argument("name")
        key_source_options(command)
        if action == "add":
            command.add_argument("--path-regex", action="append")
        command.set_defaults(func=recipient_add_or_update)

    for action in ("link", "unlink"):
        command = recipient_ops.add_parser(action)
        command.add_argument("kind", choices=tuple(ENTITY_PREFIX))
        command.add_argument("name")
        command.add_argument("--path-regex", required=True)
        command.set_defaults(func=recipient_link)

    remove_recipient = recipient_ops.add_parser("remove")
    remove_recipient.add_argument("kind", choices=tuple(ENTITY_PREFIX))
    remove_recipient.add_argument("name")
    remove_recipient.add_argument("--replace-with")
    remove_recipient.set_defaults(func=recipient_remove)

    recipient_ops.add_parser("list").set_defaults(func=lambda args: recipient_list())
    sync = recipient_ops.add_parser("sync")
    sync.add_argument("files", nargs="+")
    sync.set_defaults(func=lambda args: recipient_sync(args.files))

    for action, func in (("add", file_add), ("edit", file_edit), ("remove", file_remove)):
        command = file_ops.choices[action]
        command.set_defaults(func=lambda args, func=func: func(args.file))
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    if not argv:
        parser.print_help()
        return 0
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.parse_args([args.group, "--help"])
        return 0
    try:
        args.func(args)
        return 0
    except CliError as exc:
        print(f"nix-secrets: {exc}", file=sys.stderr)
        return 1
    except OSError:
        print("nix-secrets: filesystem or executable operation failed; no secret value was displayed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
