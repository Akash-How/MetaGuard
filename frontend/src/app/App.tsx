import { useEffect, useMemo, useState } from "react";

import { AppShell } from "../components/layout/AppShell";
import {
  askChat,
  getBlastRadiusTable,
  getDeadDataScan,
  getDeadDataSummary,
  getHealthcheck,
  getPassport,
  getStormAlerts,
  getWatchedAssets,
  simulateStormAlert,
} from "../lib/api";

const DEMO_ASSETS = [
  "warehouse.commerce.curated.fct_orders",
  "warehouse.commerce.curated.customer_360",
  "warehouse.sales.raw.invoices_raw",
  "warehouse.logistics.staging.shipments_stg",
  "warehouse.finance.mart.budgets_summary",
] as const;

type Loadable<T> = {
  loading: boolean;
  error: string | null;
  data: T | null;
};

function createLoadable<T>(): Loadable<T> {
  return { loading: true, error: null, data: null };
}

export function App() {
  const [selectedAsset, setSelectedAsset] = useState<string>(DEMO_ASSETS[0]);
  const [healthStatus, setHealthStatus] = useState("Checking backend");
  const [deadSummary, setDeadSummary] = useState(createLoadable<any>());
  const [deadScan, setDeadScan] = useState(createLoadable<any>());
  const [passport, setPassport] = useState(createLoadable<any>());
  const [blast, setBlast] = useState(createLoadable<any>());
  const [stormAlerts, setStormAlerts] = useState(createLoadable<any>());
  const [watchedAssets, setWatchedAssets] = useState(createLoadable<any>());
  const [chatQuestion, setChatQuestion] = useState(
    "In Diagnostic: give me a business summary for this asset and call out trust risks.",
  );
  const [chatAnswer, setChatAnswer] = useState<Loadable<any>>({
    loading: false,
    error: null,
    data: null,
  });
  const [simulating, setSimulating] = useState(false);

  useEffect(() => {
    let active = true;

    async function loadGlobal() {
      try {
        await getHealthcheck();
        if (active) {
          setHealthStatus("Live backend connected to MetaGuard");
        }
      } catch {
        if (active) {
          setHealthStatus("Backend not reachable");
        }
      }

      try {
        const [summary, scan, alerts, watched] = await Promise.all([
          getDeadDataSummary(),
          getDeadDataScan(),
          getStormAlerts(),
          getWatchedAssets(),
        ]);

        if (!active) {
          return;
        }

        setDeadSummary({ loading: false, error: null, data: summary });
        setDeadScan({ loading: false, error: null, data: scan });
        setStormAlerts({ loading: false, error: null, data: alerts });
        setWatchedAssets({ loading: false, error: null, data: watched });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to load dashboard";
        if (!active) {
          return;
        }
        setDeadSummary({ loading: false, error: message, data: null });
        setDeadScan({ loading: false, error: message, data: null });
        setStormAlerts({ loading: false, error: message, data: null });
        setWatchedAssets({ loading: false, error: message, data: null });
      }
    }

    void loadGlobal();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;

    async function loadAsset() {
      setPassport(createLoadable());
      setBlast(createLoadable());

      try {
        const [passportResponse, blastResponse] = await Promise.all([
          getPassport(selectedAsset),
          getBlastRadiusTable(selectedAsset),
        ]);

        if (!active) {
          return;
        }

        setPassport({ loading: false, error: null, data: passportResponse });
        setBlast({ loading: false, error: null, data: blastResponse });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to load asset modules";
        if (!active) {
          return;
        }
        setPassport({ loading: false, error: message, data: null });
        setBlast({ loading: false, error: message, data: null });
      }
    }

    void loadAsset();

    return () => {
      active = false;
    };
  }, [selectedAsset]);

  const deadDataHighlights = useMemo(() => {
    const assets = deadScan.data?.assets ?? [];
    return assets.slice(0, 4);
  }, [deadScan.data]);

  async function handleSimulateStorm() {
    setSimulating(true);
    try {
      const alert = await simulateStormAlert({
        fqn: "warehouse.commerce.curated.fct_orders",
        changes: [
          {
            column: "order_total",
            change_type: "type_change",
            before: "DECIMAL",
            after: "VARCHAR",
          },
          {
            column: "customer_id",
            change_type: "drop_column",
            before: "VARCHAR",
            after: null,
          },
        ],
      });

      setStormAlerts((current) => {
        const alerts = current.data?.alerts ?? [];
        return {
          loading: false,
          error: null,
          data: {
            status: "ok",
            total: alerts.length + 1,
            alerts: [alert, ...alerts],
          },
        };
      });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Failed to simulate storm alert";
      setStormAlerts({ loading: false, error: message, data: null });
    } finally {
      setSimulating(false);
    }
  }

  async function handleAskChat() {
    setChatAnswer({ loading: true, error: null, data: null });
    try {
      const answer = await askChat({
        question: chatQuestion,
        entity_id: selectedAsset,
      });
      setChatAnswer({ loading: false, error: null, data: answer });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to ask chat";
      setChatAnswer({ loading: false, error: message, data: null });
    }
  }

  return (
    <AppShell>
      <section className="hero-banner">
        <div>
          <p className="eyebrow">OpenMetadata intelligence layer</p>
          <h2>Reviewer-ready metadata control center for risk, trust, and waste.</h2>
          <p className="hero-copy">
            MetaGuard is now connected to your local OpenMetadata instance with seeded
            warehouse assets built specifically for the demo story.
          </p>
        </div>
        <div className="hero-metrics">
          <div className="metric-tile">
            <span>Environment</span>
            <strong>{healthStatus}</strong>
          </div>
          <div className="metric-tile">
            <span>Demo service</span>
            <strong>warehouse</strong>
          </div>
          <div className="metric-tile">
            <span>Presentation asset</span>
            <strong>{selectedAsset.split(".").slice(-1)[0]}</strong>
          </div>
        </div>
      </section>

      <section className="control-strip">
        <div>
          <label className="field-label" htmlFor="asset-select">
            Focus asset
          </label>
          <select
            id="asset-select"
            className="field-input"
            value={selectedAsset}
            onChange={(event) => setSelectedAsset(event.target.value)}
          >
            {DEMO_ASSETS.map((asset) => (
              <option key={asset} value={asset}>
                {asset}
              </option>
            ))}
          </select>
        </div>
        <div className="control-actions">
          <button className="primary-button" onClick={() => void handleAskChat()}>
            Refresh AI summary
          </button>
          <button
            className="secondary-button"
            onClick={() => void handleSimulateStorm()}
            disabled={simulating}
          >
            {simulating ? "Simulating..." : "Initiate surveillance simulation"}
          </button>
        </div>
      </section>

      <section className="stats-strip">
        <article className="stat-card">
          <span>Waste at risk</span>
          <strong>
            ${deadSummary.data?.total_monthly_waste?.toFixed?.(2) ?? "--"}
          </strong>
          <small>Monthly storage and compute tied to stale assets</small>
        </article>
        <article className="stat-card">
          <span>Delete-ready assets</span>
          <strong>{deadSummary.data?.safe_to_delete_count ?? "--"}</strong>
          <small>Immediate cleanup wins from the Dead Data workflow</small>
        </article>
        <article className="stat-card">
          <span>Integrity signal</span>
          <strong>{passport.data?.trust_score?.total ?? "--"}</strong>
          <small>Current confidence score based on clinical metadata</small>
        </article>
        <article className="stat-card">
          <span>Blast radius score</span>
          <strong>{blast.data?.overall_risk_score ?? "--"}</strong>
          <small>Estimated downstream breakage exposure</small>
        </article>
      </section>

      <section className="dashboard-grid">
        <article className="feature-card feature-card-wide">
          <div className="feature-header">
            <div>
              <p className="feature-kicker">Dead Data</p>
              <h3>Cleanup pipeline with clear cost and safety signals</h3>
            </div>
            <span className="status-pill status-pill-warm">Cost recovery</span>
          </div>
          <p className="feature-body">
            The demo environment intentionally includes an orphan archive and a backup
            table so the reviewer can immediately see waste, deletion confidence, and
            why some assets still need human review.
          </p>
          <div className="chip-row">
            {deadSummary.data &&
              Object.entries(deadSummary.data.category_breakdown).map(([key, value]) => (
                <span className="chip" key={key}>
                  {key}: {String(value)}
                </span>
              ))}
          </div>
          <div className="list-block">
            {deadDataHighlights.map((asset: any) => (
              <div className="list-row" key={asset.fqn}>
                <div>
                  <strong>{asset.fqn}</strong>
                  <p>
                    {asset.category} · confidence {asset.confidence} · owner{" "}
                    {asset.owner ?? "unassigned"}
                  </p>
                </div>
                <div className="row-metrics">
                  <span>${asset.monthly_cost_estimate ?? 0}/mo</span>
                  <span>{asset.safe_to_delete ? "Safe" : "Review"}</span>
                </div>
              </div>
            ))}
            {!deadDataHighlights.length && <p className="empty-copy">No dead-data candidates loaded yet.</p>}
          </div>
        </article>

        <article className="feature-card">
          <div className="feature-header">
            <div>
              <p className="feature-kicker">Diagnostic Profile</p>
              <h3>Business narrative and integrity record for the selected asset</h3>
            </div>
            <span className="status-pill status-pill-cool">
              Score {passport.data?.trust_score?.total ?? "--"}
            </span>
          </div>
          {passport.loading && <p className="empty-copy">Calibrating Diagnostic Profile...</p>}
          {passport.error && <p className="empty-copy">{passport.error}</p>}
          {passport.data && (
            <>
              <p className="feature-body">{passport.data.summary}</p>
              <div className="score-grid">
                {Object.entries(passport.data.trust_score)
                  .filter(([key]) => key !== "total")
                  .map(([key, value]) => (
                    <div className="score-box" key={key}>
                      <span>{key}</span>
                      <strong>{String(value)}</strong>
                    </div>
                  ))}
              </div>
              <div className="detail-copy">
                <h4>Column guide</h4>
                <p>{passport.data.sections.column_guide}</p>
              </div>
            </>
          )}
        </article>

        <article className="feature-card">
          <div className="feature-header">
            <div>
              <p className="feature-kicker">Production Surveillance</p>
              <h3>Active monitoring for schema drift and production incidents</h3>
            </div>
            <span className="status-pill status-pill-alert">
              {stormAlerts.data?.total ?? 0} alerts
            </span>
          </div>
          <p className="feature-body">
            Use the simulation to trigger a risky schema change on
            <code> fct_orders </code> and show how MetaGuard converts drift into an 
            explainable surveillance workflow.
          </p>
          <div className="list-block">
            {(stormAlerts.data?.alerts ?? []).slice(0, 3).map((alert: any) => (
              <div className="list-row" key={alert.id}>
                <div>
                  <strong>{alert.summary}</strong>
                  <p>{alert.fqn}</p>
                </div>
                <div className="row-metrics">
                  <span>{alert.severity}</span>
                  <span>{alert.change_count} changes</span>
                </div>
              </div>
            ))}
            {!(stormAlerts.data?.alerts ?? []).length && (
              <p className="empty-copy">No alerts yet. Trigger the incident button above.</p>
            )}
          </div>
        </article>

        <article className="feature-card">
          <div className="feature-header">
            <div>
              <p className="feature-kicker">Blast Radius</p>
              <h3>Lineage impact report for proposed changes</h3>
            </div>
            <span className="status-pill status-pill-cool">
              Risk {blast.data?.overall_risk_score ?? "--"}
            </span>
          </div>
          {blast.data && (
            <>
              <p className="feature-body">
                {blast.data.total_impacted_assets} impacted assets.{" "}
                {(blast.data.warnings ?? []).join(" ")}
              </p>
              <div className="list-block compact-list">
                {(blast.data.nodes ?? []).slice(0, 4).map((node: any) => (
                  <div className="list-row" key={node.fqn}>
                    <div>
                      <strong>{node.fqn}</strong>
                      <p>{node.impact_tier}</p>
                    </div>
                    <div className="row-metrics">
                      <span>Risk {node.risk_score}</span>
                      <span>{node.hop_count} hops</span>
                    </div>
                  </div>
                ))}
                {!(blast.data.nodes ?? []).length && (
                  <p className="empty-copy">No downstream consumers found for this asset yet.</p>
                )}
              </div>
            </>
          )}
        </article>

        <article className="feature-card feature-card-wide">
          <div className="feature-header">
            <div>
              <p className="feature-kicker">Metadata Chat</p>
              <h3>Guided narrative layer for demo conversations</h3>
            </div>
            <span className="status-pill status-pill-warm">Presenter assist</span>
          </div>
          <div className="chat-box">
            <textarea
              className="chat-input"
              value={chatQuestion}
              onChange={(event) => setChatQuestion(event.target.value)}
            />
            <button className="primary-button" onClick={() => void handleAskChat()}>
              Ask MetaGuard
            </button>
          </div>
          <div className="detail-copy">
            <h4>Answer</h4>
            {chatAnswer.loading && <p>Thinking...</p>}
            {chatAnswer.error && <p>{chatAnswer.error}</p>}
            {chatAnswer.data && <p>{chatAnswer.data.answer}</p>}
            {!chatAnswer.loading && !chatAnswer.error && !chatAnswer.data && (
              <p>Ask for a passport summary, blast-radius explanation, or cleanup decision.</p>
            )}
          </div>
        </article>

        <article className="feature-card">
          <div className="feature-header">
            <div>
              <p className="feature-kicker">Watched Assets</p>
              <h3>Objects under schema monitoring</h3>
            </div>
          </div>
          <div className="list-block compact-list">
            {(watchedAssets.data?.watched_assets ?? []).slice(0, 6).map((asset: any) => (
              <div className="list-row" key={asset.fqn}>
                <div>
                  <strong>{asset.fqn}</strong>
                  <p>{asset.asset_type}</p>
                </div>
              </div>
            ))}
            {!(watchedAssets.data?.watched_assets ?? []).length && (
              <p className="empty-copy">No watched assets returned yet.</p>
            )}
          </div>
        </article>
      </section>
    </AppShell>
  );
}
