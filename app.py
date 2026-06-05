"""
Party Mix -- a friendly, interactive demo of private Bitcoin mixing.

Run it with:
    pip install -r requirements.txt
    streamlit run app.py

The whole idea, in one line:
    Everyone tosses their Bitcoin into one shared "party", it all gets shuffled,
    and each person walks out with fresh coins -- so no one watching can tell
    whose money went where.

This is an educational toy. The "cryptography" is faked with random text so the
ideas stay simple. See the README section at the bottom of this file.
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
st.set_page_config(page_title="Party Mix", page_icon="🪩", layout="wide")

# Bitcoin-party palette: Bitcoin orange is the star, with disco accents.
ORANGE = "#f7931a"
PINK = "#ff3da5"
PURPLE = "#8b5cff"
TEAL = "#00e0a4"
INK = "#0e1117"

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Bungee&family=Poppins:wght@400;600;700&display=swap');

    html, body, [class*="css"] {{ font-family:'Poppins', sans-serif; }}
    h1,h2,h3,h4 {{ font-family:'Poppins', sans-serif; font-weight:700; }}

    /* ---- Hero / disco banner ---- */
    .hero {{
        position:relative; overflow:hidden;
        background:
          radial-gradient(620px 300px at 12% -10%, rgba(247,147,26,0.40), transparent 60%),
          radial-gradient(620px 300px at 88% 0%, rgba(255,61,165,0.34), transparent 60%),
          radial-gradient(620px 320px at 50% 130%, rgba(139,92,255,0.40), transparent 60%),
          linear-gradient(160deg, #160f1f, #0e1117);
        border:1px solid #2a2140; border-radius:26px; padding:2.4rem 2rem 2.1rem;
        margin-bottom:1.1rem; box-shadow:0 18px 60px rgba(247,147,26,0.12);
    }}
    .brand {{ display:flex; align-items:center; gap:1.2rem; }}
    .coin {{
        width:92px; height:92px; border-radius:50%; flex:0 0 auto;
        background: radial-gradient(circle at 32% 28%, #ffd98a, {ORANGE} 55%, #b96a05);
        color:#3a2200; font-family:'Bungee', cursive; font-size:3.2rem;
        display:flex; align-items:center; justify-content:center;
        box-shadow:0 0 42px rgba(247,147,26,0.65);
    }}
    .wordmark {{
        font-family:'Bungee', cursive; font-size:clamp(2.8rem, 7vw, 4.6rem);
        line-height:0.95; margin:0;
        background:linear-gradient(90deg,{ORANGE},{PINK},{PURPLE},{TEAL},{ORANGE});
        background-size:300% auto; -webkit-background-clip:text; background-clip:text;
        -webkit-text-fill-color:transparent; animation:shine 6s linear infinite;
    }}
    @keyframes shine {{ to {{ background-position:300% center; }} }}
    .tagline {{ color:#f3e9ff; font-size:1.25rem; font-weight:600; margin:0.5rem 0 0; }}
    .subline {{ color:#b9a8d6; font-size:0.95rem; margin:0.15rem 0 0; }}

    /* ---- Big analogy callout ---- */
    .analogy {{
        background:linear-gradient(135deg, rgba(247,147,26,0.12), rgba(139,92,255,0.12));
        border:1px dashed {ORANGE}; border-radius:18px; padding:1.1rem 1.3rem;
        font-size:1.1rem; color:#ffe9cf; line-height:1.5;
    }}
    .analogy b {{ color:{ORANGE}; }}

    /* ---- Step cards ---- */
    .step {{ background:#161020; border:1px solid #2a2140; border-radius:18px;
            padding:1.1rem 1.1rem 1.2rem; height:100%; text-align:center; }}
    .step .ic {{ font-family:'Bungee',cursive; font-size:1.6rem; width:54px; height:54px;
                border-radius:50%; display:flex; align-items:center; justify-content:center;
                margin:0 auto 0.6rem; color:#1a1024; }}
    .step h4 {{ margin:0 0 0.3rem; font-size:1.05rem; }}
    .step p {{ margin:0; color:#b6acc6; font-size:0.9rem; }}

    /* ---- Guest cards ---- */
    .guest {{ background:#161020; border:1px solid #2a2140; border-radius:16px;
             padding:0.9rem 0.6rem; text-align:center; }}
    .guest .face {{ font-size:1.9rem; }}
    .guest .name {{ font-weight:700; font-size:0.98rem; margin-top:0.2rem; }}
    .guest .amt {{ color:{ORANGE}; font-weight:700; font-size:0.92rem; }}
    .guest .sub {{ color:#8a7ea3; font-size:0.78rem; }}

    /* ---- Verdict (before/after) ---- */
    .verdict {{ border-radius:18px; padding:1.3rem 1.4rem; height:100%; }}
    .v-before {{ background:rgba(255,61,165,0.08); border:1px solid rgba(255,61,165,0.45); }}
    .v-after  {{ background:rgba(0,224,164,0.08); border:1px solid rgba(0,224,164,0.5); }}
    .verdict .lbl {{ font-size:0.8rem; font-weight:700; letter-spacing:0.06em; }}
    .verdict .ans {{ font-family:'Bungee',cursive; font-size:2rem; margin:0.2rem 0 0.5rem; }}
    .v-before .ans {{ color:{PINK}; }}
    .v-after .ans {{ color:{TEAL}; }}
    .verdict p {{ margin:0; color:#cdc4dd; }}

    /* ---- Result banner ---- */
    .winner {{
        background:linear-gradient(135deg, rgba(0,224,164,0.15), rgba(139,92,255,0.15));
        border:1px solid {TEAL}; border-radius:18px; padding:1.2rem 1.4rem; margin-bottom:0.6rem;
    }}
    .winner h2 {{ margin:0; }}
    .winner p {{ margin:0.3rem 0 0; color:#d7f7ee; }}

    /* ---- The public code ---- */
    .codebox {{ font-family:'Poppins',monospace; font-size:0.98rem; word-break:break-all;
               background:{INK}; color:{TEAL}; padding:1rem 1.1rem; border-radius:12px;
               border:1px solid {TEAL}; line-height:1.5; }}

    /* ---- Big party button ---- */
    div.stButton > button[kind="primary"] {{
        background:linear-gradient(135deg, {ORANGE}, {PINK} 60%, {PURPLE});
        color:#1a0e00; font-family:'Bungee',cursive; font-size:1.3rem; border:0;
        padding:0.85rem 1rem; border-radius:16px; letter-spacing:0.03em;
        box-shadow:0 10px 30px rgba(247,147,26,0.35); transition:transform .08s ease;
    }}
    div.stButton > button[kind="primary"]:hover {{ transform:scale(1.015); filter:brightness(1.06); }}
    </style>
    """,
    unsafe_allow_html=True,
)

# Little party faces so guests feel like real people (kept to one per guest).
FACES = ["🦊", "🐻", "🐼", "🐧", "🦁", "🐵", "🐯", "🦉", "🐸", "🐰", "🐨", "🐲"]

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "party" not in st.session_state:
    st.session_state.party = {}
if "result" not in st.session_state:
    st.session_state.result = None


# ---------------------------------------------------------------------------
# Sidebar -- kept tiny and plain
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Set up the party")
    num_participants = st.slider("How many people come?", 3, 8, 5)
    coins_per_user = st.slider("Coins each person brings", 1, 5, 3)
    extra_dancers = st.slider("Extra decoy coins", 0, 10, 3,
                              help="Fake coins added to the crowd so the real ones "
                                   "are even harder to spot.")
    if st.button("Invite the guests", use_container_width=True):
        st.session_state.party = mixer.generate_party(num_participants, coins_per_user)
        st.session_state.result = None
        st.toast("Guests invited!", icon="🎈")

    with st.expander("Bring your own CSVs"):
        uploads = st.file_uploader("Drop guest CSV files", type=["csv"],
                                   accept_multiple_files=True)
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

    st.caption("The party is private. No one knows who brought what.")


# ---------------------------------------------------------------------------
# Visualization helpers
# ---------------------------------------------------------------------------
def _render_network(G, pos, title):
    color_map = {"user": ORANGE, "tx": PINK, "mix": PURPLE, "out": TEAL}
    edge_x, edge_y, ecol = [], [], []
    for a, b in G.edges():
        edge_x += [pos[a][0], pos[b][0], None]
        edge_y += [pos[a][1], pos[b][1], None]
    edge_trace = go.Scatter(x=edge_x, y=edge_y, mode="lines",
                            line=dict(width=1.5, color="#473a5c"), hoverinfo="none")
    nx_, ny_, text, colors, sizes = [], [], [], [], []
    for n, d in G.nodes(data=True):
        nx_.append(pos[n][0]); ny_.append(pos[n][1])
        text.append(d.get("display", n)); colors.append(color_map.get(d.get("kind"), "#ccc"))
        sizes.append(40 if d.get("kind") == "mix" else 24)
    node_trace = go.Scatter(x=nx_, y=ny_, mode="markers+text", text=text,
                            textposition="bottom center", textfont=dict(size=12, color="#e6dcf5"),
                            marker=dict(size=sizes, color=colors, line=dict(width=1.5, color=INK)),
                            hoverinfo="text")
    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(title=dict(text=title, font=dict(size=15, color="#e6dcf5")),
                      showlegend=False, margin=dict(l=10, r=10, t=42, b=10), height=380,
                      xaxis=dict(visible=False, range=[-0.4, 2.7]),
                      yaxis=dict(visible=False, range=[-0.3, 1.2]),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    return fig


def graph_before(party):
    G = nx.DiGraph()
    for name in party:
        G.add_node(f"u:{name}", kind="user", display=name)
        G.add_node(f"t:{name}", kind="tx", display="their payment")
        G.add_edge(f"u:{name}", f"t:{name}")
    pos, users = {}, list(party.keys())
    for i, name in enumerate(users):
        y = 1 - (i / max(len(users) - 1, 1))
        pos[f"u:{name}"] = (0, y); pos[f"t:{name}"] = (1.6, y)
    return _render_network(G, pos, "Without Party Mix: one straight line per person")


def graph_after(result):
    G = nx.DiGraph()
    G.add_node("mix", kind="mix", display="THE MIX")
    for name in result.participants:
        G.add_node(f"u:{name}", kind="user", display=name)
        G.add_edge(f"u:{name}", "mix")
    for i, _ in enumerate(result.flows):
        G.add_node(f"o:{i}", kind="out", display="coin")
        G.add_edge("mix", f"o:{i}")
    pos, users = {}, result.participants
    for i, name in enumerate(users):
        pos[f"u:{name}"] = (0, 1 - (i / max(len(users) - 1, 1)))
    pos["mix"] = (1.35, 0.5)
    outs = [n for n, d in G.nodes(data=True) if d.get("kind") == "out"]
    for i, n in enumerate(outs):
        pos[n] = (2.5, 1 - (i / max(len(outs) - 1, 1)))
    return _render_network(G, pos, "With Party Mix: everyone mixes, lines get tangled")


def sankey_flow(result):
    participants = result.participants
    labels = list(participants) + ["THE MIX"] + ["fresh coin"] * len(result.flows)
    mix_idx = len(participants); out_start = mix_idx + 1
    p_index = {p: i for i, p in enumerate(participants)}
    src, tgt, val = [], [], []
    for flow in result.flows:
        src.append(p_index.get(flow["from"], 0)); tgt.append(mix_idx)
        val.append(max(flow["amount_sats"], 1))
    for i, flow in enumerate(result.flows):
        src.append(mix_idx); tgt.append(out_start + i)
        val.append(max(flow["amount_sats"], 1))
    colors = [ORANGE] * len(participants) + [PURPLE] + [TEAL] * len(result.flows)
    fig = go.Figure(go.Sankey(
        node=dict(label=labels, pad=16, thickness=16, color=colors,
                  line=dict(color=INK, width=0.5)),
        link=dict(source=src, target=tgt, value=val, color="rgba(247,147,26,0.22)")))
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#e6dcf5"))
    return fig


def invisibility_meter(score):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score, number=dict(suffix="%", font=dict(size=40, color=TEAL)),
        gauge=dict(axis=dict(range=[0, 100], tickcolor="#8a7ea3"),
                   bar=dict(color=TEAL),
                   steps=[dict(range=[0, 40], color="rgba(255,61,165,0.25)"),
                          dict(range=[40, 70], color="rgba(139,92,255,0.25)"),
                          dict(range=[70, 100], color="rgba(0,224,164,0.25)")])))
    fig.update_layout(height=230, margin=dict(l=20, r=20, t=10, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#e6dcf5"))
    return fig


# ---------------------------------------------------------------------------
# HERO -- big PARTY MIX wordmark
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="hero">
      <div class="brand">
        <div class="coin">&#8383;</div>
        <div>
          <h1 class="wordmark">PARTY MIX</h1>
          <p class="tagline">Mix your Bitcoin with the crowd, so no one can follow your money.</p>
          <p class="subline">A playful demo of private Bitcoin (built on the Shielded CSV idea).</p>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# The single clearest explanation: the hat-of-cash analogy.
st.markdown(
    """
    <div class="analogy">
      🎩 <b>Think of it like this:</b> everyone tosses the same kind of cash into a hat,
      gives it a shake, and each person takes the same amount back out. You still have
      your money &mdash; but <b>nobody can tell which bill was originally yours.</b>
      Party Mix does that with Bitcoin.
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("")

# Three dead-simple steps.
cols = st.columns(3)
steps = [
    (ORANGE, "1", "Everyone brings coins", "A handful of friends show up, each with some Bitcoin."),
    (PURPLE, "2", "Throw them in the mix", "All the coins go into one shared pile and get shuffled."),
    (TEAL, "3", "Walk out invisible", "Each person leaves with fresh coins no one can trace."),
]
for col, (c, n, t, b) in zip(cols, steps):
    col.markdown(
        f"<div class='step'><div class='ic' style='background:{c}'>{n}</div>"
        f"<h4>{t}</h4><p>{b}</p></div>",
        unsafe_allow_html=True,
    )

st.write("")

party = st.session_state.party
if not party:
    st.info("👈 Press **Invite the guests** in the sidebar to start the party.")
    st.stop()

# ---------------------------------------------------------------------------
# Guests
# ---------------------------------------------------------------------------
st.subheader("Who's at the party")
gcols = st.columns(min(len(party), 5))
for i, (name, df) in enumerate(party.items()):
    total = int(df["amount_sats"].sum()) if "amount_sats" in df else 0
    with gcols[i % len(gcols)]:
        st.markdown(
            f"<div class='guest'><div class='face'>{FACES[i % len(FACES)]}</div>"
            f"<div class='name'>{name}</div>"
            f"<div class='amt'>{mixer.sats_to_btc_str(total)}</div>"
            f"<div class='sub'>{len(df)} coins</div></div>",
            unsafe_allow_html=True,
        )

st.write("")

# ---------------------------------------------------------------------------
# The button
# ---------------------------------------------------------------------------
if st.button("START THE PARTY", type="primary", use_container_width=True):
    bar = st.progress(0, text="Turning on the disco lights...")
    anim = [
        "Everyone walks in with their coins",
        "Tossing all the coins into the mix",
        "Shuffling so no one knows whose is whose",
        "Sneaking in some decoy coins",
        "Handing everyone fresh coins back",
        "Posting one tiny code in public",
    ]
    for i, label in enumerate(anim):
        time.sleep(0.4)
        bar.progress(int((i + 1) / len(anim) * 100), text=label)
    st.session_state.result = mixer.run_party_mix(party, num_dummy_coins=extra_dancers)
    bar.empty()
    st.balloons()
    st.toast("Mixed! Everyone left invisible.", icon="🪩")

result = st.session_state.result

# ---------------------------------------------------------------------------
# Results -- the simple payoff first
# ---------------------------------------------------------------------------
if result is not None:
    m = result.metrics
    n_people = len(result.participants)

    st.write("")
    st.markdown(
        f"""
        <div class="winner">
          <h2>🎉 The party worked.</h2>
          <p>{n_people} people just made <b>one shared payment</b> together. To anyone
          watching the Bitcoin network, it's now impossible to tell who paid whom.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # The big question, answered before vs after.
    st.markdown("#### Could a nosy stranger follow your money?")
    vb, va = st.columns(2)
    vb.markdown(
        f"""<div class="verdict v-before"><div class="lbl">BEFORE PARTY MIX</div>
        <div class="ans">YES 😟</div>
        <p>Each person pays on their own, leaving <b>{m['nullifiers_before']} separate
        public trails</b>. Easy to follow.</p></div>""",
        unsafe_allow_html=True,
    )
    va.markdown(
        f"""<div class="verdict v-after"><div class="lbl">AFTER PARTY MIX</div>
        <div class="ans">NO 🕶️</div>
        <p>Everyone shares <b>one payment</b>. The coins got shuffled, so the trail
        leads into a crowd of <b>{m['anonymity_set']}</b> and stops.</p></div>""",
        unsafe_allow_html=True,
    )

    st.write("")

    # Three friendly numbers + the invisibility meter.
    s1, s2, s3, s4 = st.columns([1, 1, 1, 1.3])
    s1.metric("Hidden in a crowd of", m["anonymity_set"])
    s2.metric("Public payments", "1", f"was {m['nullifiers_before']}", delta_color="off")
    s3.metric("Public data posted", f"{m['bytes_after']} bytes",
              f"-{m['pct_saved']}% vs paying alone", delta_color="inverse")
    with s4:
        st.caption("Invisibility meter")
        st.plotly_chart(invisibility_meter(m["privacy_score"]),
                        use_container_width=True, config={"displayModeBar": False})

    st.write("")
    st.markdown("#### See it with your own eyes")
    g1, g2 = st.columns(2)
    with g1:
        st.plotly_chart(graph_before(party), use_container_width=True,
                        config={"displayModeBar": False})
        st.caption("Straight lines = easy to trace.")
    with g2:
        st.plotly_chart(graph_after(result), use_container_width=True,
                        config={"displayModeBar": False})
        st.caption("Tangled through the mix = the trail disappears.")

    # Everything advanced lives here, out of the main flow.
    with st.expander("🔬 Peek under the hood (for the curious)"):
        st.markdown("**Where the coins flowed** (it all funnels through the same mix):")
        st.plotly_chart(sankey_flow(result), use_container_width=True,
                        config={"displayModeBar": False})

        st.markdown("**The one thing the whole world sees** — a single 64-byte code:")
        st.markdown(f"<div class='codebox'>{result.aggregate_nullifier}</div>",
                    unsafe_allow_html=True)
        st.caption("No names, no amounts, no balances. Just this.")
        if st.button("Publish to mock Bitcoin"):
            log, shown = st.empty(), []
            for line in result.onchain_log:
                shown.append(line)
                log.code("\n".join(shown), language="text")
                time.sleep(0.5)
            st.success("Published. Outsiders learned almost nothing.")

        st.markdown("**The shared payment record** (only the party can see this):")
        show = result.joint_csv.copy()
        show["amount"] = show["amount_sats"].apply(mixer.sats_to_btc_str)
        st.dataframe(show[["shared_account_id", "output_commitment", "amount", "is_decoy"]],
                     use_container_width=True, hide_index=True)

        st.markdown("**Each guest's private list of coins:**")
        for name, df in party.items():
            st.caption(name)
            st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown("**Download the receipts:**")
        st.download_button("Shared payment record (CSV)",
                           data=mixer.df_to_csv_bytes(result.joint_csv),
                           file_name="party_mix_joint_tx.csv", mime="text/csv")
        for name, df in result.updated_states.items():
            st.download_button(f"{name}'s updated coins",
                               data=mixer.df_to_csv_bytes(df),
                               file_name=f"{name}_updated.csv", mime="text/csv",
                               key=f"dl_{name}")

st.divider()
st.caption("Educational demo only — the cryptography is faked with random text so the "
           "ideas stay simple. No real Bitcoin is involved. See ROADMAP.md for what a "
           "real version would need.")

# ===========================================================================
# README -- how to run + the idea, in plain words
# ===========================================================================
"""
PARTY MIX -- README

HOW TO RUN
    pip install -r requirements.txt
    streamlit run app.py
Then open the URL Streamlit prints (usually http://localhost:8501).

THE IDEA, IN PLAIN WORDS
Normally, every Bitcoin payment leaves its own public trail -- anyone can follow
the money. Party Mix gathers a group of people, throws all their coins into one
shared pile, shuffles it, and hands everyone fresh coins back. The only thing
posted publicly is a single tiny 64-byte code. Result: cheaper (one code instead
of many) and far more private (no one can tell who paid whom). It's a CoinJoin-
style mixer, reimagined on top of the Shielded CSV idea.
"""
