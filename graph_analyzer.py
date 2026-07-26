import time
from collections import defaultdict
from typing import List, Dict, Optional, Set

class TransactionGraph:
    def __init__(self):
        # edges[from_acc] = list of (to_acc, amount, timestamp, tx_id)
        self.outgoing = defaultdict(list)
        self.incoming = defaultdict(list)

    def add_transaction(self, tx_id: str, from_acc: str, to_acc: str, amount: float, timestamp: float):
        self.outgoing[from_acc].append((to_acc, amount, timestamp, tx_id))
        self.incoming[to_acc].append((from_acc, amount, timestamp, tx_id))

    def prune_old(self, max_age_seconds: float, now: Optional[float] = None):
        cutoff = (now if now is not None else time.time()) - max_age_seconds
        
        for acc in list(self.outgoing.keys()):
            self.outgoing[acc] = [edge for edge in self.outgoing[acc] if edge[2] >= cutoff]
            if not self.outgoing[acc]:
                del self.outgoing[acc]
                
        for acc in list(self.incoming.keys()):
            self.incoming[acc] = [edge for edge in self.incoming[acc] if edge[2] >= cutoff]
            if not self.incoming[acc]:
                del self.incoming[acc]

    def get_fan_out_candidates(self, min_targets: int, time_window: float, now: Optional[float] = None) -> Dict[str, List[tuple]]:
        cutoff = (now if now is not None else time.time()) - time_window
        candidates = {}
        for acc, edges in self.outgoing.items():
            recent = [e for e in edges if e[2] >= cutoff]
            targets = set(e[0] for e in recent)
            if len(targets) >= min_targets:
                candidates[acc] = recent
        return candidates

    def get_fan_in_candidates(self, min_sources: int, time_window: float, now: Optional[float] = None) -> Dict[str, List[tuple]]:
        cutoff = (now if now is not None else time.time()) - time_window
        candidates = {}
        for acc, edges in self.incoming.items():
            recent = [e for e in edges if e[2] >= cutoff]
            sources = set(e[0] for e in recent)
            if len(sources) >= min_sources:
                candidates[acc] = recent
        return candidates

    def find_cycles(self, max_depth: int = 5) -> List[List[str]]:
        cycles = []
        visited = set()
        
        def dfs(node: str, start_node: str, path: List[str], depth: int):
            if depth > max_depth:
                return
            for edge in self.outgoing.get(node, []):
                neighbor = edge[0]
                if neighbor == start_node and len(path) > 1:
                    cycles.append(path + [neighbor])
                    return
                if neighbor not in path:
                    dfs(neighbor, start_node, path + [neighbor], depth + 1)

        for node in self.outgoing.keys():
            if node not in visited:
                dfs(node, node, [node], 1)
                visited.add(node)
                
        return cycles

    def get_velocity(self, account: str, time_window: float, now: Optional[float] = None) -> int:
        cutoff = (now if now is not None else time.time()) - time_window
        out_recent = [e for e in self.outgoing.get(account, []) if e[2] >= cutoff]
        return len(out_recent)

    def get_account_stats(self, account: str) -> Dict[str, any]:
        total_in = sum(e[1] for e in self.incoming.get(account, []))
        total_out = sum(e[1] for e in self.outgoing.get(account, []))
        tx_count = len(self.incoming.get(account, [])) + len(self.outgoing.get(account, []))
        counterparties = set([e[0] for e in self.incoming.get(account, [])] + [e[0] for e in self.outgoing.get(account, [])])
        
        return {
            "total_in": total_in,
            "total_out": total_out,
            "tx_count": tx_count,
            "unique_counterparties": len(counterparties)
        }

    def get_rapid_movement(
        self,
        account: str,
        now: float,
        window_seconds: float,
        min_inflow: float,
        min_targets: int,
        min_ratio: float,
    ) -> Optional[Dict[str, float]]:
        cutoff = now - window_seconds
        inflows = [edge for edge in self.incoming.get(account, []) if cutoff <= edge[2] <= now]
        outflows = [edge for edge in self.outgoing.get(account, []) if cutoff <= edge[2] <= now]
        total_in = sum(edge[1] for edge in inflows)
        total_out = sum(edge[1] for edge in outflows)
        targets = len({edge[0] for edge in outflows})
        ratio = total_out / total_in if total_in else 0.0
        if total_in >= min_inflow and targets >= min_targets and ratio >= min_ratio:
            return {
                "total_in": total_in,
                "total_out": total_out,
                "targets": targets,
                "movement_ratio": round(ratio, 4),
                "window_seconds": window_seconds,
            }
        return None
