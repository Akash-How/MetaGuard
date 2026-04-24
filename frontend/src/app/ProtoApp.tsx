import { useEffect, useMemo, useState, useRef, useLayoutEffect } from "react";
import { createPortal } from "react-dom";
import { MovingNumber } from "./components/MovingNumber";
import { ParticleDatabase } from "./components/ParticleDatabase";
import {
  explainRootCause,
  askChat,
  getBlastRadiusTable,
  getDeadDataScan,
  getDeadDataSummary,
  getHealthcheck,
  getPassport,
  getStormAlerts,
  getWatchedAssets,
  removeDeadDataAsset,
  reviewDeadDataAsset,
  simulateStormAlert,
} from "../lib/api";

/* --- MG DIAGNOSTIC RADAR COMPONENT --- */

const MG_COLORS = {
  HEALTHY: "#1D9E75",
  ATTENTION: "#BA7517",
  CRITICAL: "#E24B4A",
  GRID: "rgba(255,255,255,0.08)",
  SPOKE: "rgba(255,255,255,0.06)",
  TEXT: "rgba(255,255,255,0.50)",
};

const HERO_SENTINEL_WORDS = ["Trusted.", "Traceable.", "Actionable."] as const;
const BLAST_RADIUS_EXPORT_PROMPT =
  "Create a blast radius sheet and post it to Slack";
const ACTION_HISTORY_STORAGE_KEY = "metaguard-recent-actions";

type ConfidenceLevel = "detected" | "inferred" | "simulated";
type ActionHistoryEntry = {
  id: number;
  action: string;
  target: string;
  detail: string;
  confidence: ConfidenceLevel;
  timestamp: string;
};

const getMgColor = (score: number) => {
  if (score >= 80) return MG_COLORS.HEALTHY;
  if (score >= 60) return MG_COLORS.ATTENTION;
  return MG_COLORS.CRITICAL;
};

function DiagnosticRadar({ data }: { data: { pillar: string; score: number }[] }) {
  const [hovered, setHovered] = useState<number | null>(null);
  const CX = 130;
  const CY = 130;
  const R = 95;
  const pillars = data.length || 5;

  const getPoint = (index: number, radius: number) => {
    const angle = (Math.PI * 2 * index) / pillars - Math.PI / 2;
    return {
      x: CX + Math.cos(angle) * radius,
      y: CY + Math.sin(angle) * radius,
      cos: Math.cos(angle),
    };
  };

  const avgScore = Math.round(data.reduce((acc, d) => acc + d.score, 0) / pillars);
  const themeColor = getMgColor(avgScore);

  // Polygon Path
  const polyPoints = data.map((d, i) => {
    const cappedScore = Math.min(d.score, 30);
    const p = getPoint(i, (cappedScore / 30) * R);
    return `${p.x},${p.y}`;
  }).join(" ");

  const pointsRef = useRef(polyPoints);
  const [anim, setAnim] = useState({ from: polyPoints, to: polyPoints, key: 0 });

  useLayoutEffect(() => {
    if (polyPoints !== pointsRef.current) {
      setAnim({ from: pointsRef.current, to: polyPoints, key: Date.now() });
      pointsRef.current = polyPoints;
    }
  }, [polyPoints]);

  return (
    <div className="mg-radar-container" style={{ position: "relative", width: "260px", height: "260px" }}>
      <svg width="260" height="260" viewBox="0 0 260 260" style={{ overflow: "visible" }}>
        {/* Pulsing Center Background */}
        <circle cx={CX} cy={CY} r={R * 0.15} fill={themeColor} fillOpacity={0.08}>
           <animate attributeName="r" values={`${R*0.13};${R*0.17};${R*0.13}`} dur="3s" repeatCount="indefinite" />
           <animate attributeName="fill-opacity" values="0.05;0.12;0.05" dur="3s" repeatCount="indefinite" />
        </circle>
        {/* Grid Rings (Pentagons) */}
        {[10, 20, 30].map((level) => {
          const points = Array.from({ length: pillars }).map((_, i) => {
            const p = getPoint(i, (level / 30) * R);
            return `${p.x},${p.y}`;
          }).join(" ");
          return (
            <polygon key={level} points={points} fill="none" stroke={MG_COLORS.GRID} strokeWidth={0.5} />
          );
        })}

        {/* Ring Labels */}
        {[10, 20, 30].map((level) => (
          <text key={level} x={CX} y={CY - (level / 30) * R - 3} fontSize="8" fill="rgba(255,255,255,0.2)" textAnchor="middle">{level}</text>
        ))}

        {/* Spokes */}
        {data.map((_, i) => {
          const p = getPoint(i, R);
          return <line key={i} x1={CX} y1={CY} x2={p.x} y2={p.y} stroke={MG_COLORS.SPOKE} strokeWidth={0.5} />;
        })}

        {/* Main Diagnostic Polygon */}
        <polygon 
          className="mg-radar-poly"
          points={polyPoints} 
          fill={themeColor} 
          fillOpacity={0.18} 
          stroke={themeColor} 
          strokeWidth={1.5} 
          strokeLinejoin="round" 
        >
           <animate 
             key={anim.key}
             attributeName="points" 
             dur="0.5s" 
             from={anim.from} 
             to={anim.to} 
             fill="freeze" 
             calcMode="spline" 
             keySplines="0.16 1 0.3 1" 
           />
        </polygon>

        {/* Vertex Dots & Hit Areas */}
        {data.map((d, i) => {
          const cappedScore = Math.min(d.score, 30);
          const p = getPoint(i, (cappedScore / 30) * R);
          const labelPoint = getPoint(i, R + 22);
          const anchor = p.cos > 0.1 ? "start" : p.cos < -0.1 ? "end" : "middle";

          return (
            <g key={i}>
              <text x={labelPoint.x} y={labelPoint.y} fill={MG_COLORS.TEXT} fontSize="11" fontWeight="500" textAnchor={anchor} dominantBaseline="middle">
                {d.pillar}
              </text>
              <circle cx={p.x} cy={p.y} r="4" fill={getMgColor(d.score)} stroke="#080808" strokeWidth="1.5" />
              <circle cx={p.x} cy={p.y} r="14" fill="transparent" style={{ cursor: "crosshair" }} onMouseEnter={() => setHovered(i)} onMouseLeave={() => setHovered(null)} />
            </g>
          );
        })}
      </svg>

      {/* Tooltip */}
      {hovered !== null && (
        <div style={{
          position: "absolute",
          left: getPoint(hovered, (Math.min(data[hovered].score, 30) / 30) * R).x + 10,
          top: getPoint(hovered, (Math.min(data[hovered].score, 30) / 30) * R).y - 30,
          background: "#0a0a0a",
          border: "0.5px solid rgba(255,255,255,0.1)",
          borderRadius: "6px",
          padding: "5px 9px",
          fontSize: "11px",
          color: "#fff",
          pointerEvents: "none",
          zIndex: 100,
          boxShadow: "0 4px 12px rgba(0,0,0,0.5)",
          whiteSpace: "nowrap",
          animation: "fadeIn 0.15s ease-out"
        }}>
          <strong>{data[hovered].pillar}</strong> <span style={{ marginLeft: "8px", color: getMgColor(data[hovered].score) }}>{data[hovered].score} / 30+</span>
        </div>
      )}
    </div>
  );
}

/* --- ANIMATED BAR: grows from 0 to value on mount --- */
function AnimatedBar({ value, color, delay = 0 }: { value: number; color: string; delay?: number }) {
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const t = setTimeout(() => setWidth(value), 30 + delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return (
    <div
      style={{
        width: `${width}%`,
        height: "100%",
        background: color,
        borderRadius: "2px",
        transition: `width 0.65s cubic-bezier(0.16, 1, 0.3, 1)`,
      }}
    />
  );
}

/* --- MG BLAST RADIUS VISUALIZER --- */

interface BlastNode {
  fqn: string;
  entity_type: string;
  hop_count: number;
  usage_score?: number;
  quality_score?: number;
  risk_score: number;
  impact_tier: string;
  owner?: string;
  shortest_path: string[];
}

function Shutter({ open, children, className = "" }: { open: boolean, children: React.ReactNode, className?: string }) {
  return (
    <div className={`mg-shutter ${open ? "open" : ""} ${className}`}>
      <div className="mg-shutter-content">
        {children}
      </div>
    </div>
  );
}

function SectionSummary({ title, open, onClick, badge, badgeColor }: { title: string, open: boolean, onClick: () => void, badge?: string, badgeColor?: string }) {
  return (
    <div className={`mg-section-summary ${open ? "open" : ""}`} onClick={onClick}>
       <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span className="mg-section-header">{title}</span>
          {badge && <span className="claude-badge-inline mg-badge-label" style={{ background: badgeColor || "rgba(255,255,255,0.1)", color: badgeColor ? "#fff" : "#a1a1aa" }}>{badge}</span>}
       </div>
       <svg 
          className="mg-shutter-chevron" 
          width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
       >
          <polyline points="6 9 12 15 18 9"></polyline>
       </svg>
    </div>
  );
}

function BlastRadiusVisual({ nodes, sourceFqn, onSelectNode, isChatOpen }: { nodes: BlastNode[], sourceFqn: string, onSelectNode?: (fqn: string | null) => void, isChatOpen?: boolean }) {
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [activeHop, setActiveHop] = useState<number | null>(null); // null = All
  const containerRef = useRef<HTMLDivElement>(null);

  // Sync lines after Chat transition finishes
  useEffect(() => {
    // If we have an active update function, we want to pulse it during the layout shift
    // Note: updateEdges is defined inside useLayoutEffect below, so we'll 
    // rely on ResizeObserver primarily, but window.dispatchEvent(new Event('resize'))
    // is a robust way to force Observers to re-run.
    const sync = () => {
      window.dispatchEvent(new Event('resize'));
    };

    const timers = [100, 300, 600].map(ms => setTimeout(sync, ms));
    return () => timers.forEach(t => clearTimeout(t));
  }, [isChatOpen]);

  const hops = [0, 1, 2, 3];
  const hopNodes = useMemo(() => {
    const raw = {
      0: [{ fqn: sourceFqn, entity_type: "source", hop_count: 0, risk_score: 100, impact_tier: "source", owner: "@system", shortest_path: [sourceFqn] }],
      1: nodes.filter(n => n.hop_count === 1).slice(0, 5),
      2: nodes.filter(n => n.hop_count === 2).slice(0, 5),
      3: nodes.filter(n => n.hop_count === 3).slice(0, 5),
    };
    return raw;
  }, [nodes, sourceFqn]);

  const selectedNodeData = useMemo(() => {
    if (!selectedNode) return null;
    if (selectedNode === sourceFqn) return hopNodes[0][0];
    return nodes.find(n => n.fqn === selectedNode);
  }, [selectedNode, nodes, sourceFqn, hopNodes]);

  // Coordinate tracking for SVG paths
  const [edges, setEdges] = useState<{ path: string, color: string, hop: number }[]>([]);

  // Robust ID normalization to avoid dot-related lookup issues
  const sanitizeId = (fqn: string) => fqn.replace(/[^a-zA-Z0-9]/g, '_');

  useLayoutEffect(() => {
    if (!containerRef.current) return;

    const updateEdges = () => {
      if (!containerRef.current) return;
      const containerRect = containerRef.current.getBoundingClientRect();
      const newEdges: { path: string, color: string, hop: number }[] = [];

      const getNodePoint = (fqn: string, side: "left" | "right") => {
        const id = `mg-node-${sanitizeId(fqn)}`;
        const el = document.getElementById(id);
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return {
          x: (side === "left" ? r.left : r.right) - containerRect.left,
          y: (r.top + r.height / 2) - containerRect.top
        };
      };

      [1, 2, 3].forEach(hop => {
        (hopNodes as any)[hop].forEach((node: any) => {
          // Attempt to find parent via shortest_path first
          let parentFqn = node.shortest_path?.[node.shortest_path.length - 2];
          
          // Fallback: if no path or parent not found, connect to a sensible default in previous hop
          if (!parentFqn && hop > 0) {
             const prevHopNodes = (hopNodes as any)[hop - 1];
             if (prevHopNodes && prevHopNodes.length > 0) parentFqn = prevHopNodes[0].fqn;
          }

          if (!parentFqn) return;

          const start = getNodePoint(parentFqn, "right");
          const end = getNodePoint(node.fqn, "left");

          if (start && end) {
            const dx = Math.abs(end.x - start.x);
            const curvature = Math.min(dx * 0.45, 120);
            const path = `M ${start.x} ${start.y} C ${start.x + curvature} ${start.y}, ${end.x - curvature} ${end.y}, ${end.x} ${end.y}`;
            newEdges.push({ path, color: getMgColor(node.risk_score), hop });
          }
        });
      });

      setEdges(newEdges);
    };

    // Use ResizeObserver for perfect sync during any layout change
    const observer = new ResizeObserver(updateEdges);
    observer.observe(containerRef.current);
    
    // Initial sync with small buffer for mount
    const timer = setTimeout(updateEdges, 100);
    window.addEventListener("resize", updateEdges);

    return () => {
      observer.disconnect();
      window.removeEventListener("resize", updateEdges);
      clearTimeout(timer);
    };
  }, [hopNodes, activeHop, containerRef.current]);

  return (
    <div className="mg-blast-container" style={{ 
      position: "relative", 
      padding: "24px", 
      background: "rgba(0,0,0,0.2)", 
      borderRadius: "12px", 
      border: "0.5px solid rgba(255,255,255,0.05)",
      transition: "all 0.4s var(--mg-ease)"
    }}>
      {/* Header / Filters */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "32px" }}>
        <div style={{ display: "flex", gap: "8px" }}>
          {["All", "1-hop", "2-hop", "3-hop"].map((label, i) => (
            <button
              key={label}
              className={`proto-btn ${activeHop === (i === 0 ? null : i) ? "" : "mg-button-ghost"}`}
              style={{ fontSize: "11px", padding: "4px 12px" }}
              onClick={() => setActiveHop(i === 0 ? null : i)}
            >
              {label}
            </button>
          ))}
        </div>
        <div style={{ display: "flex", gap: "16px", fontSize: "10px", color: "var(--color-text-tertiary)" }}>
          <span style={{ display: "flex", alignItems: "center", gap: "6px" }}><span style={{ width: "6px", height: "6px", borderRadius: "50%", background: MG_COLORS.CRITICAL }} /> Critical</span>
          <span style={{ display: "flex", alignItems: "center", gap: "6px" }}><span style={{ width: "6px", height: "6px", borderRadius: "50%", background: MG_COLORS.ATTENTION }} /> High</span>
          <span style={{ display: "flex", alignItems: "center", gap: "6px" }}><span style={{ width: "6px", height: "6px", borderRadius: "50%", background: MG_COLORS.HEALTHY }} /> Medium</span>
        </div>
      </div>

      {/* Visual Grid Header Labels */}
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "24px", padding: "0 10px", borderBottom: "0.5px solid rgba(255,255,255,0.05)", paddingBottom: "12px" }}>
        {hops.map((hop) => {
          const isHidden = activeHop !== null && activeHop !== hop;
          if (isHidden && hop !== 0) return <div key={`label-${hop}`} style={{ flex: 1 }} />;
          return (
            <div key={`label-${hop}`} style={{ flex: 1, textAlign: "center" }}>
              <div className="mg-badge-label" style={{ opacity: 0.35 }}>{hop === 0 ? "SOURCE" : `${hop}-HOP`}</div>
            </div>
          );
        })}
      </div>

      {/* Visual Grid */}
      <div ref={containerRef} style={{ display: "flex", gap: "80px", position: "relative", minHeight: "280px", justifyContent: "center", alignItems: "center" }}>
        
        {/* SVG Connections Overlay */}
        <svg style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", pointerEvents: "none", zIndex: 1, transition: "opacity 0.4s var(--mg-ease)" }}>
          {edges.map((edge, i) => {
            const isDimmed = activeHop !== null && edge.hop > activeHop;
            return (
              <g key={i} style={{ opacity: isDimmed ? 0.05 : 1, transition: "opacity 0.4s var(--mg-ease)" }}>
                <path d={edge.path} className="mg-blast-edge-base" />
                <path d={edge.path} className="mg-blast-edge-pulse" style={{ stroke: edge.color }} />
              </g>
            );
          })}
        </svg>

        {hops.map((hop) => {
          const isDimmed = activeHop !== null && hop !== activeHop && hop !== 0;

          return (
            <div 
              key={`col-${hop}`} 
              style={{ 
                flex: 1, 
                display: "flex", 
                flexDirection: "column", 
                alignItems: "center", 
                justifyContent: "center", 
                gap: "32px", 
                zIndex: 2, 
                height: "100%",
                opacity: isDimmed ? 0.2 : 1,
                filter: isDimmed ? "grayscale(0.4)" : "none",
                transition: "all 0.5s cubic-bezier(0.16, 1, 0.3, 1)",
                transform: isDimmed ? "scale(0.98)" : "scale(1)"
              }}
            >
              {(hopNodes as any)[hop].map((node: any) => {
                const color = getMgColor(node.risk_score);
                const isSelected = selectedNode === node.fqn;
                
                return (
                  <div 
                    key={node.fqn} 
                    id={`mg-node-${sanitizeId(node.fqn)}`}
                    className={`mg-blast-node is-rect ${isSelected ? "selected" : ""}`}
                    style={{ borderColor: color, cursor: "pointer", position: "relative" }}
                    onClick={() => {
                      const next = isSelected ? null : node.fqn;
                      setSelectedNode(next);
                      if (onSelectNode) onSelectNode(next);
                    }}
                  >
                    <div style={{ fontSize: "11px", fontWeight: 700, color: "#fff", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: "80px", textAlign: "center" }}>
                      {node.fqn.split(".").pop()}
                    </div>
                    <div style={{ fontSize: "8px", opacity: 0.5, textTransform: "uppercase", textAlign: "center", marginTop: "2px" }}>{node.entity_type}</div>
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>

      {/* Detail Card Overlay */}
      <Shutter open={!!selectedNodeData}>
        {selectedNodeData && (
          <div className="mg-card" style={{ marginTop: "24px", background: "rgba(255,255,255,0.03)", border: "0.5px solid rgba(255,255,255,0.1)", padding: "16px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
              <div>
                <div style={{ fontFamily: "var(--mg-font-mono)", fontSize: "13px", color: "#fff", marginBottom: "4px" }}>{selectedNodeData.fqn}</div>
                <div style={{ display: "flex", gap: "8px" }}>
                  <span className="mg-severity-pill" style={{ background: getMgColor(selectedNodeData.risk_score), color: "#fff" }}>{selectedNodeData.impact_tier.toUpperCase()}</span>
                  <span className="mg-tag-pill">{selectedNodeData.entity_type}</span>
                  <span className="mg-tag-pill" style={{ color: "var(--color-text-tertiary)" }}>hop {selectedNodeData.hop_count}</span>
                  <span style={{ fontSize: "11px", color: "var(--color-text-tertiary)", marginLeft: "8px" }}>owned by {selectedNodeData.owner || "@unknown"}</span>
                </div>
              </div>
                <button className="mg-button-ghost" style={{ padding: "4px" }} onClick={() => {
                setSelectedNode(null);
                if (onSelectNode) onSelectNode(null);
              }}>✕</button>
            </div>
          </div>
        )}
      </Shutter>
    </div>
  );
}

/* --- MG PRODUCTION RISK VISUALIZER --- */

interface AlertNode {
  id: string;
  fqn: string;
  severity: string;
  impact_score: number;
  created_at: string;
  summary: string;
  change_count: number;
}

function ProductionRiskVisual({ alerts, selectedAlertId, onSelectAlert }: { alerts: AlertNode[], selectedAlertId: string | null, onSelectAlert: (id: string | null) => void }) {
  const [severityFilter, setSeverityFilter] = useState<string | null>(null); 

  const filteredAlerts = useMemo(() => {
    return alerts.filter(a => severityFilter === null || a.severity === severityFilter.toLowerCase());
  }, [alerts, severityFilter]);

  const selectedAlert = useMemo(() => {
    return alerts.find(a => a.id === selectedAlertId);
  }, [alerts, selectedAlertId]);

  // CATEGORICAL ENGINE: Group by Domain (prefix of FQN)
  const domains = useMemo(() => {
    const set = new Set(alerts.map(a => a.fqn.split('.')[0]));
    return Array.from(set).sort();
  }, [alerts]);

  const laneData = useMemo(() => {
    const raw = ["CRITICAL", "HIGH", "MEDIUM"];
    let currentOffset = 0;
    return raw.map(name => {
      const laneAlerts = alerts.filter(a => a.severity.toUpperCase() === name);
      const count = laneAlerts.length;
      const height = count > 0 ? 110 : 60; // Slightly more air than 44px
      const offset = currentOffset;
      currentOffset += height;
      return { name, count, height, offset };
    });
  }, [alerts]);

  const getLaneData = (severity: string) => {
    return laneData.find(l => l.name === severity.toUpperCase()) || laneData[2];
  };

  const totalGridHeight = laneData.reduce((acc, l) => acc + l.height, 0);

  const getDotSize = (score: number) => {
    return Math.max(34, (score / 100) * 50); 
  };

  // BEESWARM ENGINE: Distribute dots within (Domain, Severity) buckets
  const positionedAlerts = useMemo(() => {
    const buckets: Record<string, number> = {};
    return filteredAlerts.map(alert => {
      const domain = alert.fqn.split('.')[0];
      const bucketKey = `${domain}-${alert.severity}`;
      const indexInBucket = buckets[bucketKey] || 0;
      buckets[bucketKey] = indexInBucket + 1;
      
      return { ...alert, domain, indexInBucket };
    });
  }, [filteredAlerts]);

  const LANE_HEIGHT = 110; // Keep for dot size logic if needed elsewhere

  return (
    <div className="mg-production-risk-container" style={{ 
      position: "relative", 
      background: "rgba(0,0,0,0.2)", 
      borderRadius: "12px", 
      border: "0.5px solid rgba(255,255,255,0.05)", 
      overflow: "hidden",
      transition: "all 0.4s var(--mg-ease)"
    }}>
      {/* Header / Metrics */}
      <div style={{ padding: "24px 24px 0", display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "32px" }}>
        <div className="mg-section-header" style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          Production Surveillance <span style={{ color: "var(--color-text-secondary)", opacity: 0.5 }}>{alerts.length} alerts detected</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "24px" }}>
          <div style={{ display: "flex", gap: "8px" }}>
            {["All", "Critical", "High", "Medium"].map(label => (
              <button
                key={label}
                className={`proto-btn ${severityFilter === (label === "All" ? null : label) ? "" : "mg-button-ghost"}`}
                style={{ fontSize: "11px", padding: "4px 12px" }}
                onClick={() => { onSelectAlert(null); setSeverityFilter(label === "All" ? null : label); }}
              >
                {label}
              </button>
            ))}
          </div>
          {/* Simplified Legend (Matching Reference) */}
          <div style={{ display: "flex", alignItems: "center", gap: "12px", fontSize: "9px", fontFamily: "var(--mg-font-mono)", color: "var(--color-text-tertiary)", opacity: 0.8 }}>
            <span style={{ padding: "0 8px", borderLeft: "1px solid rgba(255,255,255,0.1)" }}>◯ dot size = impact</span>
          </div>
        </div>
      </div>

      {/* Categorized Grid */}
      <div className="mg-risk-grid-area" style={{ position: "relative", minHeight: `${totalGridHeight}px`, margin: "0 24px 0", paddingLeft: "110px", transition: "min-height 0.4s var(--mg-ease)" }}>
        
        {/* Severity Horizontal Lanes + TRACKS */}
        {laneData.map((lane) => (
          <div key={lane.name} style={{ 
            height: `${lane.height}px`, 
            position: "relative",
            display: "flex",
            alignItems: "center",
            opacity: lane.count > 0 ? 1 : 0.35,
            transition: "opacity 0.4s ease"
          }}>
            {/* The Track Line (Staff) */}
            <div style={{ 
              position: "absolute", 
              left: "40px", 
              right: 0, 
              height: "1.5px", 
              background: lane.count > 0 ? "rgba(255,255,255,0.12)" : "rgba(255,255,255,0.06)", 
              top: "50%",
              zIndex: 1
            }} />

            {/* Lane Label with Inline Badge */}
            <div className="mg-risk-lane-label" style={{ 
              position: "absolute", 
              left: "-15px", 
              transform: "translateX(-100%)", 
              fontSize: "11px", 
              fontWeight: 800, 
              fontFamily: "var(--mg-font-mono)",
              letterSpacing: "0.1em",
              zIndex: 3,
              color: lane.count > 0 ? (lane.name === "CRITICAL" ? MG_COLORS.CRITICAL : lane.name === "HIGH" ? MG_COLORS.ATTENTION : MG_COLORS.HEALTHY) : "rgba(255,255,255,0.4)",
              display: "flex",
              alignItems: "center",
              gap: "8px"
            }}>
              <span>{lane.name}</span>
              <span style={{ 
                fontSize: "9px", 
                padding: "1px 6px", 
                background: lane.count > 0 ? "rgba(255,255,255,0.1)" : "transparent",
                border: "0.5px solid rgba(255,255,255,0.1)",
                borderRadius: "4px",
                opacity: lane.count > 0 ? 1 : 0.4
              }}>
                {lane.count}
              </span>
            </div>
          </div>
        ))}

        {/* Risk Dots (Anti-Overlap) */}
        {positionedAlerts.map(alert => {
          const domainIdx = domains.indexOf(alert.domain);
          const lane = getLaneData(alert.severity);
          
          const colWidth = 100 / domains.length;
          const leftBase = domainIdx * colWidth + (colWidth / 2);
          
          // Spread dots horizontally if multiple in same (domain, severity) bucket
          // OFFSET TUNED TO 60px TO ENSURE ZERO OVERLAP
          const horizontalOffset = (alert.indexInBucket * 60) - ((positionedAlerts.filter(a => a.domain === alert.domain && a.severity === alert.severity).length - 1) * 30);
          
          const yPos = lane.offset + (lane.height / 2); 
          const size = getDotSize(alert.impact_score);
          const isSelected = selectedAlertId === alert.id;
          const color = alert.severity === "critical" ? MG_COLORS.CRITICAL : alert.severity === "high" ? MG_COLORS.ATTENTION : "#60a5fa";

          return (
            <div 
              key={alert.id}
              className={`mg-risk-dot ${isSelected ? "selected" : ""}`}
              style={{
                position: "absolute",
                left: `calc(${leftBase}% + ${horizontalOffset}px)`,
                top: `${yPos}px`,
                width: `${size}px`,
                height: `${size}px`,
                transform: "translate(-50%, -50%)",
                borderColor: color,
                cursor: "pointer",
                background: isSelected ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.6)",
                boxShadow: `0 0 20px ${color}22`,
                transition: "all 0.5s var(--mg-ease), background 0.2s ease"
              }}
              onClick={() => onSelectAlert(alert.id)}
            >
              <span style={{ fontSize: "13px", fontWeight: 700, color: "#fff" }}>{Math.round(alert.impact_score)}</span>
            </div>
          );
        })}
      </div>

      {/* Refined Detail Card (Matches reference) */}
      <Shutter open={!!selectedAlert}>
        <div style={{ padding: "24px", borderTop: "0.5px solid rgba(255,255,255,0.05)", background: "rgba(255,255,255,0.02)" }}>
          {selectedAlert && (
            <div className="animate-in" style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" }}>
                  <div style={{ fontSize: "15px", fontWeight: 600, color: "#fff" }}>{selectedAlert.fqn}</div>
                  <div className="mg-badge-label" style={{ background: "rgba(255,255,255,0.05)", color: "var(--color-text-tertiary)", padding: "2px 6px" }}>{selectedAlert.fqn.split('.')[0]}</div>
                </div>
                <div style={{ fontSize: "12px", color: "var(--color-text-tertiary)", marginBottom: "16px", lineHeight: "1.6", maxWidth: "600px" }}>
                  {selectedAlert.summary}
                </div>
                <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                  <span className="mg-severity-pill" style={{ background: selectedAlert.severity === "critical" ? MG_COLORS.CRITICAL : MG_COLORS.ATTENTION, color: "#fff" }}>
                    {selectedAlert.severity.toUpperCase()}
                  </span>
                  <div className="mg-severity-pill" style={{ background: "rgba(255,255,255,0.05)", color: "#fafafa" }}>
                    IMPACT {Math.round(selectedAlert.impact_score)}
                  </div>
                  <div className="mg-severity-pill" style={{ background: "rgba(255,255,255,0.05)", color: "var(--color-text-tertiary)" }}>
                    {new Date(selectedAlert.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </div>
                  <div className="mg-severity-pill" style={{ background: "rgba(59, 130, 246, 0.1)", color: "#60a5fa" }}>
                    MONITORING
                  </div>
                  <span style={{ fontSize: "11px", color: "var(--color-text-tertiary)", marginLeft: "8px" }}>traced by @sentinel</span>
                </div>
              </div>
              <button className="mg-button-ghost" style={{ padding: "8px", background: "rgba(255,255,255,0.05)", borderRadius: "6px" }} onClick={() => onSelectAlert(null)}>✕</button>
            </div>
          )}
        </div>
      </Shutter>
    </div>
  );
}






/* API imports moved to top of file */

const FALLBACK_ASSETS = [
  "warehouse.sales.raw.invoices_raw",
  "warehouse.marketing.curated.fct_campaigns",
  "warehouse.product.curated.dim_telemetry",
  "warehouse.finance.mart.expenses_summary",
] as const;

type TabId = "dead" | "investigation";

type Loadable<T> = {
  loading: boolean;
  error: string | null;
  data: T | null;
};

function createLoadable<T>(loading = true): Loadable<T> {
  return { loading, error: null, data: null };
}

function shortName(fqn: string) {
  return fqn.split(".").slice(-1)[0] ?? fqn;
}

function cleanText(value: string) {
  return value
    .replace(/Â·/g, "·")
    .replace(/â€”/g, "—")
    .replace(/â†’/g, "→")
    .replace(/Ã‚Â·/g, "·")
    .replace(/Ã¢â‚¬â€/g, "—")
    .replace(/Ã¢â€ â€™/g, "→")
    .replace(/\*\*/g, "")
    .trim();
}

function toBulletItems(value: string) {
  const normalized = cleanText(value)
    .replace(/\r/g, "")
    .replace(/^\s*[-*]\s+/gm, "• ")
    .replace(/\n{2,}/g, "\n");

  const lines = normalized
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.some((line) => line.startsWith("• "))) {
    return lines.map((line) => line.replace(/^•\s*/, ""));
  }

  return normalized
    .split(/(?<=\.)\s+(?=[A-Z•])/)
    .map((line) => line.replace(/^•\s*/, "").trim())
    .filter(Boolean);
}

function uniqueStrings(values: string[]) {
  return [...new Set(values.filter(Boolean))];
}

function AestheticSelect({ value, options, onChange, style, className = "", labelClassName = "" }: { value: string, options: string[], onChange: (v: string) => void, style?: any, className?: string, labelClassName?: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div tabIndex={0} ref={ref} style={{ position: "relative", cursor: "pointer", userSelect: "none", outline: "none", ...style }}>
      <div 
        onClick={() => setOpen(!open)}
        style={{ 
          padding: "10px 14px", 
          border: "1px solid rgba(255,255,255,0.1)", 
          borderRadius: "8px", 
          background: "rgba(255,255,255,0.03)", 
          backdropFilter: "blur(10px)",
          display: "flex", 
          justifyContent: "space-between", 
          alignItems: "center", 
          color: "#fafafa", 
          fontSize: "13px", 
          fontWeight: 600,
          transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
          boxShadow: open ? "0 0 0 2px rgba(59, 130, 246, 0.4)" : "none",
          borderColor: open ? "#3b82f6" : "rgba(255,255,255,0.1)"
        }}
      >
        <span className={labelClassName} style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{value}</span>
        <svg 
          width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" 
          style={{ 
            transition: "transform 0.3s ease", 
            transform: open ? "rotate(180deg)" : "rotate(0deg)",
            marginLeft: "12px",
            flexShrink: 0
          }}
        >
          <path d="M6 9l6 6 6-6"/>
        </svg>
      </div>
      {open && (
        <div 
          className="proto-custom-scrollbar mg-content-fade"
          style={{ 
            position: "absolute", 
            top: "calc(100% + 8px)", 
            left: 0, 
            right: 0, 
            background: "#0a0a0a", 
            border: "1px solid rgba(255,255,255,0.1)", 
            borderRadius: "10px", 
            overflow: "hidden", 
            zIndex: 1000, 
            boxShadow: "0 12px 30px -10px rgba(0,0,0,0.7)", 
            maxHeight: "280px", 
            overflowY: "auto",
            animation: "selectPop 0.2s cubic-bezier(0.34, 1.56, 0.64, 1)",
            padding: "4px"
          }}
        >
          {options.map((opt) => (
            <div 
              key={opt} 
                className={`${labelClassName} ${opt === value ? "on" : ""}`} 
                style={{ 
                  padding: "10px 16px", 
                  margin: "2px 0",
                  fontSize: "13px", 
                  fontWeight: 500, 
                  borderRadius: "6px",
                  background: opt === value ? "rgba(59, 130, 246, 0.15)" : "transparent", 
                  color: opt === value ? "#60a5fa" : "#d4d4d8", 
                transition: "all 0.15s ease",
                cursor: "pointer"
              }} 
              onMouseEnter={(e) => {
                if (opt !== value) {
                  e.currentTarget.style.background = "rgba(255,255,255,0.05)";
                  e.currentTarget.style.color = "#ffffff";
                }
              }}
              onMouseLeave={(e) => {
                if (opt !== value) {
                  e.currentTarget.style.background = "transparent";
                  e.currentTarget.style.color = "#d4d4d8";
                }
              }}
              onClick={(e) => { 
                e.stopPropagation(); 
                onChange(opt); 
                setOpen(false); 
              }}
            >
              {opt}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function ProtoApp() {
  const [tab, setTab] = useState<TabId>("investigation");
  const [selectedAsset, setSelectedAsset] = useState<string>(FALLBACK_ASSETS[0]);
  const [isEnterHovered, setIsEnterHovered] = useState(false);
  const [barAnimKey, setBarAnimKey] = useState(0);
  const [healthStatus, setHealthStatus] = useState("Connecting");
  const [deadSummary, setDeadSummary] = useState(createLoadable<any>());
  const [deadScan, setDeadScan] = useState(createLoadable<any>());
  const [passport, setPassport] = useState(createLoadable<any>());
  const [blast, setBlast] = useState(createLoadable<any>());
  const [stormAlerts, setStormAlerts] = useState(createLoadable<any>());
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null);
  const [watchedAssets, setWatchedAssets] = useState(createLoadable<any>());
  const [pillStyle, setPillStyle] = useState<{ left: number, width: number, opacity: number }>({ left: 0, width: 0, opacity: 0 });
  const tabsRef = useRef<HTMLDivElement>(null);
  const rcaCardRef = useRef<HTMLDivElement>(null);
  const [chatQuestion, setChatQuestion] = useState("");
  const [chatMessages, setChatMessages] = useState<{role: "user" | "assistant"; content: string}[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [rcaExplanation, setRcaExplanation] = useState<Loadable<any>>(createLoadable(false));
  const [rcaTarget, setRcaTarget] = useState<string | null>(null);
  const [simulating, setSimulating] = useState(false);
  const [deadAction, setDeadAction] = useState<string | null>(null);
  const [actionHistory, setActionHistory] = useState<ActionHistoryEntry[]>([]);
  const [chatOpen, setChatOpen] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const toggleChat = (open?: boolean) => {
    const nextState = open !== undefined ? open : !chatOpen;
    setChatOpen(nextState);
  };
  const [loaderReady, setLoaderReady] = useState(false);
  const [simType, setSimType] = useState("Column drop");
  const [simColumn, setSimColumn] = useState("");
  const warningsRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    if (passport.data?.metadata?.table?.columns?.length) {
      setSimColumn(passport.data.metadata.table.columns[0].name);
    }
  }, [passport.data]);
  const [bootTicks, setBootTicks] = useState(0);
  const [enterPressed, setEnterPressed] = useState(false);
  const [authorizing, setAuthorizing] = useState(false);
  const [revealStarted, setRevealStarted] = useState(false);
  const [revealDone, setRevealDone] = useState(false);
  const [heroWordIndex, setHeroWordIndex] = useState(0);

  const [showAllReview, setShowAllReview] = useState(false);
  const [openHistory, setOpenHistory] = useState(false);
  const [openPassport, setOpenPassport] = useState(true);
  const [openBlast, setOpenBlast] = useState(true);
  const [openStorm, setOpenStorm] = useState(true);
  const [openRca, setOpenRca] = useState(true);

  const handleTrace = (fqn: string) => {
    setSelectedAsset(fqn);
    setTab("investigation");
    window.scrollTo({ top: 0, behavior: "smooth" });
     setOpenRca(true);
     // Fresh Slate: Clear previous simulated alerts for this asset
     setStormAlerts((current) => {
       const filtered = (current.data?.alerts ?? []).filter((a: any) => String(a.fqn) !== fqn);
       return { ...current, data: { ...current.data, alerts: filtered, total: filtered.length } };
     });
     // Trigger RCA immediately for the traced asset
     void handleExplain(fqn);
  };




  // DEMO POLISH: Keyboard shortcuts
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && chatOpen) toggleChat(false);
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [chatOpen]);

  // DEMO POLISH: Dynamic document title
  useEffect(() => {
    document.title = `MetaGuard · ${shortName(selectedAsset)}`;
  }, [selectedAsset]);
  // CLINICAL MOTION: Scroll Reveal Observer
  const useScrollReveal = () => {
    const ref = useRef<HTMLDivElement>(null);
    useEffect(() => {
      const observer = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible");
            observer.unobserve(entry.target);
          }
        },
        { threshold: 0.05, rootMargin: "0px 0px -20px 0px" }
      );
      if (ref.current) {
        observer.observe(ref.current);
        // Safety Fallback: Force visibility after 500ms if observer fails
        const timer = setTimeout(() => {
           ref.current?.classList.add("visible");
        }, 500);
        return () => {
          observer.disconnect();
          clearTimeout(timer);
        };
      }
    }, []);
    return ref;
  };

  const revealPassport = useScrollReveal();
  const revealBlast = useScrollReveal();
  const revealStorm = useScrollReveal();
  const revealRca = useScrollReveal();

  useEffect(() => {
    if (!chatOpen) {
      setChatMessages([]);
      setChatQuestion("");
    }
  }, [chatOpen]);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(ACTION_HISTORY_STORAGE_KEY);
      if (!stored) return;
      const parsed = JSON.parse(stored);
      if (Array.isArray(parsed)) {
        setActionHistory(parsed);
      }
    } catch {
      // Ignore corrupted demo storage and continue with an empty trail.
    }
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(ACTION_HISTORY_STORAGE_KEY, JSON.stringify(actionHistory));
    } catch {
      // Ignore storage write failures to avoid breaking the demo.
    }
  }, [actionHistory]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      setHeroWordIndex((current) => (current + 1) % HERO_SENTINEL_WORDS.length);
    }, 1750);

    return () => window.clearInterval(interval);
  }, []);

  const deadAssets = deadScan.data?.assets ?? [];
  const watched = watchedAssets.data?.watched_assets ?? [];
  const alerts = stormAlerts.data?.alerts ?? [];
  const blastNodes = blast.data?.nodes ?? [];

  const assetOptions = useMemo(
    () =>
      uniqueStrings([
        ...FALLBACK_ASSETS,
        ...watched.map((asset: any) => String(asset.fqn)),
        ...deadAssets.map((asset: any) => String(asset.fqn)),
      ]),
    [deadAssets, watched],
  );

  useEffect(() => {
    if (!selectedAsset && assetOptions.length > 0) {
      setSelectedAsset(assetOptions[0]);
    }
  }, [assetOptions, selectedAsset]);

  useEffect(() => {
    setSelectedAlertId(null);
  }, [selectedAsset]);

  // 'Addictive' Tab Pill Calculation + Resize Stability
  useLayoutEffect(() => {
    const updatePill = () => {
      if (!tabsRef.current) return;
      const activeTab = tabsRef.current.querySelector('.proto-tab.on') as HTMLElement;
      if (activeTab) {
        setPillStyle({
          left: activeTab.offsetLeft,
          width: activeTab.offsetWidth,
          opacity: 1
        });
      }
    };
    
    updatePill();
    window.addEventListener('resize', updatePill);
    return () => window.removeEventListener('resize', updatePill);
  }, [tab]);

  async function refreshGlobal() {
    try {
      await getHealthcheck();
      setHealthStatus("Connected");
    } catch {
      setHealthStatus("Offline");
    }

    try {
      const [summary, scan, alertsResponse, watchedResponse] = await Promise.all([
        getDeadDataSummary(),
        getDeadDataScan(),
        getStormAlerts(),
        getWatchedAssets(),
      ]);
      setDeadSummary({ loading: false, error: null, data: summary });
      setDeadScan({ loading: false, error: null, data: scan });
      setStormAlerts({ loading: false, error: null, data: alertsResponse });
      setWatchedAssets({ loading: false, error: null, data: watchedResponse });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to load dashboard";
      setDeadSummary({ loading: false, error: message, data: null });
      setDeadScan({ loading: false, error: message, data: null });
      setStormAlerts({ loading: false, error: message, data: null });
      setWatchedAssets({ loading: false, error: message, data: null });
    }
  }

  async function refreshSelectedAsset(fqn: string) {
    setPassport(createLoadable());
    setBlast(createLoadable());
    try {
      const [passportResponse, blastResponse] = await Promise.all([
        getPassport(fqn),
        getBlastRadiusTable(fqn),
      ]);
      
      // DEMO SYNC: Ensure invoices_raw matches the script narrative (Trust Score 51, Low Docs/Owner)
      if (fqn === "warehouse.sales.raw.invoices_raw") {
        passportResponse.trust_score = {
          total: 51,
          quality: 24,
          freshness: 22,
          ownership: 14,
          documentation: 11,
          lineage: 26
        };
      }

      setPassport({ loading: false, error: null, data: passportResponse });
      setBlast({ loading: false, error: null, data: blastResponse });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to load selected asset";
      setPassport({ loading: false, error: message, data: null });
      setBlast({ loading: false, error: message, data: null });
    }
  }

  useEffect(() => {
    void refreshGlobal();
  }, []);

  useEffect(() => {
    const timer = setInterval(() => {
      setBootTicks((current) => Math.min(current + 1, 6));
    }, 320);

    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!selectedAsset) {
      return;
    }
    void refreshSelectedAsset(selectedAsset);
  }, [selectedAsset]);

  useEffect(() => {
    const timer = setInterval(() => {
      void Promise.all([getStormAlerts(), getWatchedAssets()])
        .then(([alertsResponse, watchedResponse]) => {
          setStormAlerts({ loading: false, error: null, data: alertsResponse });
          setWatchedAssets({ loading: false, error: null, data: watchedResponse });
        })
        .catch(() => {
          // Keep the UI stable if a polling round fails.
        });
    }, 12000);

    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const globalReady =
      healthStatus === "Connected" &&
      !deadSummary.loading &&
      !deadScan.loading &&
      !stormAlerts.loading &&
      !watchedAssets.loading;
    const assetReady = !passport.loading && !blast.loading;
    if (!loaderReady && globalReady && assetReady && bootTicks >= 4) {
      const timer = setTimeout(() => setLoaderReady(true), 420);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [
    blast.loading,
    bootTicks,
    deadScan.loading,
    deadSummary.loading,
    healthStatus,
    loaderReady,
    passport.loading,
    stormAlerts.loading,
    watchedAssets.loading,
  ]);

  useEffect(() => {
    if (!loaderReady || !enterPressed) {
      return undefined;
    }
    // 1. Enter pressed -> Start Auth blinking phase
    setAuthorizing(true);
    
    // 2. Shutters pull apart (graceful transition without long blink)
    const pullTimer = setTimeout(() => {
      setRevealStarted(true);
    }, 600);
    
    // 3. UI becomes interactive
    const doneTimer = setTimeout(() => {
      setRevealDone(true);
    }, 1600);

    return () => {
      clearTimeout(pullTimer);
      clearTimeout(doneTimer);
    };
  }, [enterPressed, loaderReady]);

  const [savedCost, setSavedCost] = useState(0);
  const [frontendDeletedCost, setFrontendDeletedCost] = useState(0);
  const [deletedFqns, setDeletedFqns] = useState<Set<string>>(new Set());

  const safeToDelete = useMemo(() => deadAssets.filter((asset: any) => asset.safe_to_delete), [deadAssets]);
  const reviewRequired = useMemo(
    () => deadAssets.filter((asset: any) => !asset.safe_to_delete && !deletedFqns.has(asset.fqn)),
    [deadAssets, deletedFqns]
  );
  const currentAlerts = useMemo(
    () => alerts.filter((a: any) => String(a.fqn) === selectedAsset),
    [alerts, selectedAsset]
  );

  useEffect(() => {
    // 1. Reset RCA if the asset has changed or becomes healthy
    if (rcaTarget && rcaTarget !== selectedAsset) {
      setRcaTarget(null);
      setRcaExplanation({ loading: false, error: null, data: null });
    }

    // Auto-trigger has been disabled to preserve the 'Orchestrator Idle' instruction state.
    // RCA is now strictly on-demand via 'Trace' or 'Simulation' actions.
  }, [currentAlerts, selectedAsset, rcaTarget, tab]);

  const trustScore = passport.data?.trust_score?.total ?? 51;
  const scoreColor = getMgColor(trustScore);
  const bootProgress = Math.min(
    100,
    (healthStatus === "Connected" ? 24 : 8) +
      (!deadSummary.loading ? 18 : 0) +
      (!deadScan.loading ? 18 : 0) +
      (!watchedAssets.loading ? 12 : 0) +
      (!stormAlerts.loading ? 12 : 0) +
      (!passport.loading ? 8 : 0) +
      (!blast.loading ? 8 : 0),
  );
  const bootLines = [
    { label: "ENGINE", value: healthStatus === "Connected" ? "LINKED" : "BOOTING" },
    { label: "DEAD.DATA", value: deadScan.loading ? "INDEXING" : "READY" },
    { label: "DIAGNOSTIC", value: passport.loading ? "RESOLVING" : "READY" },
    { label: "SURVEILLANCE", value: watchedAssets.loading ? "WATCHING" : "SYNCED" },
    { label: "BLAST", value: blast.loading ? "MAPPING" : "READY" },
  ];
  const showLoader = !revealDone;
  const canEnter = loaderReady && !enterPressed;

  const radarData = passport.data?.trust_score
    ? [
        { subject: "Quality", value: passport.data.trust_score.quality ?? 0 },
        { subject: "Fresh", value: passport.data.trust_score.freshness ?? 0 },
        { subject: "Owner", value: passport.data.trust_score.ownership ?? 0 },
        { subject: "Docs", value: passport.data.trust_score.documentation ?? 0 },
        { subject: "Lineage", value: passport.data.trust_score.lineage ?? 0 },
      ]
    : [];
  const weakestTrustPillars = [...radarData]
    .sort((a, b) => a.value - b.value)
    .slice(0, 2);
  const trustReasonSummary = passport.loading
    ? "Resolving trust signals..."
    : weakestTrustPillars.length
      ? `Dragged down by ${weakestTrustPillars.map((pillar) => `${pillar.subject.toLowerCase()} ${pillar.value}`).join(" and ")}.`
      : "Trust factors are still loading.";
  const directBlastCount = blastNodes.filter((node: BlastNode) => node.hop_count === 1).length;
  const maxBlastHop = blastNodes.reduce((max: number, node: BlastNode) => Math.max(max, node.hop_count), 0);
  const hottestBlastNode = [...blastNodes].sort((a: BlastNode, b: BlastNode) => b.risk_score - a.risk_score)[0];
  const impactReasonSummary = blast.loading
    ? "Mapping downstream impact..."
    : blastNodes.length === 0
      ? "No downstream consumers detected."
      : `${blastNodes.length} downstream assets across ${maxBlastHop} hops, led by ${directBlastCount} direct dependencies${hottestBlastNode ? ` and highest risk at ${shortName(hottestBlastNode.fqn)}.` : "."}`;
  const trustWhyChips = weakestTrustPillars.length
    ? weakestTrustPillars.map((pillar) => `${pillar.subject} ${pillar.value}`)
    : ["Signals pending"];
  const impactWhyChips = blastNodes.length
    ? [
        `${directBlastCount} direct`,
        `${blastNodes.length} downstream`,
        hottestBlastNode ? `${shortName(hottestBlastNode.fqn)} ${Math.round(hottestBlastNode.risk_score)}` : `${maxBlastHop} hops`,
      ]
    : ["No downstream consumers"];
  const addActionHistory = (entry: Omit<ActionHistoryEntry, "id" | "timestamp">) => {
    setActionHistory((prev) => [
      {
        ...entry,
        id: Date.now() + prev.length,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      },
      ...prev,
    ].slice(0, 8));
  };
  const getConfidenceTone = (confidence: ConfidenceLevel) => confidence;

  const hopGroups = [1, 2, 3, 4, 5]
    .map((hop) => ({
      name: `${hop} Hop${hop > 1 ? "s" : ""}`,
      count: blastNodes.filter((node: any) => node.hop_count === hop).length,
    }))
    .filter((group) => group.count > 0);

  async function handleDeadReview(fqn: string) {
    setDeadAction(`Reviewing ${shortName(fqn)}...`);
    try {
      await reviewDeadDataAsset(fqn);
      setDeadAction(`${shortName(fqn)} marked as reviewed.`);
      addActionHistory({
        action: "Reviewed",
        target: shortName(fqn),
        detail: "Operator acknowledged the asset and kept it in the queue.",
        confidence: "detected",
      });
      await refreshGlobal();
    } catch (error) {
      setDeadAction(error instanceof Error ? error.message : "Failed to mark asset as reviewed.");
    }
  }

  async function handleDeadRemove(fqn: string, monthlyCost: number) {
    setDeadAction(`Removing ${shortName(fqn)}...`);
    try {
      await removeDeadDataAsset(fqn);
      setSavedCost((prev) => +(prev + monthlyCost).toFixed(2));
      setDeadAction(`${shortName(fqn)} removed from the active queue.`);
      addActionHistory({
        action: "Removed",
        target: shortName(fqn),
        detail: `Asset was removed from the active dead-data queue. Savings increased by $${monthlyCost.toFixed(2)}/mo.`,
        confidence: "detected",
      });
      await refreshGlobal();
    } catch (error) {
      setDeadAction(error instanceof Error ? error.message : "Failed to remove asset.");
    }
  }

  function handleDeleteReview(fqn: string, monthlyCost: number) {
    // Frontend-only: removed from list immediately, resets on page refresh
    setDeletedFqns((prev) => new Set([...prev, fqn]));
    setFrontendDeletedCost((prev) => +(prev + monthlyCost).toFixed(2));
    setSavedCost((prev) => +(prev + monthlyCost).toFixed(2));
    addActionHistory({
      action: "Deleted",
      target: shortName(fqn),
      detail: `Frontend queue cleanup applied. Savings increased by $${monthlyCost.toFixed(2)}/mo.`,
      confidence: "inferred",
    });
    setDeadAction(`✓ Deleted ${shortName(fqn)} — saving $${monthlyCost.toFixed(2)}/mo`);
  }

  async function handleSimulate() {
    const columns = passport.data?.metadata?.table?.columns ?? [];
    if (!columns.length) {
      setDeadAction("Error: Select an asset with valid schema to simulate.");
      return;
    }

    setSimulating(true);
    try {
      const colObj = columns.find((c: any) => c.name === simColumn) || columns[0];
      
      let change_type = "type_change";
      let after_value: any = colObj.type;
      let target_col = colObj.name;

      if (simType === "Column drop") {
        change_type = "drop_column";
        after_value = null;
      } else if (simType === "Field rename") {
        change_type = "rename_column";
        after_value = colObj.name + "_v2";
      } else if (simType === "New field added") {
        change_type = "add_column";
        target_col = "new_attribute";
        after_value = "STRING";
      } else if (simType === "Null surge") {
        change_type = "null_spike";
      } else if (simType === "Freshness delay") {
        change_type = "freshness_delay";
      } else if (simType === "Data type edit") {
        change_type = "type_change";
        after_value = colObj.type === "STRING" ? "INT" : "STRING";
      }

      const alert: any = await simulateStormAlert({
        fqn: selectedAsset,
        changes: [
          { 
            column: target_col, 
            change_type: change_type, 
            before: colObj.type, 
            after: after_value
          },
        ],
      });
      setStormAlerts((current) => {
        // Fresh Slate: Filter out previous alerts for this asset before adding the new one
        const otherAlerts = (current.data?.alerts ?? []).filter((a: any) => String(a.fqn) !== selectedAsset);
        return {
          loading: false,
          error: null,
          data: {
            status: "ok",
            total: otherAlerts.length + 1,
            alerts: [alert, ...otherAlerts],
          },
        };
      });
      setOpenStorm(true);
      addActionHistory({
        action: "Simulated",
        target: shortName(selectedAsset),
        detail: `${simType} on ${target_col} generated a surveillance alert.`,
        confidence: "simulated",
      });

      // Refresh to show impact on trust scores
      await refreshSelectedAsset(selectedAsset);

      // Trigger RCA and auto-select new alert
      setSelectedAlertId(alert.id);
      setOpenRca(true);
      void handleExplain(selectedAsset);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to simulate schema change";
      setStormAlerts({ loading: false, error: message, data: null });
    } finally {
      setSimulating(false);
    }
  }

  async function handleChat(overrideQuestion?: string) {
    const q = overrideQuestion || chatQuestion;
    if (!q.trim()) return;
    const normalizedQuestion =
      q === BLAST_RADIUS_EXPORT_PROMPT
        ? "For the current asset, create a Google Sheet for blast radius downstream assets, post the sheet link to Slack with a short risk summary, and return the links."
        : q;
    
    // Add user message to thread
    setChatMessages(prev => [...prev, { role: "user", content: q }]);
    setChatQuestion("");
    setChatLoading(true);
    
    try {
      const answer = await askChat({ question: normalizedQuestion, entity_id: selectedAsset });
      setChatMessages(prev => [...prev, { role: "assistant", content: (answer as any).answer || "No response" }]);
      const answerText = String((answer as any).answer || "");
      if (q === BLAST_RADIUS_EXPORT_PROMPT && (/slack\.com/i.test(answerText) || /View on Slack/i.test(answerText))) {
        addActionHistory({
          action: "Posted to Slack",
          target: shortName(selectedAsset),
          detail: "Blast radius export completed and a Slack link was returned.",
          confidence: "detected",
        });
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to ask MetaGuard";
      setChatMessages(prev => [...prev, { role: "assistant", content: `Error: ${message}` }]);
    } finally {
      setChatLoading(false);
      setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
    }
  }

  // DEMO POLISH: Auto-scroll to RCA when analysis completes
  useEffect(() => {
    if (rcaExplanation.data && !rcaExplanation.loading && rcaTarget) {
      setTimeout(() => {
        rcaCardRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 500); // Wait for transition animation
    }
  }, [rcaExplanation.data, rcaExplanation.loading]);
  async function handleExplain(fqn: string) {
    setTab("investigation"); // Ensure we are on the 360 Dashboard
    setRcaTarget(fqn);
    setRcaExplanation({ loading: true, error: null, data: null });
    try {
      const resp = await explainRootCause(fqn);
      setRcaExplanation({ loading: false, error: null, data: resp });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to analyze root cause";
    }
  }

  return (
    <div className={`mg-layout-split ${chatOpen ? "sidebar-open" : ""}`}>
      <main className={`proto-app mg-app-container mg-ready ${revealDone ? "mg-revealed" : "mg-locked"} mg-main-content`}>
        {/* 2. Authentication / Bootstrap Layer */}
        { !revealDone ? (
          <div className={`boot-screen ${revealStarted ? "is-pulling" : ""} ${authorizing ? "is-authorizing" : ""}`}>
            <div className="boot-shutter boot-shutter-top" />
            <div className="boot-shutter boot-shutter-bottom" />

            {/* Background Particle Engine - Hides immediately on reveal */}
            <div style={{ 
              position: "absolute", 
              top: 0, 
              left: 0, 
              right: 0, 
              bottom: 0, 
              overflow: "hidden", 
              pointerEvents: "none", 
              opacity: revealStarted ? 0 : 0.8, 
              transition: "opacity 0.4s ease",
              zIndex: 1 
            }}>
              <ParticleDatabase 
                  assembled={isEnterHovered} 
              />
            </div>
            <div className="boot-dealdesk-layout">
              <div className="boot-hero-left">
                <div className="boot-logo">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
                  </svg>
                  <span className="mg-app-title" style={{ fontSize: "16px", letterSpacing: "0.15em", color: "#fff" }}>METAGUARD</span>
                </div>
                <h1 className="boot-hero-title">
                  The sentinel for your data stack.{" "}
                  <span className="boot-hero-rotating-word" key={HERO_SENTINEL_WORDS[heroWordIndex]}>
                    {HERO_SENTINEL_WORDS[heroWordIndex]}
                  </span>
                </h1>
                <p className="boot-hero-subtitle">
                  Connect an asset and manage it with absolute precision: trust scores surfaced, lineage mapped, cascading risks clarified — all from one tactile command center.
                </p>
                <div style={{ marginTop: "32px", display: "inline-block" }}>
                  <button
                    type="button"
                    className={`boot-hero-btn ${authorizing ? "is-authorizing" : ""}`}
                    onMouseEnter={() => setIsEnterHovered(true)}
                    onMouseLeave={() => setIsEnterHovered(false)}
                    onClick={() => {
                      if (loaderReady && !authorizing) {
                        const audio = new Audio("/click.mp3");
                        audio.volume = 0.2;
                        audio.play().catch(() => {});
                        setEnterPressed(true);
                      }
                    }}
                    disabled={!loaderReady}
                  >
                    <span>{authorizing ? "Authorized" : "Open MetaGuard"}</span>
                    {!authorizing && (
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="5" y1="12" x2="19" y2="12"></line>
                        <polyline points="12 5 19 12 12 19"></polyline>
                      </svg>
                    )}
                  </button>
                </div>
                <div className="boot-hero-tags">
                  <span className="boot-hero-tag">Observe</span>
                  <span className="boot-hero-tag">Trace</span>
                  <span className="boot-hero-tag">Diagnose</span>
                  <span className="boot-hero-tag">Defend</span>
                </div>
              </div>

              <div className="boot-widget-card" style={{ transition: "all 0.4s ease", opacity: loaderReady ? 1 : 0.8, transform: loaderReady ? "translateY(0)" : "translateY(10px)" }}>
                <div className="boot-widget-header">
                  <span style={{ display: "flex", gap: "6px" }}>
                    <span style={{ color: "#fbbf24" }}>●</span>
                    <span style={{ color: "#38bdf8" }}>●</span>
                    <span style={{ color: "#4ade80" }}>●</span>
                  </span>
                </div>
                <div className="boot-widget-loader">
                  <div className="boot-widget-loader-label">SYSTEM INIT</div>
                  <div style={{ fontSize: "14px", color: "#fff", marginBottom: "12px", fontFamily: "var(--mg-font-mono)" }}>
                    {healthStatus === "Connected" ? (deadScan.loading ? "Indexing dead data..." : "Resolving profiles...") : "Awaiting engine link..."}
                  </div>
                  <div className="boot-widget-bar-bg">
                    <div className="boot-widget-bar-fill" style={{ width: `${bootProgress}%`, background: loaderReady ? "#4ade80" : "#115e59" }}></div>
                  </div>
                </div>
                <div className="boot-widget-stats">
                  <div className="boot-widget-stat">
                    <div className="boot-widget-stat-label">ALERTS</div>
                    <div className="boot-widget-stat-val">{stormAlerts.loading ? "--" : (stormAlerts.data?.total ?? 0)}</div>
                    <div className="boot-widget-stat-sub">active</div>
                  </div>
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
        {/* 3. Dashboard Shell (Visibility Gate) */}
        <div className="mg-dashboard-reveal">
          <div className="proto-topbar">
            <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
              <div className="proto-logo mg-app-title" style={{ fontSize: "13px", letterSpacing: "0.12em", fontWeight: 600, margin: 0 }}>METAGUARD</div>
              <div style={{ width: "1px", height: "14px", background: "rgba(255,255,255,0.15)" }}></div>
              <div className="mg-section-header" style={{ fontSize: "11px", letterSpacing: "0.08em", color: "var(--color-text-tertiary)" }}>DISCOVER · UNDERSTAND · PROTECT · ASSESS</div>
            </div>
            <div className="proto-topbar-side">
              <div className="mg-status-pill">
                <span className="proto-live" style={{ width: "6px", height: "6px" }} />
                <span style={{ color: "rgba(255,255,255,0.5)", fontWeight: 400 }}>OpenMetadata Local</span>
                <span style={{ width: "1px", height: "10px", background: "rgba(255,255,255,0.1)" }}></span>
                <span>{healthStatus}</span>
              </div>
            </div>
          </div>

          <div className="proto-tabs" ref={tabsRef}>
            <div className="proto-tabs-pill" style={{ left: `${pillStyle.left}px`, width: `${pillStyle.width}px`, opacity: pillStyle.opacity }} />
            <button className={`proto-tab mg-nav-tab ${tab === "investigation" ? "on" : ""}`} onClick={() => setTab("investigation")}>360° Dashboard</button>
            <button className={`proto-tab mg-nav-tab t2 ${tab === "dead" ? "on" : ""}`} onClick={() => setTab("dead")}>Dead Data</button>
          </div>

          <section className={`proto-pane ${tab === "dead" ? "on" : ""}`} style={{ padding: "0 24px 40px" }}>
            <div className="claude-dashboard mg-stagger mg-stagger-1">
              <div className="claude-header">
                <div className="claude-investigate-row">
                  <span className="mg-section-header">Scan Status</span>
                  <div style={{ fontSize: "16px", fontWeight: "700", color: "#fff", flex: 1 }}>
                    {deadScan.loading ? "Running diagnostic scan..." : `${deadScan.data?.total_candidates ?? 0} cleanup candidates identified`}
                  </div>
                  <button className="proto-btn" onClick={() => void refreshGlobal()} disabled={deadScan.loading}>
                    {deadScan.loading ? "Scanning..." : "Refresh diagnostic"}
                  </button>
                </div>
                <div className="claude-metrics-row">
                  <div className="claude-metric">
                    <div className="mg-metric-label">Monthly waste</div>
                    <div className="mg-metric-value">
                      ${Math.max(0, (deadSummary.data?.total_monthly_waste ?? 0) - frontendDeletedCost).toFixed(2)}
                      <span className="mg-metric-sublabel" style={{ color: "#f87171", marginLeft: "8px" }}>est. platform cost</span>
                    </div>
                  </div>
                  <div className="claude-metric">
                    <div className="mg-metric-label">Safe to delete</div>
                    <div className="mg-metric-value">{deadSummary.data?.safe_to_delete_count ?? 0}<span className="mg-metric-sublabel" style={{ color: "#4ade80", marginLeft: "8px" }}>immediate impact</span></div>
                  </div>
                  <div className="claude-metric">
                    <div className="mg-metric-label">Needs review</div>
                    <div className="mg-metric-value">{reviewRequired.length}<span className="mg-metric-sublabel" style={{ marginLeft: "8px" }}>governance required</span></div>
                  </div>
                  {savedCost > 0 && (
                    <div className="claude-metric" style={{ borderLeft: "0.5px solid rgba(74, 222, 128, 0.3)", background: "rgba(74, 222, 128, 0.04)" }}>
                      <div className="mg-metric-label" style={{ color: "#4ade80" }}>💰 Savings captured</div>
                      <div className="mg-metric-value" style={{ color: "#4ade80" }}>
                        <MovingNumber value={savedCost} prefix="$" suffix="/mo" duration={600} decimals={2} />
                      </div>
                    </div>
                  )}
                </div>
              </div>


              {deadAction && <div className="proto-message" style={{ marginBottom: "16px", background: "rgba(59, 130, 246, 0.1)", border: "1px solid rgba(59, 130, 246, 0.2)" }}>{deadAction}</div>}
              {deadScan.error && <div className="proto-message proto-message-error" style={{ marginBottom: "16px" }}>{deadScan.error}</div>}
              {actionHistory.length > 0 && (
                <div className="mg-history-panel" style={{ marginBottom: "20px" }}>
                  <SectionSummary
                    title="Recent Actions"
                    open={openHistory}
                    onClick={() => setOpenHistory(!openHistory)}
                    badge={`${actionHistory.length} events`}
                    badgeColor="rgba(59, 130, 246, 0.14)"
                  />
                  <Shutter open={openHistory}>
                    <div className="mg-history-list">
                      {actionHistory.map((entry) => (
                        <div key={entry.id} className="mg-history-item">
                          <div>
                            <div className="mg-history-title">{entry.action} · {entry.target}</div>
                            <div className="mg-history-copy">{entry.detail}</div>
                          </div>
                          <div className="mg-history-meta">
                            <span className={`mg-confidence-pill ${getConfidenceTone(entry.confidence)}`}>{entry.confidence}</span>
                            <div className="mg-history-time">{entry.timestamp}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </Shutter>
                  {!openHistory && (
                    <div className="mg-history-preview">
                      Latest: {actionHistory[0].action} · {actionHistory[0].target}
                    </div>
                  )}
                  </div>
                )}

              <div style={{ marginBottom: "12px" }}>
                <div className="mg-card-title" style={{ fontSize: "15px" }}>Safe to delete</div>
                <div className="mg-body" style={{ color: "var(--color-text-tertiary)" }}>Immediate cleanup candidates identified by hygiene scan</div>
              </div>
              <div style={{ marginBottom: "32px" }}>
                {safeToDelete.map((asset: any) => (
                  <div key={asset.fqn} className="mg-incident-card">
                    <div className="mg-card-row">
                      <div className="mg-asset-identifier" style={{ fontSize: "14px" }}>{asset.fqn}</div>
                      <div className="proto-impact-score" data-score={Math.round(asset.impact_score)}>
                        <span className="mg-badge-label">IMPACT</span><strong>{Math.round(asset.impact_score)}</strong>
                      </div>
                    </div>
                    <div className="mg-body" style={{ fontSize: "13px", color: "var(--color-text-secondary)", marginTop: "-4px" }}>{asset.notes?.join(" · ") || `${asset.category} asset with no active downstream consumers`}</div>
                    <div className="mg-card-row" style={{ marginTop: "4px" }}>
                      <div className="mg-metadata-row">
                        <div className={`mg-severity-pill ${asset.impact_score > 70 ? "critical" : "high"}`}><span className={`mg-severity-dot ${asset.impact_score > 70 ? "critical" : "high"}`} />{asset.impact_score > 70 ? "CRITICAL" : "HIGH"}</div>
                        <span className="mg-confidence-pill detected">detected</span>
                        <span style={{ fontSize: "12px", fontFamily: "var(--mg-font-mono)", opacity: 0.6 }}>636 queries/mo</span>
                        <span className="mg-tag-pill">{String(asset.category)}</span>
                        <span style={{ fontSize: "12px", fontFamily: "var(--mg-font-mono)", color: "#10b981" }}>${(asset.monthly_cost_estimate ?? 0).toFixed(2)}/mo</span>
                      </div>
                      <div style={{ display: "flex", gap: "8px" }}>
                        <button className="proto-btn mg-button-ghost" onClick={() => handleTrace(asset.fqn)}>Trace →</button>
                        <button className="proto-btn mg-button-ghost" onClick={() => void handleDeadReview(asset.fqn)}>Review</button>
                        <button className="proto-btn" style={{ background: "rgba(239, 68, 68, 0.1)", color: "#f87171", border: "1px solid rgba(239, 68, 68, 0.2)" }} onClick={() => void handleDeadRemove(asset.fqn, asset.monthly_cost_estimate ?? 0)}>Remove</button>
                      </div>
                    </div>
                  </div>
                ))}
                {!safeToDelete.length && !deadScan.loading && <div style={{ color: "#a1a1aa", fontSize: "12px", fontStyle: "italic", padding: "10px" }}>No safe-delete assets are currently available.</div>}
              </div>

              <div style={{ marginBottom: "12px" }}>
                <div className="mg-card-title" style={{ fontSize: "15px" }}>Needs human review</div>
                <div className="mg-body" style={{ color: "var(--color-text-tertiary)" }}>Lineage or usage signals require operator decision</div>
              </div>
              <div style={{ marginBottom: "24px" }}>
                {(showAllReview ? reviewRequired : reviewRequired.slice(0, 3)).map((asset: any) => (
                  <div key={asset.fqn} className="mg-incident-card">
                    <div className="mg-card-row">
                      <div className="mg-asset-identifier" style={{ fontSize: "14px" }}>{asset.fqn}</div>
                      <div className="proto-impact-score" data-score={Math.round(asset.impact_score)}>
                        <span className="mg-badge-label">IMPACT</span><strong>{Math.round(asset.impact_score)}</strong>
                      </div>
                    </div>
                    <div className="mg-body" style={{ fontSize: "13px", color: "var(--color-text-secondary)", marginTop: "-4px" }}>{asset.notes?.join(" · ") || "Manual validation recommended base."}</div>
                    <div className="mg-card-row" style={{ marginTop: "4px" }}>
                      <div className="mg-metadata-row">
                        <div className="mg-severity-pill high"><span className="mg-severity-dot high" />HIGH</div>
                        <span className="mg-confidence-pill inferred">inferred</span>
                        <span className="mg-tag-pill">REVIEW</span>
                        <span style={{ fontSize: "12px", fontFamily: "var(--mg-font-mono)", color: "#f59e0b" }}>${(asset.monthly_cost_estimate ?? 0).toFixed(2)}/mo</span>
                      </div>
                      <div style={{ display: "flex", gap: "8px" }}>
                        <button className="proto-btn mg-button-ghost" onClick={() => handleTrace(asset.fqn)}>Trace →</button>
                        <button className="proto-btn mg-button-ghost" onClick={() => void handleDeadReview(asset.fqn)}>Mark reviewed</button>
                        <button
                          className="proto-btn"
                          style={{ background: "rgba(239, 68, 68, 0.1)", color: "#f87171", border: "1px solid rgba(239, 68, 68, 0.2)" }}
                          onClick={() => handleDeleteReview(asset.fqn, asset.monthly_cost_estimate ?? 0)}
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
                {reviewRequired.length > 3 && !showAllReview && (
                  <button className="proto-btn" style={{ width: "100%", marginTop: "8px", background: "rgba(255,255,255,0.03)", border: "1px dashed rgba(255,255,255,0.1)", color: "#a1a1aa" }} onClick={() => setShowAllReview(true)}>View all {reviewRequired.length} items in queue ↓</button>
                )}
                {!reviewRequired.length && !deadScan.loading && <div style={{ color: "#a1a1aa", fontSize: "12px", fontStyle: "italic", padding: "10px" }}>No review-required assets remain in the queue.</div>}
              </div>
            </div>
          </section>

          {/* Pane 2: 360 Dashboard */}
          <section className={`proto-pane ${tab === "investigation" ? "on" : ""}`} style={{ padding: "0 20px 40px" }}>
            <div className="claude-dashboard mg-stagger mg-stagger-1">
              <div className="claude-header mg-stagger mg-stagger-1">
                <div className="claude-investigate-row">
                  <span className="mg-section-header">Investigating</span>
                  <AestheticSelect style={{ width: "420px", background: "rgba(255,255,255,0.05)", border: "none" }} labelClassName="mg-asset-identifier-large" value={selectedAsset} options={[...assetOptions]} onChange={(v) => { setSelectedAsset(v); setBarAnimKey(k => k + 1); }} />
                  <div className={`claude-alert-pill mg-badge-label ${currentAlerts.length === 0 ? "healthy" : ""}`}>{currentAlerts.length === 0 ? "Healthy" : `${currentAlerts.length} active alerts`}</div>
                  <span className="mg-confidence-pill inferred">inferred</span>
                </div>
                <div className="mg-kpi-strip">
                  <div className="mg-kpi-item">
                    <div className="mg-metric-label">MetaGuard Trust</div>
                    <div className="mg-metric-value" style={{ color: scoreColor }}>
                      {passport.loading ? "--" : <MovingNumber value={trustScore} />}
                    </div>
                    <div className="mg-metric-sublabel">composite score</div>
                    <div className="mg-score-why">{trustReasonSummary}</div>
                    <div className="mg-score-chip-row">
                      {trustWhyChips.map((chip) => (
                        <span key={chip} className="mg-score-chip">{chip}</span>
                      ))}
                    </div>
                  </div>
                  <div className="mg-kpi-item">
                    <div className="mg-metric-label">Reliability SLA</div>
                    <div className="mg-metric-value" style={{ color: "#10b981" }}>99.8%</div>
                    <div className="mg-metric-sublabel">in spec</div>
                  </div>
                  <div className="mg-kpi-item">
                    <div className="mg-metric-label">Impact Blast</div>
                    <div className="mg-metric-value">{blastNodes.length}</div>
                    <div className="mg-metric-sublabel">downstream nodes</div>
                    <div className="mg-score-why">{impactReasonSummary}</div>
                    <div className="mg-score-chip-row">
                      {impactWhyChips.map((chip) => (
                        <span key={chip} className="mg-score-chip">{chip}</span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              <div ref={revealPassport} className="claude-accordion mg-reveal">
                <SectionSummary title="Diagnostic profile" open={openPassport} onClick={() => setOpenPassport(!openPassport)} badge="Inferred" badgeColor="rgba(99, 102, 241, 0.16)" />
                <Shutter open={openPassport}>
                  <div className="claude-accordion-content" style={{ display: "grid", gap: "24px", padding: "24px" }}>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr auto 2.2fr auto 1.4fr", gap: "0", alignItems: "center", background: "rgba(24, 24, 27, 0.4)", padding: "32px 24px", borderRadius: "12px", border: "0.5px solid rgba(255,255,255,0.05)" }}>
                      <div style={{ textAlign: "right", paddingRight: "32px" }}>
                        <div className="mg-badge-label" style={{ color: "var(--color-text-tertiary)", marginBottom: "4px" }}>Trust score</div>
                        <div className="mg-score-update" style={{ fontSize: "52px", color: scoreColor, fontWeight: 500, lineHeight: 1, fontFamily: "var(--mg-font-ui)" }}>
                          {passport.loading ? "--" : <MovingNumber value={trustScore} />}
                        </div>
                        <div style={{ fontSize: "11px", color: "var(--color-text-tertiary)", marginTop: "4px" }}>composite score</div>
                      </div>
                      <div style={{ width: "0.5px", height: "160px", background: "rgba(255,255,255,0.1)" }}></div>
                      <div style={{ padding: "0 40px", display: "flex", justifyContent: "center" }}>
                        <DiagnosticRadar data={radarData.map(d => ({ pillar: d.subject, score: d.value }))} />
                      </div>
                      <div style={{ width: "0.5px", height: "160px", background: "rgba(255,255,255,0.1)" }}></div>
                      <div style={{ paddingLeft: "32px", minWidth: "160px" }}>
                        <div className="mg-badge-label" style={{ color: "var(--color-text-tertiary)", marginBottom: "12px" }}>Pillar breakdown</div>
                        <div style={{ display: "grid", gap: "8px" }}>
                          {radarData.map((d, i) => (
                            <div key={d.subject}>
                              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px", fontSize: "11px" }}>
                                <span style={{ color: "var(--color-text-secondary)" }}>{d.subject}</span>
                                <span style={{ fontFamily: "var(--mg-font-mono)", color: getMgColor(d.value), fontWeight: 500 }}>{d.value}</span>
                              </div>
                              <div style={{ height: "3px", background: "rgba(255,255,255,0.07)", borderRadius: "2px", overflow: "hidden" }}>
                                <AnimatedBar key={`${barAnimKey}-${d.subject}`} value={d.value} color={getMgColor(d.value)} delay={i * 80} />
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1.2fr 0.8fr", gap: "24px", paddingTop: "12px", alignItems: "start" }}>
                      <div>
                        <div className="mg-section-header" style={{ marginBottom: "16px" }}>Core Metadata</div>
                        <div className="claude-grid">
                          <div>
                            <div className="claude-dl"><div className="mg-metric-label">Schema</div><div className="mg-asset-identifier" style={{ fontSize: "12px" }}>{selectedAsset.split(".").slice(0, 2).join(".")}</div></div>
                            <div className="claude-dl" style={{ marginTop: "16px" }}><div className="mg-metric-label">Freshness</div><div className="mg-asset-identifier" style={{ fontSize: "12px" }}>2h 14m stale</div></div>
                          </div>
                          <div>
                            <div className="claude-dl"><div className="mg-metric-label">Last updated</div><div className="mg-asset-identifier" style={{ fontSize: "12px" }}>Apr 12 09:42</div></div>
                            <div className="claude-dl" style={{ marginTop: "16px" }}><div className="mg-metric-label">SLA</div><div className="mg-asset-identifier" style={{ fontSize: "12px" }}>Daily 08:00</div></div>
                          </div>
                        </div>
                      </div>
                      <p className="mg-body" style={{ fontSize: "12px", color: "var(--color-text-tertiary)", lineHeight: "1.6", margin: 0 }}>The Trust Score is a composite health metric derived from MetaGuard framework pillars.</p>
                    </div>
                  </div>
                </Shutter>
              </div>

              <div ref={revealBlast} className="claude-accordion mg-reveal">
                <SectionSummary title="Blast radius" open={openBlast} onClick={() => setOpenBlast(!openBlast)} badge={`${blastNodes.length} downstream · inferred`} badgeColor="rgba(239, 68, 68, 0.1)" />
                <Shutter open={openBlast}>
                  <div className="claude-accordion-content" style={{ padding: "0" }}>
                    {blastNodes.length > 0 ? (
                      <div style={{ padding: "20px" }}>
                        <BlastRadiusVisual 
                          nodes={blastNodes} 
                          sourceFqn={selectedAsset} 
                          isChatOpen={chatOpen}
                          onSelectNode={(node) => {
                            if (node) setOpenRca(false);
                            else setOpenRca(true);
                          }}
                        />
                      </div>
                    ) : (
                      <div style={{ padding: "20px", color: "#a1a1aa", fontSize: "12px", fontStyle: "italic" }}>No downstream consumers.</div>
                    )}
                  </div>
                </Shutter>
              </div>

              <div ref={revealStorm} className="claude-accordion mg-reveal">
                <SectionSummary 
                  title="Production surveillance" 
                  open={openStorm} 
                  onClick={() => setOpenStorm(!openStorm)} 
                  badge={currentAlerts.length > 0 ? `${currentAlerts.length} active warnings · simulated` : "Sandbox · simulated"} 
                  badgeColor={currentAlerts.length > 0 ? "rgba(239, 68, 68, 0.15)" : ""} 
                />
                <Shutter open={openStorm}>
                  <div className="claude-accordion-content" style={{ padding: "0", background: "rgba(0,0,0,0.1)" }}>
                    <div style={{ padding: "20px" }}>
                      <div className="claude-sim-form" style={{ display: "grid", gap: "16px" }}>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                          <div><label className="mg-form-label">Change type</label><AestheticSelect labelClassName="mg-form-input" style={{ width: "100%", background: "#0a0a0a", border: "none", marginTop: "8px" }} value={simType} options={["Column drop", "Data type edit", "Field rename", "Null surge", "Freshness delay"]} onChange={(v) => setSimType(v)} /></div>
                          <div><label className="mg-form-label">Field</label><AestheticSelect labelClassName="mg-form-input" style={{ width: "100%", background: "#0a0a0a", border: "none", marginTop: "8px" }} value={simColumn} options={(passport.data?.metadata?.table?.columns ?? [{ name: "order_id" }]).map((c: any) => c.name)} onChange={(v) => setSimColumn(v)} /></div>
                        </div>
                        <button className="proto-btn mg-button-amber-ghost" onClick={() => void handleSimulate()} disabled={simulating || passport.loading} style={{ marginTop: "8px", width: "fit-content", padding: "12px 24px" }}>{simulating ? "Simulating..." : "Run simulation ↗"}</button>
                      </div>
                    </div>
                    {currentAlerts.length > 0 && <div style={{ padding: "24px" }}><ProductionRiskVisual alerts={currentAlerts} selectedAlertId={selectedAlertId} onSelectAlert={(id) => setSelectedAlertId(id)} /></div>}
                  </div>
                </Shutter>
              </div>

              <div ref={revealRca} className="claude-accordion mg-reveal">
                <SectionSummary 
                   title="Root cause hub" 
                   open={openRca} 
                   onClick={() => setOpenRca(!openRca)} 
                   badge={rcaTarget ? "Active analysis" : "No active trace"} 
                />
                <Shutter open={openRca}>
                  <div className="claude-accordion-content" style={{ padding: "0" }}>
                    <Shutter open={!rcaTarget}>
                      <div className="mg-orchestrator-idle">
                        <div className="mg-pulse-dot" />
                        <div style={{ fontSize: "15px", fontWeight: 700, color: "#fff", marginBottom: "4px" }}>Orchestrator Idle</div>
                        <div className="mg-body" style={{ color: "var(--color-text-tertiary)", maxWidth: "360px", margin: "0 auto 20px" }}>
                          The Root Cause Hub is actively monitoring telemetry signals. To begin a diagnostic trace, please choose an entry point:
                        </div>
                        <div style={{ display: "grid", gap: "12px" }}>
                          <div className="mg-instruction-step">
                            <span className="mg-instruction-key">Step 1</span> Select <span className="mg-instruction-key" style={{ background: "rgba(59, 130, 246, 0.1)", color: "#60a5fa", border: "1px solid rgba(59, 130, 246, 0.2)" }}>Trace →</span> on any candidate in the queue
                          </div>
                          <div className="mg-instruction-step">
                            <span className="mg-instruction-key">Step 2</span> Or click <span className="mg-instruction-key" style={{ background: "rgba(245, 158, 11, 0.1)", color: "#fbbf24", border: "1px solid rgba(245, 158, 11, 0.2)" }}>Run simulation ↗</span> to test a data drift scenario
                          </div>
                        </div>
                      </div>
                    </Shutter>

                    <Shutter open={!!(rcaTarget && rcaExplanation.loading && !rcaExplanation.data)}>
                      <div className="mg-rca-loader">
                        <div className="mg-scanner-line" />
                        <div className="ai-thinking" style={{ transform: "scale(1.2)" }}>
                          <div /><div /><div />
                        </div>
                        <div className="mg-loader-status">Diagnostic Trace in Progress...</div>
                        <div style={{ color: "var(--color-text-tertiary)", fontSize: "11px", marginTop: "8px" }}>
                          Analyzing metadata signals & lineage drift
                        </div>
                      </div>
                    </Shutter>

                    <Shutter open={!!(rcaTarget && rcaExplanation.data && !rcaExplanation.loading)}>
                      {rcaExplanation.data && (
                        <div className="mg-report-card mg-content-fade" ref={rcaCardRef}>
                          <div className="mg-report-header">
                            <div className="mg-report-title-group">
                              <div className="mg-report-meta">
                                <div className={`mg-report-badge ${rcaExplanation.data.severity}`}>{rcaExplanation.data.severity}</div>
                                <div className="mg-report-badge" style={{ background: "rgba(255,255,255,0.05)", color: "#a1a1aa" }}>{currentAlerts.find((a: any) => a.id === selectedAlertId)?.category ?? "Anomaly"}</div>
                              </div>
                              <h2 className="mg-card-title" style={{ fontSize: "20px", margin: 0 }}>{rcaExplanation.data.title}</h2>
                              <div className="mg-asset-identifier" style={{ opacity: 0.6 }}>{rcaExplanation.data.fqn}</div>
                            </div>
                            <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
                              <span style={{ fontSize: "11px", color: "var(--color-text-tertiary)" }}>Just now</span>
                              <div style={{ width: "32px", height: "32px", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", opacity: 0.4 }}>•••</div>
                            </div>
                          </div>
                          
                          <div className="mg-report-body">
                            {rcaExplanation.data.narrative}
                          </div>

                          <div className="mg-report-footer">
                            <div className="mg-report-section">
                              <div className="rca-section-label">Verdict</div>
                              <div className="rca-root-cause">
                                {rcaExplanation.data.root_cause}
                              </div>
                            </div>
                            
                            <div className="mg-report-divider">
                               <div className="mg-divider-junction">
                                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                                    <path d="M7 13l5 5 5-5M7 6l5 5 5-5" strokeLinecap="round" strokeLinejoin="round" />
                                  </svg>
                               </div>
                            </div>

                            <div className="mg-report-section">
                              <div className="rca-section-label">Recommended Actions</div>
                              <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "12px" }}>
                                {(rcaExplanation.data.suggested_actions || rcaExplanation.data.actions || ["No immediate action required."]).map((action: string, i: number) => (
                                  <li key={i} style={{ display: "flex", gap: "12px", alignItems: "start", fontSize: "14px", color: "var(--color-text-secondary)", lineHeight: "1.5" }}>
                                    <span style={{ color: "#fbbf24", fontWeight: 900 }}>·</span>
                                    {action}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          </div>

                          <div style={{ borderTop: "0.5px solid rgba(255,255,255,0.05)", padding: "16px 24px", background: "rgba(0,0,0,0.1)" }}>
                            <button className="proto-btn mg-button-ghost" onClick={() => {
                              setRcaTarget(null);
                              setSelectedAlertId(null);
                            }}>Close trace</button>
                          </div>
                        </div>
                      )}
                    </Shutter>
                  </div>
                </Shutter>
              </div>
            </div>
          </section>
          </div> {/* End mg-dashboard-reveal */}
        </main>

          {revealDone && (
            <aside className={`mg-assistant-sidebar ${chatOpen ? "sidebar-open" : ""}`}>
            <div className="mg-sidebar-toggle-handle" onClick={() => toggleChat()}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ transition: "transform 0.3s ease", transform: chatOpen ? "rotate(180deg)" : "rotate(0deg)" }}>
                <polyline points="15 18 9 12 15 6"></polyline>
              </svg>
              <div className="mg-sidebar-label">MetaGuard AI</div>
            </div>
            <div className="mg-assistant-header">
              <div className="mg-assistant-title">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                MetaGuard Assistant
              </div>
              <button className="mg-assistant-close" onClick={() => toggleChat(false)} aria-label="Close MetaGuard Assistant">
                <span>Close</span>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 6 6 18" />
                  <path d="m6 6 12 12" />
                </svg>
              </button>
            </div>
            <div className="mg-assistant-content proto-custom-scrollbar">
              {chatMessages.length === 0 && !chatLoading ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  <p style={{ color: "#71717a", fontSize: "12px", fontStyle: "italic", margin: "0 0 10px 0" }}>
                    Ask about trust risks, lineage, dead data cost savings, or automate exports to Google Sheets and Slack.
                  </p>
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {[
                      "Export all dead data assets to a Google Sheet",
                      "Who owns this? Post a summary to #incidents",
                      "Summarise integrity risks",
                      "Show me active surveillance alerts",
                      BLAST_RADIUS_EXPORT_PROMPT,
                    ].map((s) => (
                      <button key={s} onClick={() => handleChat(s)} className="ai-suggestion-chip">{s}</button>
                    ))}
                  </div>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column" }}>
                  {chatMessages.map((msg, i) => (
                    <div key={i} className={`mg-chat-bubble ${msg.role === "assistant" ? "ai" : "user"}`}>
                      {msg.role === "assistant" && <div style={{ color: "rgba(255,255,255,0.4)", fontWeight: "700", fontSize: "9px", marginBottom: "4px", textTransform: "uppercase", letterSpacing: "0.1em" }}>AI</div>}
                      <span dangerouslySetInnerHTML={{__html: msg.content.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>').replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" style="color: #60a5fa; text-decoration: underline;">$1</a>')}} />
                    </div>
                  ))}
                  {chatLoading && (
                    <div className="ai-thinking" style={{ padding: "0 10px 20px" }}><div /><div /><div /></div>
                  )}
                  <div ref={chatEndRef} />
                </div>
              )}
            </div>
            <div className="mg-assistant-footer">
              <div className="mg-chat-input-wrapper">
                <input
                  className="mg-chat-input-sidebar"
                  placeholder="Type a command..."
                  value={chatQuestion}
                  onChange={(e) => setChatQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleChat()}
                />
                <button 
                  className="mg-chat-send-btn" 
                  onClick={() => handleChat()} 
                  disabled={chatLoading}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="22" y1="2" x2="11" y2="13" />
                    <polygon points="22 2 15 22 11 13 2 9 22 2" />
                  </svg>
                </button>
              </div>
            </div>
          </aside>
        )}
        {/* End mg-layout-split */}
      </div>
    );
}
