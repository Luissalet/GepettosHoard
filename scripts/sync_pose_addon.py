"""Install only the shared poser engine into an existing Figure Tools addon."""
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
FILES = ('core/card_pose.py', 'core/card_pose_vision.py',
         'ops/card_pose.py', 'ops/auto_card_pose.py')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('addon', type=Path)
    args = parser.parse_args()
    target = args.addon.resolve()
    if not (target / 'ops/panels.py').is_file():
        parser.error('Target must be an existing Figure Tools addon')
    for relative in FILES:
        shutil.copy2(ROOT / 'pose_engine' / relative, target / relative)
    print('Updated four poser engine files. Reload Figure Tools to use them.')
