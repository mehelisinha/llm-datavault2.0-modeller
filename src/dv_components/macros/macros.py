class DBTMacros:
    """Generates macros"""

    # ------------------------------------------------------------------
    # Macros
    # ------------------------------------------------------------------

    # Override dbt's default schema naming (which prepends target.schema).
    # With this macro, +schema in dbt_project.yml is used exactly as-is.
    @staticmethod
    def generate_schema_name() -> str:
        return """\
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
"""
