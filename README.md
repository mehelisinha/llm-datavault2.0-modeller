# LLM Data Vault 2.0 Modeller

This project uses large language models (LLMs) to help data engineers build Data Vault 2.0 models.
It reads the raw tables of a source system and proposes hubs, links and satellites.
It then writes the result as a metadata YAML file.
A deterministic engine turns that YAML into a runnable dbt project.
A human always reviews and approves the result before it is used.

## About this thesis

I built this system as part of my Master's thesis at **E.ON Digital Technology GmbH**.
It is a company thesis.
The system is now used in production at E.ON.

This GitHub repository is a personal copy for academic reference.
It is not the production system.
All organisational credentials, secrets, internal connections and company configuration have been removed.
Because of this, the project will not run out of the box.
To run it, you need your own Azure OpenAI, Databricks and Microsoft Entra ID resources.

## The problem

Data Vault 2.0 is a popular way to model a data warehouse.
It splits data into three kinds of tables.
Hubs hold business keys.
Links hold relationships between business keys.
Satellites hold descriptive data and its history.

Designing these tables by hand is slow.
An engineer must study every source table, find the business keys and decide how to split the columns.
A large source system can have hundreds of tables.
This project automates the first draft of that work and keeps a human in control of the final decision.

## How it works

The system runs as a pipeline with five steps.

1. **Snapshot.** It reads the table and column metadata of the bronze (raw) layer from Databricks.
2. **Analyze.** An LLM modeller studies the tables and proposes a modelling plan. It asks the model several times and takes a vote, so the result is more stable. A second LLM can review the plan and fix common mistakes.
3. **Architect Business Vault.** It proposes Business Vault objects such as point in time (PIT) tables and bridge tables.
4. **Generate.** A deterministic emitter turns the plan into the final metadata YAML. The same plan always gives the same YAML.
5. **Validate.** It checks the YAML for structural errors. It can also run `dbt parse`, `dbt compile` and `dbt build` to prove the model really works.

A supervisor checks the risk level after the important steps.
If the risk is high, the run pauses and waits for a human decision.
Every approval or rejection is stored in an audit trail.

The system has three more features.

* **Feedback learning.** Approved YAML files are stored. Later runs use them as examples, so the modeller can learn from past decisions.
* **Schema drift detection.** When a source system changes, the system finds every added, changed or removed column. An LLM then classifies each change as additive, cosmetic or breaking. A rule based safety check makes sure no breaking change is missed.
* **Web interface.** A React user interface lets engineers start runs, look at the proposed model, and approve or reject it.

## Data Vault layers

| Layer | Description |
|------|-------------|
| Bronze | Raw change data capture (CDC) landing zone. Delta tables with insert, update and delete flags. |
| Staging | AutomateDV stage macro. Adds hash keys, hash diffs and derived columns. |
| Raw Vault | Hubs, links and satellites. These tables keep full history and are never updated in place. |
| Business Vault | PIT tables, bridge tables and derived business rules. |

## Project structure

| Folder | What it contains |
|------|-------------|
| `dbt_builder/src/ai` | The AI pipeline. This includes the agents, orchestration, drift detection, feedback store, validation and evaluation code. |
| `dbt_builder/src/ai/prompts` | The modelling rules for each agent, written as editable Markdown files. |
| `dbt_builder/src/dv_components` | The deterministic engine that turns metadata YAML into dbt and AutomateDV models. |
| `dbt_builder/api` | The FastAPI backend used by the web interface. |
| `ui` | The React and Vite web interface. |
| `tests` | Unit and integration tests. |

## Requirements

* Python 3.12 or newer
* Node.js 20.18 or newer and pnpm 9 or newer
* [uv](https://docs.astral.sh/uv/) for Python packages (plain `pip` also works)
* An Azure OpenAI resource with chat and embedding deployments
* A Databricks workspace with a SQL Warehouse
* A Microsoft Entra ID app registration for login

## Getting started

1. Create a Python environment and install the project.

   ```bash
   uv venv
   uv pip install -e ".[dev]"
   ```

2. Copy `.env.template` to `.env` and fill in your own values. Never commit the `.env` file.

3. Start the API and the web interface together.

   ```bash
   pnpm dev
   ```

   The API runs on port 8000 and the interface runs on port 5173.

4. Run the tests.

   ```bash
   pytest tests
   ```

   Many unit tests use fakes, so they do not need a network connection.

## Author

Meheli Sinha

Master's thesis at E.ON Digital Technology GmbH
