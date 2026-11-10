import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1]


class SecretWrapperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.scripts = self.repo / "scripts"
        self.scripts.mkdir(parents=True)
        (self.repo / ".sops.yaml").write_text(
            "keys:\n  - &host_one age1one\ncreation_rules:\n"
        )
        for name in (
            "ssh-to-age-key.sh",
            "edit-secret.sh",
            "new-secret.sh",
            "list-keys.sh",
            "nix-secrets.py",
        ):
            shutil.copy2(SOURCE / "scripts" / name, self.scripts / name)

        self.bin = Path(self.temp.name) / "bin"
        self.bin.mkdir()
        self.log = Path(self.temp.name) / "sops.log"
        self.sops_input = Path(self.temp.name) / "sops.input"
        self.age_input = Path(self.temp.name) / "ssh-to-age.input"
        self._write_executable(
            self.bin / "sops",
            """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "$SOPS_LOG"
if [[ "${1:-}" == filestatus ]]; then
  if [[ "${SOPS_STATUS:-true}" == true ]]; then
    printf '{"encrypted":true}\\n'
  else
    printf '{"encrypted":false}\\n'
  fi
elif [[ "${1:-}" == --encrypt ]]; then
  cat > "$SOPS_INPUT_LOG"
  input=$(cat "$SOPS_INPUT_LOG")
  [[ "$input" == '{}' ]] || exit 43
  [[ "${SOPS_FAIL_ENCRYPT:-false}" != true ]] || exit 42
  printf 'placeholder: ENC[TEST]\\nsops:\\n  version: test\\n'
else
  printf 'SOPS_EDITOR_OPENED\\n'
fi
""",
        )
        self._write_executable(
            self.bin / "ssh-to-age",
            """#!/usr/bin/env bash
set -euo pipefail
cat > "$SSH_TO_AGE_INPUT"
printf 'age1testrecipient\\n'
""",
        )
        self.env = os.environ.copy()
        self.env.update(
            {
                "PATH": f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "SOPS_LOG": str(self.log),
                "SOPS_INPUT_LOG": str(self.sops_input),
                "SSH_TO_AGE_INPUT": str(self.age_input),
            }
        )

    @staticmethod
    def _write_executable(path, content):
        path.write_text(content)
        path.chmod(0o755)

    def run_script(self, name, *args, **env):
        run_env = self.env.copy()
        run_env.update(env)
        return subprocess.run(
            ["bash", str(self.scripts / name), *args],
            cwd=self.repo,
            env=run_env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_ssh_to_age_key_passes_public_file_on_stdin(self):
        public_file = self.repo / "host.pub"
        public_file.write_text("ssh-ed25519 test-public-key host\n")

        result = self.run_script("ssh-to-age-key.sh", str(public_file))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "age1testrecipient\n")
        self.assertEqual(
            self.age_input.read_text(), "ssh-ed25519 test-public-key host\n"
        )

    def test_ssh_to_age_key_requires_one_file(self):
        result = self.run_script("ssh-to-age-key.sh")

        self.assertEqual(result.returncode, 2)
        self.assertIn("Usage:", result.stderr)

    def test_ssh_to_age_key_rejects_private_key_input(self):
        private_file = self.repo / "id_ed25519"
        private_file.write_text("-----BEGIN OPENSSH PRIVATE KEY-----\nnot-a-public-key\n")

        result = self.run_script("ssh-to-age-key.sh", str(private_file))

        self.assertEqual(result.returncode, 1)
        self.assertIn("Expected an SSH Ed25519 public key", result.stderr)
        self.assertFalse(self.age_input.exists())

    def test_new_secret_creates_encrypted_placeholder_without_plaintext_file(self):
        result = self.run_script("new-secret.sh", "agents/rowan/secrets.yaml")
        target = self.repo / "agents/rowan/secrets.yaml"

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Created encrypted empty secret file", result.stdout)
        self.assertTrue(target.is_file())
        self.assertIn("ENC[TEST]", target.read_text())
        self.assertEqual(self.sops_input.read_text(), "{}\n")
        self.assertFalse(list(target.parent.glob(".new-secret.*.yaml")))

    def test_new_secret_refuses_overwrite(self):
        target = self.repo / "agents/rowan/secrets.yaml"
        target.parent.mkdir(parents=True)
        target.write_text("user-owned")

        result = self.run_script("new-secret.sh", "agents/rowan/secrets.yaml")

        self.assertEqual(result.returncode, 1)
        self.assertEqual(target.read_text(), "user-owned")
        self.assertFalse(self.sops_input.exists())

    def test_new_secret_rejects_path_traversal(self):
        result = self.run_script("new-secret.sh", "../outside.yaml")

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((Path(self.temp.name) / "outside.yaml").exists())

    def test_new_secret_rejects_symlink_parent_outside_repository(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (self.repo / "escape").symlink_to(outside, target_is_directory=True)

        result = self.run_script("new-secret.sh", "escape/secrets.yaml")

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((outside / "secrets.yaml").exists())

    def test_new_secret_rejects_plaintext_or_failed_encryption(self):
        result = self.run_script(
            "new-secret.sh", "agents/rowan/secrets.yaml", SOPS_STATUS="false"
        )
        target = self.repo / "agents/rowan/secrets.yaml"

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(target.exists())
        self.assertFalse(list((self.repo / "agents/rowan").glob(".new-secret.*")))

        failed = self.run_script(
            "new-secret.sh",
            "agents/jules/secrets.yaml",
            SOPS_FAIL_ENCRYPT="true",
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertFalse((self.repo / "agents/jules/secrets.yaml").exists())

    def test_edit_secret_requires_encrypted_file(self):
        target = self.repo / "agents/rowan/secrets.yaml"
        target.parent.mkdir(parents=True)
        target.write_text("plaintext")

        result = self.run_script(
            "edit-secret.sh", "agents/rowan/secrets.yaml", SOPS_STATUS="false"
        )

        self.assertEqual(result.returncode, 1)
        log = self.log.read_text()
        self.assertIn("filestatus", log)
        self.assertNotIn(f"sops {target}", log)

    def test_edit_secret_opens_sops_for_encrypted_file(self):
        target = self.repo / "agents/rowan/secrets.yaml"
        target.parent.mkdir(parents=True)
        target.write_text("encrypted")

        result = self.run_script("edit-secret.sh", "agents/rowan/secrets.yaml")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("SOPS_EDITOR_OPENED", result.stdout)
        self.assertIn(str(target), self.log.read_text())

    def test_list_keys_prints_only_top_level_entries(self):
        (self.repo / ".sops.yaml").write_text(
            "keys:\n"
            "  - &host_one age1one\n"
            "  - &user_one FINGERPRINT\n"
            "\n"
            "creation_rules:\n"
            "  - path_regex: secrets\\.yaml$\n"
        )

        result = self.run_script("list-keys.sh")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("&host_one age1one", result.stdout)
        self.assertIn("&user_one FINGERPRINT", result.stdout)
        self.assertNotIn("path_regex", result.stdout)


if __name__ == "__main__":
    unittest.main()
