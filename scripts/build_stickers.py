"""Portable, config-driven sprite-sheet to GIF and companion-asset exporter."""
import argparse
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont, ImageOps

REQUIRED = {'banner', 'cover', 'icon'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def positive(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(label + ' must be a positive integer')
    return value


def pair(value, label):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(label + ' must have two integers')
    return tuple(positive(v, label) for v in value)


def inspect(data):
    with Image.open(BytesIO(data)) as im:
        fmt, size, loop = im.format, list(im.size), im.info.get('loop')
        durations, alpha, hashes = [], [], set()
        for i in range(getattr(im, 'n_frames', 1)):
            im.seek(i)
            im.load()
            rgba = im.convert('RGBA')
            durations.append(im.info.get('duration', 0))
            alpha.append(list(rgba.getchannel('A').getextrema()))
            hashes.add(sha(rgba.tobytes()))
        return {'format': fmt, 'size': size, 'frames': len(alpha),
                'durations_ms': durations, 'duration_ms': sum(durations),
                'loop': loop, 'unique_frames': len(hashes), 'alpha_ranges': alpha,
                'bytes': len(data), 'sha256': sha(data)}


def safe_name(name):
    if not isinstance(name, str) or not name or name in ('.', '..') or '/' in name or '\\' in name:
        raise ValueError('id must be one nonempty filename component')
    return name


def local_file(folder, relative):
    path = (folder / relative).resolve()
    if folder.resolve() not in path.parents:
        raise ValueError('Bundle path escapes its directory')
    return path


def validate_record(actual, expected):
    for key in ('format', 'size'):
        if actual[key] != expected[key]:
            raise ValueError(key + ' differs from export target')
    if expected.get('max_bytes') and actual['bytes'] > expected['max_bytes']:
        raise ValueError('Export exceeds configured byte target')
    for low, high in actual['alpha_ranges']:
        if expected['transparent'] and not (low == 0 and high > 0):
            raise ValueError('Expected nonempty transparent foreground in every frame')
        if not expected['transparent'] and (low, high) != (255, 255):
            raise ValueError('Expected fully opaque export')
    for key in ('duration_ms', 'loop'):
        if key in expected and actual[key] != expected[key]:
            raise ValueError(key + ' differs from configured timeline')


def verify(folder):
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    errors, reports = [], []
    roles = [e['role'] for e in manifest['assets']]
    ids = [e['id'] for e in manifest['assets']]
    if not REQUIRED.issubset(roles) or 'sticker' not in roles or len(ids) != len(set(ids)):
        errors.append('Bundle requires GIF(s), banner, cover, icon and unique ids')
    for entry in manifest['sources']:
        try:
            if sha(local_file(folder, entry['file']).read_bytes()) != entry['sha256']:
                errors.append('Source hash mismatch: ' + entry['file'])
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
    for entry in manifest['assets']:
        try:
            actual = inspect(local_file(folder, entry['file']).read_bytes())
            validate_record(actual, entry['expected'])
            if actual['sha256'] != entry['sha256']:
                raise ValueError('Output hash mismatch')
            reports.append({'id': entry['id'], 'role': entry['role'], **actual})
        except (OSError, ValueError) as exc:
            errors.append(entry['id'] + ': ' + str(exc))
    return {'status': 'passed' if not errors else 'failed', 'assets': reports, 'errors': errors,
            'human_review': manifest['human_review'], 'platform_review': manifest['platform_review']}


def load_frames(path, item, threshold):
    cols, rows = pair(item['grid'], 'grid [columns, rows]')
    with Image.open(path) as src:
        im = src.convert('RGBA')
    if 'sheet_size' in item and im.size != pair(item['sheet_size'], 'sheet_size'):
        raise ValueError('Actual sheet size differs from sheet_size: ' + str(path))
    if im.width % cols or im.height % rows:
        raise ValueError('Sheet cannot be evenly divided into requested grid')
    cw, ch = im.width // cols, im.height // rows
    frames = []
    for i in range(cols * rows):
        cell = im.crop((i % cols * cw, i // cols * ch, (i % cols + 1) * cw, (i // cols + 1) * ch))
        alpha = cell.getchannel('A')
        if alpha.getextrema()[0] != 0:
            raise ValueError('Every cell must contain genuine transparent pixels')
        box = alpha.point(lambda a: 255 if a > threshold else 0).getbbox()
        if box is None:
            raise ValueError('Empty cell at index ' + str(i))
        # Stable lower-body center prevents arm motion from driving alignment.
        y0 = box[1] + round((box[3] - box[1]) * .72)
        lower = alpha.crop((0, y0, cw, box[3])).point(lambda a: 255 if a > threshold else 0).getbbox()
        center = (lower[0] + lower[2]) / 2 if lower else (box[0] + box[2]) / 2
        frames.append((cell, box, center))
    return frames


def encode_gif(frames, order, durations, threshold, matte, loop):
    samples = Image.new('RGB', (frames[0].width * len(frames), frames[0].height), matte)
    whites = []
    for i, frame in enumerate(frames):
        rgb = Image.new('RGBA', frame.size, matte)
        rgb.alpha_composite(frame)
        rgb = rgb.convert('RGB')
        samples.paste(rgb, (i * frame.width, 0))
        whites.append(rgb)
    palette = samples.quantize(colors=255, method=Image.Quantize.MEDIANCUT).getpalette()[:765]
    palette += palette[:3]  # reserved index duplicates index 0; remapping is lossless
    base = Image.new('P', (1, 1))
    base.putpalette(palette)
    quantized = []
    for frame, rgb in zip(frames, whites):
        q = rgb.quantize(palette=base, dither=Image.Dither.NONE)
        q = q.point(lambda value: 0 if value == 255 else value)
        q.putpalette(palette)
        mask = frame.getchannel('A').point(lambda value: 255 if value < threshold else 0)
        q.paste(255, mask=mask)
        quantized.append(q)
    seq = [quantized[i] for i in order]
    output = BytesIO()
    seq[0].save(output, format='GIF', save_all=True, append_images=seq[1:],
                duration=durations, loop=loop, transparency=255, disposal=2, optimize=False)
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--output', type=Path, help='New, nonexistent output directory')
    parser.add_argument('--check', action='store_true', help='Preflight only; writes nothing')
    parser.add_argument('--verify', type=Path, metavar='BUNDLE', help='Read-only bundle verification')
    args = parser.parse_args()
    if args.verify:
        if args.config or args.output or args.check:
            parser.error('--verify cannot be combined with build arguments')
        report = verify(args.verify.expanduser().resolve())
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report['status'] == 'passed' else 1
    if not args.config or (not args.check and not args.output):
        parser.error('Provide --config and --output (or --check)')
    config_path = args.config.expanduser().resolve()
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    if config.get('version') != 1:
        raise ValueError('Expected config version 1')
    size = pair(config.get('canvas', [240, 240]), 'canvas')
    threshold = config.get('alpha_threshold', 112)
    if type(threshold) is not int or not 1 <= threshold <= 254:
        raise ValueError('alpha_threshold must be between 1 and 254')
    box = config.get('character_box', [16, 12, size[0] - 16, size[1] - 46])
    if len(box) != 4 or not (0 <= box[0] < box[2] <= size[0] and 0 <= box[1] < box[3] <= size[1]):
        raise ValueError('character_box must fit inside canvas')
    script_path = Path(__file__).resolve()
    sources = {str(config_path): config_bytes, str(script_path): script_path.read_bytes()}

    def source(name):
        path = Path(name).expanduser()
        path = (config_path.parent / path).resolve() if not path.is_absolute() else path.resolve()
        sources[str(path)] = path.read_bytes()
        return path

    for name in config.get('provenance', []):
        source(name)
    planned, identifiers = [], set()

    def add(identifier, role, data, expected, suffix):
        safe_name(identifier)
        if identifier in identifiers:
            raise ValueError('Duplicate asset id: ' + identifier)
        identifiers.add(identifier)
        actual = inspect(data)
        validate_record(actual, expected)
        planned.append(({'id': identifier, 'role': role, 'file': 'upload/' + identifier + suffix,
                         'expected': expected, **actual}, data))

    stickers = config.get('stickers', [])
    if not stickers:
        raise ValueError('Provide at least one sticker')
    for item in stickers:
        path = source(item['sheet'])
        cells = load_frames(path, item, threshold)
        order = item.get('order', list(range(len(cells))))
        if not order or any(type(i) is not int or not 0 <= i < len(cells) for i in order):
            raise ValueError('order contains an invalid frame index')
        durations = item.get('durations_ms', [200] * len(order))
        if len(order) != len(durations) or any(type(d) is not int or d < 10 or d % 10 for d in durations):
            raise ValueError('One duration per timeline frame, positive multiples of 10 ms')
        offsets = item.get('offsets', [[0, 0]] * len(cells))
        if len(offsets) != len(cells) or any(len(v) != 2 or any(type(n) is not int for n in v) for v in offsets):
            raise ValueError('offsets needs one integer [x,y] pair per source cell')
        max_left = max(center - b[0] for _, b, center in cells)
        max_right = max(b[2] - center for _, b, center in cells)
        max_height = max(b[3] - b[1] for _, b, _ in cells)
        scale = min((box[2] - box[0]) / (2 * max(max_left, max_right)), (box[3] - box[1]) / max_height)
        font, caption = None, item.get('caption', '')
        if caption:
            font = ImageFont.truetype(str(source(config['font'])), positive(config.get('font_size', 26), 'font_size'))
        frames = []
        for i, (cell, bounds, center) in enumerate(cells):
            part = cell.crop(bounds)
            part = part.resize((max(1, round(part.width * scale)), max(1, round(part.height * scale))), Image.Resampling.LANCZOS)
            x = round((box[0] + box[2]) / 2 - (center - bounds[0]) * scale) + offsets[i][0]
            y = round(box[3] - part.height) + offsets[i][1]
            if x < 0 or y < 0 or x + part.width > size[0] or y + part.height > size[1]:
                raise ValueError('Pose or offset would clip character: ' + item['id'])
            frame = Image.new('RGBA', size)
            frame.alpha_composite(part, (x, y))
            if caption:
                draw = ImageDraw.Draw(frame)
                pos = (size[0] // 2, config.get('caption_y', size[1] - 22))
                text_box = draw.textbbox(pos, caption, font=font, anchor='mm', stroke_width=1)
                if text_box[0] < 0 or text_box[1] < 0 or text_box[2] > size[0] or text_box[3] > size[1]:
                    raise ValueError('Caption would clip; adjust font size or canvas')
                draw.text(pos, caption, font=font, anchor='mm', fill=config.get('text_color', '#44392F'),
                          stroke_width=1, stroke_fill='white')
            frames.append(frame)
        loop = item.get('loop', 0)
        if type(loop) is not int or not 0 <= loop <= 65535:
            raise ValueError('loop must be between 0 and 65535')
        data = encode_gif(frames, order, durations, threshold, config.get('matte', 'white'), loop)
        add(item['id'], 'sticker', data, {'format': 'GIF', 'size': list(size), 'transparent': True,
            'duration_ms': sum(durations), 'loop': loop, 'max_bytes': item.get('max_bytes')}, '.gif')
    companions = config.get('companions', {})
    if not REQUIRED.issubset(companions):
        raise ValueError('Companions must include banner, cover and icon')
    for role, spec in companions.items():
        if role not in REQUIRED | {'artist-avatar', 'artist-banner'}:
            raise ValueError('Unknown companion role: ' + role)
        target = pair(spec['size'], role + ' size')
        fmt = spec.get('format', 'PNG').upper()
        if fmt not in ('PNG', 'JPEG'):
            raise ValueError('Companion format must be PNG or JPEG')
        transparent = role in ('cover', 'icon')
        if transparent and fmt != 'PNG':
            raise ValueError('Cover and icon require PNG alpha')
        with Image.open(source(spec['source'])) as im:
            rgba = im.convert('RGBA')
        if not transparent and rgba.getchannel('A').getextrema() != (255, 255):
            raise ValueError('Opaque companion source required: ' + role)
        im = ImageOps.fit(rgba if transparent else rgba.convert('RGB'), target, Image.Resampling.LANCZOS)
        limit = spec.get('max_bytes')
        if limit is not None:
            positive(limit, 'max_bytes')
        for quality in ([None] if fmt == 'PNG' else [95, 90, 85, 80, 75, 70, 60]):
            out = BytesIO()
            options = {'optimize': True}
            if quality is not None:
                options.update(quality=quality, subsampling=0)
            im.save(out, format=fmt, **options)
            data = out.getvalue()
            if not limit or len(data) <= limit:
                break
        add(role, role, data, {'format': fmt, 'size': list(target), 'transparent': transparent,
                              'max_bytes': limit}, '.png' if fmt == 'PNG' else '.jpg')
    if args.check:
        print(json.dumps({'status': 'passed', 'mode': 'check-only', 'written_files': 0,
                          'assets': [e for e, _ in planned]}, ensure_ascii=False, indent=2))
        return 0
    folder = args.output.expanduser().resolve()
    skill = Path(__file__).resolve().parents[1]
    if folder == skill or skill in folder.parents:
        raise ValueError('Output cannot be inside the installed skill')
    if folder.exists():
        raise ValueError('Output already exists; choose a new version directory')
    folder.mkdir(parents=True, exist_ok=False)
    (folder / 'sources').mkdir()
    (folder / 'upload').mkdir()
    provenance = []
    for original, data in sources.items():
        filename = sha(data) + Path(original).suffix.lower()
        destination = folder / 'sources' / filename
        destination.write_bytes(data)
        provenance.append({'original': original, 'file': 'sources/' + filename, 'sha256': sha(data)})
    for entry, data in planned:
        (folder / entry['file']).write_bytes(data)
    manifest = {'version': 1, 'created_at_utc': datetime.now(timezone.utc).isoformat(),
                'pillow_version': Image.__version__, 'human_review': 'pending',
                'platform_review': 'pending', 'sources': provenance, 'assets': [e for e, _ in planned]}
    (folder / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    report = verify(folder)
    (folder / 'validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'bundle': str(folder), **report}, ensure_ascii=False, indent=2))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print('Error: ' + str(exc), file=sys.stderr)
        raise SystemExit(1)
