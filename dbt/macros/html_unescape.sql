{#
    One layer of HTML entity decoding.

    Greenhouse returns the posting body entity-escaped *twice*: the archive
    holds "&amp;lt;p&amp;gt;", which is the escaped form of "&lt;p&gt;", which
    is the escaped form of "<p>". So callers apply this macro twice before the
    markup is real markup -- see strip_html().

    "&amp;" is decoded last within a pass, so a pass unwraps exactly one layer:
    decoding it first would turn "&amp;lt;" into "<" in a single pass and the
    two layers could no longer be told apart.

    Only the entities the archive actually contains are covered, plus the
    common punctuation ones. Arbitrary numeric entities are not decoded --
    DuckDB has no built-in unescape and a general decoder is not expressible as
    a plain expression; the observed data needs none beyond those listed.
#}

{% macro html_unescape(expr) %}
{%- set entities = [
    ('&lt;',     '<'),
    ('&gt;',     '>'),
    ('&quot;',   '"'),
    ('&#34;',    '"'),
    ('&#39;',    "''"),
    ('&apos;',   "''"),
    ('&nbsp;',   ' '),
    ('&#160;',   ' '),
    ('&mdash;',  '—'),
    ('&ndash;',  '–'),
    ('&rsquo;',  '’'),
    ('&lsquo;',  '‘'),
    ('&ldquo;',  '“'),
    ('&rdquo;',  '”'),
    ('&hellip;', '…'),
    ('&bull;',   '•'),
    ('&middot;', '·'),
    ('&trade;',  '™'),
    ('&reg;',    '®'),
    ('&copy;',   '©'),
    ('&deg;',    '°'),
    ('&amp;',    '&')
] -%}
{%- set ns = namespace(sql = expr) -%}
{%- for entity, character in entities -%}
{%- set ns.sql = "replace(" ~ ns.sql ~ ", '" ~ entity ~ "', '" ~ character ~ "')" -%}
{%- endfor -%}
{{ ns.sql }}
{%- endmacro %}
