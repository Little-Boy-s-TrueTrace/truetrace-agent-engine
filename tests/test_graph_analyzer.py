from graph_analyzer import TransactionGraph


def test_detects_billion_vnd_rapid_dispersion_to_twenty_accounts():
    graph = TransactionGraph()
    now = 1_800_000_000.0
    graph.add_transaction("in-1", "origin", "mule", 1_000_000_000, now)
    for index in range(20):
        graph.add_transaction(
            f"out-{index}",
            "mule",
            f"beneficiary-{index}",
            45_000_000,
            now + index + 1,
        )

    result = graph.get_rapid_movement(
        "mule",
        now + 30,
        window_seconds=60,
        min_inflow=1_000_000_000,
        min_targets=20,
        min_ratio=0.8,
    )

    assert result is not None
    assert result["targets"] == 20
    assert result["total_in"] == 1_000_000_000
    assert result["total_out"] == 900_000_000
    assert result["movement_ratio"] == 0.9


def test_does_not_flag_normal_fan_out_below_target_count():
    graph = TransactionGraph()
    now = 1_800_000_000.0
    graph.add_transaction("in-1", "origin", "customer", 1_000_000_000, now)
    for index in range(3):
        graph.add_transaction(
            f"out-{index}", "customer", f"payee-{index}", 100_000_000, now + index
        )

    assert graph.get_rapid_movement(
        "customer", now + 10, 60, 1_000_000_000, 20, 0.8
    ) is None
