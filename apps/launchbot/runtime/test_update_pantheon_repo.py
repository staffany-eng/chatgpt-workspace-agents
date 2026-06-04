from __future__ import annotations

import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).with_name("update-pantheon-repo.sh")


class LaunchbotPantheonUpdateTest(unittest.TestCase):
    def test_ssh_publickey_denial_fails_with_root_cause_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = root / "profile"
            ssh_dir = profile / "ssh"
            ssh_dir.mkdir(parents=True)
            (ssh_dir / "pantheon_deploy_key").write_text("fake-key\n", encoding="utf-8")

            fake_bin = root / "bin"
            fake_bin.mkdir()
            git_stub = fake_bin / "git"
            git_stub.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env bash
                    set -euo pipefail
                    printf '%s\n' "$*" >> "$GIT_STUB_LOG"
                    if [ "$1" = "ls-remote" ]; then
                      printf '%s\n' "git@github.com: Permission denied (publickey)." >&2
                      exit 128
                    fi
                    printf '%s\n' "unexpected git call: $*" >&2
                    exit 99
                    """
                ),
                encoding="utf-8",
            )
            git_stub.chmod(0o755)

            env = {
                **os.environ,
                "PATH": f"{fake_bin}:{os.environ['PATH']}",
                "PROFILE_DIR": str(profile),
                "LAUNCHBOT_PANTHEON_REPO_DIR": str(root / "pantheon"),
                "LAUNCHBOT_PANTHEON_STATUS_PATH": str(root / "pantheon-repo-status.json"),
                "LAUNCHBOT_PANTHEON_SSH_KEY": str(ssh_dir / "pantheon_deploy_key"),
                "GIT_STUB_LOG": str(root / "git.log"),
            }
            result = subprocess.run(
                ["bash", str(SCRIPT_PATH)],
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("pantheon:ssh-access-denied:git@github.com:staffany-eng/pantheon.git", result.stderr)
            self.assertEqual((root / "git.log").read_text(encoding="utf-8").splitlines(), ["ls-remote git@github.com:staffany-eng/pantheon.git refs/heads/develop"])
            self.assertFalse((root / "pantheon-repo-status.json").exists())


if __name__ == "__main__":
    unittest.main()
