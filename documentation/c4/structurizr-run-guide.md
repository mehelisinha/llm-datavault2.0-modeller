# Structurizr Run Guide for DWA C4 Diagrams

This guide explains how to render the DWA C4 diagrams using Structurizr DSL.

## Files
- `documentation/c4/workspace.dsl` — Structurizr DSL definition for the DWA architecture.
- `documentation/c4/structurizr-run-guide.md` — this guide.

## Prerequisites
- Java 11+ installed
- Internet connection to download Structurizr CLI JAR
- Terminal access in the repository root

## Docker Alternative
If you want to run Structurizr CLI inside Docker, mount the documentation folder and execute the JAR from the container.

Example:
```bash
# Mount container

docker run -it --rm \
  -p 8080:8080 \
  -v $(pwd)/documentation/c4:/usr/local/structurizr \
  structurizr/lite
```
In your browser:
Open http://localhost:8080

```bash
cd /Users/contributor/Documents/Projects/DWA/dwa
mkdir -p documetation/docs/c4-diagrams

docker run --rm \
  -v "$PWD/documetation:/workspace/documetation" \
  -w /workspace/documetation \
  openjdk:17-jdk \
  bash -lc "curl -L -o structurizr-cli.jar https://github.com/structurizr/cli/releases/download/v1.57.0/structurizr-cli-1.57.0.jar && java -jar structurizr-cli.jar export -workspace dwa-architecture.c4.dsl -format png -output ../docs/c4-diagrams"
```

> Update the image, release version, and output path if needed.

## 1. Download Structurizr CLI

Download the latest Structurizr CLI JAR from the Structurizr website or GitHub releases.

Example:
```bash
cd /Users/contributor/Documents/Projects/DWA/dwa/documetation
curl -L -o structurizr-cli.jar https://github.com/structurizr/cli/releases/download/v1.57.0/structurizr-cli-1.57.0.jar
```

> Replace `v1.57.0` with the latest available release if needed.

## 2. Generate Diagrams

Run the CLI against the DSL file to export diagrams in PNG or SVG.

Example command:
```bash
java -jar structurizr-cli.jar export \
  -workspace dwa-architecture.c4.dsl \
  -format png \
  -output ../docs/c4-diagrams
```

This command will:
- Read `dwa-architecture.c4.dsl`
- Render available views
- Write PNG files to `../docs/c4-diagrams`

If the output folder does not exist, create it first:
```bash
mkdir -p ../docs/c4-diagrams
```

## 3. Render Specific Views

To render a specific view by name, use the `-view` option.

Example:
```bash
java -jar structurizr-cli.jar export \
  -workspace dwa-architecture.c4.dsl \
  -view "System Context" \
  -format png \
  -output ../docs/c4-diagrams
```

Available view names in the DSL:
- `System Context`
- `Container`
- `Project Builder Components` (component view)
- `Run Pipeline` (dynamic view)
- `Deployment View`

## 4. Alternative: Use Structurizr Lite

If you prefer a browser-based preview, use Structurizr Lite.

1. Copy `dwa-architecture.c4.dsl` into the Structurizr Lite workspace.
2. Open the local Structurizr Lite instance.
3. Load the DSL file.
4. Use the interface to view and export diagrams.

## 5. Recommended Folder Structure

Keep generated diagrams separate from source DSL files:

```
documetation/
  dwa-architecture.c4.dsl
  structurizr-run-guide.md
  ../docs/c4-diagrams/
```

## 6. Notes
- The DSL file contains a system context, container, component, dynamic, and deployment view.
- The guide is intentionally simple and works with Structurizr CLI and Structurizr Lite.
- If the CLI version changes, update the download URL accordingly.

## 7. Example Commands Summary

```bash
cd /Users/contributor/Documents/Projects/DWA/dwa/documetation
mkdir -p ../docs/c4-diagrams
curl -L -o structurizr-cli.jar https://github.com/structurizr/cli/releases/download/v1.57.0/structurizr-cli-1.57.0.jar
java -jar structurizr-cli.jar export -workspace dwa-architecture.c4.dsl -format png -output ../docs/c4-diagrams
java -jar structurizr-cli.jar export -workspace dwa-architecture.c4.dsl -view "System Context" -format png -output ../docs/c4-diagrams
```

## 8. Troubleshooting
- If `java` is not found, install Java 11 or newer.
- If the CLI fails, check the DSL file syntax and the view name.
- If the diagrams do not appear, confirm the output directory exists and contains files.
