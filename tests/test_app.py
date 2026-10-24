from app import enrich, similarity, vote_voice


def test_similarity_ignores_case_accents_and_stopwords() -> None:
    assert similarity("Ave verum corpus Mozart", "AVE VERUM CORPUS - W. A. Mozart", "") == 1.0


def test_similarity_does_not_reward_empty_query() -> None:
    assert similarity("", "Ave verum", "") == 0.0


def test_enrich_deduplicates_and_orders_by_votes_then_similarity() -> None:
    raw = [
        {"video_id": "a", "video_title": "Otra obra", "channel": "X", "voice": "song", "material_type": "full_performance"},
        {"video_id": "b", "video_title": "Ave verum corpus Mozart", "channel": "X", "voice": "song", "material_type": "full_performance"},
        {"video_id": "b", "video_title": "Ave verum corpus Mozart", "channel": "X", "voice": "song", "material_type": "full_performance"},
    ]
    counts = {("a", "song"): {"approved": 2, "rejected": 0, "mine": ""}}
    result = enrich(raw, "Ave verum corpus Mozart", counts)
    assert [item["video_id"] for item in result] == ["a", "b"]
    assert result[1]["similarity"] == 1.0

def test_vote_voice_rejects_all_and_unknown_values() -> None:
    assert vote_voice("soprano") == "soprano"
    assert vote_voice("all") == "unknown"
    assert vote_voice("otra") == "unknown"

