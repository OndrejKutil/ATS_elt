{#
    location.name is free text that can pack several locations into one string,
    separated by "|" or ";" (up to 27 of them in the current archive, in ~13%
    of postings). This is the single definition of how that string is split, so
    the column and the content hash can never disagree about it.

    Returns source order. Callers that need order-independence -- the content
    hash -- wrap this in list_sort().
#}

{% macro split_locations(expr) %}
str_split(regexp_replace(trim({{ expr }}), '\s*[|;]\s*', ';', 'g'), ';')
{% endmacro %}
