from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


load_env_file(ENV_PATH)

BASE_URL = f"{os.environ.get('OPENMETADATA_URL', 'http://localhost:8585').rstrip('/')}/api/v1"
TOKEN = os.environ.get("OPENMETADATA_JWT", "")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}


def put(client: httpx.Client, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.put(f"{BASE_URL}{path}", headers=HEADERS, json=payload, timeout=30.0)
    if response.is_error:
        raise RuntimeError(f"{response.status_code} {path}: {response.text}")
    if not response.content.strip():
        return {}
    return response.json()


def get(client: httpx.Client, path: str) -> dict[str, Any]:
    response = client.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=30.0)
    response.raise_for_status()
    return response.json()


def user_ref(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "type": "user",
        "name": user["name"],
        "fullyQualifiedName": user.get("fullyQualifiedName", user["name"]),
    }


def tag(tag_fqn: str) -> dict[str, str]:
    return {
        "tagFQN": tag_fqn,
        "labelType": "Manual",
        "state": "Confirmed",
        "source": "Tag",
    }


def main() -> None:
    with httpx.Client(follow_redirects=True) as client:
        admin = get(client, "/users/name/admin")

        users = {
            "anika": put(
                client,
                "/users",
                {
                    "name": "anika_finance",
                    "displayName": "Anika Finance",
                    "email": "anika.finance@metaguard.demo",
                },
            ),
            "ravi": put(
                client,
                "/users",
                {
                    "name": "ravi_platform",
                    "displayName": "Ravi Platform",
                    "email": "ravi.platform@metaguard.demo",
                },
            ),
            "maya": put(
                client,
                "/users",
                {
                    "name": "maya_analytics",
                    "displayName": "Maya Analytics",
                    "email": "maya.analytics@metaguard.demo",
                },
            ),
        }

        db_service = put(
            client,
            "/services/databaseServices",
            {
                "name": "metaguard_demo_warehouse",
                "displayName": "MetaGuard Demo Warehouse",
                "serviceType": "Mysql",
                "description": "Demo warehouse designed to showcase dead data, trust scoring, schema risk, and blast radius.",
                "owners": [user_ref(admin)],
            },
        )

        database = put(
            client,
            "/databases",
            {
                "name": "commerce",
                "displayName": "Commerce Lakehouse",
                "description": "Commerce analytics workspace for MetaGuard demos.",
                "service": db_service["fullyQualifiedName"],
                "owners": [user_ref(users["ravi"])],
            },
        )

        schemas = {
            "raw": put(
                client,
                "/databaseSchemas",
                {
                    "name": "raw",
                    "displayName": "Raw Landing",
                    "database": database["fullyQualifiedName"],
                    "description": "Landing layer with source-aligned tables.",
                },
            ),
            "curated": put(
                client,
                "/databaseSchemas",
                {
                    "name": "curated",
                    "displayName": "Curated Analytics",
                    "database": database["fullyQualifiedName"],
                    "description": "Business-ready reporting and marts.",
                },
            ),
            "finance": put(
                client,
                "/databaseSchemas",
                {
                    "name": "finance",
                    "displayName": "Finance Models",
                    "database": database["fullyQualifiedName"],
                    "description": "Finance-owned reporting models.",
                },
            ),
        }

        tables_payload = [
            {
                "name": "raw_orders",
                "schema_key": "raw",
                "displayName": "Raw Orders",
                "description": "Unmodeled Shopify order feed captured hourly.",
                "owners": [user_ref(users["ravi"])],
                "tags": [tag("Tier.Tier1")],
                "columns": [
                    {"name": "order_id", "dataType": "VARCHAR", "constraint": "PRIMARY_KEY", "description": "Primary order id", "dataLength": 64},
                    {"name": "customer_id", "dataType": "VARCHAR", "description": "Customer identifier", "dataLength": 64},
                    {"name": "order_total", "dataType": "DECIMAL", "description": "Gross order amount"},
                    {"name": "created_at", "dataType": "TIMESTAMP", "description": "Event creation timestamp"},
                ],
            },
            {
                "name": "raw_customers",
                "schema_key": "raw",
                "displayName": "Raw Customers",
                "description": "CRM feed with customer master records.",
                "owners": [user_ref(users["maya"])],
                "tags": [tag("PII.NonSensitive")],
                "columns": [
                    {"name": "customer_id", "dataType": "VARCHAR", "constraint": "PRIMARY_KEY", "description": "Customer identifier", "dataLength": 64},
                    {"name": "email", "dataType": "VARCHAR", "description": "Email address", "dataLength": 256},
                    {"name": "country", "dataType": "VARCHAR", "description": "Country code", "dataLength": 32},
                    {"name": "segment", "dataType": "VARCHAR", "description": "Marketing segment", "dataLength": 64},
                ],
            },
            {
                "name": "fct_orders",
                "schema_key": "curated",
                "displayName": "Fact Orders",
                "description": "Core analytics fact table for order performance and revenue reporting.",
                "owners": [user_ref(users["maya"])],
                "tags": [tag("Certification.Gold"), tag("Tier.Tier1")],
                "columns": [
                    {"name": "order_id", "dataType": "VARCHAR", "constraint": "PRIMARY_KEY", "description": "Primary order id", "dataLength": 64},
                    {"name": "customer_id", "dataType": "VARCHAR", "description": "Customer identifier", "dataLength": 64},
                    {"name": "order_total", "dataType": "DECIMAL", "description": "Net order revenue"},
                    {"name": "order_date", "dataType": "DATE", "description": "Business order date"},
                ],
            },
            {
                "name": "dim_customers",
                "schema_key": "curated",
                "displayName": "Dim Customers",
                "description": "Customer dimension used by marketing and finance models.",
                "owners": [user_ref(users["maya"])],
                "tags": [tag("PII.NonSensitive"), tag("Certification.Silver")],
                "columns": [
                    {"name": "customer_id", "dataType": "VARCHAR", "constraint": "PRIMARY_KEY", "description": "Customer identifier", "dataLength": 64},
                    {"name": "country", "dataType": "VARCHAR", "description": "Country code", "dataLength": 32},
                    {"name": "segment", "dataType": "VARCHAR", "description": "Customer segment", "dataLength": 64},
                    {"name": "lifetime_value", "dataType": "DECIMAL", "description": "Estimated customer LTV"},
                ],
            },
            {
                "name": "finance_revenue_mart",
                "schema_key": "finance",
                "displayName": "Finance Revenue Mart",
                "description": "Executive revenue model used in weekly business reviews.",
                "owners": [user_ref(users["anika"])],
                "tags": [tag("Certification.Gold"), tag("Tier.Tier1")],
                "columns": [
                    {"name": "order_date", "dataType": "DATE", "description": "Order date"},
                    {"name": "revenue", "dataType": "DECIMAL", "description": "Recognized revenue"},
                    {"name": "orders_count", "dataType": "INT", "description": "Order count"},
                    {"name": "repeat_customer_rate", "dataType": "DECIMAL", "description": "Repeat customer ratio"},
                ],
            },
            {
                "name": "customer_360",
                "schema_key": "curated",
                "displayName": "Customer 360",
                "description": "Cross-domain customer profile powering personalization and retention workflows.",
                "owners": [user_ref(users["maya"])],
                "tags": [tag("Certification.Gold")],
                "columns": [
                    {"name": "customer_id", "dataType": "VARCHAR", "constraint": "PRIMARY_KEY", "description": "Customer identifier", "dataLength": 64},
                    {"name": "country", "dataType": "VARCHAR", "description": "Country code", "dataLength": 32},
                    {"name": "segment", "dataType": "VARCHAR", "description": "Customer segment", "dataLength": 64},
                    {"name": "last_order_date", "dataType": "DATE", "description": "Last order date"},
                ],
            },
            {
                "name": "orders_archive",
                "schema_key": "raw",
                "displayName": "Orders Archive",
                "description": "Legacy archive retained after the reporting migration. Good dead-data candidate.",
                "owners": [],
                "columns": [
                    {"name": "order_id", "dataType": "VARCHAR", "constraint": "PRIMARY_KEY", "description": "Primary order id", "dataLength": 64},
                    {"name": "customer_id", "dataType": "VARCHAR", "description": "Customer identifier", "dataLength": 64},
                    {"name": "order_total", "dataType": "DECIMAL", "description": "Gross order amount"},
                    {"name": "status", "dataType": "VARCHAR", "description": "Legacy order status", "dataLength": 32},
                ],
            },
            {
                "name": "dim_customers_backup",
                "schema_key": "curated",
                "displayName": "Dim Customers Backup",
                "description": "Backup snapshot that intentionally duplicates the customer dimension for duplicate detection demos.",
                "owners": [user_ref(users["maya"])],
                "columns": [
                    {"name": "customer_id", "dataType": "VARCHAR", "constraint": "PRIMARY_KEY", "description": "Customer identifier", "dataLength": 64},
                    {"name": "country", "dataType": "VARCHAR", "description": "Country code", "dataLength": 32},
                    {"name": "segment", "dataType": "VARCHAR", "description": "Customer segment", "dataLength": 64},
                    {"name": "lifetime_value", "dataType": "DECIMAL", "description": "Estimated customer LTV"},
                ],
            },
            {
                "name": "legacy_campaign_performance",
                "schema_key": "raw",
                "displayName": "Legacy Campaign Performance",
                "description": "V1 marketing campaign table left abandoned after migration to Snowflake.",
                "owners": [],
                "columns": [
                    {"name": "campaign_id", "dataType": "VARCHAR", "constraint": "PRIMARY_KEY", "description": "Campaign UID", "dataLength": 64},
                    {"name": "clicks", "dataType": "INT", "description": "Ad clicks"},
                    {"name": "impressions", "dataType": "INT", "description": "Ad impressions"},
                    {"name": "cost", "dataType": "DECIMAL", "description": "Spend"},
                    {"name": "status", "dataType": "VARCHAR", "description": "Status code", "dataLength": 16},
                ],
            },
            {
                "name": "q3_2024_sales_archive",
                "schema_key": "finance",
                "displayName": "Q3 2024 Sales Archive",
                "description": "One-off static export used for a single Q3 audit and never queried again.",
                "owners": [],
                "columns": [
                    {"name": "tx_id", "dataType": "VARCHAR", "constraint": "PRIMARY_KEY", "description": "Transaction UID", "dataLength": 64},
                    {"name": "amount", "dataType": "DECIMAL", "description": "Tx amount"},
                    {"name": "region", "dataType": "VARCHAR", "description": "Region", "dataLength": 64},
                ],
            },
            {
                "name": "experiment_results_abandoned",
                "schema_key": "curated",
                "displayName": "Experiment Results (Abandoned)",
                "description": "A/B test results from an abandoned Q2 initiative. Heavy storage footprint.",
                "owners": [],
                "columns": [
                    {"name": "test_id", "dataType": "VARCHAR", "constraint": "PRIMARY_KEY", "description": "Test UID", "dataLength": 64},
                    {"name": "control_group", "dataType": "VARCHAR", "description": "Control tag", "dataLength": 32},
                    {"name": "variant_group", "dataType": "VARCHAR", "description": "Variant tag", "dataLength": 32},
                    {"name": "lift_metric", "dataType": "DECIMAL", "description": "Calculated lift"},
                    {"name": "p_value", "dataType": "DOUBLE", "description": "P factor"},
                    {"name": "run_date", "dataType": "DATE", "description": "Date of run"},
                    {"name": "metadata_blob", "dataType": "VARCHAR", "description": "Heavy JSON blob", "dataLength": 65000},
                ],
            },
        ]

        created_tables: dict[str, dict[str, Any]] = {}
        for table in tables_payload:
            schema = schemas[table["schema_key"]]
            payload = {
                "name": table["name"],
                "displayName": table["displayName"],
                "description": table["description"],
                "databaseSchema": schema["fullyQualifiedName"],
                "tableType": "Regular",
                "columns": table["columns"],
            }
            if table["owners"]:
                payload["owners"] = table["owners"]
            created = put(client, "/tables", payload)
            created_tables[table["name"]] = created

        pipeline_service = put(
            client,
            "/services/pipelineServices",
            {
                "name": "metaguard_airflow",
                "displayName": "MetaGuard Airflow",
                "serviceType": "Airflow",
                "description": "Demo orchestration layer used for lineage and schema-risk storytelling.",
                "owners": [user_ref(users["ravi"])],
            },
        )

        pipelines = {
            "orders_modeling": put(
                client,
                "/pipelines",
                {
                    "name": "orders_modeling",
                    "displayName": "Orders Modeling",
                    "service": pipeline_service["fullyQualifiedName"],
                    "description": "Transforms raw order events into analytics-ready order facts.",
                    "sourceUrl": "http://localhost:8080/dags/orders_modeling/grid",
                    "tasks": [
                        {"name": "extract_orders", "taskType": "BatchTask", "description": "Extract raw orders", "downstreamTasks": ["build_fct_orders"]},
                        {"name": "build_fct_orders", "taskType": "BatchTask", "description": "Build fact orders", "downstreamTasks": []},
                    ],
                },
            ),
            "customer_360_refresh": put(
                client,
                "/pipelines",
                {
                    "name": "customer_360_refresh",
                    "displayName": "Customer 360 Refresh",
                    "service": pipeline_service["fullyQualifiedName"],
                    "description": "Combines CRM and commerce activity into the customer 360 model.",
                    "sourceUrl": "http://localhost:8080/dags/customer_360_refresh/grid",
                    "tasks": [
                        {"name": "build_dim_customers", "taskType": "BatchTask", "description": "Build customer dimension", "downstreamTasks": ["build_customer_360"]},
                        {"name": "build_customer_360", "taskType": "BatchTask", "description": "Build customer 360", "downstreamTasks": []},
                    ],
                },
            ),
        }

        lineage_edges = [
            ("raw_orders", "fct_orders", "Orders are standardized and filtered into the analytics fact table.", "orders_modeling"),
            ("raw_customers", "dim_customers", "CRM records are normalized into the customer dimension.", "customer_360_refresh"),
            ("fct_orders", "finance_revenue_mart", "Finance mart aggregates order facts into executive KPIs.", "orders_modeling"),
            ("dim_customers", "customer_360", "Customer dimension feeds the unified customer profile.", "customer_360_refresh"),
            ("fct_orders", "customer_360", "Last order signals are merged into the customer 360 profile.", "customer_360_refresh"),
            ("q3_2024_sales_archive", "finance_revenue_mart", "Static audit export linked to current revenue modeling.", "orders_modeling"),
            ("legacy_campaign_performance", "fct_orders", "Legacy marketing performance ingested for historical trend analysis.", "customer_360_refresh"),
        ]

        for from_name, to_name, description, pipeline_name in lineage_edges:
            from_table = created_tables[from_name]
            to_table = created_tables[to_name]
            pipeline = pipelines[pipeline_name]
            put(
                client,
                "/lineage",
                {
                    "edge": {
                        "fromEntity": {
                            "id": from_table["id"],
                            "type": "table",
                            "name": from_table["name"],
                            "fullyQualifiedName": from_table["fullyQualifiedName"],
                        },
                        "toEntity": {
                            "id": to_table["id"],
                            "type": "table",
                            "name": to_table["name"],
                            "fullyQualifiedName": to_table["fullyQualifiedName"],
                        },
                        "description": description,
                        "lineageDetails": {
                            "source": "Manual",
                            "description": description,
                            "pipeline": {
                                "id": pipeline["id"],
                                "type": "pipeline",
                                "name": pipeline["name"],
                                "fullyQualifiedName": pipeline["fullyQualifiedName"],
                            },
                        },
                    }
                },
            )

        print(
            json.dumps(
                {
                    "databaseService": db_service["fullyQualifiedName"],
                    "database": database["fullyQualifiedName"],
                    "schemas": [schema["fullyQualifiedName"] for schema in schemas.values()],
                    "tables": [table["fullyQualifiedName"] for table in created_tables.values()],
                    "pipelines": [pipeline["fullyQualifiedName"] for pipeline in pipelines.values()],
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
