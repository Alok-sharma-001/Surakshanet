import pytest

# Mock PCU Engine logic for testing based on standard formulas
# Assume these are imported from app.engine.pcu
def get_pcu_factor(vehicle_type: str) -> float:
    factors = {
        "car": 1.0,
        "motorcycle": 0.5,
        "bus": 3.0,
        "truck": 2.5
    }
    return factors.get(vehicle_type, 1.0)

def calculate_total_pcu(counts: dict) -> float:
    return sum(count * get_pcu_factor(v_type) for v_type, count in counts.items())

def classify_congestion(total_pcu: float) -> str:
    if total_pcu < 20:
        return "FREE_FLOW"
    elif total_pcu < 50:
        return "STABLE"
    elif total_pcu < 80:
        return "CONGESTED"
    else:
        return "GRIDLOCK"


def test_car_pcu():
    assert get_pcu_factor("car") == 1.0

def test_motorcycle_pcu():
    assert get_pcu_factor("motorcycle") == 0.5

def test_bus_pcu():
    assert get_pcu_factor("bus") == 3.0

def test_mixed_traffic():
    counts = {
        "car": 10,
        "motorcycle": 20,
        "bus": 2
    }
    total = calculate_total_pcu(counts)
    # 10*1.0 + 20*0.5 + 2*3.0 = 10 + 10 + 6 = 26.0
    assert total == 26.0

def test_congestion_classification():
    assert classify_congestion(10) == "FREE_FLOW"
    assert classify_congestion(35) == "STABLE"
    assert classify_congestion(65) == "CONGESTED"
    assert classify_congestion(100) == "GRIDLOCK"

def test_empty_counts():
    assert calculate_total_pcu({}) == 0.0
