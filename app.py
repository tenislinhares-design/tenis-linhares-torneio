import os
import math
import random
from datetime import datetime, date, timedelta

import pandas as pd
import streamlit as st
from supabase import create_client

TABLE_TOURNAMENTS = "tl_tournaments"
TABLE_CATEGORIES = "tl_categories"
TABLE_PLAYERS = "tl_players"
TABLE_REGISTRATIONS = "tl_registrations"
TABLE_MATCHES = "tl_matches"

DEFAULT_CATEGORIES = [
    "1ª Classe Masculina",
    "2ª Classe Masculina",
    "3ª Classe Masculina",
    "4ª Classe Masculina",
    "5ª Classe Masculina",
    "Iniciantes",
    "1ª Classe Feminina",
    "2ª Classe Feminina",
    "3ª Classe Feminina",
    "Duplas 1ª Classe",
    "Duplas 2ª Classe",
]

BRAND_GREEN = "#CCFF00"
DARK_BG = "#0d1110"
CARD_BG = "#151c18"


def get_secret(name, default=""):
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.getenv(name, default)


@st.cache_resource
def get_supabase():
    url = get_secret("SUPABASE_URL") or get_secret("NEXT_PUBLIC_SUPABASE_URL")
    key = get_secret("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        st.error("Configure SUPABASE_URL/NEXT_PUBLIC_SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY nas variáveis do app.")
        st.stop()
    return create_client(url, key)


def sb():
    return get_supabase()


def data(resp):
    return getattr(resp, "data", None) or []


def insert(table, payload):
    rows = data(sb().table(table).insert(payload).execute())
    return rows[0] if rows else None


def update_by_id(table, row_id, payload):
    return sb().table(table).update(payload).eq("id", row_id).execute()


def select_by_id(table, row_id):
    rows = data(sb().table(table).select("*").eq("id", row_id).execute())
    return rows[0] if rows else None


def tournaments():
    return data(sb().table(TABLE_TOURNAMENTS).select("*").order("id", desc=True).execute())


def categories(tournament_id):
    return data(sb().table(TABLE_CATEGORIES).select("*").eq("tournament_id", tournament_id).order("name").execute())


def players_all():
    return data(sb().table(TABLE_PLAYERS).select("*").order("name").execute())


def registrations(tournament_id, category_id=None):
    q = sb().table(TABLE_REGISTRATIONS).select("*").eq("tournament_id", tournament_id)
    if category_id:
        q = q.eq("category_id", category_id)
    return data(q.execute())


def matches(tournament_id, category_id=None):
    q = sb().table(TABLE_MATCHES).select("*").eq("tournament_id", tournament_id).order("round_num").order("position")
    if category_id:
        q = q.eq("category_id", category_id)
    return data(q.execute())


def player(player_id):
    return select_by_id(TABLE_PLAYERS, player_id) if player_id else None


def category(category_id):
    return select_by_id(TABLE_CATEGORIES, category_id) if category_id else None


def tournament(tournament_id):
    return select_by_id(TABLE_TOURNAMENTS, tournament_id) if tournament_id else None


def player_name(player_id):
    p = player(player_id)
    if not p:
        return "Aguardando"
    return p.get("name", "Atleta") + (" • fora" if p.get("is_outside") else "")


def category_name(category_id):
    c = category(category_id)
    return c.get("name", "") if c else ""


def match_label(m):
    p1 = player_name(m.get("player1_id"))
    p2 = player_name(m.get("player2_id"))
    if not m.get("player1_id") and m.get("source1_match_id"):
        p1 = f"Vencedor Jogo {m['source1_match_id']}"
    if not m.get("player2_id") and m.get("source2_match_id"):
        p2 = f"Vencedor Jogo {m['source2_match_id']}"
    return f"{p1} x {p2}"


def apply_css():
    st.markdown(
        f"""
        <style>
        .stApp {{ background: radial-gradient(circle at top, #1a2b1d 0%, {DARK_BG} 48%, #070907 100%); color:#f7fff7; }}
        section[data-testid="stSidebar"] {{ background-color:#0b0f0d; }}
        div[data-testid="stMetric"] {{ background:{CARD_BG}; border:1px solid rgba(204,255,0,.25); padding:14px; border-radius:18px; }}
        .tl-card {{ background:rgba(21,28,24,.92); border:1px solid rgba(204,255,0,.22); border-radius:18px; padding:18px; margin:10px 0 18px 0; box-shadow:0 12px 30px rgba(0,0,0,.25); }}
        .tl-title {{ font-size:28px; font-weight:900; color:{BRAND_GREEN}; margin-bottom:0; }}
        .tl-sub {{ color:#d8ead8; font-size:15px; margin-top:4px; }}
        .tl-badge {{ display:inline-block; background:rgba(204,255,0,.14); border:1px solid rgba(204,255,0,.35); color:{BRAND_GREEN}; border-radius:999px; padding:4px 10px; font-size:12px; font-weight:700; margin:3px 3px 3px 0; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def header():
    st.markdown(
        """
        <div class="tl-card">
            <div class="tl-title">Tênis Linhares • Torneios Supabase</div>
            <div class="tl-sub">Teste separado para chaves, programação automática, resultados e avanço de fase.</div>
            <span class="tl-badge">Supabase</span>
            <span class="tl-badge">3 quadras</span>
            <span class="tl-badge">1h30 por jogo</span>
            <span class="tl-badge">seg-qui até 20:30</span>
            <span class="tl-badge">sexta desde 15:30</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def create_default_categories(tid):
    existing = {c["name"] for c in categories(tid)}
    for name in DEFAULT_CATEGORIES:
        if name not in existing:
            insert(TABLE_CATEGORIES, {"tournament_id": tid, "name": name, "max_players": 16})


def seed_if_empty():
    if tournaments():
        return
    t = insert(TABLE_TOURNAMENTS, {
        "name": "Torneio Teste Tênis Linhares",
        "start_date": date.today().isoformat(),
        "end_date": (date.today() + timedelta(days=6)).isoformat(),
        "active": True,
    })
    if t:
        create_default_categories(t["id"])


def tournament_selector():
    ts = tournaments()
    if not ts:
        st.warning("Nenhum torneio cadastrado.")
        return None
    labels = {f"{t['name']} • {t['start_date']} a {t['end_date']}": t["id"] for t in ts}
    return labels[st.selectbox("Torneio", list(labels.keys()))]


def category_selector(tid, key):
    cs = categories(tid)
    if not cs:
        st.warning("Nenhuma categoria cadastrada.")
        return None
    labels = {c["name"]: c["id"] for c in cs}
    return labels[st.selectbox("Categoria", list(labels.keys()), key=key)]


def player_ids_in_category(tid, cid):
    regs = registrations(tid, cid)
    return [r["player_id"] for r in regs]


def registered_players(tid, cid):
    ps = [player(pid) for pid in player_ids_in_category(tid, cid)]
    return sorted([p for p in ps if p], key=lambda x: x.get("name", ""))


def next_power_of_two(n):
    return 1 if n <= 1 else 2 ** math.ceil(math.log2(n))


def round_names(size):
    return {
        2: ["Final"],
        4: ["Semifinal", "Final"],
        8: ["Quartas de final", "Semifinal", "Final"],
        16: ["Oitavas de final", "Quartas de final", "Semifinal", "Final"],
        32: ["32 avos", "Oitavas de final", "Quartas de final", "Semifinal", "Final"],
    }.get(size, [f"Rodada {i+1}" for i in range(int(math.log2(size)))])


def delete_category_matches(tid, cid):
    sb().table(TABLE_MATCHES).delete().eq("tournament_id", tid).eq("category_id", cid).execute()


def refresh_bracket(tid, cid):
    ms = matches(tid, cid)
    winners = {m["id"]: m.get("winner_id") for m in ms}
    for m in ms:
        payload = {}
        if m.get("source1_match_id"):
            payload["player1_id"] = winners.get(m["source1_match_id"])
        if m.get("source2_match_id"):
            payload["player2_id"] = winners.get(m["source2_match_id"])
        if payload:
            update_by_id(TABLE_MATCHES, m["id"], payload)

    for m in matches(tid, cid):
        if not m.get("source1_match_id") and not m.get("source2_match_id") and m.get("status") != "finalizado":
            if m.get("player1_id") and not m.get("player2_id"):
                update_by_id(TABLE_MATCHES, m["id"], {"winner_id": m["player1_id"], "status": "bye"})
            elif m.get("player2_id") and not m.get("player1_id"):
                update_by_id(TABLE_MATCHES, m["id"], {"winner_id": m["player2_id"], "status": "bye"})


def generate_bracket(tid, cid, ordered_ids):
    ids = [x for x in ordered_ids if x]
    if len(ids) < 2:
        raise ValueError("É necessário ter pelo menos 2 atletas.")
    size = max(2, next_power_of_two(len(ids)))
    if size > 32:
        raise ValueError("Teste suporta até 32 atletas; o padrão recomendado é 16.")
    slots = ids + [None] * (size - len(ids))
    names = round_names(size)
    rounds = int(math.log2(size))
    delete_category_matches(tid, cid)

    previous = []
    for r in range(1, rounds + 1):
        current = []
        count = size // (2 ** r)
        round_name = names[r - 1]
        for pos in range(count):
            if r == 1:
                p1, p2 = slots[pos * 2], slots[pos * 2 + 1]
                source1 = source2 = winner = None
                status = "pendente"
                if p1 and not p2:
                    winner, status = p1, "bye"
                elif p2 and not p1:
                    winner, status = p2, "bye"
            else:
                p1 = p2 = winner = None
                source1, source2 = previous[pos * 2], previous[pos * 2 + 1]
                status = "pendente"
            row = insert(TABLE_MATCHES, {
                "tournament_id": tid, "category_id": cid, "round_num": r, "round_name": round_name,
                "position": pos + 1, "player1_id": p1, "player2_id": p2,
                "source1_match_id": source1, "source2_match_id": source2,
                "winner_id": winner, "status": status,
            })
            current.append(row["id"])
        previous = current
    refresh_bracket(tid, cid)


def pids_for_match(m):
    return [pid for pid in [m.get("player1_id"), m.get("player2_id")] if pid]


def has_outside(m):
    for pid in pids_for_match(m):
        p = player(pid)
        if p and p.get("is_outside"):
            return True
    return False


def parse_dt(d, t):
    return datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M")


def build_slots(start_date, end_date, include_weekend=True):
    slots = []
    d = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    while d <= end:
        wd = d.weekday()
        if wd in [0, 1, 2, 3]:
            times = ["16:00", "17:30", "19:00", "20:30"]
        elif wd == 4:
            times = ["15:30", "17:00", "18:30", "20:00", "21:30"]
        elif include_weekend:
            times = ["08:00", "09:30", "11:00", "14:00", "15:30", "17:00", "18:30", "20:00"]
        else:
            times = []
        for t in times:
            for court in [1, 2, 3]:
                slots.append({"date": d.isoformat(), "time": t, "court": court, "dt": parse_dt(d.isoformat(), t), "weekday": wd})
        d += timedelta(days=1)
    return slots


def clear_schedule(tid):
    sb().table(TABLE_MATCHES).update({"scheduled_date": None, "scheduled_time": None, "court": None}).eq("tournament_id", tid).execute()


def generate_schedule(tid, include_weekend=True):
    t = tournament(tid)
    clear_schedule(tid)
    slots = build_slots(t["start_date"], t["end_date"], include_weekend)
    used, player_busy, scheduled_dt, pending = set(), set(), {}, []
    ms = sorted(matches(tid), key=lambda m: (m.get("round_num", 1), m.get("category_id", 0), m.get("position", 0)))

    def score(slot, m):
        value = slot["dt"].timestamp()
        if has_outside(m):
            if slot["weekday"] == 4:
                value -= 10000000
            elif slot["weekday"] in [5, 6]:
                value -= 9000000
        return value

    for m in ms:
        ok = False
        for slot in sorted(slots, key=lambda s: score(s, m)):
            skey = (slot["date"], slot["time"], slot["court"])
            if skey in used:
                continue
            too_early = False
            for sid in [m.get("source1_match_id"), m.get("source2_match_id")]:
                if sid and sid in scheduled_dt and slot["dt"] < scheduled_dt[sid] + timedelta(minutes=90):
                    too_early = True
                    break
            if too_early:
                continue
            if any((pid, slot["date"], slot["time"]) in player_busy for pid in pids_for_match(m)):
                continue
            update_by_id(TABLE_MATCHES, m["id"], {"scheduled_date": slot["date"], "scheduled_time": slot["time"], "court": slot["court"]})
            used.add(skey)
            scheduled_dt[m["id"]] = slot["dt"]
            for pid in pids_for_match(m):
                player_busy.add((pid, slot["date"], slot["time"]))
            ok = True
            break
        if not ok:
            pending.append(m["id"])
    return len(ms) - len(pending), len(pending)


def schedule_df(tid):
    rows = []
    for m in matches(tid):
        rows.append({
            "Data": m.get("scheduled_date") or "",
            "Horário": m.get("scheduled_time") or "",
            "Quadra": m.get("court") or "",
            "Categoria": category_name(m["category_id"]),
            "Fase": m.get("round_name") or "",
            "Jogo": m["id"],
            "Confronto": match_label(m),
            "Placar": m.get("score") or "",
            "Vencedor": player_name(m.get("winner_id")) if m.get("winner_id") else "",
            "Status": m.get("status") or "",
        })
    df = pd.DataFrame(rows)
    return df.sort_values(["Data", "Horário", "Quadra"]) if not df.empty else df


def bracket_df(tid, cid):
    rows = []
    for m in matches(tid, cid):
        rows.append({
            "Fase": m.get("round_name") or "",
            "Jogo": m["id"],
            "Confronto": match_label(m),
            "Data": m.get("scheduled_date") or "",
            "Horário": m.get("scheduled_time") or "",
            "Quadra": m.get("court") or "",
            "Placar": m.get("score") or "",
            "Vencedor": player_name(m.get("winner_id")) if m.get("winner_id") else "",
            "Status": m.get("status") or "",
        })
    return pd.DataFrame(rows)


def public_page():
    tid = tournament_selector()
    if not tid:
        return
    t = tournament(tid)
    st.markdown(f"### {t['name']}")
    ms, regs = matches(tid), registrations(tid)
    done = [m for m in ms if m.get("status") in ["finalizado", "bye", "WO"]]
    c1, c2, c3 = st.columns(3)
    c1.metric("Inscrições", len(regs)); c2.metric("Jogos criados", len(ms)); c3.metric("Finalizados/bye", len(done))
    tab1, tab2, tab3 = st.tabs(["Programação", "Chaves", "Inscritos"])
    with tab1:
        df = schedule_df(tid)
        st.dataframe(df, use_container_width=True, hide_index=True) if not df.empty else st.info("Programação ainda não gerada.")
    with tab2:
        cid = category_selector(tid, "public_cat")
        if cid:
            df = bracket_df(tid, cid)
            st.dataframe(df, use_container_width=True, hide_index=True) if not df.empty else st.info("Chave ainda não gerada.")
    with tab3:
        rows = []
        for r in regs:
            p, c = player(r["player_id"]), category(r["category_id"])
            rows.append({"Categoria": c.get("name", "") if c else "", "Atleta": p.get("name", "") if p else "", "Cidade": p.get("city", "") if p else "", "Origem": "Fora" if p and p.get("is_outside") else "Linhares"})
        df = pd.DataFrame(rows)
        st.dataframe(df.sort_values(["Categoria", "Atleta"]), use_container_width=True, hide_index=True) if not df.empty else st.info("Sem inscritos.")


def admin_ok():
    if st.session_state.get("admin_ok"):
        return True
    st.markdown("### Acesso administrativo")
    pwd = st.text_input("Senha do admin", type="password")
    if st.button("Entrar"):
        correct = get_secret("ADMIN_PASSWORD") or get_secret("ADMIN_TOKEN") or "1234"
        if pwd == correct:
            st.session_state.admin_ok = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
    return False


def admin_tournaments():
    st.markdown("### Criar torneio")
    with st.form("create_t"):
        name = st.text_input("Nome", "Open Teste Tênis Linhares")
        a, b = st.columns(2)
        start = a.date_input("Data inicial", date.today())
        end = b.date_input("Data final", date.today() + timedelta(days=6))
        if st.form_submit_button("Criar torneio"):
            if end < start:
                st.error("Data final inválida.")
            else:
                t = insert(TABLE_TOURNAMENTS, {"name": name.strip(), "start_date": start.isoformat(), "end_date": end.isoformat(), "active": True})
                create_default_categories(t["id"])
                st.success("Torneio criado."); st.rerun()
    df = pd.DataFrame(tournaments())
    st.dataframe(df, use_container_width=True, hide_index=True) if not df.empty else st.info("Nenhum torneio.")


def admin_categories(tid):
    st.markdown("### Categorias")
    with st.form("cat"):
        a, b = st.columns([3, 1])
        name = a.text_input("Nome da categoria")
        limit = b.number_input("Limite", min_value=2, max_value=32, value=16)
        if st.form_submit_button("Adicionar"):
            insert(TABLE_CATEGORIES, {"tournament_id": tid, "name": name.strip(), "max_players": int(limit)})
            st.success("Categoria adicionada."); st.rerun()
    rows = []
    for c in categories(tid):
        rows.append({"id": c["id"], "Categoria": c["name"], "Limite": c["max_players"], "Inscritos": len(registrations(tid, c["id"]))})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def find_or_create_player(name, whatsapp, city, is_outside, unavailable):
    whatsapp = whatsapp.strip()
    existing = []
    if whatsapp:
        existing = data(sb().table(TABLE_PLAYERS).select("*").eq("whatsapp", whatsapp).execute())
    if existing:
        p = existing[0]
        update_by_id(TABLE_PLAYERS, p["id"], {"name": name.strip(), "city": city.strip(), "is_outside": bool(is_outside), "unavailable": unavailable.strip()})
        return p["id"]
    p = insert(TABLE_PLAYERS, {"name": name.strip(), "whatsapp": whatsapp, "city": city.strip(), "is_outside": bool(is_outside), "unavailable": unavailable.strip()})
    return p["id"]


def reg_exists(tid, cid, pid):
    return bool(data(sb().table(TABLE_REGISTRATIONS).select("id").eq("tournament_id", tid).eq("category_id", cid).eq("player_id", pid).execute()))


def admin_players(tid):
    st.markdown("### Atletas/Inscrições")
    cats = {c["name"]: c["id"] for c in categories(tid)}
    with st.form("player_form"):
        a, b = st.columns(2)
        name = a.text_input("Nome do atleta")
        whats = b.text_input("WhatsApp")
        c, d = st.columns(2)
        city = c.text_input("Cidade", "Linhares")
        outside = d.checkbox("Atleta de fora de Linhares")
        unavailable = st.text_area("Dias/horários que não pode jogar")
        selected = st.multiselect("Categorias", list(cats.keys()))
        if st.form_submit_button("Salvar inscrição"):
            if not name.strip() or not selected:
                st.error("Informe nome e categoria.")
            else:
                pid = find_or_create_player(name, whats, city, outside, unavailable)
                ok, errors = 0, []
                for cname in selected:
                    cid = cats[cname]
                    cat = category(cid)
                    if reg_exists(tid, cid, pid):
                        errors.append(f"{cname}: já inscrito")
                    elif len(registrations(tid, cid)) >= int(cat.get("max_players", 16)):
                        errors.append(f"{cname}: cheia")
                    else:
                        insert(TABLE_REGISTRATIONS, {"tournament_id": tid, "category_id": cid, "player_id": pid})
                        ok += 1
                if ok: st.success(f"{ok} inscrição(ões) salva(s).")
                if errors: st.warning(" | ".join(errors))
                st.rerun()
    rows = []
    for r in registrations(tid):
        p, c = player(r["player_id"]), category(r["category_id"])
        rows.append({"Categoria": c.get("name", "") if c else "", "Atleta": p.get("name", "") if p else "", "WhatsApp": p.get("whatsapp", "") if p else "", "Cidade": p.get("city", "") if p else "", "Origem": "Fora" if p and p.get("is_outside") else "Linhares", "Indisponibilidade": p.get("unavailable", "") if p else ""})
    df = pd.DataFrame(rows)
    st.dataframe(df.sort_values(["Categoria", "Atleta"]), use_container_width=True, hide_index=True) if not df.empty else st.info("Sem inscritos.")


def admin_brackets(tid):
    st.markdown("### Chaves")
    cid = category_selector(tid, "admin_cat")
    if not cid: return
    ps = registered_players(tid, cid)
    st.caption(f"{len(ps)} atletas inscritos nesta categoria.")
    if len(ps) < 2:
        st.warning("Cadastre pelo menos 2 atletas."); return
    a, b, c = st.columns(3)
    if a.button("Sortear chave", use_container_width=True):
        ids = [p["id"] for p in ps]; random.shuffle(ids); generate_bracket(tid, cid, ids); st.success("Chave sorteada."); st.rerun()
    if b.button("Apagar chave", use_container_width=True):
        delete_category_matches(tid, cid); st.warning("Chave apagada."); st.rerun()
    if c.button("Atualizar avanço", use_container_width=True):
        refresh_bracket(tid, cid); st.success("Atualizada."); st.rerun()
    opts = {p["name"]: p["id"] for p in ps}
    order_text = st.text_area("Ordem manual dos atletas", "\n".join(opts.keys()), height=220)
    if st.button("Gerar chave manual"):
        names = [x.strip() for x in order_text.splitlines() if x.strip()]
        unknown = [n for n in names if n not in opts]
        if unknown: st.error("Nomes não encontrados: " + ", ".join(unknown))
        else:
            ids = [opts[n] for n in names] + [p["id"] for p in ps if p["id"] not in [opts[n] for n in names]]
            generate_bracket(tid, cid, ids); st.success("Chave manual gerada."); st.rerun()
    df = bracket_df(tid, cid)
    st.dataframe(df, use_container_width=True, hide_index=True) if not df.empty else st.info("Chave ainda não gerada.")


def admin_schedule(tid):
    st.markdown("### Programação")
    st.info("Regra: 3 quadras, jogos de 1h30, seg-qui 16:00/17:30/19:00/20:30, sexta 15:30/17:00/18:30/20:00/21:30.")
    include_weekend = st.checkbox("Incluir sábado/domingo", value=True)
    a, b = st.columns(2)
    if a.button("Gerar programação automática", use_container_width=True):
        total, pending = generate_schedule(tid, include_weekend)
        st.success(f"{total} jogos agendados." if pending == 0 else f"{total} jogos agendados e {pending} sem horário."); st.rerun()
    if b.button("Limpar programação", use_container_width=True):
        clear_schedule(tid); st.warning("Programação limpa."); st.rerun()
    df = schedule_df(tid)
    st.dataframe(df, use_container_width=True, hide_index=True) if not df.empty else st.info("Sem programação.")

    st.markdown("#### Editar manualmente")
    ms = matches(tid)
    if ms:
        labels = {f"Jogo {m['id']} • {category_name(m['category_id'])} • {m['round_name']} • {match_label(m)}": m["id"] for m in ms}
        mid = labels[st.selectbox("Jogo", list(labels.keys()))]
        m = select_by_id(TABLE_MATCHES, mid)
        x, y, z = st.columns(3)
        default_date = datetime.strptime(m["scheduled_date"], "%Y-%m-%d").date() if m.get("scheduled_date") else date.today()
        nd = x.date_input("Data", default_date)
        nt = y.text_input("Horário", m.get("scheduled_time") or "18:00")
        nc = z.number_input("Quadra", min_value=1, max_value=3, value=int(m.get("court") or 1))
        if st.button("Salvar edição"):
            update_by_id(TABLE_MATCHES, mid, {"scheduled_date": nd.isoformat(), "scheduled_time": nt.strip(), "court": int(nc)})
            st.success("Jogo atualizado."); st.rerun()


def admin_results(tid):
    st.markdown("### Resultados")
    ms = matches(tid)
    if not ms:
        st.info("Gere uma chave primeiro."); return
    for m in ms:
        with st.expander(f"Jogo {m['id']} • {category_name(m['category_id'])} • {m['round_name']} • {match_label(m)}"):
            st.write(f"Status: **{m.get('status')}**")
            options = []
            if m.get("player1_id"): options.append((player_name(m["player1_id"]), m["player1_id"]))
            if m.get("player2_id"): options.append((player_name(m["player2_id"]), m["player2_id"]))
            score = st.text_input("Placar", value=m.get("score") or "", key=f"score_{m['id']}")
            if not options:
                st.info("Aguardando atletas."); continue
            labels = [o[0] for o in options]
            winner = dict(options)[st.selectbox("Vencedor", labels, key=f"win_{m['id']}")]
            a, b = st.columns(2)
            if a.button("Salvar resultado", key=f"save_{m['id']}", use_container_width=True):
                update_by_id(TABLE_MATCHES, m["id"], {"winner_id": winner, "score": score.strip(), "status": "finalizado"})
                refresh_bracket(tid, m["category_id"]); st.success("Resultado salvo e vencedor avançado."); st.rerun()
            if b.button("WO para vencedor", key=f"wo_{m['id']}", use_container_width=True):
                update_by_id(TABLE_MATCHES, m["id"], {"winner_id": winner, "score": "WO", "status": "WO"})
                refresh_bracket(tid, m["category_id"]); st.success("WO salvo."); st.rerun()


def admin_page():
    if not admin_ok(): return
    tid = tournament_selector()
    tabs = st.tabs(["Torneios", "Categorias", "Atletas", "Chaves", "Programação", "Resultados"])
    with tabs[0]: admin_tournaments()
    if tid:
        with tabs[1]: admin_categories(tid)
        with tabs[2]: admin_players(tid)
        with tabs[3]: admin_brackets(tid)
        with tabs[4]: admin_schedule(tid)
        with tabs[5]: admin_results(tid)


def main():
    st.set_page_config(page_title="Tênis Linhares • Torneios Supabase", page_icon="🎾", layout="wide")
    apply_css(); header(); seed_if_empty()
    mode = st.sidebar.radio("Menu", ["Área pública", "Admin"])
    st.sidebar.caption("App teste separado. Só usa tabelas tl_* no Supabase.")
    public_page() if mode == "Área pública" else admin_page()


if __name__ == "__main__":
    main()
