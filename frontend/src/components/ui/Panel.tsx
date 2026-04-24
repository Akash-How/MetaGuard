import { ReactNode } from "react";

type PanelProps = {
  title: string;
  description: string;
  children?: ReactNode;
};

export function Panel({ title, description, children }: PanelProps) {
  return (
    <article className="panel">
      <h2>{title}</h2>
      <p>{description}</p>
      {children}
    </article>
  );
}

