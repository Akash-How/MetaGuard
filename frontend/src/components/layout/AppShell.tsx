import { ReactNode } from "react";

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  return (
    <main className="app-shell">
      <section className="hero">
        <h1>MetaGuard</h1>
        <p>
          Actionable metadata intelligence on top of OpenMetadata, now shaped as
          a live demo environment for waste reduction, trust scoring, change
          risk, impact analysis, and metadata chat.
        </p>
      </section>
      {children}
    </main>
  );
}
