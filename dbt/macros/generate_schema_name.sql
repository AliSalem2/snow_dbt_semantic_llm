{#
  prod -> STAGING, INTERMEDIATE, MARTS
  dev  -> DBT_DEV_STAGING, DBT_DEV_MARTS, ...
  ci   -> DBT_CI_STAGING, DBT_CI_MARTS, ...
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- elif target.name in ('prod', 'serve') -%}
        {{ custom_schema_name | trim }}
    {%- else -%}
        {{ target.schema }}_{{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
