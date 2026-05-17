"""
Pathfinder — The AI Trail Companion
Streamlit front-end (English).
"""

from __future__ import annotations

import html
import json
import os
import re

import streamlit as st
from dotenv import load_dotenv

import services

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.1-8b-instant"

WELCOME_MESSAGE = (
    "Hi! I'm <b>Pathfinder</b>, your AI companion for sustainable hiking in Greece.<br><br>"
    "To give you the best dynamic recommendations, please answer these <b>3 simple questions</b>:<br>"
    "1. <b>Difficulty</b> — Easy, moderate, hard, or expert?<br>"
    "2. <b>Time available</b> — e.g., 2-3 hours, half day, full day?<br>"
    "3. <b>Landscape</b> — Do you prefer mountains or sea/coast?<br><br>"
    "Once you reply, I will present the top regions in Greece beautifully tailored just for you!"
)

SYSTEM_INSTRUCTIONS = """You are Pathfinder, an expert smart travel and sustainable companion for Greece.
Always respond in English only.

CRITICAL FORMATTING RULE:
- NEVER use Markdown asterisks (like **text**) for bolding or formatting. THIS IS STRICTLY FORBIDDEN.
- You must ONLY use clean HTML tags (like <b>text</b>) to structure your responses.
- When suggesting the 3-4 candidate locations, wrap each location recommendation inside a beautiful HTML/CSS card exactly like this:
<div style="background-color: #ffffff; border-left: 5px solid #2d6a4f; border-radius: 8px; padding: 15px; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
    <span style="font-size: 1.2rem;">📍 <b>Specific Location Name, Region</b></span><br>
    <span style="color: #2d6a4f; font-weight: bold;">Why it fits:</span> Explanation of why this fits their preferences (hiking criteria OR alternative interests like football, culture, food), including candidate weather if available.<br>
    <span style="color: #1b4332; font-size: 0.9rem;"><i>Eco-Tip: Explore the local area sustainably and respect the community.</i></span>
</div>

General Flow Rules:
- Never guess the user's GPS or current location.
- Never invent live weather numbers, trail names, or species observations.
- IF THE USER PROVIDES AN INCOMPLETE ANSWER (e.g., they only say "easy" but do not mention time or landscape), DO NOT suggest locations yet. Politely ask them to provide the missing preferences first.
- If the user expresses a specific alternative interest (e.g., football teams, local food, history), you can bypass the 3 questions and IMMEDIATELY suggest 3-4 specific Greek cities/regions.

Conversation flow:
1. If the user's request is completely vague or incomplete, ask for their missing hiking preferences (difficulty, time, landscape).
2. Once you have enough context, suggest 3-4 suitable areas using ONLY the beautiful HTML/CSS template cards (NO MARKDOWN).
   End that exact message with a new line containing exactly the single-word or simple city/island names for geocoding:
   CANDIDATES: CleanName1; CleanName2; CleanName3; CleanName4
3. When the user picks an area from your suggestions, confirm and end that message with exactly:
   SELECTED_LOCATION: <single place name for geocoding in Greece>
4. After selection, provide plans or tips using only tool data in context. Promote sustainability and Leave No Trace.
"""
TAG_CANDIDATES = re.compile(r"^CANDIDATES:\s*(.+)$", re.MULTILINE | re.IGNORECASE)
TAG_SELECTED = re.compile(r"^SELECTED_LOCATION:\s*(.+)$", re.MULTILINE | re.IGNORECASE)

st.set_page_config(
    page_title="Pathfinder - AI Trail Companion",
    page_icon="🥾",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600;700&family=Fraunces:wght@600;700&display=swap');
:root {
    --pf-forest: #1b4332; --pf-moss: #2d6a4f; --pf-cream: #f6f9f4; --pf-bark: #3d2817;
    --pf-shadow: rgba(27, 67, 50, 0.12);
}
.stApp {
    background: linear-gradient(165deg, var(--pf-cream) 0%, #eef5ee 50%, #e8f4ea 100%);
    font-family: 'DM Sans', sans-serif; color: var(--pf-bark);
}
[data-testid="stSidebar"] { background: linear-gradient(180deg, #1b4332 0%, #2d6a4f 100%) !important; }
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label { color: #e8f8ee !important; }
.pf-hero h1 { font-family: 'Fraunces', serif; font-size: 2.35rem; color: var(--pf-forest); text-align: center; margin-bottom: 5px; }
.pf-hero p { text-align: center; color: var(--pf-moss); font-size: 1.1rem; margin-bottom: 25px; }
.pf-logo-wrap { text-align: center; padding: 1rem 0; }
.pf-brand { font-family: 'Fraunces', serif; font-size: 1.55rem; color: #fff !important; }
.pf-tagline { font-size: 0.82rem; color: #d8f3dc !important; }
.pf-sustain-card {
    background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.22);
    border-radius: 14px; padding: 0.9rem 1rem; margin: 0.55rem 0;
}
.pf-sustain-card h4 { color: #fff !important; font-size: 0.92rem; margin: 0 0 5px 0; }
.pf-sustain-card p { color: #e0f2e8 !important; font-size: 0.8rem; margin: 0; }
.pf-chat-wrap { max-width: 820px; margin: 0 auto 0.6rem; }
.pf-bubble-row { display: flex; align-items: flex-end; gap: 0.5rem; margin-bottom: 0.75rem; }
.pf-bubble-row.user { justify-content: flex-end; }
.pf-bubble { max-width: 80%; padding: 0.9rem 1.1rem; border-radius: 18px; line-height: 1.6; box-shadow: 0 4px 14px var(--pf-shadow); font-size: 1rem; }
.pf-bubble.user { background: linear-gradient(135deg, #2d6a4f, #1b4332); color: #fff; }
.pf-bubble.assistant { background: #fdfdfd; border: 1px solid rgba(45,106,79,0.14); color: var(--pf-bark); }
.pf-avatar { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.2rem; }
.pf-avatar.user { background: #e9c46a; }
.pf-avatar.assistant { background: #d8f3dc; }
.pf-panel {
    background: #fff; border: 1px solid rgba(45,106,79,0.15); border-radius: 16px;
    padding: 1.1rem 1.2rem; margin: 0.75rem 0; box-shadow: 0 6px 20px var(--pf-shadow);
}
.pf-panel h3 { font-family: 'Fraunces', serif; color: var(--pf-forest); margin: 0 0 0.75rem; }
.pf-sustain-track { height: 14px; background: #e8f0ea; border-radius: 999px; overflow: hidden; margin: 0.5rem 0; }
.pf-sustain-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, #95d5b2, #52b788, #2d6a4f); }
#MainMenu, footer, header { visibility: hidden; }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def init_session() -> None:
    st.session_state.setdefault("messages", [{"role": "assistant", "content": WELCOME_MESSAGE}])
    st.session_state.setdefault("tool_snapshot", None)
    st.session_state.setdefault("extra_context", None)
    st.session_state.setdefault("current_candidates", [])
    st.session_state.setdefault("selected_name", None)


def parse_ai_tags(text: str) -> tuple[str, list[str], str | None]:
    candidates: list[str] = []
    selected: str | None = None
    cand_match = TAG_CANDIDATES.search(text)
    if cand_match:
        candidates = [p.strip() for p in cand_match.group(1).split(";") if p.strip()]
    sel_match = TAG_SELECTED.search(text)
    if sel_match:
        selected = sel_match.group(1).strip()
    display = TAG_CANDIDATES.sub("", text)
    display = TAG_SELECTED.sub("", display)
    return display.strip(), candidates, selected


def render_chat_bubble(role: str, content: str) -> None:
    avatar = "🧭" if role == "assistant" else "🥾"
    if role == "assistant":
        inner = (
            f'<div class="pf-bubble-row assistant">'
            f'<div class="pf-avatar assistant">{avatar}</div>'
            f'<div class="pf-bubble assistant">{content}</div></div>'
        )
    else:
        safe_user = html.escape(content).replace("\n", "<br>")
        inner = (
            f'<div class="pf-bubble-row user">'
            f'<div class="pf-bubble user">{safe_user}</div>'
            f'<div class="pf-avatar user">{avatar}</div></div>'
        )
    st.markdown(f'<div class="pf-chat-wrap">{inner}</div>', unsafe_allow_html=True)


def build_groq_messages(extra_context: dict | None) -> list[dict[str, str]]:
    system = SYSTEM_INSTRUCTIONS
    if extra_context:
        system += "\n\nTool / weather context:\n" + json.dumps(extra_context, ensure_ascii=False, default=str)
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    for msg in st.session_state.messages:
        role = msg.get("role")
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": msg.get("content", "")})
    return messages


def chat_reply(extra_context: dict | None = None) -> str:
    if not GROQ_API_KEY:
        return "GROQ_API_KEY is not set in .env. Add your key to enable the AI assistant."
    try:
        from groq import Groq

        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=build_groq_messages(extra_context),
        )
        return response.choices[0].message.content or "I could not generate a response."
    except Exception as exc:
        return f"Groq API error: {exc}"


def weather_for_places(names: list[str]) -> list[dict]:
    out: list[dict] = []
    for name in names[:4]:
        resolved = services.resolve_location(name)
        if not resolved:
            out.append({"place": name, "ok": False, "error": "Could not geocode"})
            continue
        w = services.get_weather(resolved["lat"], resolved["lon"])
        out.append({
            "place": name,
            "resolved_name": resolved.get("name"),
            "ok": w.get("ok", False),
            "temp_c": w.get("temp_c"),
            "description": w.get("description"),
            "wind_speed_ms": w.get("wind_speed_ms"),
            "humidity_pct": w.get("humidity_pct"),
            "error": w.get("error"),
        })
    return out


def build_location_snapshot(location_name: str) -> dict:
    resolved = services.resolve_location(location_name)
    if not resolved:
        return {"ok": False, "error": f"Could not find: {location_name}"}
    lat, lon = resolved["lat"], resolved["lon"]
    weather = services.get_weather(lat, lon)
    biodiversity = services.get_biodiversity(lat, lon)
    elevation = services.get_elevation(lat, lon)
    conditions = services.get_real_time_conditions(resolved)
    sustainability = services.calculate_sustainability_score({
        "trail": {"lat": lat, "lon": lon, "difficulty": "moderate"},
        "pois": [],
        "biodiversity": biodiversity,
        "conditions": conditions,
    })
    return {
        "ok": True,
        "location": resolved,
        "weather": weather,
        "biodiversity": biodiversity,
        "elevation": elevation,
        "sustainability": sustainability,
    }


def handle_chat_turn(user_text: str) -> None:
    st.session_state.messages.append({"role": "user", "content": user_text})
    raw = chat_reply(st.session_state.extra_context)
    display, candidates, selected = parse_ai_tags(raw)

    if candidates:
        st.session_state.current_candidates = candidates
        st.session_state.extra_context = {"candidate_weather": weather_for_places(candidates)}
        raw2 = chat_reply(st.session_state.extra_context)
        display2, _, selected2 = parse_ai_tags(raw2)
        display = display2 or display
        selected = selected2 or selected

    if selected:
        st.session_state.selected_name = selected
        st.session_state.current_candidates = []
        st.session_state.tool_snapshot = build_location_snapshot(selected)
        st.session_state.extra_context = {"selected_location_data": st.session_state.tool_snapshot}
        raw3 = chat_reply(st.session_state.extra_context)
        display3, _, _ = parse_ai_tags(raw3)
        display = display3 or display

    st.session_state.messages.append({"role": "assistant", "content": display})


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            '<div class="pf-logo-wrap"><div class="pf-logo">🌲</div>'
            '<div class="pf-brand">Pathfinder</div>'
            '<p class="pf-tagline">The AI Trail Companion</p></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div class="pf-sustain-card"><h4>Leave No Trace</h4>
            <p>Pack out what you pack in. Respect wildlife and stay on marked paths.</p></div>
            <div class="pf-sustain-card"><h4>Plan with data</h4>
            <p>Chat to get region ideas, then pick one to see weather and sustainability.</p></div>
            """,
            unsafe_allow_html=True,
        )
        snap = st.session_state.get("tool_snapshot") or {}
        loc = st.session_state.get("selected_name") or (snap.get("location") or {}).get("name")
        if loc:
            st.caption(f"Active region: {loc}")
        if st.button("New conversation", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


def render_weather_panel(snapshot: dict) -> None:
    weather = snapshot.get("weather") or {}
    name = st.session_state.get("selected_name") or "Selected Area"
    st.markdown(f'<div class="pf-panel"><h3>Weather - {name}</h3></div>', unsafe_allow_html=True)
    if not weather.get("ok"):
        st.info(weather.get("error", "Set OPENWEATHER_API_KEY in .env"))
        return
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Temperature", f"{weather.get('temp_c', '-')} °C")
    c2.metric("Humidity", f"{weather.get('humidity_pct', '-')} %")
    c3.metric("Wind", f"{weather.get('wind_speed_ms', '-')} m/s")
    elev = snapshot.get("elevation") or {}
    c4.metric("Elevation", f"{elev.get('elevation_m', '-')} m" if elev.get("ok") else "-")
    st.caption(f"Conditions: {weather.get('description', '-')}")


def render_sustainability_panel(snapshot: dict) -> None:
    sust = snapshot.get("sustainability") or {}
    bio = snapshot.get("biodiversity") or {}
    score = int(sust.get("score", 0))
    label = sust.get("label", "-")
    factors = sust.get("factors") or {}
    st.markdown('<div class="pf-panel"><h3>Sustainability and Biodiversity</h3></div>', unsafe_allow_html=True)
    st.markdown(f"**Regional sustainability score:** {score}/100 - {label}")
    st.markdown(
        f'<div class="pf-sustain-track"><div class="pf-sustain-fill" style="width:{min(100, score)}%;"></div></div>',
        unsafe_allow_html=True,
    )
    if factors:
        st.caption(f"{factors.get('crowd_avoidance', '')} - {factors.get('nature_impact', '')}")
    st.markdown("**Recent biodiversity (iNaturalist)**")
    observations = bio.get("observations") or []
    if bio.get("ok") and observations:
        for obs in observations[:6]:
            st.caption(
                f"- {obs.get('species', 'Unknown')} ({obs.get('iconic_taxon', '-')}) - {obs.get('observed_on', '')}"
            )
    elif bio.get("ok"):
        st.caption("No recent observations reported nearby.")
    else:
        st.caption(bio.get("error", "Biodiversity data unavailable."))


def main() -> None:
    init_session()
    render_sidebar()

    st.markdown(
        '<div class="pf-hero"><h1>Pathfinder</h1>'
        "<p>Your AI companion for sustainable trails in Greece</p></div>",
        unsafe_allow_html=True,
    )

    for msg in st.session_state.messages:
        render_chat_bubble(msg["role"], msg["content"])

    snapshot = st.session_state.get("tool_snapshot")
    if snapshot and snapshot.get("ok"):
        st.divider()
        render_weather_panel(snapshot)
        render_sustainability_panel(snapshot)

    # DYNAMIC INTERACTIVE BUTTONS FOR UX UPGRADE
    if st.session_state.get("current_candidates") and not st.session_state.get("tool_snapshot"):
        st.markdown("<p style='font-weight: bold; color: #2d6a4f; margin-top:15px;'>🎯 Click to explore one of these destinations:</p>", unsafe_allow_html=True)
        cols = st.columns(len(st.session_state.current_candidates))
        for idx, cand in enumerate(st.session_state.current_candidates):
            if cols[idx].button(f"📍 {cand}", key=f"cand_btn_{idx}", use_container_width=True):
                with st.spinner(f"Loading data for {cand}..."):
                    handle_chat_turn(f"I choose {cand}")
                st.rerun()

    prompt = st.chat_input("Answer the 3 questions or continue the conversation...", disabled=not GROQ_API_KEY)
    if prompt and prompt.strip():
        with st.spinner("Pathfinder is thinking..."):
            handle_chat_turn(prompt.strip())
        st.rerun()


if __name__ == "__main__":
    main()