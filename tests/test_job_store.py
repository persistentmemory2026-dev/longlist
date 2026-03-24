import job_store


def test_put_merge_and_count(tmp_path):
    job_store.init_db(str(tmp_path / "j.db"))
    job_store.put_job("abc", {"status": "parsing", "sender": "a@b.c"})
    job_store.merge_job("abc", {"status": "parsed"})
    j = job_store.get_job("abc")
    assert j["status"] == "parsed"
    assert j["sender"] == "a@b.c"
    assert job_store.count_jobs() == 1


def test_stripe_session_idempotent(tmp_path):
    job_store.init_db(str(tmp_path / "s.db"))
    assert job_store.try_claim_stripe_session("cs_test_1", "job1") is True
    assert job_store.try_claim_stripe_session("cs_test_1", "job1") is False


def test_try_claim_rejects_empty_session(tmp_path, caplog):
    job_store.init_db(str(tmp_path / "e.db"))
    assert job_store.try_claim_stripe_session("", "job1") is False
