import time
import json
import logging
from typing import Optional
from datetime import datetime
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
                
        # 4. Velocity anomaly
        velocity = self.graph.get_velocity(from_acc, 3600, timestamp)
        if velocity > 20:
            findings.append({"pattern": "velocity_anomaly", "details": f"{velocity} txs in last hour."})
            risk_score += 3.0
            
        # 5. Structuring
        if amount > Config.STRUCTURING_THRESHOLD_VND * 0.9 and amount <= Config.STRUCTURING_THRESHOLD_VND:
            findings.append({"pattern": "structuring", "details": f"Amount {amount} near threshold."})
            risk_score += 5.0

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
            
        finding_report = {
            "tx_id": tx_id,
            "account": from_acc,
            "risk_score": min(10.0, risk_score),
            "findings": findings,
            "graph": self.graph.get_account_stats(from_acc),
            "needs_str": risk_score >= Config.MONEY_TRAIL_FREEZE_THRESHOLD,
            "timestamp": timestamp,
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
        payload = {
            "alertType": "MULE_SPLIT",
            "primaryAccountNumber": finding["account"],
            "triggerTransactionId": str(finding["tx_id"]),
            "riskScore": finding["risk_score"],
            "totalAmount": amount,
            "currency": "VND",
            "timeWindowSeconds": Config.MONEY_TRAIL_WINDOW_SECONDS,
            "agentFindingJson": json_text(finding),
            "graphDataJson": json_text(finding["graph"]),
            "involvedAccountsJson": json_text(
                sorted({edge[0] for edge in self.graph.outgoing.get(finding["account"], [])})
            ),
        }
        try:
            created = await request("POST", "/api/aml/alerts", payload)
            finding["alert_id"] = created.get("alertId")
        except Exception as exc:
            logger.error("Failed to create AML alert: %s", exc)

    @staticmethod
    def _timestamp(value) -> float:
        if value is None:
            return time.time()
        if isinstance(value, (int, float)):
            return float(value)
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
