# Calm path (Remotion)

A second render path produces the slower **narrated** style: a Remotion composition (`src/Composition.tsx`,
registered as `MotoShort` in `src/Root.tsx`) at 1080x1920, 30 fps with ducked music, a voice track, an opening
hook, captions and a closing call to action.

`make_one.py spec.json` drives it: pre-encode the clip to 1080x1920, write props, `remotion render`, then
loudnorm. Specs come from `gen_batch_vo.py`, which writes voice files with word timings.

```console
npm i
npm run dev        # Remotion Studio preview
```

!!! note "Status"
    The viral path replaced this one for volume. The composition's `captions` prop is empty by default and no
    script in the viral path calls Remotion. Keep it for slower narrated formats or long-video clips.

!!! info "Remotion licence"
    Remotion is free for individuals and small teams but needs a company licence above that.
    Read [their terms](https://www.remotion.dev/license) before commercial use.
