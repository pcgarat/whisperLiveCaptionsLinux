from src.asr.streaming import LocalAgreementStreamer


def test_commits_shared_prefix_after_agreement() -> None:
    s = LocalAgreementStreamer(agreement_n=2)
    r1 = s.push("Hello world today")
    assert r1.newly_committed == ""
    assert r1.partial

    r2 = s.push("Hello world tomorrow")
    assert r2.committed.startswith("Hello world")
    assert r2.newly_committed.startswith("Hello world")
    assert "tomorrow" in r2.partial or r2.partial == "tomorrow"


def test_stable_commitment_grows_monotonically() -> None:
    s = LocalAgreementStreamer(agreement_n=2)
    s.push("One two three")
    s.push("One two three four")
    mid = s.committed
    s.push("One two three four five")
    s.push("One two three four five six")
    assert s.committed.startswith(mid)
    assert len(s.committed) >= len(mid)


def test_empty_hypothesis_is_noop() -> None:
    s = LocalAgreementStreamer(agreement_n=2)
    s.push("Alpha beta")
    s.push("Alpha beta gamma")
    before = s.committed
    r = s.push("   ")
    assert r.committed == before
    assert r.newly_committed == ""


def test_reset_clears_state() -> None:
    s = LocalAgreementStreamer(agreement_n=2)
    s.push("Hello there")
    s.push("Hello there friend")
    s.reset()
    assert s.committed == ""
    r = s.push("New text here")
    assert r.committed == ""
