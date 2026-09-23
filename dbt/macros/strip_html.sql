{#
    The single definition of "the posting body as plain text".

    Greenhouse returns job descriptions as HTML fragments, double entity-escaped
    (see html_unescape). Downstream wants prose: something searchable, diffable
    and feedable to a model, with the document's shape -- paragraphs, headings,
    bullet lists -- preserved as line breaks rather than thrown away.

    The stages, in order, and why the order matters:

      1. Decode twice, so the markup is markup. Nothing can be matched as a tag
         before this.
      2. Drop comments and embedded media (script/style/iframe/noscript/video/
         audio) *with* their contents -- boilerplate that is not part of the
         posting. RE2 has no backreferences, so each tag is handled separately.
      3. Turn structural tags into whitespace: block closers and <br> become
         newlines, list items become "- " bullets. Done before stripping, since
         stage 4 no longer knows which tag it is removing.
      4. Strip every remaining tag.
      5. Decode once more, for entities that were text rather than markup and
         so survived stage 1 as escaped text.
      6. Normalise whitespace: non-breaking and zero-width characters to
         spaces, runs of spaces collapsed, blank runs capped at one.

    Stage 5 runs after stripping on purpose: an entity-escaped "<" in prose
    becomes a literal "<" only once nothing is looking for tags any more, so it
    cannot be mistaken for markup and swallowed.
#}

{% macro strip_html(expr) %}

{#- 1. Two decode passes: the archive stores the body double-escaped. -#}
{%- set decoded = html_unescape(html_unescape('trim(' ~ expr ~ ')')) -%}

{#- 2. Embedded media and comments, contents included. -#}
{%- set ns = namespace(sql = "regexp_replace(" ~ decoded ~ ", '<!--.*?-->', ' ', 'gs')") -%}
{%- for tag in ['script', 'style', 'iframe', 'noscript', 'video', 'audio'] -%}
{%- set ns.sql = "regexp_replace(" ~ ns.sql ~ ", '<" ~ tag ~ "\\b.*?</" ~ tag ~ "\\s*>', ' ', 'gis')" -%}
{%- endfor -%}

{#- 3. Structure -> whitespace. Replacements are SQL expressions rather than
       literals so newlines stay as chr(10): a real newline inside a quoted
       string would survive into the compiled SQL and shred its formatting.
       List items come first, so the generic block-closer rule below does not
       also fire on </li> and double-space every bullet. -#}
{%- set structure = [
    ("<li\\b[^>]*>",  "chr(10) || '- '"),
    ("</li\\s*>",     "''"),
    ("<br\\s*/?>",    "chr(10)"),
    ("<hr\\b[^>]*>",  "chr(10)"),
    ("</t[dh]\\s*>",  "' '"),
    ("</(p|div|h[1-6]|tr|ul|ol|table|section|article|header|footer|blockquote)\\s*>",
                     "chr(10) || chr(10)")
] -%}
{%- for pattern, replacement in structure -%}
{%- set ns.sql = "regexp_replace(" ~ ns.sql ~ ", '" ~ pattern ~ "', " ~ replacement ~ ", 'gis')" -%}
{%- endfor -%}

{#- 4. Everything still in angle brackets. -#}
{%- set ns.sql = "regexp_replace(" ~ ns.sql ~ ", '<[^>]*>', '', 'gs')" -%}

{#- 5. Entities that were prose, not markup. -#}
{%- set ns.sql = html_unescape(ns.sql) -%}

{#- 6. Whitespace. Non-breaking/zero-width characters become ordinary spaces
       first, so the collapse rules can see them. -#}
{%- set whitespace = [
    ("[\\x{00a0}\\x{2007}\\x{202f}]",           "' '"),
    ("[\\x{200b}\\x{200c}\\x{200d}\\x{feff}]", "''"),
    ("[ \\t\\r\\f\\v]+",                      "' '"),
    (" *\\n *",                                 "chr(10)"),
    ("\\n{3,}",                                 "chr(10) || chr(10)")
] -%}
{%- for pattern, replacement in whitespace -%}
{%- set ns.sql = "regexp_replace(" ~ ns.sql ~ ", '" ~ pattern ~ "', " ~ replacement ~ ", 'g')" -%}
{%- endfor -%}

trim({{ ns.sql }})
{%- endmacro %}
