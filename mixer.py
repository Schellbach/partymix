"""
Shielded CSV Party Mix -- core simulation logic.

This module contains all the "pretend cryptography" and bookkeeping for the
demo. Nothing here is real Bitcoin code: we use random hex strings to stand in
for hashes, nullifiers and proofs so the focus stays on the *idea*, not the math.

Big picture (in plain words):
  - A "nullifier" is a tiny fingerprint a coin leaves behind when it is spent.
    It proves "this coin was used" without revealing which coin it was.
  - In Shielded CSV, the only thing posted on-chain per spend is a 64-byte
    nullifier. Everything else (amounts, owners, balances) stays on people's
    own computers.
  - The "Party Mix" lets several people combine their spends into ONE joint
    transaction. That means ONE nullifier on-chain instead of many, and nobody
    on the outside can tell whose coin went where.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import pandas as pd

# A nullifier in Shielded CSV is 64 bytes. We render it as hex (2 chars/byte).
NULLIFIER_BYTES = 64
HEX_CHARS_PER_BYTE = 2

# Friendly party-goer names so the demo reads like real people, not user_001.
PARTYGOER_NAMES = [
    "Satoshi", "Hodlina", "Nakamoto", "Zappy", "Lightning Lou", "Cold Storage Carol",
    "Mixer Mike", "Private Pat", "Anon Annie", "Block Bob", "Nullifier Nina", "Coinjoin Cody",
]

# Columns that make up one person's private "shielded state" CSV.
USER_COLUMNS = [
    "account_id",
    "coin_commitment",
    "nullifier",
    "amount_sats",
    "balance_sats",
    "proof_hash",
    "timestamp",
]


def random_hex(num_bytes: int) -> str:
    """Return a fake hex string of the given byte length (2 hex chars per byte)."""
    return "".join(random.choice("0123456789abcdef") for _ in range(num_bytes * HEX_CHARS_PER_BYTE))


def short_hex(value: str, head: int = 6, tail: int = 4) -> str:
    """Shorten a long hex string for display, e.g. 'a1b2c3...9f0e'."""
    if len(value) <= head + tail + 3:
        return value
    return f"{value[:head]}...{value[-tail:]}"


def make_aggregate_nullifier() -> str:
    """The single 64-byte nullifier that represents the whole joint transaction."""
    return random_hex(NULLIFIER_BYTES)


# ---------------------------------------------------------------------------
# Mock data generation
# ---------------------------------------------------------------------------

def generate_participant_state(name: str, num_coins: int = 3, seed: int | None = None) -> pd.DataFrame:
    """Build one participant's private shielded-state CSV as a DataFrame.

    Each row is a coin the person currently owns, with the fake crypto fields
    that Shielded CSV would track locally.
    """
    if seed is not None:
        random.seed(seed)

    account_id = "acct_" + random_hex(8)
    base_time = datetime.utcnow() - timedelta(days=random.randint(1, 30))

    rows = []
    running_balance = 0
    for i in range(num_coins):
        # Plausible spendable amounts: 10k sats (~tiny) up to 0.05 BTC.
        amount = random.randint(10_000, 5_000_000)
        running_balance += amount
        rows.append(
            {
                "account_id": account_id,
                "coin_commitment": "cc_" + random_hex(32),
                "nullifier": random_hex(NULLIFIER_BYTES // 2),  # 32-byte per-coin tag
                "amount_sats": amount,
                "balance_sats": running_balance,
                "proof_hash": "zk_" + random_hex(16),
                "timestamp": (base_time + timedelta(minutes=i * 7)).isoformat(timespec="seconds"),
            }
        )

    df = pd.DataFrame(rows, columns=USER_COLUMNS)
    df.attrs["owner"] = name
    return df


def generate_party(num_participants: int = 4, coins_per_user: int = 3) -> dict[str, pd.DataFrame]:
    """Create a whole party of mock participants -> {name: state DataFrame}."""
    names = random.sample(PARTYGOER_NAMES, k=min(num_participants, len(PARTYGOER_NAMES)))
    # If they asked for more people than we have names, top up with numbered guests.
    while len(names) < num_participants:
        names.append(f"Guest {len(names) + 1}")

    party = {}
    for name in names:
        party[name] = generate_participant_state(name, coins_per_user)
    return party


# ---------------------------------------------------------------------------
# The Party Mix itself
# ---------------------------------------------------------------------------

@dataclass
class MixResult:
    """Everything produced by one run of the Party Mix, ready for the UI."""

    shared_account_id: str
    aggregate_nullifier: str
    joint_csv: pd.DataFrame
    updated_states: dict[str, pd.DataFrame]
    flows: list[dict] = field(default_factory=list)        # input -> output coin movements
    metrics: dict = field(default_factory=dict)
    participants: list[str] = field(default_factory=list)
    num_dummy_coins: int = 0
    onchain_log: list[str] = field(default_factory=list)


def _total_input_amount(party: dict[str, pd.DataFrame]) -> int:
    return int(sum(df["amount_sats"].sum() for df in party.values()))


def run_party_mix(party: dict[str, pd.DataFrame], num_dummy_coins: int = 0) -> MixResult:
    """Simulate pooling everyone's coins and producing ONE joint shielded tx.

    Steps (all faked, but mirroring the real flow):
      1. Open a shared account everyone temporarily mixes into.
      2. Gather each person's input coins (their old nullifiers get "spent").
      3. Shuffle and re-split the total value into fresh, unlinkable output coins.
      4. Add optional decoy / dummy coins to grow the crowd you hide in.
      5. Aggregate every input signature into ONE 64-byte nullifier on-chain.
    """
    participants = list(party.keys())
    shared_account_id = "mix_" + random_hex(8)
    aggregate_nullifier = make_aggregate_nullifier()

    total_input = _total_input_amount(party)

    # --- Build the list of input coins (what each person brought) ---
    input_coins = []
    for name, df in party.items():
        for _, row in df.iterrows():
            input_coins.append(
                {
                    "owner": name,
                    "amount_sats": int(row["amount_sats"]),
                    "old_nullifier": row["nullifier"],
                    "old_commitment": row["coin_commitment"],
                }
            )

    num_real_inputs = len(input_coins)

    # --- Build the output coins (fresh, shuffled, ownership hidden) ---
    # We keep the number of outputs equal to inputs + dummies so amounts look uniform.
    num_outputs = num_real_inputs + num_dummy_coins

    # Split the pooled value into roughly even chunks so individual amounts blur.
    even_chunk = total_input // num_real_inputs if num_real_inputs else 0
    output_amounts = [even_chunk] * num_real_inputs
    # Push any rounding remainder into the first output so totals stay exact.
    if num_real_inputs:
        output_amounts[0] += total_input - sum(output_amounts)
    # Dummy coins carry 0 real value but look identical on the books.
    output_amounts += [0] * num_dummy_coins

    output_coins = []
    for i in range(num_outputs):
        output_coins.append(
            {
                "coin_commitment": "cc_" + random_hex(32),
                "amount_sats": output_amounts[i],
                "proof_hash": "zk_" + random_hex(16),
                "is_dummy": i >= num_real_inputs,
            }
        )

    # --- Secret ownership map: who really gets which output (hidden on-chain) ---
    # Real outputs are assigned back to owners by shuffling, so the public can't
    # link an input owner to an output coin.
    owners_cycle = [c["owner"] for c in input_coins]
    random.shuffle(owners_cycle)

    flows = []
    for i, out in enumerate(output_coins):
        if out["is_dummy"]:
            true_owner = "(decoy)"
            src_owner = random.choice(participants)  # decoys appear to come from someone
        else:
            true_owner = owners_cycle[i]
            src_owner = input_coins[i]["owner"]
        flows.append(
            {
                "from": src_owner,
                "to_commitment": out["coin_commitment"],
                "true_owner": true_owner,
                "amount_sats": out["amount_sats"],
                "is_dummy": out["is_dummy"],
            }
        )

    # --- Joint shielded CSV (the merged transaction record) ---
    joint_rows = []
    timestamp = datetime.utcnow().isoformat(timespec="seconds")
    for out in output_coins:
        joint_rows.append(
            {
                "shared_account_id": shared_account_id,
                "output_commitment": out["coin_commitment"],
                "amount_sats": out["amount_sats"],
                "proof_hash": out["proof_hash"],
                "aggregate_nullifier": aggregate_nullifier,
                "is_decoy": out["is_dummy"],
                "timestamp": timestamp,
            }
        )
    joint_csv = pd.DataFrame(joint_rows)

    # --- Updated per-user states (old coins spent, new coin minted) ---
    updated_states = {}
    real_index = 0
    for name, df in party.items():
        new_df = df.copy()
        new_df["status"] = "spent (mixed)"  # old coins are now consumed
        # Give each person one fresh post-mix coin commitment they can claim.
        claim = {
            "account_id": df["account_id"].iloc[0],
            "coin_commitment": "cc_" + random_hex(32),
            "nullifier": "(hidden in joint tx)",
            "amount_sats": even_chunk,
            "balance_sats": even_chunk,
            "proof_hash": "zk_" + random_hex(16),
            "timestamp": timestamp,
            "status": "fresh (post-mix)",
        }
        new_df = pd.concat([new_df, pd.DataFrame([claim])], ignore_index=True)
        updated_states[name] = new_df
        real_index += 1

    # --- Privacy metrics ---
    metrics = compute_metrics(
        num_participants=len(participants),
        num_real_inputs=num_real_inputs,
        num_dummy_coins=num_dummy_coins,
    )

    onchain_log = [
        f"[mock-chain] Broadcasting joint Shielded CSV transaction...",
        f"[mock-chain] Posting ONE 64-byte nullifier: {aggregate_nullifier}",
        f"[mock-chain] Confirmed. Outsiders see {NULLIFIER_BYTES} bytes and nothing else.",
    ]

    return MixResult(
        shared_account_id=shared_account_id,
        aggregate_nullifier=aggregate_nullifier,
        joint_csv=joint_csv,
        updated_states=updated_states,
        flows=flows,
        metrics=metrics,
        participants=participants,
        num_dummy_coins=num_dummy_coins,
        onchain_log=onchain_log,
    )


def compute_metrics(num_participants: int, num_real_inputs: int, num_dummy_coins: int) -> dict:
    """Turn the mix into easy-to-grok privacy numbers.

    - Bytes saved: normally each spender posts their own 64-byte nullifier.
      Joined together they post just one.
    - Anonymity set: how big the crowd is that you hide in (people + decoys).
    - Privacy score: a friendly 0-100 number derived from the crowd size.
    """
    # Without the party: one nullifier per participant. With it: just one.
    bytes_before = num_participants * NULLIFIER_BYTES
    bytes_after = NULLIFIER_BYTES
    bytes_saved = max(bytes_before - bytes_after, 0)
    pct_saved = round((bytes_saved / bytes_before) * 100, 1) if bytes_before else 0.0

    anonymity_set = num_participants + num_dummy_coins
    # Entropy in bits = log2(crowd size). 1 person = 0 bits (no privacy).
    entropy_bits = round(math.log2(anonymity_set), 2) if anonymity_set > 1 else 0.0
    # Map entropy onto a 0-100 "vibe" score; ~6 bits (64-way) feels great.
    privacy_score = min(100, round((entropy_bits / 6.0) * 100))

    nullifiers_before = num_participants
    nullifiers_after = 1

    return {
        "bytes_before": bytes_before,
        "bytes_after": bytes_after,
        "bytes_saved": bytes_saved,
        "pct_saved": pct_saved,
        "anonymity_set": anonymity_set,
        "entropy_bits": entropy_bits,
        "privacy_score": privacy_score,
        "nullifiers_before": nullifiers_before,
        "nullifiers_after": nullifiers_after,
        "num_dummy_coins": num_dummy_coins,
    }


def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Encode a DataFrame as CSV bytes for Streamlit download buttons."""
    return df.to_csv(index=False).encode("utf-8")


def sats_to_btc_str(sats: int) -> str:
    """Pretty-print satoshis as BTC, e.g. 12_500_000 -> '0.12500000 BTC'."""
    return f"{sats / 100_000_000:.8f} BTC"
