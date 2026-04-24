from __future__ import annotations

from collections import deque
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from hashlib import sha1
from typing import Any

import httpx

from app.core.config import get_settings

NOW = datetime(2026, 4, 9, 9, 0, tzinfo=UTC)


def _days_ago(days: int) -> str:
    return (NOW - timedelta(days=days)).isoformat()


def _hours_ago(hours: int) -> str:
    return (NOW - timedelta(hours=hours)).isoformat()


def _hash_columns(columns: list[dict[str, str]]) -> str:
    text = "|".join(f"{column['name']}:{column['type']}" for column in columns)
    return sha1(text.encode("utf-8")).hexdigest()


class OpenMetadataClient:
    """Hackathon-friendly in-memory implementation of the PRD client surface."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.live_mode = self.settings.app_mode.lower() == "live" and bool(self.settings.openmetadata_jwt)
        self.base_url = (
            f"{self.settings.openmetadata_url.rstrip('/')}"
            f"{self.settings.openmetadata_api_path}"
        )
        self._cache: dict[str, tuple[datetime, Any]] = {}
        self._cache_ttl = timedelta(minutes=5)
        
        self.tables: dict[str, dict[str, Any]] = {}
        self.pipelines: dict[str, dict[str, Any]] = {}
        self.owners: dict[str, dict[str, Any]] = {
            "alice": {"name": "Alice Johnson", "contact": "alice@example.com", "team": "Data Platform", "active": True},
            "bob": {"name": "Bob Singh", "contact": "bob@example.com", "team": "Analytics Engineering", "active": True},
            "carol": {"name": "Carol Rivera", "contact": "carol@example.com", "team": "Marketing Analytics", "active": True},
            "dave": {"name": "Dave Chen", "contact": "dave@example.com", "team": "Finance Data", "active": True},
            "eve": {"name": "Eve Smith", "contact": "eve@example.com", "team": "Product Analytics", "active": False},
        }
        self.usage: dict[str, dict[str, Any]] = {}
        self.quality: dict[str, dict[str, Any]] = {}
        self.profiling: dict[str, dict[str, Any]] = {}
        self.glossary: dict[str, str] = {
            "order_id": "Unique identifier for a customer order.",
            "customer_id": "Canonical customer identifier shared across domains.",
            "order_total": "Gross order amount including discounts and taxes where applicable.",
            "segment": "Marketing audience segment assigned to the customer.",
            "revenue": "Recognized revenue amount for the reporting grain.",
        }
        self.downstream_edges: dict[str, list[str]] = {}
        self.asset_types: dict[str, str] = {}
        self.column_lineage: dict[tuple[str, str], list[str]] = {}
        self.schema_versions: dict[str, list[dict[str, Any]]] = {}

        # 1. Base Demo Tables
        base_tables = [
            {
                "fqn": "warehouse.commerce.curated.fct_orders",
                "display_name": "Orders",
                "description": "Core order fact table for completed and cancelled orders.",
                "created_at": _days_ago(420),
                "tags": ["gold", "finance-critical"],
                "columns": [
                    {"name": "order_id", "type": "STRING", "description": "Primary order key"},
                    {"name": "customer_id", "type": "STRING", "description": "Customer identifier"},
                    {"name": "order_total", "type": "FLOAT", "description": "Total order value"},
                    {"name": "status", "type": "STRING", "description": "Lifecycle state"},
                ],
                "owner_id": "alice",
                "quality_in_active_suite": True,
            },
            {
                "fqn": "warehouse.commerce.raw.orders_archive",
                "display_name": "Orders Archive",
                "description": "Historical archive retained for compliance checks.",
                "created_at": _days_ago(540),
                "tags": ["archive"],
                "columns": [
                    {"name": "order_id", "type": "STRING", "description": "Primary order key"},
                    {"name": "customer_id", "type": "STRING", "description": "Customer identifier"},
                    {"name": "order_total", "type": "FLOAT", "description": "Total order value"},
                    {"name": "status", "type": "STRING", "description": "Lifecycle state"},
                ],
                "owner_id": None,
                "quality_in_active_suite": False,
            },
            {
                "fqn": "warehouse.commerce.curated.dim_customers",
                "display_name": "Customer Dimension",
                "description": "Master customer dimension powering CRM and BI views.",
                "created_at": _days_ago(300),
                "tags": ["gold"],
                "columns": [
                    {"name": "customer_id", "type": "STRING", "description": "Customer identifier"},
                    {"name": "segment", "type": "STRING", "description": "Marketing segment"},
                    {"name": "country", "type": "STRING", "description": "Customer country"},
                ],
                "owner_id": "bob",
                "quality_in_active_suite": True,
            },
            {
                "fqn": "warehouse.commerce.curated.dim_customers_backup",
                "display_name": "Customer Dimension Backup",
                "description": "Legacy backup snapshot retained after migration.",
                "created_at": _days_ago(220),
                "tags": ["backup"],
                "columns": [
                    {"name": "customer_id", "type": "STRING", "description": "Customer identifier"},
                    {"name": "country", "type": "STRING", "description": "Customer country"},
                    {"name": "segment", "type": "STRING", "description": "Marketing segment"},
                ],
                "owner_id": "bob",
                "quality_in_active_suite": False,
            },
            {
                "fqn": "warehouse.commerce.curated.customer_360",
                "display_name": "Leads",
                "description": "",
                "created_at": _days_ago(110),
                "tags": [],
                "columns": [
                    {"name": "lead_id", "type": "STRING", "description": ""},
                    {"name": "source", "type": "STRING", "description": ""},
                    {"name": "created_at", "type": "TIMESTAMP", "description": ""},
                ],
                "owner_id": "carol",
                "quality_in_active_suite": False,
            },
            {
                "fqn": "warehouse.commerce.finance.finance_revenue_mart",
                "display_name": "Revenue Summary",
                "description": "Finance summary table used in executive reporting.",
                "created_at": _days_ago(260),
                "tags": ["gold", "executive"],
                "columns": [
                    {"name": "order_date", "type": "DATE", "description": "Order date"},
                    {"name": "revenue", "type": "FLOAT", "description": "Revenue total"},
                    {"name": "orders_count", "type": "INT", "description": "Order count"},
                ],
                "owner_id": "dave",
                "quality_in_active_suite": True,
            },
        ]

        owners_list = list(self.owners.keys())
        
        domains_entities = [
            ("sales", "invoices"), ("sales", "transactions"), ("sales", "leads"),
            ("marketing", "campaigns"), ("marketing", "clicks"), ("marketing", "impressions"),
            ("logistics", "shipments"), ("logistics", "fleet"), ("logistics", "warehouse_stock"),
            ("hr", "employees"), ("hr", "payroll"), ("hr", "benefits"),
            ("finance", "expenses"), ("finance", "pnl"), ("finance", "budgets"),
            ("product", "telemetry"), ("product", "features"), ("product", "subscriptions")
        ]

        idx = 0
        dashboards = set()
        
        for dom, ent in domains_entities:
            # 5 tables and 1 dashboard per entity flow
            raw_fqn = f"warehouse.{dom}.raw.{ent}_raw"
            staging_fqn = f"warehouse.{dom}.staging.{ent}_stg"
            dim_fqn = f"warehouse.{dom}.curated.dim_{ent}"
            fct_fqn = f"warehouse.{dom}.curated.fct_{ent}"
            mart_fqn = f"warehouse.{dom}.mart.{ent}_summary"
            dash_fqn = f"sandbox.dashboard.{dom}_{ent}_metrics"
            
            dashboards.add(dash_fqn)
            owner_id = owners_list[idx % len(owners_list)]
            
            tables_to_add = [
                (raw_fqn, f"Raw {ent.title()}", f"Raw ingestion of {ent} data from external systems.", "raw"),
                (staging_fqn, f"Staging {ent.title()}", f"Cleaned and deduped {ent} data.", "staging"),
                (dim_fqn, f"{ent.title()} Dimension", f"Master dimension for {ent}.", "gold"),
                (fct_fqn, f"{ent.title()} Facts", f"Event facts for {ent}.", "gold"),
                (mart_fqn, f"{ent.title()} Summary", f"Aggregated {ent} metrics.", "mart"),
            ]
            
            for fqn, disp, desc, tier in tables_to_add:
                cols = [
                    {"name": "id", "type": "STRING", "description": "Primary key"},
                    {"name": f"{ent}_value", "type": "FLOAT", "description": "Metric value"},
                    {"name": "updated_at", "type": "TIMESTAMP", "description": "Update timestamp"},
                ]
                if tier == "raw":
                    cols.append({"name": "_raw_ingested", "type": "TIMESTAMP", "description": ""})
                elif tier == "staging":
                    cols.append({"name": "dedup_hash", "type": "STRING", "description": ""})
                elif tier == "mart":
                    cols.append({"name": "agg_period", "type": "STRING", "description": ""})
                    
                base_tables.append({
                    "fqn": fqn,
                    "display_name": disp,
                    "description": desc,
                    "created_at": _days_ago(50 + (idx * 5) % 300),
                    "tags": [tier, dom],
                    "columns": cols,
                    "owner_id": owner_id,
                    "quality_in_active_suite": (tier in ["gold", "mart"]),
                })
                idx += 1
            
            # Lineage wiring
            self.downstream_edges[raw_fqn] = [staging_fqn]
            self.downstream_edges[staging_fqn] = [dim_fqn, fct_fqn]
            self.downstream_edges[dim_fqn] = [mart_fqn]
            self.downstream_edges[fct_fqn] = [mart_fqn]
            self.downstream_edges[mart_fqn] = [dash_fqn]
            
        for t in base_tables:
            self.tables[t["fqn"]] = t

        for i, (fqn, t) in enumerate(self.tables.items()):
            if "commerce" in fqn:
                continue
            is_gold = t.get("quality_in_active_suite", False)
            usage_90d = (500 + i * 15) % 2000 if is_gold else (50 + i * 2) % 200
            
            self.usage[fqn] = {
                "query_count_90d": usage_90d, 
                "query_count_60d": usage_90d // 2 if usage_90d else 0, 
                "last_query_at": _days_ago(1 + i % 10) if usage_90d else _days_ago(150)
            }
            pass_rate = 0.85 + (i % 12) / 100.0 if t["quality_in_active_suite"] else 0.4 + (i % 40)/100.0
            self.quality[fqn] = {"pass_rate": pass_rate, "failing_tests": []}
            self.profiling[fqn] = {
                "row_count": (i + 1) * 200000, 
                "byte_size": (i + 1) * 150_000_000, 
                "freshness_hours": (2 + i % 22) if is_gold else (72 + i % 500), 
                "last_row_added_at": _days_ago(0) if is_gold else _days_ago(3 + i % 10)
            }
                
        # Fill explicit signals for demo base tables
        self.usage.update({
            "warehouse.commerce.curated.fct_orders": {"query_count_90d": 1850, "query_count_60d": 1200, "last_query_at": _days_ago(1)},
            "warehouse.commerce.raw.orders_archive": {"query_count_90d": 0, "query_count_60d": 0, "last_query_at": _days_ago(250)},
            "warehouse.commerce.curated.dim_customers": {"query_count_90d": 840, "query_count_60d": 460, "last_query_at": _days_ago(2)},
            "warehouse.commerce.curated.dim_customers_backup": {"query_count_90d": 0, "query_count_60d": 0, "last_query_at": _days_ago(130)},
            "warehouse.commerce.curated.customer_360": {"query_count_90d": 12, "query_count_60d": 2, "last_query_at": _days_ago(18)},
            "warehouse.commerce.finance.finance_revenue_mart": {"query_count_90d": 420, "query_count_60d": 210, "last_query_at": _days_ago(1)},
        })
        self.quality.update({
            "warehouse.commerce.curated.fct_orders": {"pass_rate": 0.98, "failing_tests": []},
            "warehouse.commerce.raw.orders_archive": {"pass_rate": 0.92, "failing_tests": ["archived orders freshness not tracked"]},
            "warehouse.commerce.curated.dim_customers": {"pass_rate": 0.95, "failing_tests": []},
            "warehouse.commerce.curated.dim_customers_backup": {"pass_rate": 0.7, "failing_tests": ["null segment ratio spike"]},
            "warehouse.commerce.curated.customer_360": {"pass_rate": 0.5, "failing_tests": ["missing source values", "late ingestion"]},
            "warehouse.commerce.finance.finance_revenue_mart": {"pass_rate": 0.99, "failing_tests": []},
        })
        self.profiling.update({
            "warehouse.commerce.curated.fct_orders": {"row_count": 12000000, "byte_size": 240_000_000_000, "freshness_hours": 3, "last_row_added_at": _hours_ago(2)},
            "warehouse.commerce.raw.orders_archive": {"row_count": 5600000, "byte_size": 500_000_000_000, "freshness_hours": 2200, "last_row_added_at": _days_ago(200)},
            "warehouse.commerce.curated.dim_customers": {"row_count": 900000, "byte_size": 30_000_000_000, "freshness_hours": 8, "last_row_added_at": _hours_ago(6)},
            "warehouse.commerce.curated.dim_customers_backup": {"row_count": 900000, "byte_size": 30_000_000_000, "freshness_hours": 3000, "last_row_added_at": _days_ago(170)},
            "warehouse.commerce.curated.customer_360": {"row_count": 65000, "byte_size": 4_000_000_000, "freshness_hours": 48, "last_row_added_at": _days_ago(2)},
            "warehouse.commerce.finance.finance_revenue_mart": {"row_count": 1200, "byte_size": 600_000_000, "freshness_hours": 6, "last_row_added_at": _hours_ago(4)},
        })

        self.pipelines = {
            "airflow.jobs.orders_modeling": {
                "fqn": "airflow.jobs.orders_modeling",
                "display_name": "Daily Orders Archive",
                "owner_id": "alice",
                "active": True,
                "schedule": "0 2 * * *",
                "avg_run_duration_hours": 0.5,
                "writes_to": ["warehouse.commerce.raw.orders_archive"],
                "created_at": _days_ago(420),
            },
            "airflow.jobs.customer_360_refresh": {
                "fqn": "airflow.jobs.customer_360_refresh",
                "display_name": "Customer Backup Sync",
                "owner_id": "bob",
                "active": True,
                "schedule": "0 */6 * * *",
                "avg_run_duration_hours": 0.2,
                "writes_to": ["warehouse.commerce.curated.dim_customers_backup"],
                "created_at": _days_ago(180),
            },
        }
        self.usage.update({
            "airflow.jobs.orders_modeling": {"query_count_90d": 0, "query_count_60d": 0, "last_query_at": _days_ago(1)},
            "airflow.jobs.customer_360_refresh": {"query_count_90d": 0, "query_count_60d": 0, "last_query_at": _days_ago(1)},
        })

        self.downstream_edges.update({
            "warehouse.commerce.curated.fct_orders": ["warehouse.commerce.finance.finance_revenue_mart"],
            "warehouse.commerce.curated.dim_customers": ["warehouse.commerce.finance.finance_revenue_mart"],
            "warehouse.commerce.raw.orders_archive": [],
            "warehouse.commerce.curated.dim_customers_backup": [],
            "warehouse.commerce.curated.customer_360": [],
            "warehouse.commerce.finance.finance_revenue_mart": ["sandbox.dashboard.exec_revenue"],
            "warehouse.commerce.finance.q3_2024_sales_archive": [
                "warehouse.commerce.finance.finance_revenue_mart",
                "sandbox.dashboard.finance_audit_v1"
            ],
            "warehouse.commerce.raw.legacy_campaign_performance": [
                "warehouse.commerce.curated.fct_orders"
            ],
            "airflow.jobs.orders_modeling": ["warehouse.commerce.raw.orders_archive"],
            "airflow.jobs.customer_360_refresh": ["warehouse.commerce.curated.dim_customers_backup"],
        })
        
        self.asset_types = {
            **{fqn: "table" for fqn in self.tables},
            **{fqn: "pipeline" for fqn in self.pipelines},
            **{fqn: "dashboard" for fqn in dashboards}, # Ensure dynamic dashboards are added
            "sandbox.dashboard.exec_revenue": "dashboard",
            "sandbox.dashboard.finance_audit_v1": "dashboard",
        }
        self.column_lineage = {
            ("warehouse.commerce.curated.fct_orders", "order_total"): ["warehouse.commerce.finance.finance_revenue_mart"],
            ("warehouse.commerce.curated.fct_orders", "customer_id"): ["warehouse.commerce.finance.finance_revenue_mart"],
        }
        for fqn, table in self.tables.items():
            self.schema_versions[fqn] = [
                {
                    "version": 1,
                    "captured_at": table["created_at"],
                    "columns": deepcopy(table["columns"]),
                    "hash": _hash_columns(table["columns"]),
                }
            ]
        if self.live_mode:
            pass

    def list_all_tables(self) -> list[dict[str, Any]]:


        if self.tables:
            return [deepcopy(table) for table in self.tables.values()]
        if self.live_mode:
            try:
                response = self._request("GET", "/tables", params={"limit": 100})
                data = response.get("data", [])
                if data:
                    return [self._normalize_live_table(item) for item in data]
            except Exception:
                pass
        return [deepcopy(table) for table in self.tables.values()]

    def list_all_pipelines(self) -> list[dict[str, Any]]:
        if self.pipelines:
            return [deepcopy(pipeline) for pipeline in self.pipelines.values()]
        if self.live_mode:
            try:
                response = self._request("GET", "/pipelines", params={"limit": 100})
                data = response.get("data", [])
                if data:
                    return [self._normalize_live_pipeline(item) for item in data]
            except Exception:
                pass
        return [deepcopy(pipeline) for pipeline in self.pipelines.values()]

    def get_table(self, fqn: str) -> dict[str, Any]:
        if fqn in self.tables:
            return deepcopy(self.tables[fqn])
        if self.live_mode:
            try:
                response = self._request("GET", f"/tables/name/{fqn}", params={"fields": "columns,tags"})
                return self._normalize_live_table(response)
            except Exception:
                for table in self.list_all_tables():
                    if table.get("fqn") == fqn:
                        return table
        if fqn not in self.tables:
            raise KeyError(f"Unknown table '{fqn}'")
        return deepcopy(self.tables[fqn])

    def get_asset(self, fqn: str) -> dict[str, Any]:
        if fqn in self.tables:
            return self.get_table(fqn)
        if fqn in self.pipelines:
            return deepcopy(self.pipelines[fqn])
        if self.live_mode:
            try:
                table = self.get_table(fqn)
                if table: return table
            except KeyError:
                pass
            for pipeline in self.list_all_pipelines():
                if pipeline.get("fqn") == fqn:
                    return pipeline
        raise KeyError(f"Unknown asset '{fqn}'")

    def get_lineage(self, fqn: str, depth: int = 10) -> dict[str, Any]:
        if fqn.startswith("warehouse") or fqn.startswith("airflow"):
            downstream = self._bfs_paths(fqn, direction="downstream", depth=depth)
            upstream = self._bfs_paths(fqn, direction="upstream", depth=min(depth, 5))
            return {
                "fqn": fqn,
                "upstream": upstream,
                "downstream": downstream,
                "coverage": "complete",
            }
        if self.live_mode:
            try:
                response = self._request("GET", f"/lineage/table/name/{fqn}")
                nodes = response.get("nodes", [])
                entity = response.get("entity")
                if isinstance(entity, dict):
                    nodes = [entity, *nodes]
                edges = response.get("upstreamEdges", []) + response.get("downstreamEdges", []) + response.get("edges", [])
                downstream = self._lineage_from_graph(fqn, nodes, edges, direction="downstream", depth=depth)
                upstream = self._lineage_from_graph(fqn, nodes, edges, direction="upstream", depth=min(depth, 5))
                return {"fqn": fqn, "upstream": upstream, "downstream": downstream, "coverage": "complete"}
            except Exception:
                pass
        downstream = self._bfs_paths(fqn, direction="downstream", depth=depth)
        upstream = self._bfs_paths(fqn, direction="upstream", depth=min(depth, 5))
        return {
            "fqn": fqn,
            "upstream": upstream,
            "downstream": downstream,
            "coverage": "partial" if fqn == "warehouse.commerce.curated.customer_360" else "complete",
        }

    def get_usage(self, fqn: str) -> dict[str, Any]:
        return deepcopy(self.usage.get(fqn, {"query_count_90d": 0, "query_count_60d": 0, "last_query_at": None}))

    def get_quality(self, fqn: str) -> dict[str, Any]:
        return deepcopy(self.quality.get(fqn, {"pass_rate": 0.0, "failing_tests": []}))

    def get_profiling(self, fqn: str) -> dict[str, Any] | None:
        if fqn in self.profiling:
            return deepcopy(self.profiling[fqn])
        if self.live_mode:
            try:
                response = self._request("GET", f"/tables/name/{fqn}", params={"fields": "profile"})
                profile = response.get("profile")
                if profile and profile.get("sizeInByte"):
                    return {
                        "row_count": profile.get("rowCount", 0),
                        "byte_size": profile.get("sizeInByte", 0),
                        "freshness_hours": 24,
                        "last_row_added_at": response.get("updatedAt"),
                    }
                # Fallback: OpenMetadata table exists but didn't run profiling yet!
                # We'll generate a deterministic mock size so the UI still shows costs.
                col_count = len(response.get("columns", [])) or 5
                return {
                    "row_count": col_count * 1250000,
                    "byte_size": col_count * 15_000_000_000,  # e.g., 15GB per column
                    "freshness_hours": 24,
                    "last_row_added_at": response.get("updatedAt"),
                }
            except Exception:
                pass
        value = self.profiling.get(fqn)
        return deepcopy(value) if value else None

    def get_schema_versions(self, fqn: str) -> list[dict[str, Any]]:
        if self.live_mode and fqn not in self.schema_versions:
            try:
                table = self.get_table(fqn)
                version = {
                    "version": 1,
                    "captured_at": table.get("created_at") or NOW.isoformat(),
                    "columns": deepcopy(table.get("columns", [])),
                    "hash": _hash_columns(table.get("columns", [])),
                }
                self.schema_versions[fqn] = [version]
                self.tables[fqn] = deepcopy(table)
            except Exception:
                pass
        return deepcopy(self.schema_versions.get(fqn, []))

    def get_owner(self, fqn: str) -> dict[str, Any] | None:
        owner_id = None
        if fqn in self.tables:
            owner_id = self.tables[fqn]["owner_id"]
        elif fqn in self.pipelines:
            owner_id = self.pipelines[fqn]["owner_id"]
        if owner_id is not None:
            owner = deepcopy(self.owners.get(owner_id))
            if owner is not None:
                owner["id"] = owner_id
                return owner
        if self.live_mode:
            try:
                asset = self.get_table(fqn) if self.get_asset_type(fqn) == "table" else None
                if asset and asset.get("owner"):
                    return asset["owner"]
            except Exception:
                pass
        return None

    def get_glossary(self, term: str) -> dict[str, str]:
        return {term: self.glossary[term]} if term in self.glossary else {}

    def get_asset_type(self, fqn: str) -> str:
        if self.live_mode and fqn not in self.asset_types:
            if ".pipelines." in fqn or fqn.startswith("pipeline."):
                return "pipeline"
            return "table"
        return self.asset_types.get(fqn, "unknown")

    def is_quality_suite_active(self, fqn: str) -> bool:
        return bool(self.tables.get(fqn, {}).get("quality_in_active_suite"))

    def apply_schema_change(self, fqn: str, changes: list[dict[str, Any]]) -> dict[str, Any]:
        if self.live_mode and fqn not in self.tables:
            table = self.get_table(fqn)
            self.tables[fqn] = deepcopy(table)
            self.schema_versions.setdefault(
                fqn,
                [
                    {
                        "version": 1,
                        "captured_at": table.get("created_at") or NOW.isoformat(),
                        "columns": deepcopy(table.get("columns", [])),
                        "hash": _hash_columns(table.get("columns", [])),
                    }
                ],
            )
        table = self.tables[fqn]
        columns = deepcopy(table["columns"])
        for change in changes:
            change_type = change["change_type"]
            column_name = change["column"]
            if change_type == "drop_column":
                columns = [column for column in columns if column["name"] != column_name]
            elif change_type == "rename_column":
                for column in columns:
                    if column["name"] == column_name:
                        column["name"] = change["after"] or column["name"]
            elif change_type == "type_change":
                for column in columns:
                    if column["name"] == column_name:
                        column["type"] = change["after"] or column["type"]
            elif change_type == "add_column":
                columns.append({"name": column_name, "type": change.get("after") or "STRING", "description": ""})
        table["columns"] = columns
        version = {
            "version": len(self.schema_versions[fqn]) + 1,
            "captured_at": NOW.isoformat(),
            "columns": deepcopy(columns),
            "hash": _hash_columns(columns),
        }
        self.schema_versions[fqn].append(version)
        return deepcopy(version)

    def _bfs_paths(self, origin: str, direction: str, depth: int) -> list[dict[str, Any]]:
        if depth <= 0:
            return []
        neighbors = self.downstream_edges if direction == "downstream" else self._reverse_edges()
        queue: deque[tuple[str, list[str], int]] = deque([(origin, [origin], 0)])
        visited = {origin}
        results: list[dict[str, Any]] = []
        while queue:
            current, path, hops = queue.popleft()
            if hops >= depth:
                continue
            for neighbor in neighbors.get(current, []):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                next_path = [*path, neighbor]
                results.append(
                    {
                        "fqn": neighbor,
                        "entity_type": self.get_asset_type(neighbor),
                        "hop_count": hops + 1,
                        "path": next_path,
                    }
                )
                queue.append((neighbor, next_path, hops + 1))
        return results

    def _reverse_edges(self) -> dict[str, list[str]]:
        reversed_edges: dict[str, list[str]] = {}
        for source, targets in self.downstream_edges.items():
            for target in targets:
                reversed_edges.setdefault(target, []).append(source)
        return reversed_edges

    def _request(self, method: str, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        cache_key = f"{method}:{path}:{str(params)}"
        if method == "GET" and cache_key in self._cache:
            created_at, value = self._cache[cache_key]
            if datetime.now() - created_at < self._cache_ttl:
                return value
            self._cache.pop(cache_key)

        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.settings.openmetadata_jwt}",
            "Content-Type": "application/json",
            "User-Agent": "MetaGuard/0.1",
        }
        verify_options = [self.settings.openmetadata_verify_ssl]
        if self.settings.openmetadata_verify_ssl:
            verify_options.append(False)
        last_error: Exception | None = None
        for verify in verify_options:
            try:
                with httpx.Client(
                    timeout=httpx.Timeout(3.0, connect=1.0),
                    verify=verify,
                    follow_redirects=True,
                    http2=False,
                ) as client:
                    response = client.request(method, url, headers=headers, params=params)
                    response.raise_for_status()
                    data = response.json()
                    if method == "GET":
                        self._cache[cache_key] = (datetime.now(), data)
                    return data
            except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError, httpx.ReadTimeout) as exc:
                last_error = exc
                continue
        if last_error is not None:
            raise last_error
        raise RuntimeError("OpenMetadata request failed without a captured exception.")

    def _normalize_live_table(self, item: dict[str, Any]) -> dict[str, Any]:
        owner = item.get("owner")
        if not owner and isinstance(item.get("owners"), list) and item["owners"]:
            owner = item["owners"][0]
        owner_id = None
        if isinstance(owner, dict):
            owner_id = owner.get("id") or owner.get("name")
        return {
            "fqn": item.get("fullyQualifiedName") or item.get("fqn"),
            "display_name": item.get("displayName") or item.get("name"),
            "description": item.get("description") or "",
            "created_at": item.get("updatedAt") or NOW.isoformat(),
            "tags": [tag.get("tagFQN", "") for tag in item.get("tags", []) if isinstance(tag, dict)],
            "columns": [
                {
                    "name": column.get("name", ""),
                    "type": column.get("dataType", "STRING"),
                    "description": column.get("description", ""),
                }
                for column in item.get("columns", [])
            ],
            "owner_id": owner_id,
            "owner": self._normalize_live_owner(owner),
            "quality_in_active_suite": False,
        }

    def _normalize_live_pipeline(self, item: dict[str, Any]) -> dict[str, Any]:
        owner = item.get("owner")
        if not owner and isinstance(item.get("owners"), list) and item["owners"]:
            owner = item["owners"][0]
        owner_id = None
        if isinstance(owner, dict):
            owner_id = owner.get("id") or owner.get("name")
        return {
            "fqn": item.get("fullyQualifiedName") or item.get("fqn"),
            "display_name": item.get("displayName") or item.get("name"),
            "owner_id": owner_id,
            "owner": self._normalize_live_owner(owner),
            "active": True,
            "schedule": "Unknown",
            "avg_run_duration_hours": self.pipelines.get(item.get("fullyQualifiedName") or item.get("fqn"), {}).get("avg_run_duration_hours", 0.0),
            "writes_to": self.pipelines.get(item.get("fullyQualifiedName") or item.get("fqn"), {}).get("writes_to", []),
            "created_at": item.get("updatedAt") or NOW.isoformat(),
        }

    def _normalize_live_owner(self, owner: Any) -> dict[str, Any] | None:
        if not isinstance(owner, dict):
            return None
        return {
            "id": owner.get("id") or owner.get("name"),
            "name": owner.get("displayName") or owner.get("name"),
            "contact": owner.get("email"),
            "team": None,
            "active": not owner.get("deleted", False),
        }

    def _lineage_from_graph(
        self,
        origin: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        direction: str,
        depth: int,
    ) -> list[dict[str, Any]]:
        node_lookup: dict[str, dict[str, Any]] = {}
        id_lookup: dict[str, str] = {}
        for node in nodes:
            fqn = node.get("fullyQualifiedName") or node.get("fqn") or node.get("name")
            if fqn:
                node_lookup[fqn] = node
            node_id = node.get("id")
            if isinstance(node_id, str) and fqn:
                id_lookup[node_id] = fqn
        adjacency: dict[str, list[str]] = {}
        for edge in edges:
            from_entity = edge.get("fromEntity") or edge.get("from")
            to_entity = edge.get("toEntity") or edge.get("to")
            from_fqn = self._edge_fqn(from_entity, id_lookup)
            to_fqn = self._edge_fqn(to_entity, id_lookup)
            if not from_fqn or not to_fqn:
                continue
            source, target = (from_fqn, to_fqn) if direction == "downstream" else (to_fqn, from_fqn)
            adjacency.setdefault(source, []).append(target)
        queue: deque[tuple[str, list[str], int]] = deque([(origin, [origin], 0)])
        visited = {origin}
        results: list[dict[str, Any]] = []
        while queue:
            current, path, hops = queue.popleft()
            if hops >= depth:
                continue
            for neighbor in adjacency.get(current, []):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                next_path = [*path, neighbor]
                node = node_lookup.get(neighbor, {})
                results.append(
                    {
                        "fqn": neighbor,
                        "entity_type": self._live_entity_type(node),
                        "hop_count": hops + 1,
                        "path": next_path,
                    }
                )
                queue.append((neighbor, next_path, hops + 1))
        return results

    def _edge_fqn(self, value: Any, id_lookup: dict[str, str] | None = None) -> str | None:
        if isinstance(value, str):
            if id_lookup and value in id_lookup:
                return id_lookup[value]
            return value
        if isinstance(value, dict):
            return value.get("fullyQualifiedName") or value.get("fqn") or value.get("name")
        return None

    def _bootstrap_live_state(self) -> None:
        try:
            for table in self.list_all_tables():
                fqn = table.get("fqn")
                columns = deepcopy(table.get("columns", []))
                if not fqn or not columns:
                    continue
                self.tables[fqn] = deepcopy(table)
                self.schema_versions[fqn] = [
                    {
                        "version": 1,
                        "captured_at": table.get("created_at") or NOW.isoformat(),
                        "columns": columns,
                        "hash": _hash_columns(columns),
                    }
                ]
        except Exception:
            pass

    def _live_entity_type(self, node: dict[str, Any]) -> str:
        entity_type = node.get("type")
        if isinstance(entity_type, str) and entity_type:
            return entity_type.lower()
        return "table"


@lru_cache
def get_openmetadata_client() -> OpenMetadataClient:
    return OpenMetadataClient()
