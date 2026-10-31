#!/usr/bin/env python3
"""Supply Iris colors to existing Matugen templates; Python 3.11+ required."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib


def rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def mix(a, b, amount):
    return '#' + ''.join(f'{round(x + (y - x) * amount):02x}'
                         for x, y in zip(rgb(a), rgb(b)))


def luminance(color):
    channels = [c / 255 for c in rgb(color)]
    linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4
              for c in channels]
    return sum(c * w for c, w in zip(linear, (.2126, .7152, .0722)))


def contrast(a, b):
    x, y = sorted((luminance(a), luminance(b)))
    return (y + .05) / (x + .05)


def foreground(background, preferred):
    if contrast(background, preferred) >= 4.5:
        return preferred
    return max(('#000000', '#ffffff'), key=lambda c: contrast(background, c))


def darken_for_text(color, backgrounds, target=4.5):
    """Keep as much of the original color as possible, checking rounded RGB."""
    for step in range(101):
        candidate = mix(color, '#000000', step / 100)
        if all(contrast(candidate, background) >= target for background in backgrounds):
            return candidate
    raise ValueError(f'Cannot reach {target}:1 contrast on the supplied light backgrounds')


def light_roles(colors):
    colors = colors.copy()
    backgrounds = [value for name, value in colors.items()
                   if name in ('background', 'surface', 'surface_variant', 'surface_dim')
                   or name.startswith('surface_container')]
    for name in ('on_surface', 'on_background'):
        colors[name] = darken_for_text(colors[name], backgrounds, 7)
    for name in ('on_surface_variant', 'outline', 'outline_variant'):
        colors[name] = darken_for_text(colors[name], backgrounds)
    for name in ('primary', 'secondary', 'tertiary', 'error'):
        colors[name] = darken_for_text(colors[name], backgrounds)
        colors['on_' + name] = foreground(colors[name], colors['background'])
    colors['surface_tint'] = colors['primary']
    return colors


def application_roles(colors, name, mode):
    """Adapt role semantics to the unchanged templates, not the stylesheets."""
    result = colors.copy()
    if mode != 'light':
        return result
    bg = result['background']
    if name == 'waybar':
        # These background-like roles are used as label colors in style.css.
        for role in ('primary_fixed', 'primary_container', 'surface_container_high',
                     'surface_bright'):
            result[role] = darken_for_text(result[role], [bg])
    elif name == 'kitty':
        for role in ('surface_variant', 'secondary_fixed_dim', 'tertiary_fixed_dim',
                     'on_secondary_fixed_variant', 'on_tertiary_fixed_variant'):
            result[role] = darken_for_text(result[role], [bg])
        for role in ('primary', 'secondary', 'tertiary', 'error'):
            container = role + '_container'
            result[container] = darken_for_text(result[container], [bg])
            # The same containers also back selections, tabs and prompt bubbles.
            result['on_' + container] = foreground(result[container], bg)
    elif name == 'sway':
        # Unfocused titles use on_secondary over background, not secondary.
        result['on_secondary'] = darken_for_text(result['on_secondary'], [bg], 7)
        # Inactive titles use surface (light) as text over primary_fixed.
        result['primary_fixed'] = darken_for_text(result['primary_fixed'], [bg])
        result['primary_fixed_dim'] = result['primary_fixed']
        result['on_tertiary'] = foreground(result['tertiary_container'], result['on_surface'])
    elif name == 'neovim':
        backgrounds = [result[key] for key in ('surface', 'surface_container_highest')]
        for role in ('primary_fixed_dim', 'secondary_fixed_dim', 'tertiary_fixed_dim'):
            result[role] = darken_for_text(result[role], backgrounds)
        # The unchanged JSON template lightens this input by 20 percentage points.
        result['inverse_primary'] = mix(result['primary'], '#000000', .85)
    return result


def roles(theme, mode):
    for key in ('bg', 'fg', 'surface', 'dim', 'accent', 'red', 'green', 'yellow'):
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', str(theme.get(key, ''))):
            raise ValueError(f'Iris palette has invalid or missing {key!r}')
    bg, fg = theme['bg'], theme['fg']
    dark = mode == 'dark'
    if not dark:
        # Iris can call a saturated midtone a light background. Retain its tint
        # while giving dark text sufficient luminance headroom on raised panels.
        bg = next(mix(bg, '#ffffff', step / 100) for step in range(101)
                  if luminance(mix(bg, '#ffffff', step / 100)) >= .8)
    result = dict(background=bg, on_background=fg, surface=bg, on_surface=fg,
                  surface_variant=theme['surface'] if dark else mix(bg, fg, .06),
                  on_surface_variant=theme['dim'],
                  outline=theme['dim'], outline_variant=mix(bg, fg, .25),
                  shadow='#000000', scrim='#000000', surface_tint=theme['accent'],
                  inverse_surface=fg, inverse_on_surface=bg)
    # Keep five distinct elevation levels, even on nearly monochrome wallpapers.
    for suffix, amount in [('lowest', 0), ('low', .03), ('', .06),
                           ('high', .09), ('highest', .12)]:
        name = 'surface_container' + ('_' + suffix if suffix else '')
        result[name] = mix(bg, fg, amount)
    result['surface_dim'] = bg if dark else mix(bg, fg, .12)
    result['surface_bright'] = mix(bg, fg, .12) if dark else bg
    # Preserve the existing templates' terminal associations: yellow and green.
    for name, source in [('primary', 'accent'), ('secondary', 'yellow'),
                         ('tertiary', 'green'), ('error', 'red')]:
        accent = theme[source]
        container = mix(bg, accent, .28)
        result.update({name: accent, f'on_{name}': foreground(accent, bg),
                       f'{name}_container': container,
                       f'on_{name}_container': foreground(container, fg)})
        if name != 'error':
            fixed = mix(accent, '#ffffff', .65)
            fixed_dim = mix(accent, '#ffffff', .4)
            result.update({f'{name}_fixed': fixed, f'{name}_fixed_dim': fixed_dim,
                           f'on_{name}_fixed': foreground(fixed, '#202020'),
                           f'on_{name}_fixed_variant': foreground(fixed_dim, '#303030')})
    result['inverse_primary'] = mix(theme['accent'], '#000000' if dark else '#ffffff', .3)
    return result if dark else light_roles(result)


def atomic_write(destination, content):
    # Resolve existing symlinks so application includes and dotfile links survive.
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + destination.name, dir=destination.parent)
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(content)
        os.chmod(temporary, destination.stat().st_mode & 0o777 if destination.exists() else 0o644)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wallpaper', type=Path)
    parser.add_argument('mode', choices=('light', 'dark'))
    parser.add_argument('--config', type=Path, default=Path.home() / '.config/matugen/config.toml')
    parser.add_argument('--preview', type=Path, help='Render here without installing files or running hooks')
    parser.add_argument('--palette-json', type=Path, help='Use saved Iris JSON instead of invoking Iris')
    parser.add_argument('--wallpaper-link', type=Path, help='Update this symlink after installing colors, before hooks')
    args = parser.parse_args()
    wallpaper = args.wallpaper.expanduser().resolve(strict=True)
    config_path = args.config.expanduser().resolve(strict=True)
    config = tomllib.loads(config_path.read_text())
    if args.wallpaper_link and not args.preview:
        link = args.wallpaper_link.expanduser().absolute()
        if link.exists() and not link.is_symlink():
            raise ValueError(f'Refusing to replace a regular wallpaper file: {link}')
    matugen = shutil.which('matugen') or str(Path.home() / '.cargo/bin/matugen')
    if args.palette_json:
        theme = json.loads(args.palette_json.read_text())
    else:
        iris = shutil.which('iris') or str(Path.home() / '.local/bin/iris')
        theme = json.loads(subprocess.check_output(
            [iris, str(wallpaper), '--dark', '1' if args.mode == 'dark' else '0', '--json-only'], text=True))
    colors = roles(theme, args.mode)
    data = {'colors': {name: {scheme: {'color': color} for scheme in (args.mode, 'default')}
                       for name, color in colors.items()}, 'image': str(wallpaper), 'mode': args.mode}
    with tempfile.TemporaryDirectory(prefix='iris-theme-') as temporary:
        stage = Path(temporary)
        palette = stage / 'palette.json'
        palette.write_text(json.dumps(data))
        entries = []
        for index, (name, entry) in enumerate(config.get('templates', {}).items()):
            source = Path(entry['input_path']).expanduser()
            if not source.is_absolute():
                source = config_path.parent / source
            if not source.read_text().strip():
                print(f'Skipping empty template: {name}', file=sys.stderr)
                continue
            rendered = stage / f'{index}-{Path(entry["output_path"]).name}'
            destination = Path(entry['output_path']).expanduser()
            if not destination.is_absolute():
                destination = config_path.parent / destination
            entries.append((name, rendered, destination, entry.get('post_hook')))
            lines = ['[config]', f'[templates.{json.dumps(name)}]',
                          f'input_path = {json.dumps(str(source))}',
                          f'output_path = {json.dumps(str(rendered))}']
            app_colors = application_roles(colors, name, args.mode)
            app_data = dict(data, colors={key: {scheme: {'color': value}
                                               for scheme in (args.mode, 'default')}
                                         for key, value in app_colors.items()})
            app_palette = stage / f'{index}-palette.json'
            app_palette.write_text(json.dumps(app_data))
            staging_config = stage / 'config.toml'
            staging_config.write_text('\n'.join(lines) + '\n')
            subprocess.run([matugen, 'json', str(app_palette), '--mode', args.mode,
                            '--config', str(staging_config)], check=True)
        # Validate every output before touching any live destination.
        for name, rendered, destination, hook in entries:
            content = rendered.read_text()
            if '{{' in content or '<*' in content:
                raise ValueError(f'Unresolved template expression in {name}')
            if destination.suffix == '.json':
                json.loads(content)
        if args.preview:
            args.preview.mkdir(parents=True, exist_ok=True)
            for name, rendered, destination, hook in entries:
                shutil.copyfile(rendered, args.preview / rendered.name)
            shutil.copyfile(palette, args.preview / 'palette.json')
            for app_palette in stage.glob('*-palette.json'):
                shutil.copyfile(app_palette, args.preview / app_palette.name)
            print(f'Preview written to {args.preview.resolve()}; no live files or hooks changed.')
            return
        for name, rendered, destination, hook in entries:
            atomic_write(destination, rendered.read_bytes())
        if args.wallpaper_link:
            link = args.wallpaper_link.expanduser().absolute()
            link.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='.iris-link-', dir=link.parent) as directory:
                pending = Path(directory) / 'wallpaper'
                pending.symlink_to(wallpaper)
                os.replace(pending, link)
        # Hooks come from the user's existing trusted Matugen config.
        for name, rendered, destination, hook in entries:
            if hook and subprocess.run(hook, shell=True, cwd=config_path.parent).returncode:
                print(f'Warning: {name} reload hook failed; colors were installed.', file=sys.stderr)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        sys.exit(f'iris-theme: {error}')
