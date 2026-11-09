# 5. Metadata and upload

## Metadata files

Each montage needs a `meta/<id>.json`:

```json
{
  "video": "out/g_pov_00.mp4",
  "title": "…  #Shorts",
  "description": "<one-line hook>\n\n<your signature line>\n\n<hashtags> #Shorts",
  "tags": ["moto", "motovlog"],
  "categoryId": "2",
  "lang": "fr",
  "privacy": "public",
  "publishAt": "2026-11-12T17:00:00Z"
}
```

`gen_batch.py` already writes title, tags and `publishAt` into `batch_manifest.json`. **Turning the manifest
into `meta/*.json` is not scripted yet** (see the [review](../review.md)). The description should always
carry your signature and hashtags.

## `upload_short.py`

Uploads each meta file with the YouTube Data API (`videos.insert`, resumable, 8 MB chunks).

- `publishAt` set: the video is uploaded **private** and goes public at that time.
- `uploadLimitExceeded`: waits `--retry-min` minutes and retries until `--max-hours`.
- Network errors: up to 5 retries, 20 s apart, with a 180 s socket timeout.
- `--dry-run` prints what would be sent; `--not-before HH:MM` delays the start.
- Writes `meta/_uploaded_<date>.json` (file → video id) when the batch ends.

## OAuth and the YouTube client

The uploader reuses the OAuth client and token of **social2shorts**
(`secrets/client_secret.json`, `secrets/token.json`) and its `get_credentials()`. Set the client up once with
social2shorts' guide, then run the uploader with `uv run` from that project so `social2shorts` is importable.

!!! info "Upload limits"
    Unverified channels are throttled to roughly 15 uploads per 24 h. Verifying the channel for
    *Advanced features* (6-second selfie video, ID, or channel history) lifts it. The review takes about
    24 h; re-submitting restarts the clock.

!!! warning "Disclosure flag"
    `containsSyntheticMedia` is currently hard-coded to `false`. Re-check YouTube's current altered/synthetic
    content rules for your use of a text-to-speech voice, and read the value from the meta file if needed.
