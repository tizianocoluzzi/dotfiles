"""Run with: python3 -B -m unittest discover -s scripts/iris-theme -p 'test_*.py'."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('adapter', Path(__file__).with_name('apply.py'))
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class LightContrastTests(unittest.TestCase):
    def test_light_palettes_and_application_pairs(self):
        for background in ('#ffffff', '#ec9e83', '#777777', '#111111'):
            with self.subTest(background=background):
                theme = dict(bg=background, fg='#777777', surface='#888888',
                             dim='#aaaaaa', accent='#ffff00', red='#ffaaaa',
                             green='#aaffaa', yellow='#eeeeaa')
                colors = adapter.roles(theme, 'light')
                panels = [colors[key] for key in ('surface', 'surface_container_highest', 'surface_variant')]
                for panel in panels:
                    self.assertGreaterEqual(adapter.contrast(colors['on_surface'], panel), 7)
                    for role in ('primary', 'secondary', 'tertiary', 'error', 'on_surface_variant'):
                        self.assertGreaterEqual(adapter.contrast(colors[role], panel), 4.5)
                bg = colors['background']
                waybar = adapter.application_roles(colors, 'waybar', 'light')
                for role in ('primary_fixed', 'primary_container', 'surface_container_high', 'surface_bright'):
                    self.assertGreaterEqual(adapter.contrast(waybar[role], bg), 4.5)
                kitty = adapter.application_roles(colors, 'kitty', 'light')
                for role in ('primary', 'secondary', 'tertiary', 'error'):
                    container = role + '_container'
                    self.assertGreaterEqual(adapter.contrast(kitty[container], bg), 4.5)
                    self.assertGreaterEqual(adapter.contrast(kitty['on_' + container], kitty[container]), 4.5)
                sway = adapter.application_roles(colors, 'sway', 'light')
                self.assertGreaterEqual(adapter.contrast(sway['on_secondary'], bg), 7)
                self.assertGreaterEqual(adapter.contrast(sway['primary_fixed'], bg), 4.5)
                self.assertEqual(adapter.application_roles(colors, 'kitty', 'dark'), colors)


if __name__ == '__main__':
    unittest.main()
