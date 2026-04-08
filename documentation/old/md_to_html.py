#!/usr/bin/env python3
"""
Markdown to HTML Converter with Mermaid Support

This script converts Markdown files to HTML, with special handling for Mermaid diagrams.
Mermaid code blocks are wrapped in <div class="mermaid"> tags for rendering.

Usage:
    python md_to_html.py input.md output.html

Requirements:
    pip install mistune
"""


import os
import re
import sys
from pathlib import Path
from typing import Dict, List

import mistune
from mistune import HTMLRenderer

try:
    import markdown
    from jinja2 import Template
    from markdown.extensions import codehilite, fenced_code, tables, toc
except ImportError as e:
    print(
        "Missing required packages. Install with: pip install markdown jinja2 pygments"
    )
    print(f"Error: {e}")
    sys.exit(1)

class MermaidRenderer(HTMLRenderer):
    """Custom renderer that handles Mermaid code blocks."""

    def block_code(self, code, lang=None):
        if lang and lang.lower() == 'mermaid':
            # Wrap Mermaid code in div with mermaid class
            return f'<div class="mermaid">\n{code}\n</div>\n'
        else:
            # Use default rendering for other code blocks
            return super().block_code(code, lang)

class MdToHtmlConverter:
    """Class to convert Markdown to HTML with Mermaid support."""

    def __init__(self, docs_dir: str, output_dir: str):
        self.docs_dir = Path(docs_dir)
        self.output_dir = Path(output_dir)
        self.md_files: List[Path] = []
        self.file_map: Dict[str, str] = {}  # relative_path -> html_path

        # Configure markdown extensions
        self.md_extensions = [
            "toc",  # Table of contents
            "fenced_code",  # Code blocks with ```
            "codehilite",  # Syntax highlighting
            "tables",  # Table support
            "nl2br",  # Line breaks
            "sane_lists",  # Better list handling
        ]
        self.mermaid_renderer = MermaidRenderer()
        # HTML template
        self.html_template = Template("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - EDH Documentation</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header {
            border-bottom: 2px solid #007acc;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        .nav {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        .nav a {
            color: #007acc;
            text-decoration: none;
            margin-right: 15px;
        }
        .nav a:hover {
            text-decoration: underline;
        }
        h1, h2, h3, h4, h5, h6 {
            color: #007acc;
            margin-top: 1.5em;
        }
        h1 { border-bottom: 1px solid #ddd; padding-bottom: 10px; }
        code {
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        }
        pre {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            border: 1px solid #e9ecef;
        }
        pre code {
            background: none;
            padding: 0;
        }
        blockquote {
            border-left: 4px solid #007acc;
            padding-left: 15px;
            margin-left: 0;
            color: #666;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px 12px;
            text-align: left;
        }
        th {
            background-color: #f8f9fa;
            font-weight: bold;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        .toc {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }
        .toc ul {
            margin: 0;
            padding-left: 20px;
        }
        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #666;
            font-size: 0.9em;
        }
        .breadcrumb {
            margin-bottom: 20px;
            font-size: 0.9em;
        }
        .breadcrumb a {
            color: #666;
        }
        /* Mermaid diagram styling */
        .mermaid {
            text-align: center;
            margin: 20px 0;
        }
    </style>
    <!-- Mermaid.js for diagram rendering -->
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10.6.1/dist/mermaid.min.js"></script>
    <script>
        mermaid.initialize({
            startOnLoad: true,
            theme: 'default',
            securityLevel: 'loose',
            fontFamily: 'arial',
            fontSize: 14
        });
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{{ title }}</h1>
            {% if breadcrumb %}
            <div class="breadcrumb">{{ breadcrumb|safe }}</div>
            {% endif %}
        </div>

        <div class="nav">
            <a href="index.html">🏠 Home</a>
            {% for link in nav_links %}
            <a href="{{ link.url }}">{{ link.title }}</a>
            {% endfor %}
        </div>

        <div class="content">
            {{ content|safe }}
        </div>

        <div class="footer">
            <p>Generated from markdown documentation. Last updated: {{ timestamp }}</p>
            <p><a href="https://github.com/microsoft/vscode">EDH Data Pipeline Documentation</a></p>
        </div>
    </div>
</body>
</html>
        """)

    def convert_links(self, content: str, current_file: Path) -> str:
        """Convert relative markdown links to HTML links."""
        # Convert .md links to .html
        content = re.sub(
            r"\[([^\]]+)\]\(([^)]+\.md)\)",
            lambda m: f"[{m.group(1)}]({m.group(2).replace('.md', '.html')})",
            content,
        )

        # Handle relative path adjustments for nested directories
        def fix_relative_link(match):
            link_text = match.group(1)
            link_path = match.group(2)

            if link_path.startswith("./") or link_path.startswith("../"):
                # Calculate relative path from current file to target
                try:
                    target_path = (current_file.parent / link_path).resolve()
                    rel_path = os.path.relpath(target_path, self.docs_dir)
                    html_path = str(Path(rel_path).with_suffix(".html"))
                    return f"[{link_text}]({html_path})"
                except:
                    pass
            return match.group(0)

        content = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", fix_relative_link, content)
        return content

    def convert_md_to_html(self, md_content):
        """Convert Markdown content to HTML with Mermaid support."""
        renderer = self.mermaid_renderer
        markdown = mistune.Markdown(renderer)
        html_body = markdown(md_content)

        # Full HTML template with Mermaid support
        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Markdown Document</title>
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{ startOnLoad: true }});
    </script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }}
        pre {{
            background: #f4f4f4;
            padding: 10px;
            border-radius: 5px;
            overflow-x: auto;
        }}
        code {{
            background: #f4f4f4;
            padding: 2px 4px;
            border-radius: 3px;
        }}
        .mermaid {{
            text-align: center;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    {html_body}
</body>
</html>"""

        return html_template


    def main(self):
        # parser = argparse.ArgumentParser(description='Convert Markdown to HTML with Mermaid support')
        # parser.add_argument('input_file', help='Input Markdown file')
        # parser.add_argument('output_file', help='Output HTML file')

        # args = parser.parse_args()

        try:
            with open(self.in, 'r', encoding='utf-8') as f:
                md_content = f.read()
            # Convert markdown to HTML
            html_content = self.convert_md_to_html(md_content)
            # Convert markdown to HTML

            with open(output_file_full_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            print(f"Successfully converted {input_file_full_path} to {output_file_full_path}")

        except FileNotFoundError:
            print(f"Error: Input file '{input_file_full_path}' not found")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == '__main__':
    path = "documentation/datavault_v2_principles.md"
    output_path = "documentation/datavault_v2_principles.html"
    html_convertor = MdToHtmlConverter(output_file_full_path=output_path, input_file_full_path=path)
    html_convertor.main()
