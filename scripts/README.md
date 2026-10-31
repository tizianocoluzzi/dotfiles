# Iris palette, existing Matugen templates

This is an additive migration: no application configuration, stylesheet, Matugen
template or Matugen configuration needs editing. Iris chooses the colors; Matugen
4.2+ renders them using the existing template syntax. Requires Python 3.11+ and
Iris. Both generators are already installed on this machine.

## Run

Use the new picker directly:

```sh
bash "$HOME/dotfiles/scripts/iris-theme/select-wallpaper"
```

Or apply one wallpaper:

```sh
bash "$HOME/dotfiles/scripts/iris-theme/change-wallpaper" \
  "$HOME/Documents/wallpaper/Galassia.png" dark
```

`select-wallpaper` is the updated version of the first supplied script.
`change-wallpaper` is the replacement for the second. They work directly from
this directory, and resolve their location through symlinks. The installed
`~/.local/bin/change-wallpaper` has deliberately not been overwritten.

To keep the old picker, change only its invocation to:

```sh
bash "$HOME/dotfiles/scripts/iris-theme/change-wallpaper" "$SELECTED_WALL" "$MODE"
```

Alternatively, replace the body of the installed `change-wallpaper` with:

```bash
#!/usr/bin/env bash
exec bash "$HOME/dotfiles/scripts/iris-theme/change-wallpaper" "$@"
```

The new picker handles cancellation at either prompt and quotes wallpaper paths.
It excludes `wall.png`, the current-wallpaper symlink, from the choices.

## Preview before applying

```sh
python3 "$HOME/dotfiles/scripts/iris-theme/apply.py" \
  "$HOME/Documents/wallpaper/wall.png" light \
  --preview /tmp/iris-theme-light
```

Preview writes numbered output files and the mapped `palette.json` to the chosen
directory. It never installs application colors, changes the wallpaper link, or
runs reload hooks. Iris itself may cache its extracted palette. `--palette-json`
accepts saved Iris JSON for reproducible testing without invoking Iris.

## What changes at runtime

1. Run `iris IMAGE --dark 1|0 --json-only`.
2. Map Iris roles to the names consumed by the existing templates.
3. Read `~/.config/matugen/config.toml` for template paths, destinations and hooks.
4. Render via `matugen json` using a temporary config with staged destinations and
   no hooks. Validate unresolved expressions and generated JSON before installation.
5. Atomically replace each output, following existing output symlinks. This is
   atomic per file, not a transaction spanning every application; an installation
   I/O failure can leave some files updated and others unchanged.
6. Update `~/Documents/wallpaper/wall.png`, then execute the existing post-hooks.
   A failed reload is reported as a warning after colors have been installed.

The adapter supports the current configuration's `input_path`, `output_path` and
literal shell `post_hook` entries. It does not implement additional Matugen config
features such as pre-hooks, mode-specific template paths or templated hook commands.
There is no separate wallpaper setter: Sway's existing reload remains responsible
for displaying the wallpaper, as in the original setup.

The two existing GTK templates are empty and are skipped, leaving their current
outputs alone. To theme GTK later would require populated templates; this migration
does not change them.

## Palette policy

- `surface`/`background` = Iris `bg`; foreground = `fg`.
- Primary = `accent`; secondary = `yellow`; tertiary = `green`; error = `red`.
  Yellow and green retain the associations used by the existing Kitty template.
- Surface containers are progressively blended toward `fg` (0%, 3%, 6%, 9%, 12%).
- Accent containers blend 28% of the accent into the background.
- `on_*` foregrounds use the preferred color if contrast is at least 4.5:1,
  otherwise whichever of black or white has greater contrast.
- Fixed accents are light tints. Outline and muted text derive from `dim`.

These are compatibility roles, not a recreation of Material You. Iris still
determines the palette, and existing template filters and alpha suffixes remain
effective. Exact colors will differ from Matugen-generated themes.

### Light-mode contrast correction

Light mode additionally lightens the wallpaper-tinted background to relative
luminance 0.8 or greater. Normal text is darkened to reach 7:1 against generated
surface levels; muted text and accents target 4.5:1. Dark mode is unchanged.

The adapter renders each application with its own palette when necessary:
Waybar's container/fixed/surface roles used as labels are darkened; Kitty's pale
ANSI colors are darkened and their paired selection/tab foregrounds recalculated;
Sway's unfocused and inactive title pairs are corrected. Neovim's fixed accents
are darkened and its inverse-primary input compensates for the template's lighten
filter. Preview directories include numbered per-application palette JSON files.

These corrections live entirely in the adapter. They target the inspected
templates/styles and solid background pairs, not arbitrary future role usages,
transparency or composited backgrounds. Kitty color0 still equals its background
because the unchanged template uses the same role for both.

Run regression checks with:

```sh
python3 -B -m unittest discover -s scripts/iris-theme -p 'test_*.py'
```

## Rollback

Run the original `~/.local/bin/change-wallpaper` (if it has not been replaced), or
the original Matugen image command. It regenerates colors through the untouched
configuration and templates. No application imports need reverting.
