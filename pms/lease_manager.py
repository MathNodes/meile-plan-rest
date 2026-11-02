#!/usr/bin/env python3
"""
End active plan leases for a list of sentnode addresses, unlink the nodes from
their plans, and purge them from the MySQL bookkeeping tables.

Between every broadcast we poll for the tx to land in a block and reload the
signer account so the sequence number stays in sync (avoids account sequence
mismatch errors).

Usage:
    python purge_node_leases.py --nodes nodes.txt [--dry-run]

nodes.txt: one bech32 sentnode address per line (# comments / blanks ok).
"""

import argparse
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Iterable, Optional

import grpc
import mysql.connector  # pip install mysql-connector-python

import sentinel_protobuf.cosmos.tx.v1beta1.service_pb2 as tx_service_pb2
import sentinel_protobuf.cosmos.tx.v1beta1.service_pb2_grpc as tx_service_pb2_grpc

from sentinel_sdk.sdk import SDKInstance
from sentinel_sdk.types import TxParams


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
)
log = logging.getLogger("purge_node_leases")


# --------------------------------------------------------------------------- #
# Config (env-driven; secrets never on the command line)
# --------------------------------------------------------------------------- #
@dataclass
class Config:
    db_host: str = field(default_factory=lambda: os.getenv("DB_HOST", "127.0.0.1"))
    db_port: int = field(default_factory=lambda: int(os.getenv("DB_PORT", "3306")))
    db_user: str = field(default_factory=lambda: os.getenv("DB_USER", "mathnodes"))
    db_password: str = field(default_factory=lambda: os.getenv("DB_PASSWORD", ""))
    db_name: str = field(default_factory=lambda: os.getenv("DB_NAME", "meile"))

    grpc_addr: str = field(default_factory=lambda: os.getenv("SENTINEL_GRPC_ADDR", "grpc.ungovernable.dev"))
    grpc_port: int = field(default_factory=lambda: int(os.getenv("SENTINEL_GRPC_PORT", "443")))
    grpc_ssl: bool = field(default_factory=lambda: os.getenv("SENTINEL_GRPC_SSL", "true").lower() == "true")

    # Provider secret: mnemonic or hex private key. Signs the tx messages.
    secret: str = field(default_factory=lambda: os.getenv("SENTINEL_SECRET", ""))

    gas: int = field(default_factory=lambda: int(os.getenv("SENTINEL_GAS", "400000")))
    fee_amount: int = field(default_factory=lambda: int(os.getenv("SENTINEL_FEE_AMOUNT", "31415")))
    fee_denom: str = field(default_factory=lambda: os.getenv("SENTINEL_FEE_DENOM", "udvpn"))

    # Confirmation polling
    confirm_timeout: int = field(default_factory=lambda: int(os.getenv("CONFIRM_TIMEOUT", "60")))
    confirm_interval: float = field(default_factory=lambda: float(os.getenv("CONFIRM_INTERVAL", "2")))
    post_confirm_sleep: float = field(default_factory=lambda: float(os.getenv("POST_CONFIRM_SLEEP", "1")))


# --------------------------------------------------------------------------- #
# Chain wrapper: lease + plan modules, with confirmation polling.
# --------------------------------------------------------------------------- #
class Chain:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.sdk = SDKInstance(
            grpcaddr=cfg.grpc_addr,
            grpcport=cfg.grpc_port,
            secret=cfg.secret,
            ssl=cfg.grpc_ssl,
        )
        # Dedicated tx service stub for GetTx polling.
        self._tx_stub = tx_service_pb2_grpc.ServiceStub(self.sdk._channel)

    # ----- helpers -------------------------------------------------------- #
    def _tx_params(self) -> TxParams:
        try:
            return TxParams(
                gas=self.cfg.gas,
                fee_amount=self.cfg.fee_amount,
                denom=self.cfg.fee_denom,
            )
        except TypeError:
            return TxParams()

    @staticmethod
    def _extract(res, *names):
        for n in names:
            if isinstance(res, dict):
                if n in res:
                    return res[n]
            else:
                v = getattr(res, n, None)
                if v is not None:
                    return v
        return None

    def _tx_hash(self, res) -> str:
        return self._extract(res, "txhash", "tx_hash", "hash") or ""

    def _check_broadcast(self, res, label: str) -> str:
        """Validate the initial broadcast (CheckTx) result and return tx hash."""
        code = self._extract(res, "code")
        tx_hash = self._tx_hash(res)
        if code not in (0, None):
            raw = self._extract(res, "raw_log", "log") or ""
            raise RuntimeError(f"{label} broadcast failed (code={code}): {raw}")
        if not tx_hash:
            raise RuntimeError(f"{label} broadcast returned no tx hash: {res}")
        return tx_hash

    def _reload_account(self):
        """Refresh the signer's sequence/number after a committed tx."""
        try:
            self.sdk._client.load_account_data(account=self.sdk._account)
        except Exception as exc:
            log.warning("Account reload failed (will retry on next tx): %s", exc)

    def wait_for_tx(self, tx_hash: str, label: str) -> None:
        """
        Poll the tx service until the tx is included in a block, then verify it
        did not fail on delivery (DeliverTx code). Reload account afterward.
        """
        deadline = time.time() + self.cfg.confirm_timeout
        last_err: Optional[Exception] = None
        while time.time() < deadline:
            try:
                resp = self._tx_stub.GetTx(
                    tx_service_pb2.GetTxRequest(hash=tx_hash)
                )
                tx_resp = resp.tx_response
                if tx_resp and tx_resp.height and int(tx_resp.height) > 0:
                    if tx_resp.code not in (0,):
                        raise RuntimeError(
                            f"{label} tx {tx_hash} failed on-chain "
                            f"(code={tx_resp.code}): {tx_resp.raw_log}"
                        )
                    log.info("%s tx %s confirmed at height %s.",
                             label, tx_hash, tx_resp.height)
                    # Small settle delay then refresh sequence.
                    if self.cfg.post_confirm_sleep > 0:
                        time.sleep(self.cfg.post_confirm_sleep)
                    self._reload_account()
                    return
            except grpc.RpcError as e:
                # tx not indexed yet -> NotFound is expected; keep polling.
                code = e.code() if hasattr(e, "code") else None
                if code != grpc.StatusCode.NOT_FOUND:
                    last_err = e
            except RuntimeError:
                raise
            time.sleep(self.cfg.confirm_interval)

        raise TimeoutError(
            f"{label} tx {tx_hash} not confirmed within "
            f"{self.cfg.confirm_timeout}s"
            + (f" (last error: {last_err})" if last_err else "")
        )

    # ----- queries -------------------------------------------------------- #
    def node_leases(self, node_address: str) -> list:
        """All live leases for a node (any returned lease is active)."""
        leases = self.sdk.lease.QueryNodeLeases(address=node_address)
        return leases or []

    def active_leases_for_plans(self, node_address: str, plan_ids: set) -> list:
        matched = []
        for lease in self.node_leases(node_address):
            lease_plan = getattr(lease, "plan_id", None)
            if lease_plan is None:
                log.debug("Lease id=%s has no plan_id field.",
                          getattr(lease, "id", "?"))
                continue
            if lease_plan in plan_ids:
                matched.append(lease)
        return matched

    # ----- transactions --------------------------------------------------- #
    def end_lease(self, lease_id: int) -> str:
        res = self.sdk.lease.EndLease(
            subscription_id=lease_id,  # named 'subscription_id' but is lease id
            tx_params=self._tx_params(),
        )
        tx_hash = self._check_broadcast(res, "EndLease")
        self.wait_for_tx(tx_hash, "EndLease")
        return tx_hash

    def unlink_node(self, plan_id: int, node_address: str) -> str:
        res = self.sdk.plans.UnlinkNode(
            plan_id,
            node_address,
            self._tx_params(),
        )
        tx_hash = self._check_broadcast(res, "UnlinkNode")
        self.wait_for_tx(tx_hash, "UnlinkNode")
        return tx_hash


# --------------------------------------------------------------------------- #
# Database access
# --------------------------------------------------------------------------- #
class Database:
    def __init__(self, cfg: Config):
        self.conn = mysql.connector.connect(
            host=cfg.db_host,
            port=cfg.db_port,
            user=cfg.db_user,
            password=cfg.db_password,
            database=cfg.db_name,
            autocommit=False,
        )

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass

    def plan_ids_for_node(self, node_address: str) -> set:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT plan_id
            FROM plan_node_subscriptions
            WHERE node_address = %s AND plan_id IS NOT NULL
            """,
            (node_address,),
        )
        ids = {row[0] for row in cur.fetchall()}
        cur.close()
        return ids

    def delete_node(self, node_address: str) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "DELETE FROM plan_node_subscriptions WHERE node_address = %s",
            (node_address,),
        )
        deleted = cur.rowcount
        cur.execute(
            "DELETE FROM plan_nodes WHERE node_address = %s",
            (node_address,),
        )
        deleted += cur.rowcount
        cur.close()
        return deleted

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()


# --------------------------------------------------------------------------- #
# Core
# --------------------------------------------------------------------------- #
def read_nodes(path: str) -> Iterable[str]:
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            yield line


def process_node(node: str, db: Database, chain: Chain, dry_run: bool) -> bool:
    log.info("=== Processing node %s ===", node)

    plan_ids = db.plan_ids_for_node(node)
    if plan_ids:
        log.info("Node %s tracked on plan_id(s): %s", node, sorted(plan_ids))
    else:
        log.warning("No plan_ids recorded for %s in plan_node_subscriptions.",
                    node)

    # 1) End any active leases on tracked plans.
    leases = chain.active_leases_for_plans(node, plan_ids)
    if not leases:
        log.info("No active leases found for %s on tracked plans.", node)
    else:
        for lease in leases:
            lease_id = getattr(lease, "id", None)
            lease_plan = getattr(lease, "plan_id", None)
            log.info("Active lease id=%s on plan_id=%s for %s.",
                     lease_id, lease_plan, node)
            if dry_run:
                log.info("[dry-run] Would EndLease id=%s.", lease_id)
                continue
            try:
                tx = chain.end_lease(lease_id)
                log.info("Ended lease id=%s (tx=%s).", lease_id, tx)
            except Exception as exc:
                log.error("EndLease failed for lease id=%s (%s): %s",
                          lease_id, node, exc)
                return False  # do NOT unlink or delete if lease end failed

    # 2) Unlink the node from every plan it is tracked on.
    for plan_id in sorted(plan_ids):
        if dry_run:
            log.info("[dry-run] Would UnlinkNode(plan_id=%s, node=%s).",
                     plan_id, node)
            continue
        try:
            tx = chain.unlink_node(plan_id, node)
            log.info("Unlinked node %s from plan_id=%s (tx=%s).",
                     node, plan_id, tx)
        except Exception as exc:
            log.error("UnlinkNode failed (plan_id=%s, node=%s): %s",
                      plan_id, node, exc)
            return False  # do NOT delete DB rows if unlink failed

    # 3) DB cleanup — only after chain state is clean.
    if dry_run:
        log.info("[dry-run] Would delete %s from plan_node_subscriptions "
                 "and plan_nodes.", node)
        return True

    try:
        deleted = db.delete_node(node)
        db.commit()
        log.info("Deleted %d row(s) for %s from MySQL.", deleted, node)
    except Exception as exc:
        db.rollback()
        log.error("DB delete failed for %s (rolled back): %s", node, exc)
        return False

    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nodes", required=True,
                        help="File with one sentnode address per line.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report actions without ending leases/deleting.")
    args = parser.parse_args()

    cfg = Config()
    if not cfg.secret:
        log.error("SENTINEL_SECRET (provider mnemonic or hex key) is required.")
        return 2

    chain = Chain(cfg)
    db = Database(cfg)

    failures: list[str] = []
    try:
        for node in read_nodes(args.nodes):
            if not process_node(node, db, chain, args.dry_run):
                failures.append(node)
    finally:
        db.close()

    if failures:
        log.error("Completed with %d failure(s): %s",
                  len(failures), ", ".join(failures))
        return 1

    log.info("All nodes processed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())