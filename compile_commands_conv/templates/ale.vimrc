if !exists('g:ale_linters')
    let g:ale_linters = {}
endif

{%- for x in ale_linters %}
let g:ale_linters['{{x.filetype}}'] = ['{{x.name}}']
let g:ale_{{x.filetype}}_{{x.vname}}_executable = '{{x.executable}}'
let g:ale_{{x.filetype}}_{{x.vname}}_options = '{{x.options}}'
{%- endfor %}
