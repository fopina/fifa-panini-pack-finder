import runpy
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ('version', 'expected_tuple'),
    [
        ('1.0.0', (1, 0, 0)),
        ('1.0.0a1', (1, 0, 0, 'a1')),
        ('1.0.0b1', (1, 0, 0, 'b1')),
        ('1.0.0rc1', (1, 0, 0, 'rc1')),
        ('1.0.0.dev1', (1, 0, 0, 'dev1')),
        ('1.0.0.post1', (1, 0, 0, 'post1')),
    ],
)
def test_set_release_version(tmp_path, version, expected_tuple):
    root = Path(__file__).resolve().parent.parent
    script = tmp_path / '.github' / 'change_version.py'
    package = tmp_path / 'fifa_panini' / '__init__.py'
    script.parent.mkdir()
    package.parent.mkdir()
    shutil.copy2(root / '.github' / 'change_version.py', script)
    shutil.copy2(root / 'fifa_panini' / '__init__.py', package)

    subprocess.run([sys.executable, str(script), '--set', version], cwd=script.parent, check=True)

    namespace = runpy.run_path(str(package))
    assert namespace['__version__'] == namespace['version'] == version
    assert namespace['__version_tuple__'] == namespace['version_tuple'] == expected_tuple
