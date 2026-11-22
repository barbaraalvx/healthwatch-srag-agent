from srag.report.markup import markdown_to_html, split_sections


def test_split_sections_maps_each_heading_to_its_body():
    text = "## Resumo executivo\nA\n\n## Análise do cenário\nB1\n\nB2\n"

    assert split_sections(text) == {"Resumo executivo": "A", "Análise do cenário": "B1\n\nB2"}


def test_split_sections_ignores_text_before_the_first_heading():
    assert split_sections("intro\n## Resumo executivo\nA") == {"Resumo executivo": "A"}


def test_links_are_rendered_as_anchors():
    html = markdown_to_html("Veja [Fiocruz](https://agencia.fiocruz.br/x).")

    assert '<a href="https://agencia.fiocruz.br/x">Fiocruz</a>' in html


def test_raw_html_is_escaped():
    html = markdown_to_html("<script>alert(1)</script> texto")

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_javascript_links_are_not_turned_into_anchors():
    html = markdown_to_html("[clique](javascript:alert(1))")

    assert "<a " not in html
