from modules import realtime_stream_queue as rsq


class _FakeRedis:
    def __init__(self):
        self.messages = []
        self.pending = {}
        self.deleted = []
        self.group_created = False

    def xgroup_create(self, name, groupname, id, mkstream):
        if self.group_created:
            raise Exception("BUSYGROUP Consumer Group name already exists")
        self.group_created = True
        return True

    def xadd(self, name, fields, maxlen=None, approximate=None):
        msg_id = f"{len(self.messages) + 1}-0"
        self.messages.append((msg_id, dict(fields)))
        return msg_id

    def xreadgroup(self, groupname, consumername, streams, count, block):
        # Move one message to pending and return it.
        if not self.messages:
            return []
        msg = self.messages.pop(0)
        self.pending[msg[0]] = msg[1]
        return [("realtime_ingestion_stream", [msg])]

    def xautoclaim(self, name, groupname, consumername, min_idle_time, start_id, count):
        # Return one pending message if present.
        if not self.pending:
            return ("0-0", [])
        msg_id, fields = next(iter(self.pending.items()))
        return ("0-0", [(msg_id, fields)])

    def xack(self, stream_name, group_name, message_id):
        self.pending.pop(message_id, None)
        return 1

    def xdel(self, stream_name, message_id):
        self.deleted.append(message_id)
        return 1

    def xinfo_groups(self, stream_name):
        return [{"name": "realtime_workers", "pending": len(self.pending), "consumers": 1}]


def test_publish_dequeue_ack_flow(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(rsq, "REALTIME_USE_REDIS_STREAMS", True)
    monkeypatch.setattr(rsq, "get_redis_client", lambda: fake)

    msg_id = rsq.publish_realtime_job(
        job_id="job-1",
        session_id="session-1",
        twin_id="twin-1",
        force=True,
        reason="commit",
    )
    assert msg_id is not None

    job = rsq.dequeue_realtime_stream_job("consumer-1")
    assert job is not None
    assert job["job_id"] == "job-1"
    assert job["job_type"] == "realtime_ingestion"
    assert job["metadata"]["session_id"] == "session-1"
    assert job["stream_message_id"] == msg_id

    acked = rsq.ack_realtime_stream_message(job["stream_message_id"])
    assert acked is True


def test_metrics_when_unavailable(monkeypatch):
    monkeypatch.setattr(rsq, "REALTIME_USE_REDIS_STREAMS", True)
    monkeypatch.setattr(rsq, "get_redis_client", lambda: None)
    metrics = rsq.get_realtime_stream_metrics()
    assert metrics["enabled"] is True
    assert metrics["available"] is False


def test_metrics_with_fake_redis(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(rsq, "REALTIME_USE_REDIS_STREAMS", True)
    monkeypatch.setattr(rsq, "get_redis_client", lambda: fake)

    rsq.publish_realtime_job(
        job_id="job-2",
        session_id="session-2",
        twin_id="twin-1",
        force=False,
        reason="threshold",
    )
    _ = rsq.dequeue_realtime_stream_job("consumer-1")
    metrics = rsq.get_realtime_stream_metrics()
    assert metrics["available"] is True
    assert metrics["pending"] is not None
    assert metrics["consumers"] == 1

