from app import enrich, similarity, voice_match, vote_voice


def test_similarity_ignores_case_accents_and_stopwords() -> None:
    assert similarity("Ave verum corpus Mozart", "AVE VERUM CORPUS - W. A. Mozart", "") == 1.0


def test_similarity_does_not_reward_empty_query() -> None:
    assert similarity("", "Ave verum", "") == 0.0


def test_enrich_deduplicates_and_orders_by_text_similarity() -> None:
    raw = [
        {"video_id": "a", "video_title": "Otra obra", "channel": "X", "voice": "song", "material_type": "full_performance"},
        {"video_id": "b", "video_title": "Ave verum corpus Mozart", "channel": "X", "voice": "song", "material_type": "full_performance"},
        {"video_id": "b", "video_title": "Ave verum corpus Mozart", "channel": "X", "voice": "song", "material_type": "full_performance"},
    ]
    counts = {("a", "song"): {"approved": 2, "rejected": 0, "mine": ""}}
    result = enrich(raw, "Ave verum corpus Mozart", counts, "song")
    assert [item["video_id"] for item in result] == ["b", "a"]
    assert result[0]["similarity"] == 1.0

def test_vote_voice_rejects_all_and_unknown_values() -> None:
    assert vote_voice("soprano") == "soprano"
    assert vote_voice("all") == "unknown"
    assert vote_voice("otra") == "unknown"



def test_voice_match_uses_localized_words_without_substring_false_positives() -> None:
    assert voice_match("Ensayo de bajo", "bass") == 1.0
    assert voice_match("Baix solista", "bass") == 1.0
    assert voice_match("Bassoon concerto", "bass") == 0.0
