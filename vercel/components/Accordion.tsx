import React from 'react';

type Props = {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
};

export default function Accordion({ title, defaultOpen, children }: Props) {
  return (
    <details className="card" open={defaultOpen}>
      <summary>{title}</summary>
      <div className="content pad">{children}</div>
    </details>
  );
}

