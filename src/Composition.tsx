import React from 'react';
import {
  AbsoluteFill,
  Audio,
  OffthreadVideo,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

export type Caption = {from: number; to: number; text: string};
export type StyleName = 'day' | 'night' | 'raw';

export type MotoShortProps = {
  clip: string;
  music: string;
  vo: string;
  hook: string;
  cta: string;
  style: StyleName;
  voStartFrame: number;
  voLenFrames: number;
  captions: Caption[];
  durationInFrames: number;
};

const THEMES: Record<StyleName, {hook: string; cta: string; hookSize: number}> = {
  day: {hook: '#ffffff', cta: '#ffd400', hookSize: 70},
  night: {hook: '#19e6ff', cta: '#ffffff', hookSize: 70},
  raw: {hook: '#ffffff', cta: '#ff2e2e', hookSize: 74},
};

const OUTLINE = '0 3px 10px rgba(0,0,0,0.85), 0 0 5px rgba(0,0,0,0.95)';
const FONT_BLACK = '"Arial Black", Arial, sans-serif';

export const MotoShort: React.FC<MotoShortProps> = ({
  clip,
  music,
  vo,
  hook,
  cta,
  style,
  voStartFrame,
  voLenFrames,
  captions,
}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const theme = THEMES[style] ?? THEMES.day;

  // Musique calme en lit, duckee sous la voix.
  const voEnd = voStartFrame + voLenFrames;
  const musicVol = interpolate(
    frame,
    [voStartFrame - 12, voStartFrame + 6, voEnd - 6, voEnd + 12],
    [0.2, 0.09, 0.09, 0.2],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );

  // Hook : 0 -> ~2.7 s, pop + fade.
  const hookOp = interpolate(frame, [0, 10, 72, 84], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const hookScale = interpolate(frame, [0, 12], [0.86, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  // CTA : fin.
  const ctaStart = durationInFrames - 78;
  const ctaOp = interpolate(
    frame,
    [ctaStart, ctaStart + 10, durationInFrames - 10, durationInFrames],
    [0, 1, 1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );

  const active = captions.find((c) => frame >= c.from && frame <= c.to);

  return (
    <AbsoluteFill style={{backgroundColor: 'black'}}>
      <OffthreadVideo src={staticFile(clip)} />
      <Audio src={staticFile(music)} volume={musicVol} />
      <Sequence from={voStartFrame}>
        <Audio src={staticFile(vo)} volume={0.95} />
      </Sequence>

      {/* HOOK */}
      <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center', paddingTop: 150}}>
        <div
          style={{
            opacity: hookOp,
            transform: `scale(${hookScale})`,
            color: theme.hook,
            fontFamily: FONT_BLACK,
            fontWeight: 900,
            fontSize: theme.hookSize,
            letterSpacing: 1,
            textAlign: 'center',
            textShadow: OUTLINE,
            maxWidth: 940,
            lineHeight: 1.06,
            textTransform: 'uppercase',
            padding: '0 40px',
          }}
        >
          {hook}
        </div>
      </AbsoluteFill>

      {/* SOUS-TITRES */}
      {active ? (
        <AbsoluteFill style={{justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 470}}>
          <div
            style={{
              color: '#ffffff',
              fontFamily: 'Arial, sans-serif',
              fontWeight: 800,
              fontSize: 44,
              textAlign: 'center',
              textShadow: OUTLINE,
              maxWidth: 920,
              lineHeight: 1.14,
              whiteSpace: 'pre-line',
              padding: '0 40px',
            }}
          >
            {active.text}
          </div>
        </AbsoluteFill>
      ) : null}

      {/* CTA */}
      <AbsoluteFill style={{justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 270}}>
        <div
          style={{
            opacity: ctaOp,
            color: theme.cta,
            fontFamily: FONT_BLACK,
            fontWeight: 900,
            fontSize: 50,
            textAlign: 'center',
            textShadow: OUTLINE,
            padding: '0 40px',
          }}
        >
          {cta}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
