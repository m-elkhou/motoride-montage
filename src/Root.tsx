import React from 'react';
import {Composition} from 'remotion';
import {MotoShort, MotoShortProps} from './Composition';

// Rendu batch en 1080x1920 (depuis sources 4K = net, format telephone).
// Les vrais 4K masters se refont a la demande avec --scale=2.
export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="MotoShort"
      component={MotoShort}
      fps={30}
      width={1080}
      height={1920}
      durationInFrames={660}
      defaultProps={
        {
          clip: 'clip.mp4',
          music: 'movin.mp3',
          vo: 'vo.wav',
          hook: 'My kind of therapy',
          cta: 'Follow for the daily escape',
          style: 'day',
          voStartFrame: 60,
          voLenFrames: 390,
          captions: [],
          durationInFrames: 660,
        } as MotoShortProps
      }
      calculateMetadata={({props}) => ({
        durationInFrames: props.durationInFrames ?? 660,
      })}
    />
  );
};
