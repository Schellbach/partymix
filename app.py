"""
Shielded CSV Party Mix -- a friendly, interactive demo of private Bitcoin mixing.

Run it with:
    pip install -r requirements.txt
    streamlit run app.py

What this shows (in one sentence):
    Several people throw their coins into one shared "party", the party makes a
    single private transaction, and outsiders only ever see one tiny 64-byte
    fingerprint -- not who brought what, how much, or who took it home.

This is an educational toy. The "cryptography" is faked with random hex so the
ideas stay front-and-center. See README section at the bottom of this file.
"""

import time

import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import mixer

# ---------------------------------------------------------------------------
# Page setup + a little styling
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Shielded CSV Party Mix",
    page_icon="🎉",
    layout="wide",
)

st.markdown(
    """
    <style>
    .big-null {
        font-family: monospace;
        font-size: 0.95rem;
        word-break: break-all;
        background: #0e1117;
        color: #00e0a4;
        padding: 0.75rem 1rem;
        border-radius: 8px;
        border: 1px solid #00e0a4;
    }
    .pill {
        display:inline-block; padding:2px 10px; border-radius:999px;
        background:#262730; color:#fafafa; font-size:0.75rem; margin-right:6px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Simple, jargon-free explanations reused as tooltips throughout the app.
HELP = {
    "nullifier": "A tiny fingerprint a coin leaves when it's spent. It proves the "
    "coin was used without revealing which coin it was.",
    "shielded_state": "Your own private spreadsheet of coins. It lives on your "
    "computer -- the blockchain never sees it.",
    "shared_account": "A temporary shared piggy bank everyone mixes into for the "
    "party, then leaves with fresh coins.",
    "aggregate_nullifier": "ONE 64-byte fingerprint that stands in for the whole "
    "group's transaction. It's all the outside world gets to see.",
    "dummy_coins": "Fake decoy coins added to the mix so the real ones are harder "
    "to pick out -- like extra dancers on the floor.",
    "anonymity_set": "The size of the crowd you blend into. Bigger crowd = harder "
    "to single you out.",
    "privacy_score": "A friendly 0-100 vibe-check of how hidden you are, based on "
    "how big the crowd is.",
}

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "party" not in st.session_state:
    st.session_state.party = {}          # {name: DataFrame}
if "result" not in st.session_state:
    st.session_state.result = None       # MixResult


# ---------------------------------------------------------------------------
# Sidebar -- controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("🎉 Party Controls")
    st.caption("Set up the guest list, then hit the mix button in the main area.")

    st.subheader("1. Generate a mock party")
    num_participants = st.slider(
        "Number of guests", min_value=3, max_value=8, value=4,
        help="How many people bring coins to the party.",
    )
    coins_per_user = st.slider(
        "Coins each guest brings", min_value=1, max_value=5, value=3,
        help="Each coin is one row in that person's private spreadsheet.",
    )
    if st.button("🎲 Generate mock guests", use_container_width=True):
        st.session_state.party = mixer.generate_party(num_participants, coins_per_user)
        st.session_state.result = None
        st.toast("Fresh guests invited!", icon="🎈")

    st.divider()
    st.subheader("2. Or bring your own CSVs")
    uploads = st.file_uploader(
        "Drag & drop guest CSV files",
        type=["csv"],
        accept_multiple_files=True,
        help=HELP["shielded_state"],
    )
    if uploads:
        loaded = {}
        for up in uploads:
            try:
                df = pd.read_csv(up)
                name = up.name.replace(".csv", "")
                loaded[name] = df
            except Exception as exc:  # noqa: BLE001 -- show friendly error in UI
                st.error(f"Couldn't read {up.name}: {exc}")
        if loaded:
            st.session_state.party = loaded
            st.session_state.result = None
            st.success(f"Loaded {len(loaded)} guest file(s).")

    st.divider()
    st.subheader("3. Mix settings")
    num_dummy = st.slider(
        "Decoy coins (extra privacy)", min_value=0, max_value=10, value=2,
        help=HELP["dummy_coins"],
    )

    st.divider()
    st.caption(
        "The party is private. No one knows who brought what. 🕶️"
    )


# ---------------------------------------------------------------------------
# Visualization helpers
# ---------------------------------------------------------------------------
def graph_before(party: dict) -> go.Figure:
    """Each guest's spend is its own line on-chain -- fully linkable."""
    G = nx.DiGraph()
    for name in party:
        G.add_node(f"👤 {name}", kind="user")
        G.add_node(f"🔗 {name}'s tx", kind="tx")
        G.add_edge(f"👤 {name}", f"🔗 {name}'s tx")

    pos = {}
    users = list(party.keys())
    for i, name in enumerate(users):
        y = 1 - (i / max(len(users) - 1, 1))
        pos[f"👤 {name}"] = (0, y)
        pos[f"🔗 {name}'s tx"] = (1, y)
    return _render_network(G, pos, "Before: everyone posts their own transaction (easy to trace)")


def graph_after(result, private_view: bool) -> go.Figure:
    """Everyone funnels through one shared mix -> outputs can't be linked back."""
    G = nx.DiGraph()
    mix_node = "🌀 SHARED MIX"
    G.add_node(mix_node, kind="mix")

    for name in result.participants:
        G.add_node(f"👤 {name}", kind="user")
        G.add_edge(f"👤 {name}", mix_node)

    for i, flow in enumerate(result.flows):
        label = "🪙 ???" if private_view else f"🪙 out {i + 1}"
        G.add_node(label + f"\u200b{i}", kind="out", display=label)
        G.add_edge(mix_node, label + f"\u200b{i}")

    pos = {}
    users = result.participants
    for i, name in enumerate(users):
        y = 1 - (i / max(len(users) - 1, 1))
        pos[f"👤 {name}"] = (0, y)
    pos[mix_node] = (1, 0.5)
    outs = [n for n, d in G.nodes(data=True) if d.get("kind") == "out"]
    for i, n in enumerate(outs):
        y = 1 - (i / max(len(outs) - 1, 1))
        pos[n] = (2, y)

    title = (
        "After: one shared mix, outputs unlinkable (private view 🕶️)"
        if private_view
        else "After: one shared mix (peek view -- outputs shown but still shuffled)"
    )
    return _render_network(G, pos, title)


def _render_network(G: nx.DiGraph, pos: dict, title: str) -> go.Figure:
    """Shared plotly renderer for the before/after node graphs."""
    color_map = {
        "user": "#4c9be8",
        "tx": "#e8714c",
        "mix": "#a64ce8",
        "out": "#00e0a4",
    }

    edge_x, edge_y = [], []
    for a, b in G.edges():
        edge_x += [pos[a][0], pos[b][0], None]
        edge_y += [pos[a][1], pos[b][1], None]

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y, mode="lines",
        line=dict(width=1.2, color="#888"), hoverinfo="none",
    )

    node_x, node_y, text, colors = [], [], [], []
    for n, d in G.nodes(data=True):
        node_x.append(pos[n][0])
        node_y.append(pos[n][1])
        text.append(d.get("display", n))
        colors.append(color_map.get(d.get("kind"), "#cccccc"))

    node_trace = go.Scatter(
        x=node_x, y=node_y, mode="markers+text",
        text=text, textposition="middle right",
        marker=dict(size=22, color=colors, line=dict(width=1, color="#222")),
        hoverinfo="text",
    )

    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        title=title,
        showlegend=False,
        margin=dict(l=10, r=10, t=40, b=10),
        height=420,
        xaxis=dict(visible=False, range=[-0.3, 2.6]),
        yaxis=dict(visible=False, range=[-0.2, 1.2]),
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def sankey_flow(result, private_view: bool) -> go.Figure:
    """Sankey: guests -> shared mix -> output coins (ownership obscured)."""
    participants = result.participants
    labels = [f"👤 {p}" for p in participants] + ["🌀 SHARED MIX"]
    mix_idx = len(participants)

    out_start = len(labels)
    for i, flow in enumerate(result.flows):
        labels.append("🪙 ???" if private_view else f"🪙 coin {i + 1}")

    src, tgt, val = [], [], []
    # Guests -> mix
    p_index = {p: i for i, p in enumerate(participants)}
    for flow in result.flows:
        amt = max(flow["amount_sats"], 1)  # keep tiny/decoy links visible
        src.append(p_index.get(flow["from"], 0))
        tgt.append(mix_idx)
        val.append(amt)
    # Mix -> outputs
    for i, flow in enumerate(result.flows):
        amt = max(flow["amount_sats"], 1)
        src.append(mix_idx)
        tgt.append(out_start + i)
        val.append(amt)

    fig = go.Figure(
        go.Sankey(
            node=dict(label=labels, pad=15, thickness=16,
                      color="#4c9be8", line=dict(color="#222", width=0.5)),
            link=dict(source=src, target=tgt, value=val,
                      color="rgba(166,76,232,0.35)"),
        )
    )
    fig.update_layout(
        title="Coin flow: in through guests, scrambled in the mix, out as fresh coins",
        height=440, margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig


# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------
st.title("🎉 Shielded CSV Party Mix")
st.markdown(
    "**Throw a coin party. Leave with privacy.** Several people pool their coins, "
    "make *one* shared private transaction, and the outside world only ever sees a "
    "single tiny fingerprint -- not who brought what or who took home what."
)

with st.expander("🧠 New here? 30-second explainer (no jargon)"):
    st.markdown(
        """
        - Normally, **every spend leaves its own trail** on Bitcoin. Anyone can
          follow the money.
        - **Shielded CSV** keeps your coin details on *your* computer. The only
          thing posted publicly is a **64-byte fingerprint** (a *nullifier*).
        - The **Party Mix** lets a group combine their spends into **one** shared
          transaction. Result:
            1. **Cheaper** -- one fingerprint instead of many.
            2. **More private** -- outsiders can't tell whose coin is whose.
        - We add optional **decoy coins** to make the crowd even bigger. 🕺
        """
    )

party = st.session_state.party

if not party:
    st.info("👈 Start by generating mock guests or uploading CSVs in the sidebar.")
    st.stop()

# --- Participant overview ---
st.header("👥 Guest list")
st.caption("Each guest brings a private spreadsheet of coins (their *shielded state*).")

cols = st.columns(min(len(party), 4))
for i, (name, df) in enumerate(party.items()):
    col = cols[i % len(cols)]
    with col:
        total = int(df["amount_sats"].sum()) if "amount_sats" in df else 0
        coins = len(df)
        st.metric(f"👤 {name}", mixer.sats_to_btc_str(total), f"{coins} coins")

with st.expander("🔍 Peek at each guest's private spreadsheet"):
    for name, df in party.items():
        st.markdown(f"**👤 {name}** — `{HELP['shielded_state']}`")
        st.dataframe(df, use_container_width=True, hide_index=True)

# --- The mix button ---
st.header("🌀 Start the mix")
st.caption(f"Decoy coins set to **{num_dummy}** (more decoys = bigger crowd to hide in).")

if st.button("✨ MIX THE PARTY ✨", type="primary", use_container_width=True):
    progress = st.progress(0, text="Inviting coins into the shared account...")
    steps = [
        "Opening a shared account 🪩",
        "Collecting everyone's coins 🪙",
        "Shuffling + scrambling ownership 🔀",
        "Sprinkling in decoy coins 🎭",
        "Doing the zk magic + signature aggregation 🪄",
        "Posting ONE 64-byte fingerprint on-chain 📡",
    ]
    for i, label in enumerate(steps):
        time.sleep(0.45)
        progress.progress(int((i + 1) / len(steps) * 100), text=label)
    st.session_state.result = mixer.run_party_mix(party, num_dummy_coins=num_dummy)
    progress.empty()
    st.balloons()
    st.toast("Party mixed! Everyone left private. 🕶️", icon="🎉")

result = st.session_state.result

# ---------------------------------------------------------------------------
# Results dashboard
# ---------------------------------------------------------------------------
if result is not None:
    st.header("📊 Results dashboard")

    m = result.metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("On-chain bytes saved", f"{m['bytes_saved']} B", f"-{m['pct_saved']}%",
              help="One shared fingerprint instead of one per person.")
    c2.metric("Fingerprints on-chain", f"{m['nullifiers_after']}",
              f"was {m['nullifiers_before']}",
              help=HELP["aggregate_nullifier"])
    c3.metric("Crowd size (hide-in)", f"{m['anonymity_set']}",
              help=HELP["anonymity_set"])
    c4.metric("Privacy score", f"{m['privacy_score']}/100",
              help=HELP["privacy_score"])

    st.progress(m["privacy_score"] / 100, text=f"Privacy vibe: {m['privacy_score']}/100")

    tabs = st.tabs([
        "🔗 Before vs After", "🌊 Coin flow", "📡 On-chain view",
        "📁 Joint CSV", "⬇️ Downloads",
    ])

    # --- Tab 1: transaction graphs ---
    with tabs[0]:
        private_view = st.toggle(
            "🕶️ Private view (hide output details)", value=True,
            help="On = what outsiders see. Off = peek behind the curtain.",
        )
        gcol1, gcol2 = st.columns(2)
        with gcol1:
            st.plotly_chart(graph_before(party), use_container_width=True)
            st.caption("😬 Separate transactions are easy to follow coin-by-coin.")
        with gcol2:
            st.plotly_chart(graph_after(result, private_view), use_container_width=True)
            st.caption("😎 One shared mix breaks the link between who paid and who got paid.")

    # --- Tab 2: Sankey ---
    with tabs[1]:
        private_view2 = st.toggle(
            "🕶️ Hide which coin is which", value=True, key="sankey_priv",
        )
        st.plotly_chart(sankey_flow(result, private_view2), use_container_width=True)
        st.caption(
            "Money flows left to right, but it all passes through the same mix -- "
            "so you can't trace a single guest to a single output."
        )

    # --- Tab 3: on-chain view ---
    with tabs[2]:
        st.subheader("What the whole world actually sees")
        st.caption(HELP["aggregate_nullifier"])
        st.markdown(
            f"<div class='big-null'>{result.aggregate_nullifier}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<span class='pill'>64 bytes</span>"
            f"<span class='pill'>{m['anonymity_set']}-way mix</span>"
            f"<span class='pill'>{result.num_dummy_coins} decoys</span>",
            unsafe_allow_html=True,
        )
        st.write("")
        if st.button("📡 Publish to mock Bitcoin", use_container_width=True):
            log = st.empty()
            shown = []
            for line in result.onchain_log:
                shown.append(line)
                log.code("\n".join(shown), language="text")
                time.sleep(0.5)
            st.success("Published! Outsiders learned almost nothing. 🤫")
        st.info(
            f"That's it. No amounts, no names, no balances -- just **64 bytes** "
            f"standing in for **{len(result.participants)} people** and "
            f"**{len(result.flows)} coins**."
        )

    # --- Tab 4: joint CSV ---
    with tabs[3]:
        st.subheader("The merged Joint Shielded CSV")
        st.caption("The shared transaction record. Amounts shown here are private to "
                   "the party; outsiders never see this table.")
        show = result.joint_csv.copy()
        show["amount"] = show["amount_sats"].apply(mixer.sats_to_btc_str)
        st.dataframe(
            show[["shared_account_id", "output_commitment", "amount", "is_decoy", "proof_hash"]],
            use_container_width=True, hide_index=True,
        )

    # --- Tab 5: downloads ---
    with tabs[4]:
        st.subheader("Take the receipts home")
        st.download_button(
            "⬇️ Joint Shielded CSV",
            data=mixer.df_to_csv_bytes(result.joint_csv),
            file_name="joint_shielded_tx.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.write("**Updated guest spreadsheets (old coins spent, fresh coins added):**")
        dl_cols = st.columns(min(len(result.updated_states), 4))
        for i, (name, df) in enumerate(result.updated_states.items()):
            with dl_cols[i % len(dl_cols)]:
                st.download_button(
                    f"⬇️ {name}",
                    data=mixer.df_to_csv_bytes(df),
                    file_name=f"{name}_updated_state.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key=f"dl_{name}",
                )

st.divider()
st.caption(
    "🔐 Educational demo only. The cryptography here is faked with random hex so "
    "the ideas stay simple. Real Shielded CSV does the heavy lifting with actual "
    "zero-knowledge proofs."
)

# ===========================================================================
# README (how to run + the novel idea, in plain words)
# ===========================================================================
"""
SHIELDED CSV PARTY MIX -- README
================================

HOW TO RUN
----------
    pip install -r requirements.txt
    streamlit run app.py

Then open the URL Streamlit prints (usually http://localhost:8501).

WHAT IT DOES
------------
1. Generate (or upload) 3-8 guests, each with a private "shielded state" CSV of
   coins.
2. Click "MIX THE PARTY". The app pools everyone's coins into one shared account,
   shuffles ownership, sprinkles in optional decoy coins, and produces ONE joint
   private transaction.
3. The only thing "posted on-chain" is a single 64-byte fingerprint (nullifier).
4. Explore the dashboard: before/after graphs, a coin-flow Sankey, the on-chain
   view, the merged CSV, and downloads.

THE NOVEL MIXING IDEA (in plain words)
--------------------------------------
Shielded CSV already shrinks each spend down to a tiny 64-byte fingerprint and
keeps all the real details (amounts, owners, balances) on your own computer.

The "Party Mix" takes that one step further: instead of each person making their
own private spend, a GROUP makes a SINGLE shared spend together. Because all the
inputs and outputs live inside one transaction:
  - You only pay for ONE fingerprint on-chain (cheaper for everyone).
  - Outsiders can't link any input to any output (better privacy).
  - Adding decoy coins grows the crowd you blend into.

It's a CoinJoin-style mixer reimagined for Shielded CSV: shared accounts +
combined fingerprints = strong privacy at a fraction of the on-chain footprint.
"""
