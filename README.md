# FFXI Mobs · Batch Processor

**Import your models in Resonite. Pick a batch. Merge duplicate-material submeshes and fix the mob materials in one run.**

A Python CLI for **ResoniteLink**—not a model importer, and no AI service is needed to run it.

- **Native merge:** calls Resonite’s `MergeByMaterial()`.
- **Mob recipe:** XiexeToon → **Culling Off · Blend Mode Opaque**.
- **Your textures stay yours:** preserves texture references, tints, UVs and other source settings.
- **Repeatable:** already-correct models produce no changes.
- **You choose:** select models, review the preview, then type `APPLY`.
- **No automatic AI tags or license components.**

> **Save your world first.** Native merging is not transactional; diagnostic snapshots are not backups. This version processes XiexeToon mob materials, not the separate PBS environment workflow.

## Quick start

Requires **Python 3.11+**, your own locally available GLB catalog, and ResoniteLink enabled in a session you are authorized to edit. Run these from this repository’s folder.

Create the environment and install the pinned dependency—no shell activation required:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.txt
```

Start with a read-only preview. Replace `YOUR_LINK_PORT` with the port currently displayed by Resonite; replace the catalog path and scene parent with yours:

```sh
.venv/bin/python mob_processor.py --host ::1 --port YOUR_LINK_PORT --catalog-dir ./Catalog --parent-path 'Root/My Batch' --select all --dry-run
```

To process models, replace `--select all --dry-run` with `--apply`. You’ll get an interactive numbered selection, a preview, and a final `APPLY` prompt. If your models are directly under `Root`, omit `--parent-path`.

**Multiple families?** Both `--catalog-dir ./Catalog/aquan/*` and `--catalog-dir ./Catalog/*` work. Directory discovery is recursive; only matching models already present beneath the selected scene parent are candidates.

```text
Native import → Find matching slots → Select → Preview → APPLY
                                                   ↓
                                  Merge → Opaque + Culling Off
                                                   ↓
                                      Readback + no-op check
```

**Version: 1.2.0** · Expand the sections below for installation alternatives, flags, safety limits and troubleshooting.

---

<details>
<summary><strong>📦 Installation alternatives & offline tests</strong></summary>

Requires Python 3.11+. Live connections additionally require `websocket-client`. The activation example below is for **Bash/POSIX shells**; Fish users can use the activation-free Quick start above:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements.txt
sh ./FFXI-Mob-Processor.sh --help
sh ./FFXI-Mob-Processor.sh --version
python3 -B -m unittest discover -v
```

The POSIX launcher finds the source beside itself and uses `python3` from PATH (including an activated virtual environment). It does not install anything or require a fixed directory. On Windows, invoke `python mob_processor.py` directly. Help, version, and all 31 tests run offline using only the Python standard library; dependency installation is a separate network operation unless you provide a local package cache. No wheels are bundled.

</details>

<details>
<summary><strong>🎛️ Selection, flags & multi-folder examples</strong></summary>

Supply your own current ResoniteLink host and listening port. In the examples below, `$LINK_HOST` and `$LINK_PORT` must already be set in your shell; they are placeholders, not a saved endpoint. You can instead substitute literal values. Use the activated environment for the portable `sh` launcher, or invoke `.venv/bin/python mob_processor.py` directly as in Quick start:

```sh
sh ./FFXI-Mob-Processor.sh --host "$LINK_HOST" --port "$LINK_PORT" \
  --catalog-dir ./catalog --parent-path 'Root/My Batch' --select all --dry-run

sh ./FFXI-Mob-Processor.sh --host "$LINK_HOST" --port "$LINK_PORT" \
  --catalog-dir ./catalog --parent-path 'Root/My Batch' --apply
```

Create/populate `./catalog` yourself with GLB files whose names exactly match your imported child slots. Discovery is recursive, bounded at 100,000 GLB entries across deduplicated roots; selection is independently limited to 1–200 live imports before any model subtree reads. Files are used as a filename allowlist, not uploaded. Only operate on scenes you are authorized to modify. Save your world first and do not edit/move selected objects during processing.

- `--host`, `--port`, `--catalog-dir`: required connection and catalog inputs. `--catalog-dir` accepts multiple directories and repeated flags. Unquoted shell globs expand in Fish, Bash and POSIX shells; quote only a path containing spaces, not the wildcard. Direct GLB-file inputs and missing inputs are rejected; regular non-GLB files (such as a README expanded by `Catalog/*`) are ignored.
- Canonical overlapping directories are traversed once. Directory symlinks (including symlink ancestors of explicit roots) are rejected as inputs and skipped during traversal. Regular GLB file symlinks are allowed, including aliases to assets outside the catalog; broken links fail closed. Do not modify catalog directories during discovery.
- Names retain exact case. Duplicate filenames resolving to the same file or identical bytes are tolerated; conflicting bytes fail before connection. Only duplicate-name files are hashed, with cached SHA-256 results.
- Large catalogs do not trigger recursive world discovery: only exact direct child matches under the selected parent are listed, and only explicitly selected models are read (maximum 200).
- `--parent-path`: exact slash-separated unique slot names, starting at `Root` (default `Root`). No recursive world search.
- `--select '1,3'` or `--select all`: explicit deterministic name-sorted displayed indices. Omit to prompt; there is no default selection.
- `--select-name 'YourModel.glb'`: select one exact candidate name instead of indices. Do not combine with `--select`.
- `--dry-run`: read-only preview. This is also the default without `--apply`. It still connects to Resonite and writes local diagnostic files.
- `--apply`: preview, prompt for exact `APPLY`, revalidate selected inputs, then permit writes. No unattended confirmation option. Cannot combine with `--dry-run`.
- `--reference`: capture name used only by `--refresh-reference`; defaults to `ROM_375_102-Original-Idle.glb`. Normal batches use the recorded recipe and treat this filename like any other explicitly selected catalog match; there is no permanent exclusion.
- `--refresh-reference`: read-only capture of one exact reference beneath the parent. Validates the recorded Culling Off / BlendMode Opaque recipe and exits; does not update/expand the built-in recipe or process models. Cannot combine with `--apply`.
- `--output-dir`: diagnostic directory; defaults to `~/.local/state/ffxi-mob-processor`. Each run creates a new private run subdirectory.
- `--help`, `--version`: no connection required.

Duplicate candidate sibling names, user/avatar hierarchies, unresolved/oversized hierarchies, changed renderer state and incompatible native method signatures fail closed. Reference capture requires an exact unique reference. Normal batches have no reference prerequisite; duplicate names among actual catalog-matching siblings still fail closed.

### Multi-folder commands (Fish-compatible)

```sh
sh ./FFXI-Mob-Processor.sh --host "$LINK_HOST" --port "$LINK_PORT" --catalog-dir ./Catalog/aquan/* --apply
sh ./FFXI-Mob-Processor.sh --host "$LINK_HOST" --port "$LINK_PORT" --catalog-dir ./Catalog/* --apply
sh ./FFXI-Mob-Processor.sh --host "$LINK_HOST" --port "$LINK_PORT" --catalog-dir ./Catalog --select all --dry-run
```

The first two forms still prompt for explicit model selection and typed `APPLY`. A whole catalog is an allowlist, not permission to process every world object. `--parent-path` remains available to restrict the scene parent. If more than 200 models match, select a smaller subset; unselected model subtrees are not read.

</details>

<details>
<summary><strong>🛠️ What changes—and what stays untouched</strong></summary>

Deep rigs are read using depth-12 requests plus targeted continuation at observed reference-only child boundaries. Per selected import, discovery is limited to 5,000 slots, depth 128 and 256 slot requests. Continuation checks identity, parent edges, renamed slots and repeated IDs; unresolved stubs fail closed. No whole-world depth increase or mutation is used to fix truncation. These snapshots are sequential observations, not atomic world transactions.

The owner-approved recipe sets **XiexeToon Culling to Off and BlendMode to Opaque**. This corrects the earlier choice to preserve Cutout/alpha modes. Other public source material values, including texture references, tint, UVs, AlphaClip and vertex colors, are preserved. Other shader families and incompatible/missing Culling or BlendMode enum fields are rejected. Previously merged Culling-Off/Cutout models receive a material-only correction; converged Opaque/Off models remain no-ops. Changed materials are copied into the selected renderer slot and rebound; shared source materials are not modified.

Repeated material references are merged through native `MeshRenderer.MergeByMaterial()`, not by manually shortening a material list. The tool checks completion, ordering, mesh-provider replacement and bone-reference equality. It verifies new materials and bindings by readback and requires an empty second-pass plan.

Native merge is **non-transactional**. Failure can leave a merged renderer or an unattached material. There is no automatic rollback, reconnect, write replay or deletion. Inspect your scene and private journal before trying again. Bone-reference checks are not visual/animation validation. Visual appearance, animation and save/reload portability require your own verification. No avatar setup, AnimX generation, inventory saving or proprietary assets are included.

</details>

<details>
<summary><strong>🏷️ AI assistance, credits & tagging</strong></summary>

AI-assisted development: **Jorden / Hermes Agent**.

AI assistance applies to development of this script, not to the original game assets. Original FFXI artwork remains attributable to Square Enix; this repository supplies none of it.

Version 1.2.0 does **not create AI_GeneratedContent tags**, attribution components, or license components. Automatic tagging, its preview message and its reflection dependency have been removed. Existing tags on previously processed world objects are left untouched: there is no tag migration, editing or deletion. Script-development credit is not a license grant or a claim of ownership over imported assets.

</details>

<details>
<summary><strong>🔒 Privacy, test evidence & version history</strong></summary>

Runtime snapshots and journals can contain scene identifiers, asset URIs and session data. Keep them private; do not commit them. They are diagnostics, not world backups or safe permanent-ID restore scripts.

This publication contains only source, portable launcher, hash-pinned dependency requirement, documentation, tests and hand-authored synthetic fixtures. There are no captured scene fixtures, private IDs, user endpoints, machine-specific paths, live snapshots/journals, GLBs or PNGs. Synthetic fixtures are invented test input, **not live execution evidence**.

Version 1.1.1 changes the earlier v1.1.0 tagging behavior at the owner’s request; native-merge processing remains unchanged. Version 1.2.0 additionally supports recursive multi-folder catalogs, bounded deep rigs, normal selection of the former reference, and the owner-corrected Opaque blend recipe. The 31 offline tests use synthetic data, including full successful CLI apply coverage for new imports and imports with existing tags. They do not connect to a world. The portable launcher still resolves source beside itself and relies on an explicitly installed dependency; the separately deployed desktop launcher is unchanged. Private pilot reports and machine-specific instructions are omitted. Offline tests are not live world evidence.

</details>

<details>
<summary><strong>📄 License & game-asset rights</strong></summary>

No license grant is supplied in this publication pending the owner's license decision. Public availability alone is not an open-source license. Third-party dependencies retain their own licenses; no rights to game assets are granted.

</details>

<details>
<summary><strong>🩺 Troubleshooting & finish checklist</strong></summary>

- **Connection refused:** check ResoniteLink is enabled and use its current port. The port can change between sessions. `::1` is local IPv6; use the host on which your endpoint actually listens.
- **No matching models:** disk filenames must match imported slot names exactly. Catalog discovery is recursive, but scene matching checks direct children of `--parent-path`, not every object in the world.
- **Duplicate sibling names:** place batches beneath distinct parents and select one with `--parent-path`; the tool will not guess which duplicate you meant.
- **Unsupported material:** only XiexeToon is supported. It does not convert PBS/environment materials.
- **Hierarchy limit / changed state / merge timeout:** stop, inspect the printed evidence directory and scene, then investigate. Do not bypass checks or repeatedly apply while editing the models.
- **Nothing changed:** without `--apply` this is a preview. `Already converged` means the selected models already match the recipe.
- **Old AI tags remain:** this version neither adds nor removes tags. Existing tags require a separate deliberate cleanup.

After a successful apply:

- [ ] Check the models visually, including transparent-looking areas now set to Opaque.
- [ ] Check animation and deformation.
- [ ] Run another preview and confirm no further operations are proposed.
- [ ] Save and respawn a representative model before treating the batch as portable.

</details>
