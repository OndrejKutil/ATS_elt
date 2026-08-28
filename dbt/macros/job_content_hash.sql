{#
    The single definition of what "the same posting content" means.

    Hashed over an explicit allowlist, in a fixed order, so a change to any
    meaningful field produces a new hash and nothing else does. Deliberately
    excluded: updated_at and other server-generated fields -- Greenhouse
    bulk-touches updated_at, so including it would make every posting hash
    differently on every run and the deduplication would detect nothing.

    Whitespace in content is collapsed before hashing: the same description
    reflowed or re-indented is not a content change.

    Department and office names are sorted, so a reordering of those lists by
    the API does not read as a content change. Location gets the same treatment:
    it is split on its delimiters and sorted, so "Chicago; San Francisco" and
    "San Francisco; Chicago" are one body, not two.
#}

{% macro job_content_hash(job) %}
md5(concat_ws('||',
    coalesce({{ job }}.title, ''),
    coalesce(regexp_replace(trim({{ job }}.content), '\s+', ' ', 'g'), ''),
    coalesce(array_to_string(list_sort({{ split_locations(job ~ '.location.name') }}), ','), ''),
    coalesce(array_to_string(list_sort(list_transform({{ job }}.departments, x -> x.name)), ','), ''),
    coalesce(array_to_string(list_sort(list_transform({{ job }}.offices, x -> x.name)), ','), ''),
    coalesce({{ job }}.absolute_url, '')
))
{% endmacro %}
