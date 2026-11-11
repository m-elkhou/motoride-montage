# 5. Metadata and upload

## Metadata: `scan/make_meta.py`

`gen_batch.py` writes titles, tags and `publishAt` into `batch_manifest.json`. `make_meta.py` turns it into one
`meta/<id>.json` per montage, which is what the uploader reads:

```console
python scan/make_meta.py                       # signature read from social2shorts' config.toml
python scan/make_meta.py --signature "📸 Follow me on Instagram: @handle"
```

```json
{
  "video": "…/out/g_pov_00.mp4",
  "title": "…  #Shorts",
  "privacy": "private",
  "publishAt": "2026-11-12T17:00:00Z",
  "categoryId": "2",
  "lang": "fr",
  "tags": ["moto", "motovlog"],
  "description": "<theme hook>\n\n<about>\n\n<call to subscribe>\n\n<your signature>\n\n#moto #motovlog … #Shorts"
}
```

- **Strict description rule** (`mm_description.py`, the same rule is enforced in social2shorts): the description is
  **always detailed** (hook, presentation, call to subscribe: at least 150 characters over two paragraphs), then
  **your signature** (it holds your Instagram), then a **last line made only of hashtags** (at least three). The
  signature is read from the local configuration, never written in the code.
- **No signature, no file**: the script stops; `--no-signature` exists only for tests and produces a file the uploader
  **refuses**. `upload_short.py` re-checks every meta against the rule before the first upload.
- Existing meta files are never overwritten without `--force`; a montage without a video is skipped with a warning.
- Texts can be overridden in `scan/gen_config.json` (`descriptions`).

## Uploading: `upload_short.py`

```console
uv run python upload_short.py "meta/g_*.json" --dry-run      # from the social2shorts folder
uv run python upload_short.py "meta/g_*.json" --retry-min 45 --max-hours 30
```

Arguments are files or **quoted patterns** (`*`, `?`, `[…]`); files starting with `_` are never treated as metadata.

| Behaviour | Detail |
|---|---|
| **Validated up front** | every meta is checked (fields, title ≤ 100, video exists, `privacy`, `publishAt`) **before** the first upload; an invalid one is reported and skipped, it no longer stops the batch |
| **Upload ledger** | each success is written to `meta/_uploaded.json` **immediately** (atomic write). A crash loses nothing, and a relaunch skips what already left. Older `meta/_uploaded_*.json` files are read too |
| Scheduling | `publishAt` set ⇒ uploaded **private**, public at that time |
| Quota | `uploadLimitExceeded` ⇒ wait `--retry-min` minutes and retry until `--max-hours` |
| Network | up to 5 retries, 20 s apart, 180 s socket timeout |
| Synthetic media | `containsSyntheticMedia` is read from the meta file (default `false`) |
| `--dry-run` | validates and lists, needs **no network and no token** |
| Exit code | `0` if everything left, `1` if failures or invalid files remain |

!!! warning "Disclosure flag"
    Re-check YouTube's current altered/synthetic content rules for your use of a text-to-speech voice, and set
    `"containsSyntheticMedia": true` in the meta file if they apply.

### Unattended run

`scan/_upload_launch.ps1` finds `meta/g_*.json` itself (pattern, retry and hours are parameters) and runs the
uploader from the social2shorts project. Start it **detached** so it survives the terminal:

```powershell
Start-Process powershell -ArgumentList '-NoProfile','-File','scan\_upload_launch.ps1' -WindowStyle Hidden
```

### OAuth and the YouTube client

The uploader reuses the OAuth client and token of **social2shorts** (`secrets/client_secret.json`,
`secrets/token.json`) and its `get_credentials()`. If `social2shorts` cannot be imported, the script says so and
points to `MM_S2S_ROOT` instead of failing with a stack trace. Set the client up once with social2shorts' guide.

!!! info "Upload limits"
    Unverified channels are throttled to roughly 15 uploads per 24 h. Verifying the channel for
    *Advanced features* (6-second selfie video, ID, or channel history) lifts it. The review takes about
    24 h; re-submitting restarts the clock.
