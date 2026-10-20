"""Exercise the real compiler/CPU/ffmpeg CLI in a disposable workspace."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg/ffprobe required')
class RenderCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        (self.work / 'programs').mkdir()
        (self.work / 'programs/smoke.cin').write_text('''
fn main() {
  let i = 0;
  while (i < $FRAMES) {
    pixel(i, 0, 65535);
    flush();
    i = i + 1;
  }
}
''')
        self.full = self.work / 'full.gif'
        self.full.write_bytes(b'existing full render')
        self.scene = self.work / 'scene.json'
        self.scene.write_text(json.dumps({
            'program': 'smoke', 'frames': 12, 'seed': 1,
            'fps': 10, 'output': str(self.full),
        }))

    def render(self, *args, env=None):
        return subprocess.run([
            sys.executable, str(ROOT / 'render.py'), '--scene', str(self.scene), *args,
        ], cwd=self.work, env=env, capture_output=True, text=True, timeout=30)

    def frame_count(self, path):
        return int(subprocess.check_output([
            'ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
            '-show_entries', 'stream=nb_read_frames', '-of', 'csv=p=0', str(path),
        ], text=True).strip())

    def test_preview_renders_four_frames_without_overwriting_full_output(self):
        run = self.render('--preview')
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(self.full.read_bytes(), b'existing full render')
        self.assertEqual(self.frame_count(self.work / 'full_preview.gif'), 4)
        self.assertEqual((self.work / 'full_preview.png').read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
        self.assertFalse((self.work / 'full_preview.gif.frames').exists())

    def test_explicit_output_is_respected(self):
        target = self.work / 'nested' / 'chosen.gif'
        run = self.render('--preview', '--output', str(target))
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(self.frame_count(target), 4)
        self.assertEqual(self.full.read_bytes(), b'existing full render')
        self.assertFalse((self.work / 'full_preview.gif').exists())

    def test_missing_ffmpeg_fails_before_creating_output(self):
        env = dict(os.environ, PATH=str(self.work / 'empty-path'))
        run = self.render('--preview', env=env)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn('ffmpeg is required', run.stderr)
        self.assertEqual(self.full.read_bytes(), b'existing full render')
        self.assertFalse((self.work / 'full_preview.gif.frames').exists())


if __name__ == '__main__':
    unittest.main()
