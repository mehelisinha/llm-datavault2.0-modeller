## Folder Structure
```html
project_root/
│
├── config/                     # All configuration files and templates
│   ├── delta_tables/           # Scripts to create Delta metadata tables
│   │   ├── sources.sql
│   │   ├── source_tables.sql
│   │   ├── table_fields.sql
│   │   └── dv_models.sql
│   ├── templates/              # Jinja2 templates for DBT YAML or SQL models
│   │   ├── hub_template.yml
│   │   ├── link_template.yml
│   │   └── sat_template.yml
│   └── metadata_examples/      # Example CSV or JSON inserts for testing
│
├── notebooks/                  # Databricks notebooks
│   ├── orchestrator/           # High-level orchestration notebooks
│   │   ├── run_source.py       # Parent notebook per source
│   │   ├── process_table.py    # Child notebook per table
│   │   └── pre_processing.py   # Optional preprocessing transformations
│   └── utilities/              # Helper notebooks (optional)
│       ├── dbt_runner.py
│       └── dv_generator.py
│
├── dbt/                        # DBT project folder
│   ├── models/                 # DBT SQL models
│   │   ├── hubs/
│   │   ├── links/
│   │   └── satellites/
│   ├── seeds/                  # Static seed tables if any
│   ├── snapshots/              # DBT snapshots if needed
│   └── generated/              # Dynamically generated YAMLs and models
│
├── dags/                       # Optional: if integrating with Airflow
│   └── dv_jobs.py
│
├── scripts/                    # Auxiliary scripts
│   ├── deploy_dbt.py
│   └── update_config.py
│
├── tests/                      # Unit tests / Pytest
│   ├── test_transformations.py
│   ├── test_dv_generation.py
│   └── test_metadata_read.py
│
├── logs/                       # Runtime logs for pipeline executions
│
├── ci_cd/                      # CI/CD pipeline code
│   ├── azure_devops/
│   │   ├── build.yml
│   │   └── release.yml
│   └── scripts/
│       └── upload_delta_config.py
│
└── README.md
```
### Explanation of Each Folder
| Folder |  Purpose |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| **config/**    | Store Delta table creation scripts, templates for DBT YAML/SQL, and example metadata.                                                                 |
| **notebooks/** | Parent/child orchestration notebooks, preprocessing logic, and utilities.                                                                             |
| **dbt/**       | All DBT code: SQL models, dynamically generated YAMLs, seeds, snapshots. The `generated/` folder is populated at runtime by your Python orchestrator. |
| **dags/**      | Optional — if you later integrate with Airflow for orchestration.                                                                                     |
| **scripts/**   | Standalone Python scripts (e.g., for deployment or config updates).                                                                                   |
| **tests/**     | Unit tests for transformations, metadata reading, DV2 generation logic.                                                                               |
| **logs/**      | Store run-time logs for debugging and monitoring.                                                                                                     |
| **ci_cd/**     | YAML pipelines and scripts for automated deployment of DBT models, Delta config, and Python notebooks.                                                |

### Notes for Scalability
- Dynamic DBT generation:
All dynamically generated DBT models go into dbt/generated/ so you can separate static models vs runtime-generated models.
- Multiple sources:
Each source can be fully independent — you don’t need a separate folder per source unless desired.
Source-specific configurations (e.g., landing paths) live in Delta tables, not in folder structure.
- Transformation / test definitions:
Store in table_fields metadata; Python orchestration reads it and applies it.
Any helper logic goes into notebooks/utilities/ so it can be reused.
- CI/CD readiness:
ci_cd/ can include scripts for uploading Delta configs, DBT deployment, and automated tests.
Keeps deployment independent from your notebooks

## 1. Configurations
```sql
CREATE TABLE IF NOT EXISTS config.sources (
    source_id INT,
    source_name STRING,
    source_type STRING,          -- sql / parquet / csv / api
    connection STRING,           -- JDBC or path for files
    load_type STRING             -- full / incremental
) USING DELTA;
```
```html
table_fields
----------------------------
field_id
table_id
field_name
field_type
is_key BOOLEAN    -- business key
role              -- hub / link / sat
dv_model_name     -- e.g., sat_customer_info, sat_customer_address
scd_type          -- e.g 2, 1 (SCD2)
update_frequency  -- `high`, `medium`, `low`
source_system     -- optional: `CRM`, `ERP`, etc.
data_format       -- optional: `string`, `int`, ...
tests              -- e.g., "not_null,unique,email_format"
transformations    -- e.g., "trim,uppercase,hash_md5"
```

| satellite_name     | update_frequency | scd_type | unique_key  | strategy  | updated_at | hard_deletes |
| ------------------ | ---------------- | -------- | ----------- | --------- | ---------- | ------------ |
| sat_customer_info  | low              | 2        | customer_id | timestamp | updated_at | invalidate   |
| sat_customer_login | high             | 1        | login_id    | latest    | last_login | ignore       |



```
field_rules
----------------------------
field_id
test_name           -- e.g., not_null, unique, regex
transformation_name -- e.g., trim, upper, hash_md5
parameters          -- optional JSON for transformation params
```
```
dv_models
----------------------------
model_id
table_id          -- FK to source_tables
hub_name
link_name
sat_name          -- default satellite if there is only one
hash_strategy
```
## 2. Python Orchestrator

```python
from pyspark.sql import SparkSession
from automatedv import dv_generator
import dbt_runner  # custom module to generate/run dbt models dynamically

spark = SparkSession.builder.getOrCreate()

def run_pipeline_for_source(source_name):
    # --- 1. Load metadata ---
    source = spark.table("config.sources").filter(f"source_name = `{source_name}`").collect()[0]
    tables = spark.table("config.source_tables").filter(f"source_id = {source.source_id}").collect()
    
    for table in tables:
        fields = spark.table("config.table_fields").filter(f"table_id = {table.table_id}").collect()
        dv_model = spark.table("config.dv_models").filter(f"table_id = {table.table_id}").collect()[0]

        # --- 2. Build runtime metadata for AutomateDV ---
        dv_meta = {
            "table_name": table.table_name,
            "hub_name": dv_model.hub_name,
            "link_name": dv_model.link_name,
            "sat_name": dv_model.sat_name,
            "fields": [{"name": f.field_name, "type": f.field_type, "role": f.is_hub_link_satellite_key} for f in fields],
            "business_key": table.business_key,
            "load_type": source.load_type
        }

        # --- 3. Generate DV artifacts ---
        dv_generator.run(**dv_meta)

        # --- 4. Generate DBT YAML dynamically ---
        dbt_runner.generate_dbt_yaml(dv_meta)

        # --- 5. Run DBT Models ---
        dbt_runner.run_model(dv_meta["hub_name"])
        dbt_runner.run_model(dv_meta["link_name"])
        dbt_runner.run_model(dv_meta["sat_name"])

# --- 6. Example: run all sources ---
all_sources = [row.source_name for row in spark.table("config.sources").collect()]
for src in all_sources:
    run_pipeline_for_source(src)
```

## 3. Dynamic DBT YAML / Model Generation
```python
from jinja2 import Template

hub_template = """
version: 2
models:
  - name: {{ hub_name }}
    description: "Hub table for {{ table_name }}"
    columns:
      {% for field in fields if field.role == `hub` %}
      - name: {{ field.name }}
        tests:
          - not_null
          - unique
      {% endfor %}
"""

def generate_dbt_yaml(dv_meta):
    t = Template(hub_template)
    yaml_content = t.render(**dv_meta)
    
    file_path = f"/dbt_generated/{dv_meta[`hub_name`]}.yml"
    with open(file_path, "w") as f:
        f.write(yaml_content)
    return file_path
```

## 4. AutomateDV Integration
```python
from automatedv import dv_generator

dv_generator.run(
    table_name=dv_meta["table_name"],
    hub_name=dv_meta["hub_name"],
    link_name=dv_meta["link_name"],
    sat_name=dv_meta["sat_name"],
    business_key=dv_meta["business_key"],
    fields=dv_meta["fields"],
    load_type=dv_meta["load_type"]
)
```

## 5. Orchestratiom
    - 5.1 Parent Notebook (run_source.py)
    ```python
    from pyspark.sql import SparkSession
    import json

    spark = SparkSession.builder.getOrCreate()

    # Input param: source_name
    dbutils.widgets.text("source_name", "")
    source_name = dbutils.widgets.get("source_name")

    # Read tables for this source
    tables = spark.table("config.source_tables") \
                .join(spark.table("config.sources"), "source_id") \
                .filter(f"source_name = `{source_name}`") \
                .select("table_name") \
                .collect()

    # Return list of tables as job parameter for child tasks
    table_list = [row.table_name for row in tables]
    dbutils.jobs.taskValues.set(key="tables", value=json.dumps(table_list))
    ```
    - 5.2 Child Notebook (process_table.py)
    ```python
    import json
    from pyspark.sql import SparkSession
    from automatedv import dv_generator
    import dbt_runner

    spark = SparkSession.builder.getOrCreate()

    # Input parameters
    dbutils.widgets.text("table_name", "")
    table_name = dbutils.widgets.get("table_name")

    # Load metadata for this table
    table = spark.table("config.source_tables").filter(f"table_name = `{table_name}`").collect()[0]
    fields = spark.table("config.table_fields").filter(f"table_id = {table.table_id}").collect()
    dv_model = spark.table("config.dv_models").filter(f"table_id = {table.table_id}").collect()[0]

    # Build DV metadata
    dv_meta = {
        "table_name": table.table_name,
        "hub_name": dv_model.hub_name,
        "link_name": dv_model.link_name,
        "sat_name": dv_model.sat_name,
        "fields": [{"name": f.field_name, "type": f.field_type, "role": f.is_hub_link_satellite_key} for f in fields],
        "business_key": table.business_key
    }

    # Run AutomateDV
    dv_generator.run(**dv_meta)

    # Generate & run DBT
    dbt_runner.generate_dbt_yaml(dv_meta)
    dbt_runner.run_model(dv_meta["hub_name"])
    dbt_runner.run_model(dv_meta["link_name"])
    dbt_runner.run_model(dv_meta["sat_name"])
    ```

#### Databricks Jobs Setup
- Task 1 – Extract tables
    - Notebook: run_source.py
    - Input: source_name
    - Output: tables (JSON array)
- Task 2 – For Each Table
    - Task type: Notebook
    - Notebook: process_table.py
    - Input: table_name from each element in tables output
    - Can be set to run in parallel.

## Python Example: Mapping Fields to Satellites    
``` python
# fields is a list of dicts from table_fields
hubs = [f for f in fields if f[`role`] == `hub`]
links = [f for f in fields if f[`role`] == `link`]

# Group satellites by satellite_name
from collections import defaultdict

# fields is a list of dicts from table_fields
satellites = defaultdict(list)

for f in fields:
    if f['role'] == 'sat':
        # create satellite name based on frequency or source if needed
        sat_name = f.get('satellite_name')  # base name
        freq = f.get('update_frequency')
        src = f.get('source_system')
        
        # Optional: append frequency or source to satellite name
        sat_name_dynamic = f"{sat_name}_{freq}_{src}" if freq or src else sat_name
        satellites[sat_name_dynamic].append(f)

# satellites now has multiple satellites per table based on update rate/source

# Now you can generate DV2 tables:
# hubs -> hub table
# links -> link table
# satellites -> one satellite table per satellite_name
```
## DBT Tests
```python
for field in fields:
    if field.get("tests"):
        test_list = [t.strip() for t in field["tests"].split(",")]
        for t in test_list:
            dbt_runner.add_test(model_name=target_table, column=field["name"], test=t)
```
## Transformations
```python
for field in fields:
    if field.get("transformations"):
        transformations = field["transformations"].split(",")
        for tf in transformations:
            if tf == "trim":
                df = df.withColumn(field["name"], F.trim(F.col(field["name"])))
            elif tf == "uppercase":
                df = df.withColumn(field["name"], F.upper(F.col(field["name"])))
            elif tf == "hash_md5":
                df = df.withColumn(field["name"], F.md5(F.col(field["name"])))
```

### How to Incorporate Transformations
There are three approaches:
## Option A – Pre-Transform Data in Python Before AutomateDV
Apply transformations to your raw dataframe before passing it to AutomateDV.
Example: clean strings, hash sensitive fields, apply business logic.
Pros: Full control over transformations.
Cons: Adds a preprocessing step, but is fully compatible.
```python
# Pre-transform before calling AutomateDV
for field in fields:
    if field.get("transformations"):
        transformations = field["transformations"].split(",")
        for tf in transformations:
            if tf == "trim":
                df = df.withColumn(field["name"], F.trim(F.col(field["name"])))
            elif tf == "uppercase":
                df = df.withColumn(field["name"], F.upper(F.col(field["name"])))
            elif tf == "hash_md5":
                df = df.withColumn(field["name"], F.md5(F.col(field["name"])))

# Now pass df to AutomateDV

dv_generator.run(df=df, **dv_meta)
```
This works because AutomateDV can accept a DataFrame as input, not just a table path.

### Option B – Use AutomateDV’s Built-in Transformation Hooks

- Some AutomateDV versions allow custom transformation rules or mapping tables.  
  Example: AutomateDV supports hashing, trimming, date conversion rules via metadata.

- You can store these rules in your Delta config and feed them to AutomateDV.  

**Example field config:**

| field_name      | role | satellite_name | transformation |
|-----------------|------|----------------|----------------|
| customer_email  | sat  | sat_customer   | hash_md5       |
| signup_date     | sat  | sat_customer   | to_date        |

AutomateDV reads the transformation rules and applies them automatically.  
The limitation is you must use transformations AutomateDV knows, or extend it via its plugin/extension mechanisms.

---

### Option C – Post-Transform Data After AutomateDV

1. Load DV2 tables using AutomateDV as standard.  
2. Apply additional DBT transformations after load.  

**Example DBT post-processing:**

```sql
select
    hub_key,
    upper(customer_email) as customer_email,
    signup_date
from {{ ref('sat_customer') }}
```
Pros: Keeps AutomateDV pure.
Cons: Two-step transformation, but fully integrates with DBT.

### Recommended Approach
For a fully metadata-driven pipeline:
- Use Delta config to define transformations per field.
- Pre-process high-complexity transformations in Python before passing to AutomateDV (Option A).
- Simple transformations or validations can be done via DBT after AutomateDV (Option C).
- AutomateDV standard transformations (hash keys, trimming, date conversions) can be configured in metadata (Option B).
This gives you full flexibility, preserves DV2 principles, and keeps each table independent.

>Example Metadata-Driven Flow
> - Read table_fields config (includes transformations).
> - Preprocess the raw source DataFrame according to transformations.
> - Pass transformed DataFrame to AutomateDV.
> - AutomateDV generates hubs/links/satellites.
> - Optionally, run DBT transformations/tests on resulting DV2 tables.

# Classes:

## Base Class (DVModel)
- Holds common metadata: table name, fields, business keys, source info, load type, hash strategy, etc.
- Provides common methods for validation, logging, and schema building.
- Can include a method to generate DBT YAML, optionally overridden in child classes.
```python
from typing import List, Dict

class DVModel:
    def __init__(self, table_name: str, fields: List[Dict], business_key: str, hash_strategy="md5"):
        self.table_name = table_name
        self.fields = fields
        self.business_key = business_key
        self.hash_strategy = hash_strategy

    def validate_fields(self):
        # check required fields exist
        if not self.business_key:
            raise ValueError(f"Business key not defined for {self.table_name}")

    def generate_yaml(self) -> str:
        # Base YAML generator; can be overridden
        raise NotImplementedError
```

## Child Classes
### Hub
```python
class Hub(DVModel):
    def generate_yaml(self):
        columns = [{"name": f['name'], "tests": ["not_null", "unique"]} for f in self.fields]
        yaml_content = {
            "version": 2,
            "models": [
                {
                    "name": self.table_name,
                    "description": f"Hub table for {self.table_name}",
                    "columns": columns
                }
            ]
        }
        return yaml_content
```
### Link
```pythpn
class Link(DVModel):
    def generate_yaml(self):
        columns = [{"name": f['name'], "tests": []} for f in self.fields]
        yaml_content = {
            "version": 2,
            "models": [
                {
                    "name": self.table_name,
                    "description": f"Link table for {self.table_name}",
                    "columns": columns
                }
            ]
        }
        return yaml_content
```

### Satellite
```python
class Satellite(DVModel):
    def __init__(self, table_name: str, fields: List[FieldConfig], parent_hub: str, satellite_name: str, config: SatelliteConfig):
        super().__init__(table_name, fields)
        self.parent_hub = parent_hub
        self.satellite_name = satellite_name
        self.scd_type = config.scd_type
        self.unique_key = config.unique_key
        self.strategy = config.strategy
        self.updated_at = config.updated_at
        self.hard_deletes = config.hard_deletes

    def generate_yaml(self):
        columns = [{"name": f.name, "tests": f.tests} for f in self.fields]
        yaml_content = {
            "version": 2,
            "models": [
                {
                    "name": self.satellite_name,
                    "description": f"Satellite for {self.parent_hub}",
                    "columns": columns,
                    "scd2": self.scd_type == 2,
                    "unique_key": self.unique_key,
                    "strategy": self.strategy,
                    "updated_at": self.updated_at,
                    "hard_deletes": self.hard_deletes
                }
            ]
        }
        return yaml_content
```

# Using Pydantic for Config Validation
Pydantic models are perfect for validating extracted metadata from Delta tables.
For example:
from pydantic import BaseModel
from typing import List, Optional
```python
class FieldConfig(BaseModel):
    name: str
    type: str
    role: str  # hub/link/sat
    satellite_name: Optional[str]
    tests: Optional[List[str]]
    transformations: Optional[List[str]]

class TableConfig(BaseModel):
    table_name: str
    business_key: Optional[str]
    fields: List[FieldConfig]
    hash_strategy: Optional[str] = "md5"

class SatelliteConfig(BaseModel):
    satellite_name: str
    update_frequency: str
    scd_type: int = 1
    unique_key: str
    strategy: str = "timestamp"
    updated_at: str = None
    hard_deletes: str = "ignore"
```
Load metadata from Delta → validate via Pydantic → feed into DVModel classes.

# How the Full Flow Works
- Extract metadata from Delta tables.
- Validate metadata using Pydantic models.
- Instantiate DVModel objects:
- Hub → Hub(fields=hub_fields, ...)
- Link → Link(fields=link_fields, ...)
- Satellites → Satellite(fields=sat_fields, parent_hub=hub_name, ...)
- Generate DBT YAML per object: obj.generate_yaml().
- Optionally generate DBT SQL models (if you want full dynamic DBT).
- Run AutomateDV with metadata-driven DataFrame (pre-transformed if needed).
- DBT applies tests automatically from YAML.

# Pipeline

```python
from typing import List, Dict
from pydantic import BaseModel
from collections import defaultdict
import json
from automatedv import dv_generator
import dbt_runner
from pyspark.sql import DataFrame, SparkSession
import pyspark.sql.functions as F

# ------------------------
# Pydantic models for config validation
# ------------------------
class FieldConfig(BaseModel):
    name: str
    type: str
    role: str  # hub/link/sat
    satellite_name: str = None
    tests: List[str] = []
    transformations: List[str] = []

class TableConfig(BaseModel):
    table_name: str
    business_key: str = None
    fields: List[FieldConfig]
    hash_strategy: str = "md5"
    source_system: str = None
    update_frequency: str = None

# ------------------------
# DV2 objects
# ------------------------
class DVModel:
    def __init__(self, table_name: str, fields: List[FieldConfig], business_key: str = None):
        self.table_name = table_name
        self.fields = fields
        self.business_key = business_key

    def validate(self):
        if self.fields is None or len(self.fields) == 0:
            raise ValueError(f"No fields defined for {self.table_name}")

    def generate_yaml(self):
        raise NotImplementedError

class Hub(DVModel):
    def generate_yaml(self):
        columns = [{"name": f.name, "tests": f.tests or ["not_null","unique"]} for f in self.fields]
        return {
            "version": 2,
            "models": [{"name": self.table_name, "description": f"Hub table {self.table_name}", "columns": columns}]
        }

class Link(DVModel):
    def generate_yaml(self):
        columns = [{"name": f.name, "tests": f.tests} for f in self.fields]
        return {
            "version": 2,
            "models": [{"name": self.table_name, "description": f"Link table {self.table_name}", "columns": columns}]
        }

class Satellite(DVModel):
    def __init__(self, table_name: str, fields: List[FieldConfig], parent_hub: str, satellite_name: str):
        super().__init__(table_name, fields)
        self.parent_hub = parent_hub
        self.satellite_name = satellite_name

    def generate_yaml(self):
        columns = [{"name": f.name, "tests": f.tests} for f in self.fields]
        return {
            "version": 2,
            "models": [{"name": self.satellite_name, "description": f"Satellite for {self.parent_hub}", "columns": columns}]
        }

# ------------------------
# Pipeline class
# ------------------------
class Pipeline:
    def __init__(self, source_name: str, spark: SparkSession):
        self.source_name = source_name
        self.spark = spark
        self.table_configs: List[TableConfig] = []

    def load_metadata(self):
        # Load tables for this source from Delta
        tables_df = self.spark.table("config.source_tables").filter(f"source_name = '{self.source_name}'")
        fields_df = self.spark.table("config.table_fields")
        
        for tbl in tables_df.collect():
            tbl_fields = fields_df.filter(f"table_id = {tbl.table_id}").collect()
            field_configs = [FieldConfig(
                name=f.field_name,
                type=f.field_type,
                role=f.role,
                satellite_name=f.get("satellite_name"),
                tests=json.loads(f.get("tests","[]")),
                transformations=json.loads(f.get("transformations","[]"))
            ) for f in tbl_fields]
            table_config = TableConfig(
                table_name=tbl.table_name,
                business_key=tbl.business_key,
                fields=field_configs
            )
            self.table_configs.append(table_config)

    def preprocess_dataframe(self, df: DataFrame, fields: List[FieldConfig]) -> DataFrame:
        # Apply transformations
        for f in fields:
            for tf in f.transformations:
                if tf == "trim":
                    df = df.withColumn(f.name, F.trim(F.col(f.name)))
                elif tf == "uppercase":
                    df = df.withColumn(f.name, F.upper(F.col(f.name)))
                elif tf == "hash_md5":
                    df = df.withColumn(f.name, F.md5(F.col(f.name)))
        return df

    def run(self):
        from collections import defaultdict

    # inside Pipeline.run()
    for tbl_cfg in self.table_configs:
        # Preprocess raw table
        df = self.spark.table(f"raw.{tbl_cfg.table_name}")
        df = self.preprocess_dataframe(df, tbl_cfg.fields)

        # Generate DV objects
        hubs = [Hub(tbl_cfg.table_name, [f for f in tbl_cfg.fields if f.role=="hub"], tbl_cfg.business_key)]
        links = [Link(tbl_cfg.table_name+"_link", [f for f in tbl_cfg.fields if f.role=="link"])]

        # --- Dynamically create satellites based on satellite_name AND update_frequency ---
        satellites_dict = defaultdict(list)
        for f in tbl_cfg.fields:
            if f.role == "sat":
                # Construct satellite name: base_name + update_frequency
                freq_suffix = f.update_frequency or "default"
                sat_name = f"{f.satellite_name or tbl_cfg.table_name}_sat_{freq_suffix}"
                satellites_dict[sat_name].append(f)

        satellites = [
            Satellite(
                table_name=tbl_cfg.table_name,
                fields=fields,
                parent_hub=tbl_cfg.table_name,
                satellite_name=sat_name
            )
            for sat_name, fields in satellites_dict.items()
        ]

        # Run AutomateDV for each object
        for obj in hubs + links + satellites:
            dv_generator.run(df=df, table_name=obj.table_name, fields=[f.dict() for f in obj.fields])

        # Generate DBT YAMLs
        for obj in hubs + links + satellites:
            yaml_content = obj.generate_yaml()
            dbt_runner.write_yaml(yaml_content, f"dbt/generated/{obj.table_name}.yml")
```
```
                     ┌─────────────────────────────┐
                     │   Delta Metadata Tables     │
                     │-----------------------------│
                     │ source_config               │
                     │ table_filds_config          │
                     │ load_strategy_config        │
                     │ quality_rules_config        │
                     └─────────────┬───────────────┘
                                   │
                                   ▼
                     ┌─────────────────────────────┐
                     │   Metadata Preprocessing    │
                     └─────────────┬───────────────┘
                                   │
                                   │ 
                                   ▼ 
                    ┌──────────────────────────────┐                                
                    │ AutomateDV Runtime Macros.   │   
                    │  - Read Delta tables         │   
                    │  - Generate SQL dynamically. │   
                    │  - Runtime incremental logic │   
                    └─────────────┬────────────────┘   
                                  │ 
                                  ▼                    
            Generic dbt Models (single model per layer)
            ┌──────────────┬──────────────┬──────────────┐
            │ staging      │ hub/link     │ satellite    │
            │ (generic)    │ (generic)    │ (generic)    │
            └──────┬───────┴───────┬──────┴───────┬───────┘
                   │               │               │
                   ▼               ▼               ▼
               Silver Layer     Business Vault    Gold Marts

```