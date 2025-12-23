from src.parser import parse_availability
from src.util import hash_json, normalize_slots


def test_hash_normalization_order_independent():
    slots_a = [
        {"date": "2024-10-01", "time": "09:30"},
        {"date": "2024-10-01", "time": "10:15"},
    ]
    slots_b = list(reversed(slots_a))

    payload_a = {"status": "available", "slots": normalize_slots(slots_a), "evidence": {}}
    payload_b = {"status": "available", "slots": normalize_slots(slots_b), "evidence": {}}

    assert hash_json(payload_a) == hash_json(payload_b)


def test_unavailable_text_detection():
    body = "Leider keine freien Termine verfügbar."
    status, slots, evidence = parse_availability(body, "http://example.com", ["keine freien termine"])
    assert status == "unavailable"
    assert slots == []
    assert evidence["found_unavailable_text"] is True


def test_available_with_times():
    body = "Freie Zeiten: 09:30 und 10:15"
    status, slots, evidence = parse_availability(body, "http://example.com", ["keine freien termine"])
    assert status == "available"
    assert evidence["slot_time_count"] == 2
