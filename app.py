"""
Shielded CSV Party Mix -- a friendly, interactive demo of private Bitcoin mixing.

Run it with:
    pip install -r requirements.txt
    streamlit run app.py

The idea in one sentence:
    A group of people make ONE shared payment together, so the outside world
    only ever sees a single tiny code -- not who paid, how much, or who got paid.

This is an educational toy. The "cryptography" is faked with random text so the
ideas stay front-and-center. See the README section at the bottom of this file.
"""

import time

import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import mixer

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Shielded CSV Party Mix",
    page_icon="🪩",
    layout="wide",
)

# Brand palette -- one fun accent (teal), one playful secondary (violet),
# one warm "watch out" color (coral) for the non-private "before" state.
TEAL = "#00e0a4"
VIOLET = "#8b5cff"
CORAL = "#ff6b6b"
BLUE = "#4c9be8"
INK = "#0e1117"

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;500;600&display=swap');

    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
    h1, h2, h3, h4 {{ font-family: 'Space Grotesk', sans-serif; letter-spacing: -0.01em; }}

    /* Hero banner */
    .hero {{
        background:
            radial-gradient(1200px 200px at 10% -20%, rgba(139,92,255,0.35), transparent),
            linear-gradient(135deg, {VIOLET} 0%, {TEAL} 100%);
        padding: 2.2rem 2rem;
        border-radius: 20px;
        color: #0a0a0a;
        box-shadow: 0 12px 40px rgba(0,224,164,0.15);
        margin-bottom: 0.5rem;
    }}
    .hero h1 {{ font-size: 2.6rem; margin: 0 0 0.4rem 0; color: #0a0a0a; }}
    .hero p {{ font-size: 1.15rem; margin: 0; color: #0a0a0a; opacity: 0.85; font-weight: 500; }}
    .chips {{ margin-top: 1rem; }}
    .chip {{
        display:inline-block; padding:6px 14px; border-radius:999px; margin:4px 6px 0 0;
        background: rgba(0,0,0,0.18); color:#0a0a0a; font-weight:600; font-size:0.85rem;
    }}

    /* Generic cards */
    .card {{
        background: #161b27; border: 1px solid #232b3d; border-radius: 16px;
        padding: 1.1rem 1.2rem; height: 100%;
    }}
    .card .num {{ font-family:'Space Grotesk'; font-size:1.6rem; font-weight:700; color:{TEAL}; }}
    .card h4 {{ margin: 0.1rem 0 0.4rem 0; }}
    .card p {{ color:#aab2c5; font-size:0.92rem; margin:0; }}

    /* Before / After comparison */
    .cmp {{ border-radius:16px; padding:1.2rem 1.3rem; height:100%; }}
    .cmp-before {{ background: rgba(255,107,107,0.08); border:1px solid rgba(255,107,107,0.4); }}
    .cmp-after {{ background: rgba(0,224,164,0.08); border:1px solid rgba(0,224,164,0.45); }}
    .cmp h3 {{ margin-top:0; }}
    .cmp ul {{ margin:0.4rem 0 0 0; padding-left:1.1rem; color:#cdd4e2; }}
    .cmp li {{ margin:0.35rem 0; }}
    .tag {{ font-size:0.8rem; font-weight:700; padding:3px 10px; border-radius:999px; }}
    .tag-bad {{ background:rgba(255,107,107,0.2); color:{CORAL}; }}
    .tag-good {{ background:rgba(0,224,164,0.2); color:{TEAL}; }}

    /* Guest cards */
    .guest {{
        background:#161b27; border:1px solid #232b3d; border-radius:14px;
        padding:0.9rem 1rem; text-align:center;
    }}
    .guest .name {{ font-family:'Space Grotesk'; font-weight:700; font-size:1.05rem; }}
    .guest .amt {{ color:{TEAL}; font-weight:600; }}
    .guest .sub {{ color:#8893a7; font-size:0.8rem; }}

    /* The on-chain code */
    .big-null {{
        font-family: 'Space Grotesk', monospace; font-size: 1rem; word-break: break-all;
        background:{INK}; color:{TEAL}; padding:1rem 1.1rem; border-radius:12px;
        border:1px solid {TEAL}; line-height:1.5;
    }}

    /* Make the primary button big and fun */
    div.stButton > button[kind="primary"] {{
        background: linear-gradient(135deg, {VIOLET}, {TEAL});
        color:#08110d; font-weight:700; font-size:1.15rem; border:0;
        padding:0.75rem 1rem; border-radius:14px; transition: transform .08s ease;
    }}
    div.stButton > button[kind="primary"]:hover {{ transform: scale(1.01); filter:brightness(1.05); }}
    </style>
    """,
    unsafe_allow_html=True,
)

# Plain-language explanations reused as tooltips.
HELP = {
    "shielded_state": "Each person's own private list of coins. It lives on their "
    "computer -- the public blockchain never sees it.",
    "aggregate_code": "ONE small 64-byte code that stands in for the whole group's "
    "payment. It's all the outside world gets to see.",
    "dummy_coins": "Decoy coins added to the mix so the real ones are harder to pick "
    "out -- like extra dancers on the floor.",
    "anonymity_set": "The size of the crowd you blend into. Bigger crowd, harder to "
    "single you out.",
    "privacy_score": "A friendly 0-100 read on how hidden you are, based on how big "
    "the crowd is.",
}

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "party" not in st.session_state:
    st.session_state.party = {}
if "result" not in st.session_state:
    st.session_state.result = None


# ---------------------------------------------------------------------------
# Sidebar -- controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Party controls")
    st.caption("Set the guest list, then press the big button.")

    st.subheader("1 · Make a party")
    num_participants = st.slider("Number of guests", 3, 8, 4,
                                 help="How many people bring coins.")
    coins_per_user = st.slider("Coins each guest brings", 1, 5, 3,
                               help="Each coin is one row in their private list.")
    if st.button("Generate guests", use_container_width=True):
        st.session_state.party = mixer.generate_party(num_participants, coins_per_user)
        st.session_state.result = None
        st.toast("Fresh guests invited", icon="🎈")

    st.divider()
    st.subheader("2 · Or upload CSVs")
    uploads = st.file_uploader("Drag & drop guest CSV files", type=["csv"],
                               accept_multiple_files=True, help=HELP["shielded_state"])
    if uploads:
        loaded = {}
        for up in uploads:
            try:
                loaded[up.name.replace(".csv", "")] = pd.read_csv(up)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Couldn't read {up.name}: {exc}")
        if loaded:
            st.session_state.party = loaded
            st.session_state.result = None
            st.success(f"Loaded {len(loaded)} file(s).")

    st.divider()
    st.subheader("3 · Privacy boost")
    num_dummy = st.slider("Decoy coins", 0, 10, 2, help=HELP["dummy_coins"])

    st.divider()
    st.caption("The party is private. No one knows who brought what.")


# ---------------------------------------------------------------------------
# Visualization helpers (no emojis -- color + shape carry the meaning)
# ---------------------------------------------------------------------------
def _render_network(G, pos, title, legend):
    color_map = {"user": BLUE, "tx": CORAL, "mix": VIOLET, "out": TEAL}
    edge_x, edge_y = [], []
    for a, b in G.edges():
        edge_x += [pos[a][0], pos[b][0], None]
        edge_y += [pos[a][1], pos[b][1], None]
    edge_trace = go.Scatter(x=edge_x, y=edge_y, mode="lines",
                            line=dict(width=1.4, color="#3a4258"), hoverinfo="none")
    node_x, node_y, text, colors, sizes = [], [], [], [], []
    for n, d in G.nodes(data=True):
        node_x.append(pos[n][0]); node_y.append(pos[n][1])
        text.append(d.get("display", n)); colors.append(color_map.get(d.get("kind"), "#ccc"))
        sizes.append(34 if d.get("kind") == "mix" else 22)
    node_trace = go.Scatter(
        x=node_x, y=node_y, mode="markers+text", text=text, textposition="bottom center",
        textfont=dict(size=12, color="#cdd4e2"),
        marker=dict(size=sizes, color=colors, line=dict(width=1.5, color="#0e1117")),
        hoverinfo="text",
    )
    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        title=dict(text=title, font=dict(size=15)),
        showlegend=False, margin=dict(l=10, r=10, t=42, b=10), height=430,
        xaxis=dict(visible=False, range=[-0.4, 2.7]),
        yaxis=dict(visible=False, range=[-0.35, 1.25]),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        annotations=[dict(text=legend, x=0, y=1.18, xref="paper", yref="paper",
                          showarrow=False, font=dict(size=11, color="#8893a7"), align="left")],
    )
    return fig


def graph_before(party):
    G = nx.DiGraph()
    for name in party:
        G.add_node(f"u:{name}", kind="user", display=name)
        G.add_node(f"t:{name}", kind="tx", display="payment")
        G.add_edge(f"u:{name}", f"t:{name}")
    pos, users = {}, list(party.keys())
    for i, name in enumerate(users):
        y = 1 - (i / max(len(users) - 1, 1))
        pos[f"u:{name}"] = (0, y); pos[f"t:{name}"] = (1.4, y)
    return _render_network(G, pos, "Without the party: one public trail per person",
                           "Blue = person   ·   Coral = their own public payment")


def graph_after(result, private_view):
    G = nx.DiGraph()
    mix = "mix"
    G.add_node(mix, kind="mix", display="SHARED MIX")
    for name in result.participants:
        G.add_node(f"u:{name}", kind="user", display=name)
        G.add_edge(f"u:{name}", mix)
    for i, _flow in enumerate(result.flows):
        label = "?" if private_view else f"coin {i+1}"
        G.add_node(f"o:{i}", kind="out", display=label)
        G.add_edge(mix, f"o:{i}")
    pos, users = {}, result.participants
    for i, name in enumerate(users):
        pos[f"u:{name}"] = (0, 1 - (i / max(len(users) - 1, 1)))
    pos[mix] = (1.35, 0.5)
    outs = [n for n, d in G.nodes(data=True) if d.get("kind") == "out"]
    for i, n in enumerate(outs):
        pos[n] = (2.4, 1 - (i / max(len(outs) - 1, 1)))
    return _render_network(
        G, pos,
        "With the party: one shared mix, outputs can't be traced",
        "Everyone flows through the same mix, so inputs and outputs can't be linked",
    )


def sankey_flow(result, private_view):
    participants = result.participants
    labels = [p for p in participants] + ["SHARED MIX"]
    mix_idx = len(participants)
    out_start = len(labels)
    for i, _flow in enumerate(result.flows):
        labels.append("?" if private_view else f"coin {i+1}")
    p_index = {p: i for i, p in enumerate(participants)}
    src, tgt, val = [], [], []
    for flow in result.flows:
        src.append(p_index.get(flow["from"], 0)); tgt.append(mix_idx)
        val.append(max(flow["amount_sats"], 1))
    for i, flow in enumerate(result.flows):
        src.append(mix_idx); tgt.append(out_start + i)
        val.append(max(flow["amount_sats"], 1))
    node_colors = [BLUE] * len(participants) + [VIOLET] + [TEAL] * len(result.flows)
    fig = go.Figure(go.Sankey(
        node=dict(label=labels, pad=16, thickness=16, color=node_colors,
                  line=dict(color="#0e1117", width=0.5)),
        link=dict(source=src, target=tgt, value=val, color="rgba(139,92,255,0.28)"),
    ))
    fig.update_layout(title="Money goes in, gets scrambled in the mix, comes out fresh",
                      height=440, margin=dict(l=10, r=10, t=42, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#cdd4e2"))
    return fig


def privacy_gauge(score):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score, number=dict(suffix="/100", font=dict(size=34)),
        title=dict(text="Privacy score", font=dict(size=15)),
        gauge=dict(
            axis=dict(range=[0, 100], tickcolor="#8893a7"),
            bar=dict(color=TEAL),
            bgcolor="rgba(0,0,0,0)",
            steps=[dict(range=[0, 40], color="rgba(255,107,107,0.25)"),
                   dict(range=[40, 70], color="rgba(139,92,255,0.25)"),
                   dict(range=[70, 100], color="rgba(0,224,164,0.25)")],
        ),
    ))
    fig.update_layout(height=240, margin=dict(l=20, r=20, t=50, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#cdd4e2"))
    return fig


# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="hero">
      <h1>Shielded CSV Party Mix</h1>
      <p>Pay together. Stay private. Save fees.</p>
      <div class="chips">
        <span class="chip">Group up</span>
        <span class="chip">One shared payment</span>
        <span class="chip">One tiny public code</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# How it works -- three plain cards
hc = st.columns(3)
steps = [
    ("1", "Everyone brings coins", "Each guest has a private list of coins on their own device."),
    ("2", "Make one payment together", "All the coins go into a shared mix and come out shuffled."),
    ("3", "The public sees one code", "Outsiders get a single 64-byte code. No names. No amounts."),
]
for col, (n, title, body) in zip(hc, steps):
    col.markdown(
        f"<div class='card'><div class='num'>{n}</div><h4>{title}</h4><p>{body}</p></div>",
        unsafe_allow_html=True,
    )

st.write("")

party = st.session_state.party
if not party:
    st.info("Start by generating guests or uploading CSVs in the sidebar on the left.")
    st.stop()

# ---------------------------------------------------------------------------
# Guest list
# ---------------------------------------------------------------------------
st.subheader("Guest list")
st.caption("Each guest brings a private list of coins (only they can see the details).")
gcols = st.columns(min(len(party), 4))
for i, (name, df) in enumerate(party.items()):
    total = int(df["amount_sats"].sum()) if "amount_sats" in df else 0
    with gcols[i % len(gcols)]:
        st.markdown(
            f"<div class='guest'><div class='name'>{name}</div>"
            f"<div class='amt'>{mixer.sats_to_btc_str(total)}</div>"
            f"<div class='sub'>{len(df)} coins</div></div>",
            unsafe_allow_html=True,
        )

with st.expander("Peek at each guest's private list"):
    for name, df in party.items():
        st.markdown(f"**{name}**")
        st.dataframe(df, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Mix CTA
# ---------------------------------------------------------------------------
st.write("")
st.subheader("Run the mix")
st.caption(f"Decoy coins: {num_dummy}  ·  more decoys = a bigger crowd to hide in.")

if st.button("Mix the party", type="primary", use_container_width=True):
    progress = st.progress(0, text="Opening a shared account...")
    steps_anim = [
        "Opening a shared account",
        "Collecting everyone's coins",
        "Shuffling and hiding who owns what",
        "Adding decoy coins",
        "Combining everything into one payment",
        "Posting one small code to the chain",
    ]
    for i, label in enumerate(steps_anim):
        time.sleep(0.4)
        progress.progress(int((i + 1) / len(steps_anim) * 100), text=label)
    st.session_state.result = mixer.run_party_mix(party, num_dummy_coins=num_dummy)
    progress.empty()
    st.balloons()
    st.toast("Mixed. Everyone left private.", icon="✅")

result = st.session_state.result

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
if result is not None:
    m = result.metrics
    n_people = len(result.participants)

    st.write("")
    st.subheader("What just happened")

    # The obvious value: side-by-side before vs after.
    b, a = st.columns(2)
    b.markdown(
        f"""
        <div class="cmp cmp-before">
          <span class="tag tag-bad">WITHOUT THE PARTY</span>
          <h3>Easy to follow</h3>
          <ul>
            <li><b>{m['nullifiers_before']}</b> separate public payments</li>
            <li><b>{m['bytes_before']} bytes</b> posted on-chain</li>
            <li>Anyone can trace each coin to a person</li>
          </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )
    a.markdown(
        f"""
        <div class="cmp cmp-after">
          <span class="tag tag-good">WITH THE PARTY</span>
          <h3>Private &amp; cheap</h3>
          <ul>
            <li><b>1</b> shared payment for {n_people} people</li>
            <li><b>{m['bytes_after']} bytes</b> on-chain ({m['pct_saved']}% less)</li>
            <li>No one can tell who paid whom</li>
          </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")
    k1, k2, k3 = st.columns([1, 1, 1.2])
    with k1:
        st.metric("On-chain bytes saved", f"{m['bytes_saved']} B", f"-{m['pct_saved']}%")
        st.metric("Public codes", f"{m['nullifiers_after']}", f"was {m['nullifiers_before']}",
                  help=HELP["aggregate_code"])
    with k2:
        st.metric("Crowd you hide in", f"{m['anonymity_set']}", help=HELP["anonymity_set"])
        st.metric("Decoy coins", f"{m['num_dummy_coins']}", help=HELP["dummy_coins"])
    with k3:
        st.plotly_chart(privacy_gauge(m["privacy_score"]), use_container_width=True,
                        config={"displayModeBar": False})

    st.write("")
    tabs = st.tabs(["Before vs After", "Coin flow", "Public view", "The shared record", "Downloads"])

    with tabs[0]:
        private_view = st.toggle("Private view (hide output details)", value=True,
                                 help="On = what outsiders see. Off = peek behind the curtain.")
        g1, g2 = st.columns(2)
        with g1:
            st.plotly_chart(graph_before(party), use_container_width=True,
                            config={"displayModeBar": False})
            st.caption("Separate payments are easy to follow, coin by coin.")
        with g2:
            st.plotly_chart(graph_after(result, private_view), use_container_width=True,
                            config={"displayModeBar": False})
            st.caption("One shared mix breaks the link between payer and receiver.")

    with tabs[1]:
        pv = st.toggle("Hide which coin is which", value=True, key="sankey_priv")
        st.plotly_chart(sankey_flow(result, pv), use_container_width=True,
                        config={"displayModeBar": False})
        st.caption("Everything passes through the same mix, so no single guest "
                   "can be traced to a single output.")

    with tabs[2]:
        st.markdown("#### What the whole world actually sees")
        st.caption(HELP["aggregate_code"])
        st.markdown(f"<div class='big-null'>{result.aggregate_nullifier}</div>",
                    unsafe_allow_html=True)
        st.write("")
        if st.button("Publish to mock Bitcoin", use_container_width=True):
            log, shown = st.empty(), []
            for line in result.onchain_log:
                shown.append(line)
                log.code("\n".join(shown), language="text")
                time.sleep(0.5)
            st.success("Published. Outsiders learned almost nothing.")
        st.info(f"That's it: **64 bytes** standing in for **{n_people} people** and "
                f"**{len(result.flows)} coins**. No amounts, names, or balances.")

    with tabs[3]:
        st.markdown("#### The shared payment record")
        st.caption("Only the party can see this. Outsiders never get this table.")
        show = result.joint_csv.copy()
        show["amount"] = show["amount_sats"].apply(mixer.sats_to_btc_str)
        st.dataframe(show[["shared_account_id", "output_commitment", "amount",
                           "is_decoy", "proof_hash"]],
                     use_container_width=True, hide_index=True)

    with tabs[4]:
        st.markdown("#### Take the receipts home")
        st.download_button("Joint shared record (CSV)",
                           data=mixer.df_to_csv_bytes(result.joint_csv),
                           file_name="joint_shielded_tx.csv", mime="text/csv",
                           use_container_width=True)
        st.write("**Updated guest lists (old coins spent, fresh coins added):**")
        dl = st.columns(min(len(result.updated_states), 4))
        for i, (name, df) in enumerate(result.updated_states.items()):
            with dl[i % len(dl)]:
                st.download_button(name, data=mixer.df_to_csv_bytes(df),
                                   file_name=f"{name}_updated_state.csv", mime="text/csv",
                                   use_container_width=True, key=f"dl_{name}")

st.divider()
st.caption("Educational demo only. The cryptography here is faked with random text "
           "so the ideas stay simple. Real Shielded CSV does the heavy lifting with "
           "actual zero-knowledge proofs.")

# ===========================================================================
# README -- how to run + the novel idea, in plain words
# ===========================================================================
"""
SHIELDED CSV PARTY MIX -- README
================================

HOW TO RUN
    pip install -r requirements.txt
    streamlit run app.py
Then open the URL Streamlit prints (usually http://localhost:8501).

WHAT IT DOES
1. Generate (or upload) 3-8 guests, each with a private list of coins.
2. Click "Mix the party". Everyone's coins pool into one shared account,
   ownership gets shuffled, optional decoy coins are added, and the group makes
   ONE shared private payment.
3. The only thing posted publicly is a single 64-byte code.
4. Explore the dashboard: before/after, coin flow, the public view, the shared
   record, and downloads.

THE NOVEL MIXING IDEA (in plain words)
Shielded CSV already shrinks each payment down to a tiny 64-byte code and keeps
the real details (amounts, owners, balances) on your own computer. The Party Mix
goes further: a GROUP makes a SINGLE shared payment together. Because all the
inputs and outputs live inside one transaction:
  - You only pay for ONE code on-chain (cheaper for everyone).
  - Outsiders can't link any input to any output (better privacy).
  - Adding decoy coins grows the crowd you blend into.
It's a CoinJoin-style mixer reimagined for Shielded CSV.
"""
