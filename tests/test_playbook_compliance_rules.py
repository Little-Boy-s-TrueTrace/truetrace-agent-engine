import pytest
import time
from graph_analyzer import TransactionGraph
from cccd_validator import validate_format
from config import Config

def test_graph_analyzer_edge_cases_and_pruning():
    graph = TransactionGraph()
    now = time.time()
    
    # Add old transaction and fresh transactions
    graph.add_transaction("tx_old", "ACC_SRC", "ACC_TARGET_1", 50000000.0, now - 100)
    graph.add_transaction("tx_new1", "ACC_SRC", "ACC_TARGET_2", 190000000.0, now - 5)
    graph.add_transaction("tx_new2", "ACC_SRC", "ACC_TARGET_3", 190000000.0, now - 2)

    # Prune old transactions beyond 60s
    graph.prune_old(max_age_seconds=60, now=now)
    
    # Check structuring activity within 60s window
    structuring = graph.get_structuring_activity(
        account="ACC_SRC",
        lower_amount=100000000.0,
        upper_amount=200000000.0,
        time_window=60,
        now=now
    )
    
    assert structuring["count"] == 2
    assert structuring["total_amount"] == 380000000.0
    assert "ACC_TARGET_2" in structuring["counterparties"]
    assert "ACC_TARGET_3" in structuring["counterparties"]

def test_rapid_dispersion_boundary_conditions():
    graph = TransactionGraph()
    now = time.time()
    
    mule_acc = "MULE_001"
    # Inflow 1 Billion VND
    graph.add_transaction("in_1", "SOURCE_BANK", mule_acc, 1000000000.0, now - 10)
    
    # 20 distinct outflows of 45 Million VND each (Total 900M VND = 90% ratio)
    for i in range(20):
        graph.add_transaction(f"out_{i}", mule_acc, f"BENEFICIARY_{i}", 45000000.0, now - 5)
        
    rapid_result = graph.get_rapid_movement(
        account=mule_acc,
        now=now,
        window_seconds=60,
        min_inflow=1000000000.0,
        min_targets=20,
        min_ratio=0.80
    )
    
    assert rapid_result is not None
    assert rapid_result["total_in"] == 1000000000.0
    assert rapid_result["total_out"] == 900000000.0
    assert rapid_result["targets"] == 20
    assert rapid_result["movement_ratio"] == 0.9

def test_cccd_checksum_and_format_validation():
    # Valid 12-digit Citizen ID format (001 = Hanoi, 0 = Male 1900s, 99 = 1999)
    valid_cccd = "001099123456"
    res_valid = validate_format(valid_cccd)
    assert res_valid["valid"] is True
    assert res_valid["province"] == "Hà Nội"
    assert res_valid["gender"] == "Male"
    assert res_valid["birth_year"] == 1999
    
    # Invalid length
    invalid_len = "0010991234"
    res_invalid = validate_format(invalid_len)
    assert res_invalid["valid"] is False
    assert "Must be 12 digits" in res_invalid["error"]

    # Non-digit characters
    invalid_char = "001099ABCDEF"
    res_char = validate_format(invalid_char)
    assert res_char["valid"] is False

def test_config_defaults():
    assert Config.MONEY_TRAIL_FREEZE_THRESHOLD == 7.0
    assert Config.MONEY_TRAIL_WINDOW_SECONDS == 60
    assert Config.DEEPFAKE_REVIEW_THRESHOLD == 0.50
    assert Config.DEEPFAKE_REJECT_THRESHOLD == 0.80

def test_config_production_validation_rejection():
    # In non-production mode, validate_runtime passes silently
    Config.ENVIRONMENT = 'demo'
    Config.validate_runtime()
    
    # In production mode without secrets, it raises RuntimeError
    Config.ENVIRONMENT = 'production'
    with pytest.raises(RuntimeError) as exc_info:
        Config.validate_runtime()
    assert "Production configuration rejected" in str(exc_info.value)
    
    # Reset back to demo
    Config.ENVIRONMENT = 'demo'
