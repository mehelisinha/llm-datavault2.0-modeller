# Documentation Export

This directory contains scripts to export the markdown documentation to HTML format for easy viewing and sharing.

## Files

- `export_docs.py` - Python script that converts all markdown files to HTML
- `export_docs.sh` - Shell script wrapper for easy execution

## Dependencies

The following packages are required for documentation export:

- `Markdown==3.7` - Markdown to HTML conversion
- `Jinja2==3.1.4` - HTML templating (already in requirements)
- `Pygments==2.18.0` - Syntax highlighting (already in requirements)

## Usage

### Method 1: Using the Shell Script (Recommended)

```bash
# Export to default directory (docs_html)
./export_docs.sh

# Export to custom directory
./export_docs.sh my_docs
```

### Method 2: Using Python Directly

```bash
# Activate virtual environment
source .venv/bin/activate

# Export to default directory
python export_docs.py

# Export to custom directory
python export_docs.py my_custom_docs

# Specify custom source directory
python export_docs.py --docs-dir custom_docs output_dir
```

## Features

- **Complete Conversion**: Converts all `.md` files in the `documentation/` directory
- **Directory Structure**: Maintains the original folder structure in HTML output
- **Link Conversion**: Automatically converts relative markdown links (`.md`) to HTML links (`.html`)
- **Navigation**: Adds breadcrumb navigation and related page links
- **Styling**: Includes modern, responsive CSS styling
- **Index Page**: Creates a comprehensive index page with table of contents
- **Syntax Highlighting**: Code blocks with syntax highlighting using Pygments
- **Table Support**: Markdown tables are converted to HTML tables
- **TOC Support**: Table of contents generation for documents with headers

## Output Structure

```
output_directory/
├── index.html              # Main index page with TOC
├── framework.html          # Converted markdown files
├── transformer/
│   ├── transformer_factory_overview.html
│   └── transformer_service.html
├── pipeline/
│   ├── plan/
│   │   ├── plan.html
│   │   └── plan_execute/
│   │       ├── plan_executor_overview.html
│   │       └── ...
│   └── ...
└── ...
```

## HTML Features

- **Responsive Design**: Works on desktop and mobile devices
- **Modern Styling**: Clean, professional appearance with VS Code-inspired colors
- **Navigation**: Breadcrumb navigation and related page links
- **Code Highlighting**: Syntax highlighting for code blocks
- **Table Styling**: Properly formatted tables with alternating row colors
- **Link Handling**: All relative links work correctly between HTML pages

## Browser Viewing

After export, open `output_directory/index.html` in any modern web browser to view the documentation.

On macOS, the shell script will offer to open the documentation in your default browser automatically.

## Troubleshooting

### Missing Dependencies

If you get import errors, install the required packages:

```bash
source .venv/bin/activate
pip install Markdown==3.7 Pygments==2.18.0
```

### Permission Issues

Make sure the scripts are executable:

```bash
chmod +x export_docs.sh
```

### Python Path Issues

If `python` command is not found, use `python3`:

```bash
python3 export_docs.py
```

## Integration

These scripts can be integrated into CI/CD pipelines or documentation workflows to automatically generate HTML documentation from markdown sources.