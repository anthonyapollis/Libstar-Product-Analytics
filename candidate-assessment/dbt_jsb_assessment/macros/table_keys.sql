{#
  Primary key, unique keys and indexes for a mart table, used as a post_hook.

  dbt's CREATE TABLE ... AS SELECT carries no keys or indexes on MySQL/MariaDB, so every mart
  gets them added after it is built. The macro first checks whether the primary key already
  exists: a table model is rebuilt from scratch each run, so it always needs keys, while an
  incremental model keeps its table, so keys are added only on the first (or full-refresh) build.

  Usage:
    {{ config(post_hook="{{ table_keys(['bet_id'], indexes=[['player_id'], ['placed_date']]) }}") }}
#}
{% macro table_keys(primary_key, unique=[], indexes=[]) %}
  {%- set has_pk = false -%}
  {%- if execute -%}
    {%- set result = run_query(
          "select count(*) from information_schema.statistics"
          ~ " where table_schema = '" ~ this.schema ~ "' and table_name = '" ~ this.identifier ~ "'"
          ~ " and index_name = 'PRIMARY'") -%}
    {%- set has_pk = result.columns[0].values()[0] > 0 -%}
  {%- endif -%}
  {%- if has_pk -%}
    select 1  /* keys already present (incremental run) */
  {%- else -%}
    alter table {{ this }}
      add primary key ({{ primary_key | join(', ') }})
      {%- for cols in unique %},
      add unique key ux_{{ this.identifier }}_{{ loop.index }} ({{ cols | join(', ') }})
      {%- endfor %}
      {%- for cols in indexes %},
      add index ix_{{ this.identifier }}_{{ loop.index }} ({{ cols | join(', ') }})
      {%- endfor %}
  {%- endif -%}
{% endmacro %}
