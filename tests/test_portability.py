"""Offline behavior checks using geometric fixtures, no image-generation calls."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw


class PortableSkillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sticker-portability-', dir=os.environ.get('STICKER_TEST_TMPDIR'))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skill = self.root / 'installed' / 'plush-animated-stickers'
        shutil.copytree(Path(__file__).resolve().parents[1], self.skill,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        self.script = self.skill / 'scripts' / 'build_stickers.py'
        self.cwd = self.root / 'unrelated-empty-directory'
        self.cwd.mkdir()
        self.inputs = self.root / 'workspace' / 'inputs'
        self.inputs.mkdir(parents=True)
        self.output = self.root / 'workspace' / 'release'
        self.config = self.inputs / 'config.json'
        sheet = Image.new('RGBA', (128, 64))
        draw = ImageDraw.Draw(sheet)
        for i in range(2):
            x = 64 * i
            draw.rounded_rectangle((x + 14, 12, x + 48, 52), 8, fill='white')
            draw.ellipse((x + 20 + i * 4, 22, x + 25 + i * 4, 28), fill='black')
        sheet.save(self.inputs / 'sheet.png')
        sheet.crop((0, 0, 64, 64)).save(self.inputs / 'cover.png')
        Image.new('RGB', (160, 90), '#4f8191').save(self.inputs / 'banner.png')
        (self.inputs / 'prompt.txt').write_text('Geometric technical fixture', encoding='utf-8')
        self.data = {'version': 1, 'canvas': [64, 64], 'character_box': [8, 8, 56, 56],
                     'provenance': ['prompt.txt'],
                     'stickers': [{'id': 'wave', 'sheet': 'sheet.png', 'grid': [2, 1],
                                   'sheet_size': [128, 64], 'order': [0, 1, 0],
                                   'durations_ms': [100, 200, 300], 'offsets': [[0, 0], [0, -2]]}],
                     'companions': {'banner': {'source': 'banner.png', 'size': [75, 40], 'format': 'JPEG'},
                                    'cover': {'source': 'cover.png', 'size': [48, 48]},
                                    'icon': {'source': 'cover.png', 'size': [16, 16]}}}
        self.save_config()

    def save_config(self):
        self.config.write_text(json.dumps(self.data), encoding='utf-8')

    def run_cli(self, *args, success=True):
        result = subprocess.run([sys.executable, str(self.script), *map(str, args)],
                                cwd=self.cwd, text=True, capture_output=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        return result.stderr

    def build(self):
        return self.run_cli('--config', self.config, '--output', self.output)

    def test_relocated_build_and_verification_without_original_inputs(self):
        result = self.build()
        self.assertEqual(result['status'], 'passed')
        with Image.open(self.output / 'upload' / 'wave.gif') as im:
            self.assertEqual(im.size, (64, 64))
            self.assertEqual(im.n_frames, 3)
            self.assertEqual(im.info['loop'], 0)
            timings, tops = [], []
            for i in range(im.n_frames):
                im.seek(i)
                rgba = im.convert('RGBA')
                self.assertEqual(rgba.getchannel('A').getextrema(), (0, 255))
                pixels = rgba.get_flattened_data() if hasattr(rgba, 'get_flattened_data') else rgba.getdata()
                self.assertTrue(any(a == 255 and min(r, g, b) > 240 for r, g, b, a in pixels))
                timings.append(im.info['duration'])
                tops.append(rgba.getchannel('A').getbbox()[1])
            self.assertEqual(timings, [100, 200, 300])
            self.assertEqual(tops[1], tops[0] - 2)
        for name, size in [('cover', (48, 48)), ('icon', (16, 16))]:
            with Image.open(self.output / 'upload' / (name + '.png')) as im:
                self.assertEqual(im.size, size)
                self.assertEqual(im.getchannel('A').getextrema(), (0, 255))
        shutil.rmtree(self.inputs)
        report = self.run_cli('--verify', self.output)
        self.assertEqual(report['status'], 'passed')
        self.assertEqual(report['human_review'], 'pending')

    def test_preflight_is_read_only_and_refuses_missing_companion(self):
        before = sorted(str(p) for p in self.root.rglob('*'))
        report = self.run_cli('--config', self.config, '--check')
        self.assertEqual(report['written_files'], 0)
        self.assertEqual(before, sorted(str(p) for p in self.root.rglob('*')))
        del self.data['companions']['icon']
        self.save_config()
        self.assertIn('banner, cover and icon', self.run_cli('--config', self.config, '--output', self.output, success=False))
        self.assertFalse(self.output.exists())

    def test_bad_grid_and_timing_fail_before_writing(self):
        self.data['stickers'][0]['grid'] = [3, 1]
        self.save_config()
        self.assertIn('evenly divided', self.run_cli('--config', self.config, '--output', self.output, success=False))
        self.data['stickers'][0]['grid'] = [2, 1]
        self.data['stickers'][0]['durations_ms'] = [1, 2, 3]
        self.save_config()
        self.assertIn('10 ms', self.run_cli('--config', self.config, '--output', self.output, success=False))
        self.assertFalse(self.output.exists())

    def test_no_overwrite_and_detect_modified_source(self):
        self.build()
        manifest = self.output / 'manifest.json'
        original = manifest.read_bytes()
        self.assertIn('already exists', self.run_cli('--config', self.config, '--output', self.output, success=False))
        self.assertEqual(manifest.read_bytes(), original)
        source = json.loads(original)['sources'][0]['file']
        (self.output / source).write_bytes(b'changed')
        result = subprocess.run([sys.executable, str(self.script), '--verify', str(self.output)],
                                cwd=self.cwd, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Source hash mismatch', result.stdout)


if __name__ == '__main__':
    unittest.main()
