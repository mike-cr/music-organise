# music-organise

Move MP3 and FLAC files from a source folder into a destination folder using
their tags, then copy XSPF playlists into a destination folder with updated
`<location>` entries. Source playlist files are left in place unless you choose
to update playlists in place.

If the music source and destination are the same folder, files are moved within
that folder and empty folders are cleaned up after apply mode. Empty folders are
not cleaned up when the music source and destination are different.

The command runs in dry-run mode unless `--apply` is supplied.

## Install

```bash
python3 -m pip install -e .
```

On Arch Linux, install through the package manager from the local `PKGBUILD`
without building inside the repo:

```bash
scripts/install-arch-package.sh
```

The script copies `PKGBUILD` into a temporary directory and runs `makepkg -si`.

## Usage

Start the interactive TUI:

```bash
music-organise
```

Or explicitly:

```bash
music-organise --tui
```

In the TUI, press `Tab` while entering a path to autocomplete folders. The TUI
also asks whether to run in `dry-run` mode or `apply` mode; `dry-run` is the
default.

```bash
music-organise \
  /path/to/source-music \
  /path/to/destination-library \
  /path/to/source-playlists \
  /path/to/destination-playlists
```

Apply the changes:

```bash
music-organise \
  /path/to/source-music \
  /path/to/destination-library \
  /path/to/source-playlists \
  /path/to/destination-playlists \
  --apply
```

Run without installing the package:

```bash
PYTHONPATH=src python3 -m music_organise.cli \
  --tui
```

Or run the non-interactive command without installing:

```bash
PYTHONPATH=src python3 -m music_organise.cli \
  /path/to/source-music \
  /path/to/destination-library \
  /path/to/source-playlists \
  /path/to/destination-playlists
```

Available format fields:

- `{artist}`
- `{albumartist}`
- `{album}`
- `{title}`
- `{track}`
- `{disc}`
- `{disc_suffix}`: ` (Disc N)` when `{disc}` is greater than zero, otherwise empty
- `{year}`: leading four-digit year from date tags, for example `2006` from `2006-09-04`
- `{genre}`
- `{ext}`

The default format is:

```text
{artist}/{year} - {album}{disc_suffix}/{track:02d} - {title}{ext}
```

Playlist files are copied to the playlist destination folder, preserving their
relative folder structure. Locations are updated when they reference an organised
audio file as an absolute path, a `file://` URI, or a relative path from the
original playlist file. Updated relative paths are written relative to the
copied playlist's new location. Set the playlist source and destination to the
same folder to update playlists in place.

The app refuses to process a source folder when any track in that folder is
missing a date tag, or when tracks in that folder have different artists or
albums. It also refuses folders where tracks are missing track numbers or where
track numbers do not proceed sequentially for each disc. Track numbers must
start at 1 unless every track in the source folder has a disc number greater
than 1; in that case they may start later but must still be contiguous. If a
track has `discnumber` set to `1/1`, apply mode removes that disc tag and treats
it as no disc number.

Image files in the same folder as organised tracks are treated as cover art and
moved into each destination folder produced by tracks from that source folder.
Supported cover art extensions are `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`,
`.bmp`, `.tif`, and `.tiff`.
