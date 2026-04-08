#!/usr/bin/env python3
"""
Markdown to HTML Documentation Exporter

This script converts all markdown documentation files to HTML format,
creating a navigable HTML documentation site.

Usage:
    python export_docs.py [output_dir]

Arguments:
    output_dir: Directory to output HTML files (default: docs_html)

Features:
    - Converts all .md files in documentation/ to .html
    - Maintains directory structure
    - Converts relative markdown links to .html
    - Adds navigation and styling
    - Creates an index page with table of contents
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, List

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


class MarkdownExporter:
    """Converts markdown documentation to HTML with navigation."""

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

    def find_markdown_files(self):
        """Find all markdown files in the documentation directory."""
        self.md_files = list(self.docs_dir.rglob("*.md"))
        print(f"Found {len(self.md_files)} markdown files")

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

    def convert_markdown_to_html(self, md_file: Path) -> str:
        """Convert a markdown file to HTML."""
        with open(md_file, "r", encoding="utf-8") as f:
            md_content = f.read()

        # Convert relative links
        md_content = self.convert_links(md_content, md_file)

        # Handle Mermaid diagrams
        md_content = self._process_mermaid_blocks(md_content)

        # Convert to HTML
        html_content = markdown.markdown(md_content, extensions=self.md_extensions)

        return html_content

    def _process_mermaid_blocks(self, content: str) -> str:
        """Process Mermaid code blocks for proper rendering."""
        import re

        # Pattern to match ```mermaid blocks
        mermaid_pattern = r"```mermaid\s*\n(.*?)\n```"

        def replace_mermaid_block(match):
            mermaid_code = match.group(1).strip()
            # Create a div with class mermaid that Mermaid.js will render
            return f'<div class="mermaid">\n{mermaid_code}\n</div>'

        # Replace all mermaid code blocks
        content = re.sub(
            mermaid_pattern, replace_mermaid_block, content, flags=re.DOTALL
        )

        return content

    def get_breadcrumb(self, rel_path: Path) -> str:
        """Generate breadcrumb navigation."""
        parts = list(rel_path.parts)
        if not parts:
            return ""

        breadcrumb = ['<a href="index.html">docs</a>']
        current_path = Path(".")

        for i, part in enumerate(parts[:-1]):  # Exclude the current file
            current_path = current_path / part
            breadcrumb.append(f'<a href="{current_path}/index.html">{part}</a>')

        breadcrumb.append(f"<span>{rel_path.stem}</span>")
        return " / ".join(breadcrumb)

    def get_nav_links(self, current_file: Path) -> List[Dict[str, str]]:
        """Generate navigation links for the current page."""
        nav_links = []

        # Add parent directory index if it exists
        parent_index = current_file.parent / "index.html"
        if parent_index.exists():
            nav_links.append(
                {
                    "title": "📁 Parent",
                    "url": os.path.relpath(parent_index, current_file.parent),
                }
            )

        # Add sibling pages
        for sibling in current_file.parent.glob("*.html"):
            if sibling != current_file.with_suffix(".html"):
                nav_links.append(
                    {
                        "title": f"📄 {sibling.stem.replace('_', ' ').title()}",
                        "url": sibling.name,
                    }
                )

        return nav_links[:5]  # Limit to 5 links

    def create_index_page(self):
        """Create an index page with table of contents."""
        toc_content = ["# EDH Data Pipeline Documentation\n\n"]

        # Group files by directory
        dirs = {}
        for md_file in sorted(self.md_files):
            rel_path = md_file.relative_to(self.docs_dir)
            dir_name = str(rel_path.parent) if rel_path.parent != Path(".") else "root"

            if dir_name not in dirs:
                dirs[dir_name] = []

            html_path = str(rel_path.with_suffix(".html"))
            title = md_file.stem.replace("_", " ").title()
            dirs[dir_name].append(f"- [{title}]({html_path})")

        # Create table of contents
        for dir_name, files in sorted(dirs.items()):
            if dir_name != "root":
                toc_content.append(f"## {dir_name.title()}\n")
            else:
                toc_content.append("## Main Documentation\n")

            toc_content.extend(files)
            toc_content.append("")

        index_md = "\n".join(toc_content)

        # Convert to HTML
        html_content = markdown.markdown(index_md, extensions=self.md_extensions)

        # Generate index.html
        index_path = self.output_dir / "index.html"
        nav_links = []

        html_output = self.html_template.render(
            title="EDH Documentation Home",
            content=html_content,
            breadcrumb="",
            nav_links=nav_links,
            timestamp="2026-03-25",
        )

        with open(index_path, "w", encoding="utf-8") as f:
            f.write(html_output)

        print(f"Created index page: {index_path}")

    def export_file(self, md_file: Path):
        """Export a single markdown file to HTML."""
        rel_path = md_file.relative_to(self.docs_dir)
        html_file = self.output_dir / rel_path.with_suffix(".html")

        # Create output directory
        html_file.parent.mkdir(parents=True, exist_ok=True)

        # Convert markdown to HTML
        html_content = self.convert_markdown_to_html(md_file)

        # Generate breadcrumb
        breadcrumb = self.get_breadcrumb(rel_path)

        # Generate navigation links
        nav_links = self.get_nav_links(html_file)

        # Generate title
        title = md_file.stem.replace("_", " ").title()

        # Render HTML template
        html_output = self.html_template.render(
            title=title,
            content=html_content,
            breadcrumb=breadcrumb,
            nav_links=nav_links,
            timestamp="2026-03-25",
        )

        # Write HTML file
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html_output)

        print(f"Exported: {rel_path} -> {html_file}")

    def export_all(self):
        """Export all markdown files to HTML."""
        print(f"Exporting documentation from {self.docs_dir} to {self.output_dir}")

        # Find all markdown files
        self.find_markdown_files()

        if not self.md_files:
            print("No markdown files found!")
            return

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Export each file
        for md_file in self.md_files:
            self.export_file(md_file)

        # Create index page
        self.create_index_page()

        print(f"\nExport complete! {len(self.md_files)} files converted.")
        print(
            f"Open {self.output_dir}/index.html in your browser to view the documentation."
        )


def main():
    parser = argparse.ArgumentParser(
        description="Export markdown documentation to HTML"
    )
    parser.add_argument(
        "output_dir",
        nargs="?",
        default="docs_html",
        help="Output directory for HTML files (default: docs_html)",
    )
    parser.add_argument(
        "--docs-dir",
        default="documentation",
        help="Source directory containing markdown files (default: documentation)",
    )

    args = parser.parse_args()

    # Initialize exporter
    exporter = MarkdownExporter(args.docs_dir, args.output_dir)

    # Export all documentation
    exporter.export_all()


if __name__ == "__main__":
    main()
