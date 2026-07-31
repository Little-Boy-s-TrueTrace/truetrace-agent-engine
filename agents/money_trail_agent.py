import time
import json
import logging
from typing import Optional
from datetime import datetime, timezone
from graph_analyzer import TransactionGraph
from config import Config
from backend_client import json_text, request

logger = logging.getLogger(__name__)

class MoneyTrailAgent:
    def __init__(self, kafka_producer=None):
        self.graph = TransactionGraph()
        self.kafka_producer = kafka_producer
        
    async def process_transaction(self, tx: dict) -> Optional[dict]:
        tx_id = tx.get('tx_id') or tx.get('id')
        from_acc = tx.get('from_account') or tx.get('sourceAccountNumber')
        to_acc = tx.get('to_account') or tx.get('targetAccountNumber')
        amount = float(tx.get('amount', 0))
        timestamp = self._timestamp(tx.get('timestamp'))
        if not tx_id or not from_acc or not to_acc or amount <= 0:
            raise ValueError("transaction requires id, source, target and positive amount")
        
        # Add to graph
        self.graph.add_transaction(tx_id, from_acc, to_acc, amount, timestamp)
        
        # Prune old
        self.graph.prune_old(Config.MONEY_TRAIL_WINDOW_SECONDS, timestamp)
        
        # Detect patterns
        findings = []
        risk_score = 0.0
        
        # 1. Fan-out
        fan_outs = self.graph.get_fan_out_candidates(
            Config.FAN_OUT_MIN_TARGETS, Config.MONEY_TRAIL_WINDOW_SECONDS, timestamp
        )
        if from_acc in fan_outs:
            findings.append({"pattern": "fan_out", "details": f"Sent to {len(fan_outs[from_acc])} accounts recently."})
            risk_score += 4.0
            
        # 2. Fan-in
        fan_ins = self.graph.get_fan_in_candidates(
            Config.FAN_OUT_MIN_TARGETS, Config.MONEY_TRAIL_WINDOW_SECONDS, timestamp
        )
        if to_acc in fan_ins:
            findings.append({"pattern": "fan_in", "details": f"Received from {len(fan_ins[to_acc])} accounts recently."})
            risk_score += 4.0
            
        # 3. Circular flow
        cycles = self.graph.find_cycles(max_depth=5)
        for cycle in cycles:
            if from_acc in cycle or to_acc in cycle:
                findings.append({"pattern": "circular_flow", "details": f"Cycle detected: {cycle}"})
                risk_score += 6.0
                break
                
        # 4. Velocity anomaly (short window or 1-hour window)
        velocity_window = self.graph.get_velocity(from_acc, Config.MONEY_TRAIL_WINDOW_SECONDS, timestamp)
        velocity_hour = self.graph.get_velocity(from_acc, 3600, timestamp)
        if velocity_hour > 20 or velocity_window >= 2:
            findings.append({
                "pattern": "velocity_anomaly",
                "details": f"{velocity_window} rapid txs in last {Config.MONEY_TRAIL_WINDOW_SECONDS}s, {velocity_hour} in last hour."
            })
            risk_score += 8.0 if velocity_window >= 3 else 3.0
            
        # 5. Repeated structuring: multiple transfers inside the sliding window
        structuring = self.graph.get_structuring_activity(
            from_acc,
            Config.STRUCTURING_THRESHOLD_VND * 0.9,
            Config.STRUCTURING_THRESHOLD_VND,
            Config.MONEY_TRAIL_WINDOW_SECONDS,
            timestamp,
        )
        if structuring["count"] > 0:
            findings.append({"pattern": "structuring", "details": structuring})
            risk_score += 8.0 if structuring["count"] >= 2 else 3.0

        rapid = self.graph.get_rapid_movement(
            from_acc,
            timestamp,
            Config.MONEY_TRAIL_WINDOW_SECONDS,
            Config.RAPID_MOVEMENT_MIN_INFLOW_VND,
            Config.FAN_OUT_MIN_TARGETS,
            Config.RAPID_MOVEMENT_RATIO,
        )
        if rapid:
            findings.append({"pattern": "rapid_mule_dispersion", "details": rapid})
            risk_score += 8.0
            
        if not findings:
            return None
            
        evidence = self._build_evidence(from_acc)
        finding_report = {
            "tx_id": tx_id,
            "trigger_transaction_id": str(tx_id),
            "account": from_acc,
            "risk_score": min(10.0, risk_score),
            "findings": findings,
            "graph": self.graph.get_account_stats(from_acc),
            "alert_type": self._alert_type(findings),
            "involved_accounts": evidence["involved_accounts"],
            "transaction_chain": evidence["transaction_chain"],
            "graph_data": evidence["graph_data"],
            "total_amount": evidence["total_amount"],
            "currency": "VND",
            "time_window_seconds": Config.MONEY_TRAIL_WINDOW_SECONDS,
            "needs_str": risk_score >= Config.MONEY_TRAIL_FREEZE_THRESHOLD,
            "timestamp": self._iso_timestamp(timestamp),
        }
        
        if risk_score >= Config.MONEY_TRAIL_FREEZE_THRESHOLD:
            await self._freeze_account(from_acc)
            await self._create_alert(finding_report, amount)
            
        if self.kafka_producer:
            try:
                await self.kafka_producer.send_and_wait(
                    Config.TOPIC_FINDINGS_MONEY_TRAIL,
                    json.dumps(finding_report).encode('utf-8')
                )
                if finding_report["needs_str"]:
                    await self.kafka_producer.send_and_wait(
                        Config.TOPIC_ALERTS,
                        json.dumps(finding_report).encode("utf-8"),
                    )
            except Exception as e:
                logger.error(f"Failed to publish money trail finding: {e}")
                
        return finding_report

    async def _freeze_account(self, account: str):
        logger.warning(f"Risk score exceeded threshold! Freezing account {account}...")
        try:
            await request("POST", f"/api/aml/freeze/{account}")
        except Exception as e:
            logger.error(f"Error freezing account {account}: {e}")

    async def _create_alert(self, finding: dict, amount: float) -> None:
        evidence = self._build_evidence(finding["account"])
        rapid = next(
            (
                item.get("details", {})
                for item in finding.get("findings", [])
                if item.get("pattern") == "rapid_mule_dispersion"
            ),
            {},
        )
        suspicious_amount = max(
            float(amount),
            float(finding.get("total_amount", 0)),
            float(rapid.get("total_in", 0)),
            float(rapid.get("total_out", 0)),
        )
        payload = {
            "alertType": finding.get("alert_type") or self._alert_type(finding["findings"]),
            "primaryAccountNumber": finding["account"],
            "triggerTransactionId": str(finding["tx_id"]),
            "riskScore": finding["risk_score"],
            "totalAmount": suspicious_amount,
            "currency": "VND",
            "timeWindowSeconds": Config.MONEY_TRAIL_WINDOW_SECONDS,
            "agentFindingJson": json_text(finding),
            "graphDataJson": json_text(finding.get("graph_data") or evidence["graph_data"]),
            "involvedAccountsJson": json_text(
                finding.get("involved_accounts") or evidence["involved_accounts"]
            ),
            "transactionChainJson": json_text(
                finding.get("transaction_chain") or evidence["transaction_chain"]
            ),
        }
        try:
            created = await request("POST", "/api/aml/alerts", payload)
            finding["alert_id"] = created.get("alertId")
            finding["alert_db_id"] = created.get("id")
        except Exception as exc:
            logger.error("Failed to create AML alert: %s", exc)

    def _build_evidence(self, account: str) -> dict:
        chain_by_id = {}
        for source, amount, timestamp, tx_id in self.graph.incoming.get(account, []):
            chain_by_id[str(tx_id)] = {
                "txId": str(tx_id),
                "from": source,
                "to": account,
                "amount": amount,
                "timestamp": self._iso_timestamp(timestamp),
                "channel": "bank_transfer",
            }
        for target, amount, timestamp, tx_id in self.graph.outgoing.get(account, []):
            chain_by_id[str(tx_id)] = {
                "txId": str(tx_id),
                "from": account,
                "to": target,
                "amount": amount,
                "timestamp": self._iso_timestamp(timestamp),
                "channel": "bank_transfer",
            }
        transaction_chain = sorted(
            chain_by_id.values(), key=lambda item: item["timestamp"]
        )

        account_totals = {}
        for item in transaction_chain:
            source = item["from"]
            target = item["to"]
            account_totals.setdefault(source, {"in": 0.0, "out": 0.0})
            account_totals.setdefault(target, {"in": 0.0, "out": 0.0})
            account_totals[source]["out"] += float(item["amount"])
            account_totals[target]["in"] += float(item["amount"])

        involved_accounts = []
        for account_number, totals in sorted(account_totals.items()):
            if totals["in"] > 0 and totals["out"] > 0:
                role = "INTERMEDIARY"
            elif totals["out"] > 0:
                role = "SOURCE"
            else:
                role = "DESTINATION"
            involved_accounts.append(
                {
                    "accountNumber": account_number,
                    "role": role,
                    "totalInflow": totals["in"],
                    "totalOutflow": totals["out"],
                }
            )
        graph_data = {
            "nodes": [
                {
                    "id": item["accountNumber"],
                    "label": item["accountNumber"],
                    "type": item["role"].lower(),
                    "riskLevel": "high" if item["accountNumber"] == account else "medium",
                }
                for item in involved_accounts
            ],
            "edges": [
                {
                    "source": item["from"],
                    "target": item["to"],
                    "amount": item["amount"],
                    "timestamp": item["timestamp"],
                }
                for item in transaction_chain
            ],
        }
        return {
            "involved_accounts": involved_accounts,
            "transaction_chain": transaction_chain,
            "graph_data": graph_data,
            "total_amount": max(
                account_totals.get(account, {}).get("in", 0.0),
                account_totals.get(account, {}).get("out", 0.0),
            ),
        }

    @staticmethod
    def _alert_type(findings: list[dict]) -> str:
        patterns = {item.get("pattern") for item in findings}
        for pattern, alert_type in (
            ("rapid_mule_dispersion", "RAPID_MOVEMENT"),
            ("circular_flow", "CIRCULAR_FLOW"),
            ("structuring", "STRUCTURING"),
            ("fan_out", "MULE_SPLIT"),
            ("fan_in", "FAN_IN"),
            ("velocity_anomaly", "VELOCITY_ANOMALY"),
        ):
            if pattern in patterns:
                return alert_type
        return "MULE_SPLIT"

    @staticmethod
    def _iso_timestamp(value: float) -> str:
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _timestamp(value) -> float:
        if value is None:
            return time.time()
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, (list, tuple)):
            if len(value) < 3:
                raise ValueError("timestamp array requires at least year, month and day")
            parts = [int(part) for part in value]
            year, month, day = parts[:3]
            hour = parts[3] if len(parts) > 3 else 0
            minute = parts[4] if len(parts) > 4 else 0
            second = parts[5] if len(parts) > 5 else 0
            # Jackson represents LocalDateTime as
            # [year, month, day, hour, minute, second, nanoseconds].
            microsecond = parts[6] // 1000 if len(parts) > 6 else 0
            return datetime(
                year, month, day, hour, minute, second, microsecond
            ).timestamp()
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
