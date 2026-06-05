# Roadmap: from demo to real coins

This project is an **educational simulation**. Nullifiers, commitments, and
proofs are random text, and it touches no real money. This document is an honest
look at what it would take to turn the idea into something usable with real
Bitcoin.

> TL;DR: the gap is large. The demo shows the *shape* of the workflow; almost
> everything that actually protects money is currently faked. A real version is
> a multi-person, 12+ month effort and depends on the Shielded CSV protocol
> itself maturing.

## 1. Real cryptography (the bulk of the work)

Today these are `random hex`. Real versions are needed:

- **Coin commitments** — bind *amount + owner + secret blinding factor* so
  amounts stay hidden but can't be forged.
- **Nullifiers** — derived deterministically from each coin's secret so a coin
  can't be spent twice, while the link back to the coin stays hidden.
- **Nullifier accumulator** — a real Merkle tree (or RSA accumulator) of spent
  nullifiers, with membership / non-membership proofs.
- **Zero-knowledge proofs** — the hard core. ZK circuits for the Shielded CSV
  state machine (balance conserved, signatures valid, nullifier fresh) on a real
  proving system (Groth16/PLONK/STARKs, or folding like Nova for the recursive
  PCD part). Writing, optimizing, and **auditing** these is specialist work.
- **Real signature aggregation** — actual Schnorr/BLS half-aggregation.

## 2. The protocol must exist in production

Shielded CSV is a **research proposal**, not a deployed Bitcoin feature. A real
version needs:

- An agreed-upon **spec + reference implementation**.
- A **publication / anchoring layer** for the 64-byte nullifiers (Bitcoin L1
  commitment, a federation, or a data-availability layer).
- A **peg-in / peg-out** so BTC can enter and leave the shielded pool — either
  covenant opcodes Bitcoin doesn't have yet (e.g. CTV/CSFS) or a federation /
  bridge, which adds a trust assumption that must be designed carefully.

## 3. Real multi-party mixing coordination

The demo's "mix" is one function call. A real CoinJoin needs:

- A **coordination protocol** (e.g. WabiSabi-style) with registration → signing
  → broadcast rounds, where the coordinator **cannot** deanonymize or steal.
- **Anti-Sybil / anti-DoS** — fake participants secretly run by one party shrink
  the real anonymity set toward 1.
- **Amount handling** — unequal amounts leak identity; use equal denominations
  or credential-based amount hiding.

## 4. Safety properties that must be proven

- **No theft**: no one can withdraw more than they deposited (enforced in ZK).
- **No double-spend / replay**, **Bitcoin reorg handling**, state consistency.
- **Metadata privacy**: network anonymity (Tor/Dandelion), timing, and change
  outputs can unmask users even with perfect crypto.

## 5. Wallet-grade engineering (Streamlit has to go)

- A real **wallet**: secure key management (seed phrases, hardware wallets),
  encrypted local state, and **backup & recovery** (today, losing your local CSV
  means losing your coins), plus resync/rescan.
- A heavy **prover** and real persistence/networking. A single-session Streamlit
  server is a demo tool, not a wallet.

## 6. Process & non-technical

- **Signet/testnet first**, then mainnet with tiny amounts.
- **Independent security audits** of circuits and code, plus a bug bounty.
- **Legal/regulatory reality**: mixers attract heavy scrutiny (AML, sanctions).
  This is a serious consideration before touching real money.

## Suggested path

1. Implement the crypto for real **on testnet** (commitments, nullifiers,
   accumulator, ZK circuits) — replacing `mixer.py` with an actual library.
2. Build the **coordination protocol** with anti-Sybil/DoS.
3. Solve **peg-in/peg-out** and the publication layer (likely a federation
   first).
4. Wrap it in a **real wallet** with key management and recovery.
5. **Audit → Signet → small-value mainnet → scale.**
