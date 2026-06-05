# 🎉 Shielded CSV Party Mix

**Throw a coin party. Leave with privacy.**

A fun, beginner-friendly Streamlit demo that shows how a group of people can pool
their Bitcoin coins, make **one** shared private transaction, and have the
outside world see only a single tiny **64-byte fingerprint** — not who brought
what, how much, or who took home what.

It's a CoinJoin-style mixer reimagined on top of the **Shielded CSV** idea
(private, efficient Client-Side Validation).

> ⚠️ Educational toy. All "cryptography" is faked with random hex so the *ideas*
> stay front and center. No real Bitcoin, no real proofs.

---

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open the URL Streamlit prints (usually <http://localhost:8501>).

## Deploy to Streamlit Community Cloud

This app is ready to deploy for free on [Streamlit Community Cloud](https://share.streamlit.io):

1. Go to <https://share.streamlit.io> and sign in with GitHub.
2. Click **Create app → Deploy a public/private app from GitHub**.
3. Pick this repo (`Schellbach/partymix`), branch `main`, main file `app.py`.
   - Because the repo is **private**, authorize Streamlit to access it when prompted.
4. Click **Deploy**. Streamlit installs `requirements.txt` automatically and
   applies the theme in `.streamlit/config.toml`.

That's it — you'll get a public `*.streamlit.app` URL to share.

## How to use it

1. **Make a party** — in the sidebar, generate 3–8 mock guests, or drag & drop
   your own guest CSVs.
2. **Pick decoys** — more decoy coins = a bigger crowd to hide in.
3. **Click `✨ MIX THE PARTY ✨`** — watch the zk magic + aggregation animation.
4. **Explore the dashboard:**
   - Before vs After transaction graphs (with a privacy toggle)
   - Coin-flow Sankey diagram
   - The "on-chain view" (just the 64-byte fingerprint)
   - The merged Joint Shielded CSV
   - Download buttons for every CSV

## The novel idea, in plain words

Normally **every spend leaves its own trail** on Bitcoin — anyone can follow the
money.

**Shielded CSV** keeps your coin details on *your* computer. The only thing
posted publicly is a tiny 64-byte fingerprint (a *nullifier*).

The **Party Mix** goes one step further: instead of each person making their own
private spend, a **group makes a single shared spend together**. Because all the
inputs and outputs live inside one transaction:

- **Cheaper** — one fingerprint on-chain instead of one per person.
- **More private** — outsiders can't link any input to any output.
- **Stronger in numbers** — decoy coins grow the crowd you blend into.

Shared accounts + a combined fingerprint = strong privacy at a fraction of the
on-chain footprint.

## Project layout

| File | Purpose |
| --- | --- |
| `app.py` | Streamlit UI, visualizations, and an inline README section |
| `mixer.py` | Core simulation: mock data, the party-mix logic, privacy metrics |
| `requirements.txt` | Python dependencies |

## The (fake) data model

Each guest's CSV represents their private *shielded state*:

| column | meaning (plain words) |
| --- | --- |
| `account_id` | the guest's account |
| `coin_commitment` | a sealed envelope standing for a coin |
| `nullifier` | the fingerprint a coin leaves when spent |
| `amount_sats` | the coin's value in satoshis (stays private) |
| `balance_sats` | running balance |
| `proof_hash` | a stand-in for a zero-knowledge proof |
| `timestamp` | when the coin was created |
