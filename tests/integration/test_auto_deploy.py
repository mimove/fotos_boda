import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / 'deploy' / 'auto-deploy.sh'


class AutoDeployTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.source, self.app, self.release = root / 'source', root / 'app', root / 'release'
        self.source.mkdir()
        self.app.mkdir()
        (self.app / '.env').write_text('secret')
        (self.app / 'files').mkdir()
        (self.app / 'data').mkdir()
        (self.app / 'data' / 'selected.json').write_text('keep')
        self.git('init', '-b', 'main')
        self.git('config', 'user.email', 'test@example.com')
        self.git('config', 'user.name', 'Test')
        (self.source / 'README').write_text('initial')
        self.git('add', '.')
        self.git('commit', '-m', 'initial')
        bindir = root / 'bin'
        bindir.mkdir()
        docker = bindir / 'docker'
        docker.write_text('#!/bin/sh\necho called >> "$WEDDING_TEST_LOG"\nexit "${WEDDING_TEST_EXIT:-0}"\n')
        docker.chmod(0o755)
        curl = bindir / 'curl'
        curl.write_text('#!/bin/sh\nexit 0\n')
        curl.chmod(0o755)
        self.state = root / 'state' / 'last-success'
        self.log = root / 'docker.log'
        self.env = dict(os.environ, PATH=str(bindir) + os.pathsep + os.environ['PATH'],
                        WEDDING_APP_HOME=str(self.app), WEDDING_RELEASE_DIR=str(self.release),
                        WEDDING_DEPLOY_STATE=str(self.state), WEDDING_GIT_REMOTE=str(self.source),
                        WEDDING_TEST_LOG=str(self.log))

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        subprocess.run(['git', '-C', str(self.source), *args], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def run_deploy(self, **env):
        return subprocess.run([str(SCRIPT)], env=dict(self.env, **env), capture_output=True, text=True)

    def test_waits_for_configuration_then_deploys_once_and_preserves_data(self):
        result = self.run_deploy()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.log.exists())
        (self.source / 'docker-compose.yml').write_text('services: {}\n')
        self.git('add', '.')
        self.git('commit', '-m', 'production config')
        result = self.run_deploy()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.log.read_text().splitlines(), ['called'])
        self.assertEqual((self.app / 'data' / 'selected.json').read_text(), 'keep')
        self.assertEqual(self.run_deploy().returncode, 0)
        self.assertEqual(self.log.read_text().splitlines(), ['called'])

    def test_failed_build_retries(self):
        (self.source / 'docker-compose.yml').write_text('services: {}\n')
        self.git('add', '.')
        self.git('commit', '-m', 'production config')
        self.assertNotEqual(self.run_deploy(WEDDING_TEST_EXIT='1').returncode, 0)
        self.assertFalse(self.state.exists())
        result = self.run_deploy()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.log.read_text().splitlines(), ['called', 'called'])


if __name__ == '__main__':
    unittest.main()
