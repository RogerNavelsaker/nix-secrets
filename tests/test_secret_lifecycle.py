import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1]
TEST_AGE = "age1" + "a" * 58
TEST_AGENT_AGE = "age1" + "c" * 58
TEST_NEW_AGE = "age1" + "d" * 58
TEST_ROTATED_AGE = "age1" + "e" * 58


class LifecycleCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.scripts = self.repo / "scripts"
        self.scripts.mkdir(parents=True)
        shutil.copy2(SOURCE / "scripts" / "nix-secrets.py", self.scripts / "nix-secrets.py")
        for name in ("new-secret.sh", "edit-secret.sh"):
            shutil.copy2(SOURCE / "scripts" / name, self.scripts / name)
        (self.repo / ".sops.yaml").write_text(
            "keys:\n"
            f"  - &host_roger-aio {TEST_AGE}\n"
            f"  - &host_agent_rowan {TEST_AGENT_AGE}\n"
            "  - &user_rona ABCDEF0123456789ABCDEF0123456789ABCDEF01\n"
            "creation_rules:\n"
            "  - path_regex: ^agents/rowan/secrets\\.(yaml|yml|json|env|ini)$\n"
            "    key_groups:\n"
            "      - age:\n"
            "        - *host_agent_rowan\n"
            "        - *host_roger-aio\n"
            "        pgp:\n"
            "        - *user_rona\n"
            "  - path_regex: ^keys/.+\\.(yaml|yml|json|env|ini)$\n"
            "    key_groups:\n"
            "      - pgp:\n"
            "        - *user_rona\n"
        )
        self.bin = Path(self.temp.name) / "bin"
        self.bin.mkdir()
        self.log = Path(self.temp.name) / "sops.log"
        self.sops_input = Path(self.temp.name) / "sops.input"
        self.value_input = Path(self.temp.name) / "value.input"
        self._write_executable(
            self.bin / "sops",
            """#!/usr/bin/env python3
import os
import sys
from pathlib import Path
args = sys.argv[1:]
Path(os.environ["SOPS_LOG"]).open("a").write(repr(args) + "\\n")
if args and args[0] == "filestatus":
    unencrypted = set(os.environ.get("UNENCRYPTED_PATHS", "").split("|"))
    print('{"encrypted":false}' if len(args) > 1 and args[1] in unencrypted else '{"encrypted":true}')
elif args and args[0] == "--encrypt":
    data = sys.stdin.buffer.read()
    Path(os.environ["SOPS_INPUT"]).write_bytes(data)
    sys.stdout.buffer.write(b"ENC[TEST]\\nsops:\\n  version: test\\n")
elif args and args[0] == "--decrypt":
    index = args[args.index("--extract") + 1]
    present = set(os.environ.get("PRESENT_PATHS", "").split("|"))
    if index not in present:
        print("component not found", file=sys.stderr)
        sys.exit(1)
    sys.stdout.write("null\\n")
elif args and args[0] == "set":
    data = sys.stdin.buffer.read()
    Path(os.environ["VALUE_INPUT"]).write_bytes(data)
elif args and args[0] == "unset":
    pass
elif args and args[0] == "updatekeys":
    pass
else:
    print("SOPS_EDITOR_OPENED")
""",
        )
        self._write_executable(
            self.bin / "ssh-to-age",
            """#!/usr/bin/env python3
import sys
sys.stdin.buffer.read()
print("age1" + "f" * 58)
""",
        )
        self.env = os.environ.copy()
        self.env.update(
            {
                "PATH": f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "NIX_SECRETS_ROOT": str(self.repo),
                "SOPS_LOG": str(self.log),
                "SOPS_INPUT": str(self.sops_input),
                "VALUE_INPUT": str(self.value_input),
            }
        )

    @staticmethod
    def _write_executable(path, content):
        path.write_text(content)
        path.chmod(0o755)

    def run_cli(self, *args, input=None, env=None):
        run_env = self.env.copy()
        if env:
            run_env.update(env)
        return subprocess.run(
            ["python3", str(self.scripts / "nix-secrets.py"), *args],
            cwd=self.repo,
            env=run_env,
            input=input,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_no_args_prints_help_without_mutation(self):
        result = self.run_cli()

        self.assertEqual(result.returncode, 0)
        self.assertIn("usage:", result.stdout.lower())
        self.assertFalse(self.log.exists())

    def test_file_add_creates_encrypted_empty_mapping(self):
        result = self.run_cli("file", "add", "agents/new/secrets.yaml")
        target = self.repo / "agents/new/secrets.yaml"

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Created encrypted", result.stdout)
        self.assertTrue(target.is_file())
        self.assertIn("ENC[TEST]", target.read_text())
        self.assertEqual(self.sops_input.read_text(), "{}\n")

    def test_file_add_refuses_overwrite(self):
        target = self.repo / "agents/new/secrets.yaml"
        target.parent.mkdir(parents=True)
        target.write_text("user-owned")

        result = self.run_cli("file", "add", "agents/new/secrets.yaml")

        self.assertEqual(result.returncode, 1)
        self.assertEqual(target.read_text(), "user-owned")
        self.assertFalse(self.sops_input.exists())

    def test_file_edit_requires_encrypted_file(self):
        target = self.repo / "agents/rowan/secrets.yaml"
        target.parent.mkdir(parents=True)
        target.write_text("ciphertext")

        result = self.run_cli("file", "edit", "agents/rowan/secrets.yaml")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("SOPS_EDITOR_OPENED", result.stdout)

    def test_file_edit_supports_clanker_secret_path(self):
        target = self.repo / "clankers/rowan/secrets.yaml"
        target.parent.mkdir(parents=True)
        target.write_text("ciphertext")

        result = self.run_cli("file", "edit", "clankers/rowan/secrets.yaml")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("SOPS_EDITOR_OPENED", result.stdout)

    def test_file_remove_requires_confirmation(self):
        target = self.repo / "agents/rowan/secrets.yaml"
        target.parent.mkdir(parents=True)
        target.write_text("ciphertext")

        result = self.run_cli(
            "file", "remove", "agents/rowan/secrets.yaml",
            input="no\n",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(target.exists())

    def test_file_remove_after_typed_confirmation(self):
        target = self.repo / "agents/rowan/secrets.yaml"
        target.parent.mkdir(parents=True)
        target.write_text("ciphertext")

        result = self.run_cli(
            "file", "remove", "agents/rowan/secrets.yaml",
            input="REMOVE agents/rowan/secrets.yaml\n",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(target.exists())

    def test_entry_add_reads_json_from_stdin_without_argv_leak(self):
        target = self.repo / "agents/rowan/secrets.yaml"
        target.parent.mkdir(parents=True)
        target.write_text("ciphertext")
        index = '["api"]["token"]'

        result = self.run_cli(
            "entry", "add", "agents/rowan/secrets.yaml", index,
            input='"test-secret-value"\n',
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.value_input.read_text(), '"test-secret-value"\n')
        self.assertNotIn("test-secret-value", self.log.read_text())

    def test_entry_add_rejects_existing_path(self):
        target = self.repo / "agents/rowan/secrets.yaml"
        target.parent.mkdir(parents=True)
        target.write_text("ciphertext")

        result = self.run_cli(
            "entry", "add", "agents/rowan/secrets.yaml", '["api"]',
            input='"new"\n',
            env={"PRESENT_PATHS": '["api"]'},
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.value_input.exists())

    def test_entry_update_changes_existing_value_without_argv_leak(self):
        target = self.repo / "agents/rowan/secrets.yaml"
        target.parent.mkdir(parents=True)
        target.write_text("ciphertext")
        index = '["api"]["token"]'

        result = self.run_cli(
            "entry", "update", "agents/rowan/secrets.yaml", index,
            input='"replacement-secret"\n',
            env={"PRESENT_PATHS": index},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.value_input.read_text(), '"replacement-secret"\n')
        self.assertNotIn("replacement-secret", self.log.read_text())

    def test_entry_update_requires_existing_path(self):
        target = self.repo / "agents/rowan/secrets.yaml"
        target.parent.mkdir(parents=True)
        target.write_text("ciphertext")

        result = self.run_cli(
            "entry", "update", "agents/rowan/secrets.yaml", '["api"]',
            input='"new"\n',
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.value_input.exists())

    def test_entry_remove_requires_confirmation_and_existing_path(self):
        target = self.repo / "agents/rowan/secrets.yaml"
        target.parent.mkdir(parents=True)
        target.write_text("ciphertext")
        index = '["api"]["token"]'

        result = self.run_cli(
            "entry", "remove", "agents/rowan/secrets.yaml", index,
            input="no\n",
            env={"PRESENT_PATHS": index},
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("unset", self.log.read_text())

    def test_entry_remove_after_confirmation(self):
        target = self.repo / "agents/rowan/secrets.yaml"
        target.parent.mkdir(parents=True)
        target.write_text("ciphertext")
        index = '["api"]["token"]'

        result = self.run_cli(
            "entry", "remove", "agents/rowan/secrets.yaml", index,
            input="REMOVE agents/rowan/secrets.yaml " + index + "\n",
            env={"PRESENT_PATHS": index},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("unset", self.log.read_text())

    def test_recipient_add_creates_anchor_and_default_rule(self):
        result = self.run_cli(
            "recipient", "add", "agent", "jules",
            "--age-recipient", TEST_NEW_AGE,
        )
        config = (self.repo / ".sops.yaml").read_text()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"&host_agent_jules {TEST_NEW_AGE}", config)
        self.assertIn("^agents/jules/secrets", config)
        self.assertIn("*host_roger-aio", config)
        self.assertIn("*user_rona", config)

    def test_recipient_add_converts_public_ssh_key(self):
        public_key = self.repo / "rowan.pub"
        public_key.write_text("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFakePublicKey rowan\n")
        result = self.run_cli(
            "recipient", "add", "agent", "jules",
            "--ssh-public-key", str(public_key),
        )
        config = (self.repo / ".sops.yaml").read_text()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"&host_agent_jules {'age1' + 'f' * 58}", config)
        self.assertFalse(self.log.exists())

    def test_recipient_add_rejects_private_ssh_key(self):
        before = (self.repo / ".sops.yaml").read_text()
        private_key = self.repo / "rowan"
        private_key.write_text("-----BEGIN OPENSSH PRIVATE KEY-----\nexample\n")
        result = self.run_cli(
            "recipient", "add", "agent", "jules",
            "--ssh-public-key", str(private_key),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.repo / ".sops.yaml").read_text(), before)
        self.assertFalse(self.log.exists())

    def test_recipient_add_supports_pgp_recipients(self):
        fingerprint = "a1" * 20
        result = self.run_cli(
            "recipient", "add", "user", "alice",
            "--pgp-fingerprint", fingerprint,
        )
        config = (self.repo / ".sops.yaml").read_text()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"&user_alice {fingerprint.upper()}", config)
        self.assertIn("^users/alice/secrets", config)
        self.assertIn("*host_roger-aio", config)
        self.assertIn("*user_rona", config)

    def test_recipient_add_works_without_optional_recovery_aliases(self):
        (self.repo / ".sops.yaml").write_text(
            "keys:\n"
            f"  - &host_agent_rowan {TEST_AGENT_AGE}\n"
            "creation_rules:\n"
            "  - path_regex: ^agents/rowan/secrets\\.yaml$\n"
            "    key_groups:\n"
            "      - age:\n"
            "        - *host_agent_rowan\n"
        )

        result = self.run_cli(
            "recipient", "add", "agent", "jules",
            "--age-recipient", TEST_NEW_AGE,
        )
        config = (self.repo / ".sops.yaml").read_text()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"&host_agent_jules {TEST_NEW_AGE}", config)
        self.assertNotIn("host_roger-aio", config)
        self.assertNotIn("user_rona", config)

    def test_recipient_update_replaces_same_type_recipient(self):
        result = self.run_cli(
            "recipient", "update", "agent", "rowan",
            "--age-recipient", TEST_ROTATED_AGE,
            input="UPDATE host_agent_rowan\n",
        )
        config = (self.repo / ".sops.yaml").read_text()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"&host_agent_rowan {TEST_ROTATED_AGE}", config)
        self.assertNotIn(f"&host_agent_rowan {TEST_AGENT_AGE}", config)

    def test_recipient_link_and_unlink(self):
        linked = self.run_cli(
            "recipient", "link", "agent", "rowan",
            "--path-regex", r"^vessels/rowan/secrets\.yaml$",
        )
        config = (self.repo / ".sops.yaml").read_text()
        self.assertEqual(linked.returncode, 0, linked.stderr)
        self.assertIn(r"^vessels/rowan/secrets\.yaml$", config)
        self.assertIn("*host_agent_rowan", config)

        unlinked = self.run_cli(
            "recipient", "unlink", "agent", "rowan",
            "--path-regex", r"^vessels/rowan/secrets\.yaml$",
            input=r"REMOVE LINK host_agent_rowan ^vessels/rowan/secrets\.yaml$" + "\n",
        )
        self.assertEqual(unlinked.returncode, 0, unlinked.stderr)
        config = (self.repo / ".sops.yaml").read_text()
        block = config.split(r"^vessels/rowan/secrets\.yaml$", 1)[1].split("  - path_regex:", 1)[0]
        self.assertNotIn("*host_agent_rowan", block)

    def test_recipient_remove_requires_confirmation_and_safe_replacement(self):
        result = self.run_cli(
            "recipient", "remove", "agent", "rowan",
            "--replace-with", "host_roger-aio",
            input="REMOVE host_agent_rowan\n",
        )
        config = (self.repo / ".sops.yaml").read_text()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("&host_agent_rowan", config)
        self.assertIn("*host_roger-aio", config)

    def test_recipient_remove_resolves_existing_recovery_alias(self):
        before = (self.repo / ".sops.yaml").read_text()
        result = self.run_cli("recipient", "remove", "host", "roger-aio", input="no\n")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Removal not confirmed", result.stderr)
        self.assertEqual((self.repo / ".sops.yaml").read_text(), before)

    def test_recipient_remove_refuses_to_empty_a_rule(self):
        before = (self.repo / ".sops.yaml").read_text()
        result = self.run_cli(
            "recipient", "remove", "user", "rona",
            input="REMOVE user_rona\n",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.repo / ".sops.yaml").read_text(), before)

    def test_recipient_sync_preflights_all_files_before_updating(self):
        for name in ("rowan", "jules"):
            target = self.repo / f"agents/{name}/secrets.yaml"
            target.parent.mkdir(parents=True)
            target.write_text("ciphertext")

        result = self.run_cli(
            "recipient", "sync", "agents/rowan/secrets.yaml", "agents/jules/secrets.yaml",
            env={"UNENCRYPTED_PATHS": str(self.repo / "agents/jules/secrets.yaml")},
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("updatekeys", self.log.read_text())

    def test_recipient_sync_rejects_symlink_escape(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (self.repo / "agents").mkdir()
        (self.repo / "agents/escape").symlink_to(outside, target_is_directory=True)
        (outside / "secrets.yaml").write_text("ciphertext")

        result = self.run_cli("recipient", "sync", "agents/escape/secrets.yaml")

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_recipient_sync_delegates_only_encrypted_files(self):
        target = self.repo / "agents/rowan/secrets.yaml"
        target.parent.mkdir(parents=True)
        target.write_text("ciphertext")

        result = self.run_cli("recipient", "sync", "agents/rowan/secrets.yaml")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("updatekeys", self.log.read_text())


if __name__ == "__main__":
    unittest.main()
