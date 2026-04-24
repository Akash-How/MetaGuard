import { Panel } from "../../components/ui/Panel";

export function StormWarningPanel() {
  return (
    <Panel
      title="Storm Warning"
      description="Surface schema-change risks and downstream breakage signals before incidents happen."
    >
      <span className="badge">Alert workflow pending</span>
    </Panel>
  );
}

