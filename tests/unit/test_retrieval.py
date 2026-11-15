from ragent.llm.fake import ScriptedChat
from ragent.models import ChatResponse, Chunk, ScoredChunk
from ragent.retrieval.fusion import rrf
from ragent.retrieval.rerank import LexicalReranker, LLMReranker, NoReranker, parse_scores
from ragent.store.pgvector import build_tsquery


def _candidates() -> list[ScoredChunk]:
    return [
        ScoredChunk(Chunk("a", 0, "Intro", "general words about storage", 4), 0.03),
        ScoredChunk(
            Chunk("a", 1, "Timeout", "the default visibility timeout is 30 seconds", 7), 0.02
        ),
        ScoredChunk(Chunk("b", 0, "Other", "nothing relevant here", 3), 0.01),
    ]


def test_rrf_rewards_items_found_by_both_lists():
    fused = rrf({"vector": ["a", "b", "c"], "keyword": ["b", "d"]}, k=60)
    assert max(fused, key=fused.get) == "b"
    assert fused["a"] == 1 / 61 and fused["b"] == 1 / 62 + 1 / 61
    assert rrf({}) == {}


def test_memory_store_vector_and_keyword_search(offline):
    query = "default visibility timeout"
    vector_hits = offline.store.vector_search(offline.embedder.embed_query(query), 3)
    keyword_hits = offline.store.keyword_search(query, 3)
    assert vector_hits[0][0].section.endswith("Visibility timeout")
    assert keyword_hits[0][0].section.endswith("Visibility timeout")
    assert offline.store.keyword_search("zzzz qqqq", 3) == []


def test_keyword_search_finds_exact_identifier(offline):
    hits = offline.store.keyword_search("ReceiveMessageWaitTimeSeconds", 3)
    assert hits and hits[0][0].section.endswith("Long polling")


def test_neighbours_and_get_chunk(offline):
    chunk = offline.store.get_chunk("sqs", 2)
    assert chunk is not None and chunk.id == "sqs#2"
    assert [c.ordinal for c in offline.store.neighbours("sqs", 2, 1)] == [1, 2, 3]
    assert [c.ordinal for c in offline.store.neighbours("sqs", 0, 1)] == [0, 1]
    assert (
        offline.store.neighbours("nope", 0, 1) == [] and offline.store.get_chunk("sqs", 999) is None
    )


def test_retriever_modes_and_ranks(offline):
    hits = offline.retriever.retrieve("What is the default visibility timeout?", 3)
    assert len(hits) == 3 and hits[0].chunk.section.endswith("Visibility timeout")
    assert set(hits[0].ranks) == {"vector", "keyword"}
    assert set(offline.retriever.retrieve("visibility timeout", 3, "vector")[0].ranks) == {"vector"}
    assert set(offline.retriever.retrieve("visibility timeout", 3, "keyword")[0].ranks) == {
        "keyword"
    }


def test_no_reranker_keeps_order_and_lexical_promotes_overlap():
    query = "default visibility timeout"
    assert [c.chunk.id for c in NoReranker().rerank(query, _candidates(), 2)] == ["a#0", "a#1"]
    reranked = LexicalReranker().rerank(query, _candidates(), 2)
    assert [c.chunk.id for c in reranked] == ["a#1", "a#0"]
    assert 0 <= reranked[1].score <= reranked[0].score <= 1
    assert LexicalReranker().rerank(query, [], 2) == []


def test_llm_reranker_uses_scores_and_survives_bad_output():
    good = ScriptedChat(
        [ChatResponse('Here: [{"i": 1, "score": 2}, {"i": 2, "score": 9}, {"i": 3, "score": 0}]')]
    )
    reranked = LLMReranker(good).rerank("q", _candidates(), 2)
    assert [c.chunk.id for c in reranked] == ["a#1", "a#0"] and reranked[0].score == 0.9
    bad = ScriptedChat([ChatResponse("I think the second one is best.")])
    assert [c.chunk.id for c in LLMReranker(bad).rerank("q", _candidates(), 2)] == ["a#0", "a#1"]


def test_parse_scores_ignores_junk():
    assert parse_scores('[{"i": 1, "score": 15}, {"i": 9, "score": 3}, {"i": "x"}, 4]', 3) == {
        1: 10.0
    }
    assert parse_scores("[not json]", 3) is None and parse_scores("none", 3) is None


def test_build_tsquery_ors_content_words_and_is_safe():
    assert (
        build_tsquery("What is the default visibility-timeout?") == "default | visibility | timeout"
    )
    assert build_tsquery("'); DROP TABLE chunks;--") == "drop | table | chunks"
    assert build_tsquery("the of and") == ""
