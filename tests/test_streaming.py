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


def test_agreement_n_one_commits_first_hypothesis() -> None:
    s = LocalAgreementStreamer(agreement_n=1, max_latency_sec=5.0)
    r = s.push("Hello world")
    assert r.newly_committed == "Hello world"
    assert r.committed == "Hello world"
    assert r.partial == ""


def test_force_commit_after_max_latency() -> None:
    clock = {"t": 0.0}

    def now() -> float:
        return clock["t"]

    s = LocalAgreementStreamer(agreement_n=2, max_latency_sec=1.0, clock=now)
    r1 = s.push("One path alpha")
    assert r1.newly_committed == ""
    assert r1.partial

    clock["t"] = 0.5
    r2 = s.push("Two path beta")
    assert r2.newly_committed == ""

    clock["t"] = 1.2
    r3 = s.push("Two path beta longer")
    assert r3.newly_committed
    assert "path" in r3.committed.lower() or "Two" in r3.committed


def test_no_force_commit_before_max_latency() -> None:
    clock = {"t": 0.0}

    def now() -> float:
        return clock["t"]

    s = LocalAgreementStreamer(agreement_n=2, max_latency_sec=2.0, clock=now)
    s.push("Alpha one")
    clock["t"] = 1.0
    r = s.push("Beta two")
    assert r.newly_committed == ""
    assert r.partial
