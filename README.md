# FFXI mob processor — v1.1.1

Selected native ResoniteLink processing of manually imported models. This is **not an importer**: import your own GLBs with Resonite first. The processor matches immediate GLB filenames in a local catalog to direct child slots beneath an explicit scene parent, previews selected renderer operations, and requires `--apply` plus typed `APPLY` before any world writes.

## Install and offline checks

Requires Python 3.11+. Live connections additionally require `websocket-client`:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements.txt
sh ./FFXI-Mob-Processor.sh --help
sh ./FFXI-Mob-Processor.sh --version
python3 -B -m unittest discover -v
```

The POSIX launcher finds the source beside itself and uses `python3` from PATH (including an activated virtual environment). It does not install anything or require a fixed directory. On Windows, invoke `python mob_processor.py` directly. Help, version, and all 20 tests run offline using only the Python standard library; dependency installation is a separate network operation unless you provide a local package cache. No wheels are bundled.

## Usage

Supply your own current ResoniteLink host and listening port. These shell variables are placeholders, not a saved user endpoint:

```sh
sh ./FFXI-Mob-Processor.sh --host "$LINK_HOST" --port "$LINK_PORT" \
  --catalog-dir ./catalog --parent-path 'Root/My Batch' --select all --dry-run

sh ./FFXI-Mob-Processor.sh --host "$LINK_HOST" --port "$LINK_PORT" \
  --catalog-dir ./catalog --parent-path 'Root/My Batch' --apply
```

Create/populate `./catalog` yourself with 1–200 immediate GLB files whose names exactly match your imported child slots. Files are used as a filename allowlist, not uploaded. Only operate on scenes you are authorized to modify. Save your world first and do not edit/move selected objects during processing.

- `--host`, `--port`, `--catalog-dir`: required connection and catalog inputs.
- `--parent-path`: exact slash-separated unique slot names, starting at `Root` (default `Root`). No recursive world search.
- `--select '1,3'` or `--select all`: explicit deterministic name-sorted displayed indices. Omit to prompt; there is no default selection.
- `--select-name 'YourModel.glb'`: select one exact candidate name instead of indices. Do not combine with `--select`.
- `--dry-run`: read-only preview. This is also the default without `--apply`. It still connects to Resonite and writes local diagnostic files.
- `--apply`: preview, prompt for exact `APPLY`, revalidate selected inputs, then permit writes. No unattended confirmation option. Cannot combine with `--dry-run`.
- `--reference`: protected reference name; defaults to `ROM_375_102-Original-Idle.glb`. Both that built-in name and the supplied reference name are excluded from candidates. Normal batches do not require a live reference.
- `--refresh-reference`: read-only capture of one exact reference beneath the parent. Validates the recorded Culling Off recipe and exits; does not update/expand the built-in recipe or process models. Cannot combine with `--apply`.
- `--output-dir`: diagnostic directory; defaults to `~/.local/state/ffxi-mob-processor`. Each run creates a new private run subdirectory.
- `--help`, `--version`: no connection required.

Duplicate candidate sibling names, user/avatar hierarchies, truncated hierarchies, changed renderer state and incompatible native method signatures fail closed. Reference absence/movement/duplication does not block ordinary batches, but does block reference capture when an exact unique reference cannot be found.

## Processing behavior and limits

The recorded recipe changes **only XiexeToon Culling to Off**. Other public source material values, including texture references, tint, UVs, blend/cutout and vertex colors, are preserved. Other shader families and incompatible/missing Culling fields are rejected. Changed materials are copied into the selected renderer slot and rebound; shared source materials are not modified.

Repeated material references are merged through native `MeshRenderer.MergeByMaterial()`, not by manually shortening a material list. The tool checks completion, ordering, mesh-provider replacement and bone-reference equality. It verifies new materials and bindings by readback and requires an empty second-pass plan.

Native merge is **non-transactional**. Failure can leave a merged renderer or an unattached material. There is no automatic rollback, reconnect, write replay or deletion. Inspect your scene and private journal before trying again. Bone-reference checks are not visual/animation validation. Visual appearance, animation and save/reload portability require your own verification. No avatar setup, AnimX generation, inventory saving or proprietary assets are included.

## Attribution

AI-assisted development: **Jorden / Hermes Agent**.

AI assistance applies to development of this script, not to the original game assets. Original FFXI artwork remains attributable to Square Enix; this repository supplies none of it.

Version 1.1.1 does **not create AI_GeneratedContent tags**, attribution components, or license components. Automatic tagging, its preview message and its reflection dependency have been removed. Existing tags on previously processed world objects are left untouched: there is no tag migration, editing or deletion. Script-development credit is not a license grant or a claim of ownership over imported assets.

## Privacy and publication differences

Runtime snapshots and journals can contain scene identifiers, asset URIs and session data. Keep them private; do not commit them. They are diagnostics, not world backups or safe permanent-ID restore scripts.

This publication contains only source, portable launcher, hash-pinned dependency requirement, documentation, tests and hand-authored synthetic fixtures. There are no captured scene fixtures, private IDs, user endpoints, machine-specific paths, live snapshots/journals, GLBs or PNGs. Synthetic fixtures are invented test input, **not live execution evidence**.

Version 1.1.1 changes the earlier v1.1.0 tagging behavior at the owner’s request; material and native-merge processing remain unchanged. The 20 offline tests use synthetic data, including full successful CLI apply coverage for new imports and imports with existing tags. They do not connect to a world. The portable launcher still resolves source beside itself and relies on an explicitly installed dependency; the separately deployed desktop launcher is unchanged. Private pilot reports and machine-specific instructions are omitted. Offline tests are not live world evidence.

## License

No license grant is supplied in this publication pending the owner's license decision. Public availability alone is not an open-source license. Third-party dependencies retain their own licenses; no rights to game assets are granted.
