import pytest

from ragent.config import Settings
from ragent.ingest.chunking import chunk_document, chunk_fixed, chunk_structure, split_sections
from ragent.ingest.loaders import html_to_text, load_dir, load_path
from ragent.ingest.pipeline import ingest_documents
from ragent.llm.fake import FakeEmbedder
from ragent.models import Document
from ragent.store.memory import MemoryStore
from tests.conftest import SAMPLE

DOC = Document(
    "demo",
    "Demo",
    "# Demo\n\nIntro text.\n\n## First\n\nAlpha beta.\n\n```\n# not a heading\n```\n\n### Deep\n\nGamma.\n\n## Second\n\nDelta.",
)


def test_split_sections_builds_heading_paths_and_ignores_fences():
    sections = split_sections(DOC.text)
    assert [s for s, _ in sections] == [
        "Demo",
        "Demo > First",
        "Demo > First > Deep",
        "Demo > Second",
    ]
    assert "# not a heading" in sections[1][1]


def test_structure_chunks_keep_section_and_sequential_ordinals():
    chunks = chunk_structure(DOC, size=50, overlap=5)
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))
    assert chunks[-1].section == "Demo > Second"
    assert chunks[-1].id == f"demo#{len(chunks) - 1}"


def test_structure_packs_paragraphs_up_to_size():
    text = "# T\n\n" + "\n\n".join(" ".join(["w"] * 10) for _ in range(5))
    chunks = chunk_structure(Document("d", "T", text), size=25, overlap=0)
    assert [c.token_count for c in chunks] == [20, 20, 10]


def test_long_paragraph_falls_back_to_window_with_overlap():
    words = [f"w{i}" for i in range(25)]
    chunks = chunk_structure(Document("d", "T", "# T\n\n" + " ".join(words)), size=10, overlap=2)
    assert [c.token_count for c in chunks] == [10, 10, 9]
    assert chunks[1].content.split()[:2] == ["w8", "w9"]  # overlap of 2 words


def test_fixed_chunks_cover_every_word():
    words = [f"w{i}" for i in range(23)]
    chunks = chunk_fixed(Document("d", "T", " ".join(words)), size=10, overlap=0)
    assert " ".join(c.content for c in chunks).split() == words


def test_invalid_chunk_settings_raise():
    with pytest.raises(ValueError):
        chunk_fixed(DOC, size=10, overlap=10)
    with pytest.raises(ValueError):
        chunk_document(DOC, "semantic", 10, 0)


def test_html_loader_drops_navigation_and_keeps_structure():
    html = """<html><head><title>Page title</title><script>x()</script></head><body>
    <nav><a>Home</a></nav><main><h1>Queues</h1><p>A <b>queue</b> holds messages.</p>
    <h2>Limits</h2><ul><li><p>Item one</p></li><li>Item two</li></ul>
    <table><tr><th>Name</th><th>Value</th></tr><tr><td>Timeout</td><td>30</td></tr></table>
    <pre>aws sqs list-queues</pre></main><footer>Legal</footer></body></html>"""
    title, text = html_to_text(html)
    assert title == "Queues"
    assert "Home" not in text and "Legal" not in text and "x()" not in text
    assert "# Queues" in text and "## Limits" in text
    assert "- Item one" in text and text.count("Item one") == 1
    assert "Timeout | 30" in text and "```\naws sqs list-queues\n```" in text


def test_load_dir_reads_the_sample_corpus(tmp_path):
    docs = load_dir(SAMPLE)
    assert {d.source for d in docs} == {"sqs", "sns", "eventbridge", "lambda", "dynamodb", "s3"}
    assert next(d for d in docs if d.source == "sqs").title == "Amazon SQS"
    (tmp_path / "empty.md").write_text("  \n")
    with pytest.raises(ValueError):
        load_path(tmp_path / "empty.md")


def test_ingest_is_idempotent_and_reacts_to_setting_changes():
    store, embedder = MemoryStore(), FakeEmbedder(64)
    settings = Settings(embed_dim=64)
    docs = load_dir(SAMPLE)
    first = ingest_documents(docs, store, embedder, settings)
    assert first.documents == 6 and first.skipped == 0 and store.count() == first.chunks
    second = ingest_documents(docs, store, embedder, settings)
    assert second.documents == 0 and second.skipped == 6
    third = ingest_documents(docs, store, embedder, Settings(embed_dim=64, chunk_strategy="fixed"))
    assert third.documents == 6 and store.count() == third.chunks
