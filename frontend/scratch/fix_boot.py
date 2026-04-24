import os

path = os.path.join(
    r"c:\Users\amohanra\OneDrive - The Estée Lauder Companies Inc\Desktop\OpenMeta",
    "frontend", "src", "app", "ProtoApp.tsx"
)

with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# The exact lines to replace are indices 1522 (line 1523) to 1603 (line 1604) inclusive.
correct_block = """                  </div>
                  <div className="boot-widget-stat">
                    <div className="boot-widget-stat-label">WASTE</div>
                    <div className="boot-widget-stat-val">{deadSummary.loading ? "--" : (deadSummary.data?.safe_to_delete_count ?? 0)}</div>
                    <div className="boot-widget-stat-sub">candidates</div>
                  </div>
                  <div className="boot-widget-stat">
                    <div className="boot-widget-stat-label">ASSETS</div>
                    <div className="boot-widget-stat-val">{watchedAssets.loading ? "--" : (watchedAssets.data?.watched_assets?.length ?? 0)}</div>
                    <div className="boot-widget-stat-sub">watched</div>
                  </div>
                </div>
                <div className="boot-widget-next">
                  <div>
                    <div className="boot-widget-next-title">{loaderReady ? "System Ready." : "Polling API..."}</div>
                    <div className="boot-widget-next-desc">{loaderReady ? "All handlers synced and diagnostic engine engaged." : "Establishing secure link to OpenMetadata."}</div>
                  </div>
                  <div className="boot-widget-status-badge" style={{ background: loaderReady ? "rgba(74, 222, 128, 0.1)" : "rgba(255,255,255,0.05)", color: loaderReady ? "#4ade80" : "#a1a1aa" }}>{loaderReady ? "Ready" : "Booting"}</div>
                </div>
              </div>
            </div>
          </div>
        ) : null }
"""

new_lines = lines[:1522] + [correct_block] + lines[1604:]

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print("Spliced correctly!")
