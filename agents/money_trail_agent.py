import time
import json
import logging
from typing import Optional
from graph_analyzer import TransactionGraph
from config import Config
import aiohttp

logger = logging.getLogger(__name__)

class MoneyTrailAgent:
    def __init__(self, kafka_producer=None):
        self.graph = TransactionGraph()
        self.kafka_producer = kafka_producer
        
    async def process_transaction(self, tx: dict) -> Optional[dict]:
        tx_id = tx.get('tx_id')
        from_acc = tx.get('from_account')
        to_acc = tx.get('to_account')
        amount = float(tx.get('amount', 0))
        timestamp = tx.get('timestamp', time.time())
        
        # Add to graph
        self.graph.add_transaction(tx_id, from_acc, to_acc, amount, timestamp)
        
        # Prune old
        self.graph.prune_old(Config.MONEY_TRAIL_WINDOW_SECONDS)
        
        # Detect patterns
        findings = []
        risk_score = 0.0
        
        # 1. Fan-out
        fan_outs = self.graph.get_fan_out_candidates(Config.FAN_OUT_MIN_TARGETS, Config.MONEY_TRAIL_WINDOW_SECONDS)
        if from_acc in fan_outs:
            findings.append({"pattern": "fan_out", "details": f"Sent to {len(fan_outs[from_acc])} accounts recently."})
            risk_score += 4.0
            
        # 2. Fan-in
        fan_ins = self.graph.get_fan_in_candidates(Config.FAN_OUT_MIN_TARGETS, Config.MONEY_TRAIL_WINDOW_SECONDS)
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
        velocity = self.graph.get_velocity(from_acc, 3600)
        if velocity > 20:
            findings.append({"pattern": "velocity_anomaly", "details": f"{velocity} txs in last hour."})
            risk_score += 3.0
            
        # 5. Structuring
        if amount > Config.STRUCTURING_THRESHOLD_VND * 0.9 and amount <= Config.STRUCTURING_THRESHOLD_VND:
            findings.append({"pattern": "structuring", "details": f"Amount {amount} near threshold."})
            risk_score += 5.0
            
        if not findings:
            return None
            
        finding_report = {
            "tx_id": tx_id,
            "account": from_acc,
            "risk_score": risk_score,
            "findings": findings,
            "timestamp": time.time()
        }
        
        if risk_score > Config.MONEY_TRAIL_FREEZE_THRESHOLD:
            await self._freeze_account(from_acc)
            
        if self.kafka_producer:
            try:
                await self.kafka_producer.send_and_wait(
                    Config.TOPIC_FINDINGS_MONEY_TRAIL,
                    json.dumps(finding_report).encode('utf-8')
                )
            except Exception as e:
                logger.error(f"Failed to publish money trail finding: {e}")
                
        return finding_report

    async def _freeze_account(self, account: str):
        logger.warning(f"Risk score exceeded threshold! Freezing account {account}...")
        url = f"{Config.BACKEND_URL}/api/aml/freeze/{account}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url) as resp:
                    logger.info(f"Freeze account {account} response: {resp.status}")
        except Exception as e:
            logger.error(f"Error freezing account {account}: {e}")
