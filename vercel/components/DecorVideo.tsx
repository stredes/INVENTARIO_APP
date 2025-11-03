"use client";
import React from 'react';

type Props = {
  className?: string;
};

export default function DecorVideo({ className }: Props) {
  const src = process.env.NEXT_PUBLIC_DECOR_VIDEO_URL;
  const [hidden, setHidden] = React.useState(false);
  if (hidden) return null;
  return (
    <div className={`decor-box ${className || ''}`.trim()}>
      <video
        className="decor-video"
        autoPlay
        muted
        loop
        playsInline
        preload="auto"
        aria-hidden="true"
        onError={() => setHidden(true)}
      >
        {src ? (
          <source src={src} />
        ) : (
          <>
            
            <source src="/video.mp4" type="video/mp4" />
            <source src="/decor.mp4" type="video/mp4" />
          </>
        )}
      </video>
    </div>
  );
}
