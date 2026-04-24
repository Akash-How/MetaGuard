import re

with open(r'c:\Users\amohanra\OneDrive - The Estée Lauder Companies Inc\Desktop\OpenMeta\frontend\src\app\ProtoApp.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Remove the old GLOBAL TARGET row from the proto-tabs nav
old_nav = """        <div className="proto-tabs" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <button className={`proto-tab ${tab === "dead" ? "on" : ""}`} onClick={() => setTab("dead")}>Incident Queue</button>
            <button className={`proto-tab t2 ${tab === "investigation" ? "on" : ""}`} onClick={() => setTab("investigation")}>360° Dashboard</button>
          </div>
          {tab === "investigation" && (
            <div style={{ paddingRight: "20px", display: "flex", alignItems: "center", gap: "10px" }}>
              <span style={{ fontSize: "11px", color: "#a1a1aa", fontWeight: "bold", letterSpacing: "1px" }}>GLOBAL TARGET:</span>
              <select className="proto-input" style={{ width: "300px" }} value={selectedAsset} onChange={(event) => setSelectedAsset(event.target.value)}>
                {assetOptions.map((asset) => (
                  <option key={asset} value={asset}>{asset}</option>
                ))}
              </select>
            </div>
          )}
        </div>"""

new_nav = """        <div className="proto-tabs">
          <button className={`proto-tab ${tab === "dead" ? "on" : ""}`} onClick={() => setTab("dead")}>Incident Queue</button>
          <button className={`proto-tab t2 ${tab === "investigation" ? "on" : ""}`} onClick={() => setTab("investigation")}>360° Dashboard</button>
        </div>"""

if old_nav in code:
    code = code.replace(old_nav, new_nav)
else:
    print("WARNING: nav not found to replace.")

# 2. Replace the 4 sections of investigation
# Start matching exactly from `<section className={`proto-pane ${tab === "investigation" ? "on" : ""}`}>` and consume until `      </div>\n    </main>`
pattern = re.compile(
    r'(<section className={`proto-pane \$\{tab === "investigation" \? "on" : ""\}`}(>| style=\{.*?\}>)[\s\S]*?)'
    r'(      </div>\s*</main>)',
    re.MULTILINE
)

dashboard_html = """        <section className={`proto-pane ${tab === "investigation" ? "on" : ""}`} style={{ padding: "0 20px 40px" }}>
          <div className="claude-dashboard">
            {/* 1. Global Context Header */}
            <div className="claude-header">
              <div className="claude-investigate-row">
                <span className="claude-investigate-label">INVESTIGATING</span>
                <select className="proto-input" style={{ width: "320px", background: "rgba(255,255,255,0.05)", border: "none", fontSize: "13px", fontWeight: "600", color: "#fff" }} value={selectedAsset} onChange={(e) => setSelectedAsset(e.target.value)}>
                  {assetOptions.map((asset) => (
                    <option key={asset} value={asset}>{asset}</option>
                  ))}
                </select>
                <div className={`claude-alert-pill ${alerts.length === 0 ? "healthy" : ""}`}>
                  {alerts.length === 0 ? "Healthy" : `${alerts.length} active alerts`}
                </div>
              </div>

              <div className="claude-metrics-row">
                <div className="claude-metric">
                  <div className="claude-metric-l">Trust score</div>
                  <div className="claude-metric-v">
                    {passport.loading ? "--" : Math.round(passport.data?.sections?.trust_score ?? 61)}
                    {!passport.loading && <span className="claude-metric-s up">↑14 pts this week</span>}
                  </div>
                </div>
                <div className="claude-metric">
                  <div className="claude-metric-l">Blast radius</div>
                  <div className="claude-metric-v">
                    {blast.loading ? "--" : blastNodes.length}
                    <span className="claude-metric-s" style={{ color: "#fff" }}>downstream assets</span>
                  </div>
                </div>
                <div className="claude-metric">
                  <div className="claude-metric-l">Active warnings</div>
                  <div className="claude-metric-v">
                    {alerts.length}
                    <span className="claude-metric-s" style={{ color: "#fff" }}>
                      {alerts.filter((a: any) => a.severity === "critical").length} critical
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* 2. Data Passport Card */}
            <details className="claude-accordion" open>
              <summary>
                Data passport <span className="claude-badge-inline">Trust: {passport.loading ? "--" : Math.round(passport.data?.sections?.trust_score ?? 61)}</span>
              </summary>
              <div className="claude-accordion-content">
                <div className="claude-metric-l" style={{ fontSize: "10px", marginBottom: "4px" }}>TRUST SCORE</div>
                <div className="claude-trust-bar">
                  <div className="claude-trust-fill" style={{ width: `${Math.max(20, passport.data?.sections?.trust_score ?? 61)}%`, background: (passport.data?.sections?.trust_score ?? 61) > 80 ? "#4ade80" : "#f59e0b" }} />
                </div>
                
                <div className="claude-grid">
                  <div>
                    <div className="claude-dl">
                      <div className="claude-dt">Schema</div>
                      <div className="claude-dd">{selectedAsset.split(".").slice(0, 2).join(".")}</div>
                    </div>
                    <div className="claude-dl" style={{ marginTop: "16px" }}>
                      <div className="claude-dt">Freshness</div>
                      <div className="claude-dd">2h 14m stale</div>
                    </div>
                    <div className="claude-dl" style={{ marginTop: "16px" }}>
                      <div className="claude-dt">Row count</div>
                      <div className="claude-dd">1,240,881</div>
                    </div>
                  </div>
                  <div>
                    <div className="claude-dl">
                      <div className="claude-dt">Last updated</div>
                      <div className="claude-dd">Apr 12 09:42</div>
                    </div>
                    <div className="claude-dl" style={{ marginTop: "16px" }}>
                      <div className="claude-dt">SLA</div>
                      <div className="claude-dd">Daily 08:00</div>
                    </div>
                    <div className="claude-dl" style={{ marginTop: "16px" }}>
                      <div className="claude-dt">Incident count</div>
                      <div className="claude-dd">7 (30d)</div>
                    </div>
                  </div>
                </div>

                <div className="claude-owners">
                  <div className="claude-metric-l" style={{ fontSize: "10px", marginBottom: "8px" }}>OWNERS</div>
                  <div className="claude-owner-chip">{passport.data?.metadata?.owner?.name ?? "@finance-eng"}</div>
                  <div className="claude-owner-chip">@data-platform</div>
                </div>
              </div>
            </details>

            {/* 3. Blast Radius Card */}
            <details className="claude-accordion" open>
              <summary>
                Blast radius <span className="claude-badge-inline red">{blastNodes.length} downstream</span>
              </summary>
              <div className="claude-accordion-content" style={{ padding: "0" }}>
                {blastNodes.length > 0 ? (
                  <table className="claude-table" style={{ margin: "20px", width: "calc(100% - 40px)" }}>
                    <thead>
                      <tr>
                        <th>Asset</th>
                        <th>Type</th>
                        <th>Severity</th>
                        <th>Owner</th>
                      </tr>
                    </thead>
                    <tbody>
                      {blastNodes.map((n: any) => (
                        <tr key={n.fqn}>
                          <td style={{ fontWeight: 600 }}>{shortName(n.fqn)}</td>
                          <td style={{ color: "#a1a1aa" }}>{n.entity_type}</td>
                          <td>
                            <span style={{ color: n.impact_tier === "direct" ? "#f87171" : "#fbbf24", display: "flex", alignItems: "center", gap: "6px" }}>
                              <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: n.impact_tier === "direct" ? "#ef4444" : "#f59e0b" }}></span>
                              {n.impact_tier === "direct" ? "Critical" : "High"}
                            </span>
                          </td>
                          <td style={{ color: "#a1a1aa" }}>{n.owner ?? "@finance-eng"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div style={{ padding: "20px", color: "#a1a1aa", fontSize: "12px", fontStyle: "italic" }}>No downstream consumers identified.</div>
                )}
              </div>
            </details>

            {/* 4. Active Warnings Card */}
            <details className="claude-accordion" open={alerts.length > 0}>
              <summary>
                Active warnings <span className={`claude-badge-inline ${alerts.length > 0 ? "red" : ""}`}>{alerts.length} warnings</span>
              </summary>
              <div className="claude-accordion-content" style={{ display: "grid", gap: "12px", background: "rgba(0,0,0,0.2)" }}>
                {alerts.map((alert: any) => (
                  <div key={alert.id} style={{ background: "#27272a", border: "1px solid rgba(255,255,255,0.05)", borderRadius: "8px", padding: "16px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                      <div style={{ fontWeight: 600, color: "#fff", fontSize: "13px" }}>{alert.change_count} changes detected on {shortName(alert.fqn)}</div>
                      <span className={`claude-badge-inline ${alert.severity === "critical" ? "red" : ""}`} style={{ margin: 0 }}>
                        {String(alert.severity).toUpperCase()}
                      </span>
                    </div>
                    <ul className="proto-bullets proto-bullets-tight" style={{ background: "transparent", padding: 0, border: "none" }}>
                      {toBulletItems(alert.summary).map((item: string, bulletIndex: number) => (
                        <li key={`${bulletIndex}-${item}`}>{item}</li>
                      ))}
                    </ul>
                  </div>
                ))}
                {!alerts.length && <div style={{ color: "#a1a1aa", fontSize: "12px", fontStyle: "italic", padding: "4px" }}>No active alerts for this target. Simulate a break below.</div>}
              </div>
            </details>

            {/* 5. Storm Warning Simulator Card */}
            <details className="claude-accordion" open>
              <summary>
                Storm warning simulator <span className="claude-badge-inline" style={{ background: "rgba(255,255,255,0.1)", color: "#a1a1aa" }}>Sandbox</span>
              </summary>
              <div className="claude-accordion-content">
                <div style={{ fontSize: "13px", fontWeight: 500, color: "#fafafa", marginBottom: "16px" }}>
                  Simulate a schema change on <b>{selectedAsset}</b>
                </div>
                <div className="claude-sim-form">
                  <div style={{ marginBottom: "16px" }}>
                    <label className="claude-sim-label">Change type</label>
                    <select className="proto-input" style={{ width: "100%", background: "#18181b" }}>
                      <option>Column drop</option>
                      <option>Data type edit</option>
                      <option>Constraint breach</option>
                    </select>
                  </div>
                  <div style={{ marginBottom: "16px" }}>
                    <label className="claude-sim-label">Column / field</label>
                    <select className="proto-input" style={{ width: "100%", background: "#18181b" }}>
                      {(passport.data?.metadata?.table?.columns ?? [{ name: "budget_amount" }]).map((c: any) => (
                        <option key={c.name}>{c.name}</option>
                      ))}
                    </select>
                  </div>
                  <div style={{ marginBottom: "20px" }}>
                    <label className="claude-sim-label">Notes</label>
                    <input className="proto-input" placeholder="Describe the change or reason..." style={{ width: "100%", background: "#18181b" }} />
                  </div>
                  <button className="proto-btn proto-btn-red" onClick={() => void handleSimulate()} disabled={simulating || passport.loading} style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.2)", color: "#fff" }}>
                    {simulating ? "Simulating..." : "Run simulation ↗"}
                  </button>
                </div>
              </div>
            </details>

            {/* 6. Root Cause Hub */}
            <details className="claude-accordion" open>
              <summary>
                Root cause hub <span className="claude-badge-inline" style={{ background: "rgba(255,255,255,0.1)", color: "#a1a1aa" }}>{rcaTarget ? "Active analysis" : "No active trace"}</span>
              </summary>
              <div className="claude-accordion-content">
                {!rcaTarget && (
                  <div style={{ textAlign: "center", padding: "40px 20px" }}>
                    <div style={{ color: "#fafafa", fontWeight: 600, fontSize: "14px", marginBottom: "6px" }}>No anomaly trace active</div>
                    <div style={{ color: "#a1a1aa", fontSize: "12px", marginBottom: "24px" }}>Start a trace from an active warning to diagnose its root cause.</div>
                    <div style={{ display: "flex", justifyContent: "center", gap: "12px" }}>
                      <button className="proto-btn" onClick={() => document.querySelector(".claude-accordion:nth-child(4) summary")?.dispatchEvent(new MouseEvent("click", { bubbles: true }))}>↓ View active warnings</button>
                      <button className="proto-btn" onClick={() => alerts[0] && handleExplain(alerts[0].fqn)} disabled={alerts.length === 0} style={alerts.length === 0 ? { opacity: 0.5 } : {}}>Start trace on latest alert</button>
                    </div>
                  </div>
                )}
                {rcaTarget && rcaExplanation.data && (
                  <div className="rca-card rca-main-card" style={{ margin: 0, border: "none", background: "rgba(0,0,0,0.2)" }}>
                    <div className="rca-severity-badge" data-severity={rcaExplanation.data.severity}>
                      {rcaExplanation.data.severity.toUpperCase()}
                    </div>
                    <h2 className="rca-title">{rcaExplanation.data.title}</h2>
                    <p className="rca-narrative">{rcaExplanation.data.narrative}</p>
                    <div className="rca-divider" />
                    <div className="rca-section-label">IDENTIFIED ROOT CAUSE</div>
                    <div className="rca-root-cause" style={{ marginBottom: "20px" }}>{rcaExplanation.data.root_cause}</div>
                    <button className="proto-btn" onClick={() => setRcaTarget(null)} style={{ background: "rgba(255,255,255,0.1)" }}>Close trace</button>
                  </div>
                )}
              </div>
            </details>
          </div>
        </section>
"""

new_code = pattern.sub(dashboard_html.replace('\\', '\\\\') + r'\n\3', code)
with open(r'c:\Users\amohanra\OneDrive - The Estée Lauder Companies Inc\Desktop\OpenMeta\frontend\src\app\ProtoApp.tsx', 'w', encoding='utf-8') as f:
    f.write(new_code)
print("Patch executed successfully!")
