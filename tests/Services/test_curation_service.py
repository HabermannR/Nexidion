from types import SimpleNamespace

from backend.services.curation_service import PROMPT_VERSION, SYSTEM_PROMPT, _request_nodes


def _response(content):
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=content))])


def test_curation_repairs_missing_page_coverage():
    responses = iter([
        _response('{"nodes":[{"title":"Kapitel 1","content":"Inhalt","page_from":1,"page_to":1,"parent_index":null}]}'),
        _response('{"nodes":[{"title":"Gesamtüberblick","content":"Inhalt","page_from":1,"page_to":2,"parent_index":null}]}'),
    ])
    calls = []

    class Completions:
        @staticmethod
        def create(**kwargs):
            calls.append(kwargs)
            return next(responses)

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    artifact = SimpleNamespace(extracted_json={"pages": [
        {"page": 1, "markdown": "Erste Seite"},
        {"page": 2, "markdown": "Zweite Seite"},
    ]}, payload=None)
    job = SimpleNamespace(visual_mode='off')

    nodes = _request_nodes(client, 'local', job, artifact)

    assert len(calls) == 2
    assert 'No node covers source pages: 2.' in calls[1]['messages'][-1]['content']
    assert nodes[0]['page_to'] == 2


def test_curation_prompt_requires_source_language_and_hierarchy():
    assert 'predominant language of the source' in SYSTEM_PROMPT
    assert '3-7 direct children' in SYSTEM_PROMPT
    assert 'single document-level root' in SYSTEM_PROMPT
    assert PROMPT_VERSION == 'pdf-curation-v4'


def test_curation_repairs_an_entirely_flat_substantial_response():
    flat = '{"nodes":[' + ','.join(
        f'{{"title":"Thema {i}","content":"Inhalt","page_from":1,"page_to":1,"parent_index":null}}'
        for i in range(4)) + ']}'
    hierarchical = ('{"nodes":['
        '{"title":"Überblick","content":"Inhalt","page_from":1,"page_to":1,"parent_index":null},'
        '{"title":"A","content":"Inhalt","page_from":1,"page_to":1,"parent_index":0},'
        '{"title":"B","content":"Inhalt","page_from":1,"page_to":1,"parent_index":0},'
        '{"title":"C","content":"Inhalt","page_from":1,"page_to":1,"parent_index":0}]}')
    responses = iter([_response(flat), _response(hierarchical)])
    calls = []

    class Completions:
        @staticmethod
        def create(**kwargs):
            calls.append(kwargs)
            return next(responses)

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    artifact = SimpleNamespace(extracted_json={"pages": [{"page": 1, "markdown": "Text"}]}, payload=None)

    nodes = _request_nodes(client, 'local', SimpleNamespace(visual_mode='off'), artifact)

    assert len(calls) == 2
    assert 'entirely flat' in calls[1]['messages'][-1]['content']
    assert [node['parent_index'] for node in nodes] == [None, 0, 0, 0]


def test_curation_repairs_multiple_top_level_topic_nodes():
    multiple_roots = ('{"nodes":['
        '{"title":"Dokument","content":"Überblick","page_from":1,"page_to":1,"parent_index":null},'
        '{"title":"Thema","content":"Inhalt","page_from":1,"page_to":1,"parent_index":null}]}')
    repaired = ('{"nodes":['
        '{"title":"Dokument","content":"Überblick","page_from":1,"page_to":1,"parent_index":null},'
        '{"title":"Thema","content":"Inhalt","page_from":1,"page_to":1,"parent_index":0}]}')
    responses = iter([_response(multiple_roots), _response(repaired)])
    calls = []

    class Completions:
        @staticmethod
        def create(**kwargs):
            calls.append(kwargs)
            return next(responses)

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    artifact = SimpleNamespace(extracted_json={"pages": [{"page": 1, "markdown": "Text"}]}, payload=None)

    nodes = _request_nodes(client, 'local', SimpleNamespace(visual_mode='off'), artifact)

    assert len(calls) == 2
    assert 'single document-level root' in calls[1]['messages'][-1]['content']
    assert [node['parent_index'] for node in nodes] == [None, 0]
