import { Panel } from "../../components/ui/Panel";

export function BlastRadiusPanel() {
  return (
    <Panel
      title="Blast Radius"
      description="Estimate the downstream impact of a proposed table or schema change using lineage."
    >
      <span className="badge">Lineage traversal pending</span>
    </Panel>
  );
}

