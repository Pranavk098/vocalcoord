"""SessionRegistry — replaces the old global. Covers the properties that matter for
P0-1 (no cross-tenant collision) and P0-3/P1-4 (bounded, TTL'd, capacity-limited)."""
import time

import pytest

from backend.sessions import CapacityError, SessionRegistry


def test_register_and_verify():
    reg = SessionRegistry(ttl=3600, max_size=10)
    token = reg.register("stream-1")
    assert reg.verify("stream-1", token) is True


def test_verify_fails_with_wrong_token():
    reg = SessionRegistry(ttl=3600, max_size=10)
    reg.register("stream-1")
    assert reg.verify("stream-1", "wrong-token") is False


def test_verify_fails_for_unregistered_stream():
    reg = SessionRegistry(ttl=3600, max_size=10)
    assert reg.verify("nope", "anything") is False


def test_capacity_limit_enforced():
    reg = SessionRegistry(ttl=3600, max_size=2)
    reg.register("a")
    reg.register("b")
    with pytest.raises(CapacityError):
        reg.register("c")


def test_re_registering_same_stream_does_not_count_against_capacity():
    reg = SessionRegistry(ttl=3600, max_size=1)
    reg.register("a")
    token = reg.register("a")  # re-register, same key — should not raise CapacityError
    assert reg.verify("a", token) is True


def test_ttl_expiry():
    reg = SessionRegistry(ttl=0.05, max_size=10)
    token = reg.register("stream-1")
    time.sleep(0.1)
    assert reg.verify("stream-1", token) is False


def test_two_concurrent_sessions_do_not_collide():
    reg = SessionRegistry(ttl=3600, max_size=10)
    token_a = reg.register("driver-a")
    token_b = reg.register("driver-b")
    assert reg.verify("driver-a", token_a) is True
    assert reg.verify("driver-b", token_b) is True
    assert reg.verify("driver-a", token_b) is False
    assert reg.verify("driver-b", token_a) is False
