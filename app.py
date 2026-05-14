import os
import math
import random
import re
import io
import csv
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st
from supabase import create_client


# ============================================================
# CONFIGURAÇÃO
# ============================================================

SUPABASE_URL = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD") or os.getenv("ADMIN_TOKEN") or "1234"

T_TOURNAMENTS = "tl_tournaments"
T_CATEGORIES = "tl_categories"
T_PLAYERS = "tl_players"
T_REGISTRATIONS = "tl_registrations"
T_MATCHES = "tl_matches"

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

WEEKDAY_TIMES = ["16:00", "17:30", "19:00", "20:30"]
FRIDAY_TIMES = ["15:30", "17:00", "18:30", "20:00", "21:30"]
WEEKEND_TIMES = ["08:00", "09:30", "11:00", "14:00", "15:30", "17:00", "18:30", "20:00"]


# ============================================================
# SUPABASE
# ============================================================

@st.cache_resource
def get_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("Configure SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY nas variáveis do Render.")
        st.stop()
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def sb():
    return get_supabase()


def response_data(resp):
    return getattr(resp, "data", None) or []


def first(rows):
    return rows[0] if rows else None


def insert_row(table, payload):
    rows = response_data(sb().table(table).insert(payload).execute())
    return first(rows)


def update_row(table, row_id, payload):
    return sb().table(table).update(payload).eq("id", row_id).execute()


def delete_matches_by_category(tournament_id, category_id):
    return (
        sb()
        .table(T_MATCHES)
        .delete()
        .eq("tournament_id", tournament_id)
        .eq("category_id", category_id)
        .execute()
    )


def get_by_id(table, row_id):
    if not row_id:
        return None
    rows = response_data(sb().table(table).select("*").eq("id", row_id).execute())
    return first(rows)


def get_tournaments():
    return response_data(sb().table(T_TOURNAMENTS).select("*").order("id", desc=True).execute())


def get_tournament(tournament_id):
    return get_by_id(T_TOURNAMENTS, tournament_id)


def get_categories(tournament_id):
    return response_data(
        sb()
        .table(T_CATEGORIES)
        .select("*")
        .eq("tournament_id", tournament_id)
        .order("name")
        .execute()
    )


def get_category(category_id):
    return get_by_id(T_CATEGORIES, category_id)


def get_player(player_id):
    return get_by_id(T_PLAYERS, player_id)


def get_matches(tournament_id, category_id=None):
    q = (
        sb()
        .table(T_MATCHES)
        .select("*")
        .eq("tournament_id", tournament_id)
        .order("round_num")
        .order("position")
    )
    if category_id:
        q = q.eq("category_id", category_id)
    return response_data(q.execute())


def get_match(match_id):
    return get_by_id(T_MATCHES, match_id)


def get_registrations(tournament_id, category_id=None):
    q = (
        sb()
        .table(T_REGISTRATIONS)
        .select("*, player:tl_players(*), category:tl_categories(*)")
        .eq("tournament_id", tournament_id)
    )
    if category_id:
        q = q.eq("category_id", category_id)
    return response_data(q.execute())


def registration_exists(tournament_id, category_id, player_id):
    rows = response_data(
        sb()
        .table(T_REGISTRATIONS)
        .select("id")
        .eq("tournament_id", tournament_id)
        .eq("category_id", category_id)
        .eq("player_id", player_id)
        .execute()
    )
    return bool(rows)


def get_player_by_whatsapp(whatsapp):
    if not whatsapp:
        return None
    rows = response_data(sb().table(T_PLAYERS).select("*").eq("whatsapp", whatsapp).execute())
    return first(rows)


def normalize_name(name):
    return re.sub(r"\s+", " ", str(name or "").strip()).lower()


def get_all_players():
    return response_data(sb().table(T_PLAYERS).select("*").execute())


def get_player_by_name(name):
    target = normalize_name(name)
    if not target:
        return None

    for player in get_all_players():
        if normalize_name(player.get("name")) == target:
            return player

    return None


def clean_imported_name(line):
    text = str(line or "").strip()
    text = re.sub(r"^\s*[\-\*\•\d\.\)\(]+\s*", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    bad_words = [
        "categoria", "chave", "quadra", "horário", "horario", "data",
        "rodada", "jogo", "confronto", "vencedor", "semifinal", "final",
        "oitavas", "quartas", "programação", "programacao"
    ]

    if not text:
        return ""

    lowered = text.lower()
    if lowered in ["bye", "wo", "w.o", "w.o."]:
        return "BYE"

    if any(lowered == word for word in bad_words):
        return ""

    if len(text) <= 1:
        return ""

    return text


def extract_text_from_uploaded_file(uploaded_file):
    if not uploaded_file:
        return ""

    name = uploaded_file.name.lower()
    raw = uploaded_file.read()

    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw))
            pages = []
            for page in reader.pages:
                pages.append(page.extract_text() or "")
            return "\n".join(pages)
        except Exception as exc:
            st.error("Não consegui ler esse PDF automaticamente. Tente enviar TXT/CSV ou colar os nomes manualmente.")
            st.code(str(exc))
            return ""

    try:
        return raw.decode("utf-8")
    except Exception:
        try:
            return raw.decode("latin-1")
        except Exception:
            return ""


def extract_names_from_csv_text(text):
    names = []
    sample = text.strip()
    if not sample:
        return names

    try:
        reader = csv.DictReader(io.StringIO(sample))
        if reader.fieldnames:
            possible = ["nome", "name", "atleta", "jogador", "player"]
            field = None
            for f in reader.fieldnames:
                if normalize_name(f) in possible:
                    field = f
                    break
            if field:
                for row in reader:
                    nm = clean_imported_name(row.get(field, ""))
                    if nm and nm.upper() != "BYE":
                        names.append(nm)
                return names
    except Exception:
        pass

    return []


def extract_names_from_free_text(text):
    names = []
    csv_names = extract_names_from_csv_text(text)
    if csv_names:
        return csv_names

    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Se a linha é um confronto, pega os dois lados.
        parts = re.split(r"\s+(?:x|X|vs|VS|v\.|V\.|×)\s+", line)
        if len(parts) >= 2:
            for part in parts[:2]:
                nm = clean_imported_name(part)
                if nm and nm.upper() != "BYE":
                    names.append(nm)
            continue

        nm = clean_imported_name(line)
        if nm and nm.upper() != "BYE":
            names.append(nm)

    seen = set()
    unique = []
    for name in names:
        key = normalize_name(name)
        if key and key not in seen:
            seen.add(key)
            unique.append(name)

    return unique


def parse_external_bracket_lines(text):
    """
    Aceita:
    João x Pedro
    Carlos x BYE
    Maria x Ana

    Retorna lista de pares [(nome1, nome2), ...].
    """
    pairs = []

    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        parts = re.split(r"\s+(?:x|X|vs|VS|v\.|V\.|×)\s+", line)
        if len(parts) >= 2:
            p1 = clean_imported_name(parts[0])
            p2 = clean_imported_name(parts[1])
            if p1 or p2:
                pairs.append((p1 or "BYE", p2 or "BYE"))

    return pairs


def find_or_create_player_by_name_only(name, city="Linhares", is_outside=False, unavailable=""):
    existing = get_player_by_name(name)
    if existing:
        # Atualiza dados básicos sem duplicar atleta.
        update_row(
            T_PLAYERS,
            existing["id"],
            {
                "name": existing.get("name") or name.strip(),
                "city": existing.get("city") or city.strip(),
                "is_outside": bool(existing.get("is_outside") or is_outside),
                "unavailable": existing.get("unavailable") or unavailable.strip(),
            },
        )
        return existing["id"]

    player = insert_row(
        T_PLAYERS,
        {
            "name": name.strip(),
            "whatsapp": "",
            "city": city.strip(),
            "is_outside": bool(is_outside),
            "unavailable": unavailable.strip(),
        },
    )
    return player["id"] if player else None


def ensure_registration(tournament_id, category_id, player_id):
    if registration_exists(tournament_id, category_id, player_id):
        return False

    cat = get_category(category_id)
    current_count = len(get_registrations(tournament_id, category_id))

    if current_count >= int(cat.get("max_players", 16)):
        return None

    insert_row(
        T_REGISTRATIONS,
        {
            "tournament_id": tournament_id,
            "category_id": category_id,
            "player_id": player_id,
        },
    )
    return True


def generate_bracket_from_slots(tournament_id, category_id, slots):
    """
    Gera chave preservando posições e BYEs importados.
    Exemplo slots:
    [joao_id, pedro_id, carlos_id, None]
    """
    non_empty = [pid for pid in slots if pid]

    if len(non_empty) < 2:
        raise ValueError("Precisa de pelo menos 2 atletas para gerar a chave.")

    size = max(2, next_power_two(len(slots)))
    if size > 32:
        raise ValueError("Este app teste suporta até 32 posições por categoria.")

    slots = list(slots) + [None] * (size - len(slots))
    names = round_names(size)
    rounds = int(math.log2(size))

    delete_matches_by_category(tournament_id, category_id)

    previous_match_ids = []

    for round_num in range(1, rounds + 1):
        match_count = size // (2 ** round_num)
        current_ids = []
        round_name = names[round_num - 1]

        for position in range(match_count):
            if round_num == 1:
                p1 = slots[position * 2]
                p2 = slots[position * 2 + 1]
                source1 = None
                source2 = None
                winner = None
                status = "pendente"

                if p1 and not p2:
                    winner = p1
                    status = "bye"
                elif p2 and not p1:
                    winner = p2
                    status = "bye"
            else:
                p1 = None
                p2 = None
                source1 = previous_match_ids[position * 2]
                source2 = previous_match_ids[position * 2 + 1]
                winner = None
                status = "pendente"

            created = insert_row(
                T_MATCHES,
                {
                    "tournament_id": tournament_id,
                    "category_id": category_id,
                    "round_num": round_num,
                    "round_name": round_name,
                    "position": position + 1,
                    "player1_id": p1,
                    "player2_id": p2,
                    "source1_match_id": source1,
                    "source2_match_id": source2,
                    "winner_id": winner,
                    "status": status,
                },
            )

            if created:
                current_ids.append(created["id"])

        previous_match_ids = current_ids

    refresh_bracket(tournament_id, category_id)


# ============================================================
# VISUAL
# ============================================================

def apply_css():
    st.markdown(
        """
        <style>
        .stApp {
            background: radial-gradient(circle at top, #1b301f 0%, #0d1110 48%, #070907 100%);
            color: #f7fff7;
        }
        section[data-testid="stSidebar"] {
            background-color: #0b0f0d;
        }
        .tl-card {
            background: rgba(21,28,24,.94);
            border: 1px solid rgba(204,255,0,.24);
            border-radius: 20px;
            padding: 20px;
            margin-bottom: 18px;
            box-shadow: 0 12px 28px rgba(0,0,0,.28);
        }
        .tl-title {
            color: #CCFF00;
            font-size: 30px;
            font-weight: 900;
            margin: 0;
        }
        .tl-sub {
            color: #e3f4df;
            font-size: 15px;
            margin-top: 5px;
        }
        .tl-badge {
            display: inline-block;
            padding: 5px 10px;
            margin: 8px 4px 0 0;
            color: #CCFF00;
            border: 1px solid rgba(204,255,0,.35);
            background: rgba(204,255,0,.12);
            border-radius: 999px;
            font-size: 12px;
            font-weight: 800;
        }
        div[data-testid="stMetric"] {
            background: rgba(21,28,24,.94);
            border: 1px solid rgba(204,255,0,.22);
            padding: 14px;
            border-radius: 18px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def header():
    st.markdown(
        """
        <div class="tl-card">
            <p class="tl-title">Tênis Linhares • Torneios</p>
            <div class="tl-sub">App teste separado com Supabase, chaves, programação automática e avanço de fase.</div>
            <span class="tl-badge">3 quadras</span>
            <span class="tl-badge">1h30 por jogo</span>
            <span class="tl-badge">Chave manual</span>
            <span class="tl-badge">Sorteio automático</span>
            <span class="tl-badge">Vencedor avança sozinho</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# REGRAS DE TORNEIO
# ============================================================

def create_default_categories(tournament_id):
    existing = {c["name"] for c in get_categories(tournament_id)}
    for name in DEFAULT_CATEGORIES:
        if name not in existing:
            insert_row(
                T_CATEGORIES,
                {
                    "tournament_id": tournament_id,
                    "name": name,
                    "max_players": 16,
                },
            )


def seed_if_empty():
    if get_tournaments():
        return

    tournament = insert_row(
        T_TOURNAMENTS,
        {
            "name": "Torneio Teste Tênis Linhares",
            "start_date": date.today().isoformat(),
            "end_date": (date.today() + timedelta(days=6)).isoformat(),
            "active": True,
        },
    )
    if tournament:
        create_default_categories(tournament["id"])


def next_power_two(n):
    if n <= 1:
        return 1
    return 2 ** math.ceil(math.log2(n))


def round_names(size):
    names = {
        2: ["Final"],
        4: ["Semifinal", "Final"],
        8: ["Quartas de final", "Semifinal", "Final"],
        16: ["Oitavas de final", "Quartas de final", "Semifinal", "Final"],
        32: ["32 avos", "Oitavas de final", "Quartas de final", "Semifinal", "Final"],
    }
    return names.get(size, [f"Rodada {i+1}" for i in range(int(math.log2(size)))])


def player_label(player_id):
    p = get_player(player_id)
    if not p:
        return "Aguardando"
    suffix = " • fora" if p.get("is_outside") else ""
    return f'{p.get("name", "Atleta")}{suffix}'


def category_label(category_id):
    c = get_category(category_id)
    return c.get("name", "") if c else ""


def match_label(match):
    p1 = player_label(match.get("player1_id"))
    p2 = player_label(match.get("player2_id"))

    if not match.get("player1_id") and match.get("source1_match_id"):
        p1 = f'Vencedor Jogo {match["source1_match_id"]}'
    if not match.get("player2_id") and match.get("source2_match_id"):
        p2 = f'Vencedor Jogo {match["source2_match_id"]}'

    return f"{p1} x {p2}"


def registered_players(tournament_id, category_id):
    regs = get_registrations(tournament_id, category_id)
    players = [r["player"] for r in regs if r.get("player")]
    return sorted(players, key=lambda p: p.get("name", ""))


def generate_bracket(tournament_id, category_id, ordered_player_ids):
    player_ids = [pid for pid in ordered_player_ids if pid]

    if len(player_ids) < 2:
        raise ValueError("Precisa de pelo menos 2 atletas para gerar a chave.")

    size = max(2, next_power_two(len(player_ids)))
    if size > 32:
        raise ValueError("Este app teste suporta até 32 atletas por categoria.")

    slots = player_ids + [None] * (size - len(player_ids))
    names = round_names(size)
    rounds = int(math.log2(size))

    delete_matches_by_category(tournament_id, category_id)

    previous_match_ids = []

    for round_num in range(1, rounds + 1):
        match_count = size // (2 ** round_num)
        current_ids = []
        round_name = names[round_num - 1]

        for position in range(match_count):
            if round_num == 1:
                p1 = slots[position * 2]
                p2 = slots[position * 2 + 1]
                source1 = None
                source2 = None
                winner = None
                status = "pendente"

                if p1 and not p2:
                    winner = p1
                    status = "bye"
                elif p2 and not p1:
                    winner = p2
                    status = "bye"
            else:
                p1 = None
                p2 = None
                source1 = previous_match_ids[position * 2]
                source2 = previous_match_ids[position * 2 + 1]
                winner = None
                status = "pendente"

            created = insert_row(
                T_MATCHES,
                {
                    "tournament_id": tournament_id,
                    "category_id": category_id,
                    "round_num": round_num,
                    "round_name": round_name,
                    "position": position + 1,
                    "player1_id": p1,
                    "player2_id": p2,
                    "source1_match_id": source1,
                    "source2_match_id": source2,
                    "winner_id": winner,
                    "status": status,
                },
            )

            if created:
                current_ids.append(created["id"])

        previous_match_ids = current_ids

    refresh_bracket(tournament_id, category_id)


def refresh_bracket(tournament_id, category_id):
    matches = get_matches(tournament_id, category_id)
    winners = {m["id"]: m.get("winner_id") for m in matches}

    for match in matches:
        payload = {}

        if match.get("source1_match_id"):
            payload["player1_id"] = winners.get(match["source1_match_id"])

        if match.get("source2_match_id"):
            payload["player2_id"] = winners.get(match["source2_match_id"])

        if payload:
            update_row(T_MATCHES, match["id"], payload)

    matches = get_matches(tournament_id, category_id)

    for match in matches:
        if match.get("source1_match_id") or match.get("source2_match_id"):
            continue

        if match.get("status") == "finalizado":
            continue

        if match.get("player1_id") and not match.get("player2_id"):
            update_row(
                T_MATCHES,
                match["id"],
                {"winner_id": match["player1_id"], "status": "bye"},
            )
        elif match.get("player2_id") and not match.get("player1_id"):
            update_row(
                T_MATCHES,
                match["id"],
                {"winner_id": match["player2_id"], "status": "bye"},
            )


def match_players(match):
    players = []
    if match.get("player1_id"):
        players.append(match["player1_id"])
    if match.get("player2_id"):
        players.append(match["player2_id"])
    return players


def has_outside_player(match):
    for player_id in match_players(match):
        p = get_player(player_id)
        if p and p.get("is_outside"):
            return True
    return False


def parse_datetime(day, hour):
    return datetime.strptime(f"{day} {hour}", "%Y-%m-%d %H:%M")


def build_slots(start_date, end_date, include_weekend=True):
    slots = []
    current = datetime.strptime(start_date, "%Y-%m-%d").date()
    final = datetime.strptime(end_date, "%Y-%m-%d").date()

    while current <= final:
        weekday = current.weekday()

        if weekday in [0, 1, 2, 3]:
            times = WEEKDAY_TIMES
        elif weekday == 4:
            times = FRIDAY_TIMES
        elif include_weekend:
            times = WEEKEND_TIMES
        else:
            times = []

        for hour in times:
            for court in [1, 2, 3]:
                slots.append(
                    {
                        "date": current.isoformat(),
                        "time": hour,
                        "court": court,
                        "dt": parse_datetime(current.isoformat(), hour),
                        "weekday": weekday,
                    }
                )

        current += timedelta(days=1)

    return slots


def clear_schedule(tournament_id):
    for match in get_matches(tournament_id):
        update_row(
            T_MATCHES,
            match["id"],
            {
                "scheduled_date": None,
                "scheduled_time": None,
                "court": None,
            },
        )


def generate_schedule(tournament_id, include_weekend=True):
    tournament = get_tournament(tournament_id)
    if not tournament:
        raise ValueError("Torneio não encontrado.")

    clear_schedule(tournament_id)

    slots = build_slots(tournament["start_date"], tournament["end_date"], include_weekend)
    matches = get_matches(tournament_id)

    used_slots = set()
    player_busy = set()
    match_datetime = {}
    pending = []

    def slot_score(slot, match):
        score = slot["dt"].timestamp()

        if has_outside_player(match):
            if slot["weekday"] == 4:
                score -= 10_000_000
            elif slot["weekday"] in [5, 6]:
                score -= 9_000_000

        return score

    matches = sorted(
        matches,
        key=lambda m: (m.get("round_num", 1), m.get("category_id", 0), m.get("position", 0)),
    )

    for match in matches:
        assigned = False
        players = match_players(match)

        for slot in sorted(slots, key=lambda s: slot_score(s, match)):
            slot_key = (slot["date"], slot["time"], slot["court"])

            if slot_key in used_slots:
                continue

            conflict = any((pid, slot["date"], slot["time"]) in player_busy for pid in players)
            if conflict:
                continue

            too_early = False
            for source_id in [match.get("source1_match_id"), match.get("source2_match_id")]:
                if source_id and source_id in match_datetime:
                    if slot["dt"] < match_datetime[source_id] + timedelta(minutes=90):
                        too_early = True
                        break

            if too_early:
                continue

            update_row(
                T_MATCHES,
                match["id"],
                {
                    "scheduled_date": slot["date"],
                    "scheduled_time": slot["time"],
                    "court": slot["court"],
                },
            )

            used_slots.add(slot_key)
            match_datetime[match["id"]] = slot["dt"]

            for player_id in players:
                player_busy.add((player_id, slot["date"], slot["time"]))

            assigned = True
            break

        if not assigned:
            pending.append(match["id"])

    return len(matches) - len(pending), len(pending)


# ============================================================
# DATAFRAMES
# ============================================================

def schedule_df(tournament_id):
    rows = []

    for match in get_matches(tournament_id):
        rows.append(
            {
                "Data": match.get("scheduled_date") or "",
                "Horário": match.get("scheduled_time") or "",
                "Quadra": match.get("court") or "",
                "Categoria": category_label(match["category_id"]),
                "Fase": match.get("round_name") or "",
                "Jogo": match["id"],
                "Confronto": match_label(match),
                "Placar": match.get("score") or "",
                "Vencedor": player_label(match.get("winner_id")) if match.get("winner_id") else "",
                "Status": match.get("status") or "",
            }
        )

    df = pd.DataFrame(rows)

    if not df.empty:
        df = df.sort_values(["Data", "Horário", "Quadra"], na_position="last")

    return df


def bracket_df(tournament_id, category_id):
    rows = []

    for match in get_matches(tournament_id, category_id):
        rows.append(
            {
                "Fase": match.get("round_name") or "",
                "Jogo": match["id"],
                "Confronto": match_label(match),
                "Data": match.get("scheduled_date") or "",
                "Horário": match.get("scheduled_time") or "",
                "Quadra": match.get("court") or "",
                "Placar": match.get("score") or "",
                "Vencedor": player_label(match.get("winner_id")) if match.get("winner_id") else "",
                "Status": match.get("status") or "",
            }
        )

    return pd.DataFrame(rows)


# ============================================================
# COMPONENTES
# ============================================================

def tournament_selector(key):
    tournaments = get_tournaments()

    if not tournaments:
        st.warning("Nenhum torneio cadastrado.")
        return None

    labels = {
        f'{t["name"]} • {t["start_date"]} a {t["end_date"]}': t["id"]
        for t in tournaments
    }

    selected = st.selectbox("Torneio", list(labels.keys()), key=key)
    return labels[selected]


def category_selector(tournament_id, key):
    cats = get_categories(tournament_id)

    if not cats:
        st.warning("Nenhuma categoria cadastrada.")
        return None

    labels = {c["name"]: c["id"] for c in cats}
    selected = st.selectbox("Categoria", list(labels.keys()), key=key)
    return labels[selected]


# ============================================================
# ÁREA PÚBLICA
# ============================================================

def public_page():
    tournament_id = tournament_selector("public_tournament")
    if not tournament_id:
        return

    tournament = get_tournament(tournament_id)
    st.subheader(tournament["name"])

    regs = get_registrations(tournament_id)
    matches = get_matches(tournament_id)
    finished = [m for m in matches if m.get("status") in ["finalizado", "bye", "WO"]]

    c1, c2, c3 = st.columns(3)
    c1.metric("Inscritos", len(regs))
    c2.metric("Jogos", len(matches))
    c3.metric("Finalizados/bye", len(finished))

    tab1, tab2, tab3 = st.tabs(["Programação", "Chaves", "Inscritos"])

    with tab1:
        df = schedule_df(tournament_id)
        if df.empty:
            st.info("Programação ainda não gerada.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tab2:
        category_id = category_selector(tournament_id, "public_category")
        if category_id:
            df = bracket_df(tournament_id, category_id)
            if df.empty:
                st.info("Chave ainda não gerada para esta categoria.")
            else:
                st.dataframe(df, use_container_width=True, hide_index=True)

    with tab3:
        rows = []
        for reg in get_registrations(tournament_id):
            p = reg.get("player") or {}
            c = reg.get("category") or {}
            rows.append(
                {
                    "Categoria": c.get("name", ""),
                    "Atleta": p.get("name", ""),
                    "Cidade": p.get("city", ""),
                    "Origem": "Fora" if p.get("is_outside") else "Linhares",
                }
            )

        df = pd.DataFrame(rows)
        if df.empty:
            st.info("Nenhum inscrito.")
        else:
            st.dataframe(df.sort_values(["Categoria", "Atleta"]), use_container_width=True, hide_index=True)


# ============================================================
# ADMIN
# ============================================================

def admin_login():
    if st.session_state.get("admin_ok"):
        return True

    st.subheader("Área administrativa")
    password = st.text_input("Senha do admin", type="password")

    if st.button("Entrar"):
        if password == ADMIN_PASSWORD:
            st.session_state["admin_ok"] = True
            st.success("Acesso liberado.")
            st.rerun()
        else:
            st.error("Senha incorreta.")

    return False


def admin_tournaments():
    st.subheader("Criar torneio")

    with st.form("new_tournament"):
        name = st.text_input("Nome do torneio", value="Open Teste Tênis Linhares")

        col1, col2 = st.columns(2)
        start = col1.date_input("Data inicial", value=date.today())
        end = col2.date_input("Data final", value=date.today() + timedelta(days=6))

        submitted = st.form_submit_button("Criar torneio")

        if submitted:
            if end < start:
                st.error("Data final não pode ser anterior à inicial.")
            else:
                tournament = insert_row(
                    T_TOURNAMENTS,
                    {
                        "name": name.strip(),
                        "start_date": start.isoformat(),
                        "end_date": end.isoformat(),
                        "active": True,
                    },
                )

                if tournament:
                    create_default_categories(tournament["id"])
                    st.success("Torneio criado.")
                    st.rerun()

    df = pd.DataFrame(get_tournaments())
    if not df.empty:
        st.dataframe(
            df[["id", "name", "start_date", "end_date", "active"]],
            use_container_width=True,
            hide_index=True,
        )


def admin_categories(tournament_id):
    st.subheader("Categorias")

    with st.form("new_category"):
        col1, col2 = st.columns([3, 1])
        name = col1.text_input("Nova categoria")
        limit = col2.number_input("Limite", min_value=2, max_value=32, value=16)
        submitted = st.form_submit_button("Adicionar categoria")

        if submitted:
            if not name.strip():
                st.error("Digite o nome da categoria.")
            else:
                insert_row(
                    T_CATEGORIES,
                    {
                        "tournament_id": tournament_id,
                        "name": name.strip(),
                        "max_players": int(limit),
                    },
                )
                st.success("Categoria adicionada.")
                st.rerun()

    rows = []
    for cat in get_categories(tournament_id):
        rows.append(
            {
                "id": cat["id"],
                "Categoria": cat["name"],
                "Limite": cat["max_players"],
                "Inscritos": len(get_registrations(tournament_id, cat["id"])),
            }
        )

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def find_or_create_player(name, whatsapp, city, is_outside, unavailable):
    whatsapp = whatsapp.strip()

    existing = get_player_by_whatsapp(whatsapp) if whatsapp else None

    # Se não tiver WhatsApp, evita duplicar pelo nome.
    if not existing and not whatsapp:
        existing = get_player_by_name(name)

    if existing:
        update_row(
            T_PLAYERS,
            existing["id"],
            {
                "name": name.strip(),
                "city": city.strip() or existing.get("city"),
                "is_outside": bool(is_outside),
                "unavailable": unavailable.strip() or existing.get("unavailable"),
            },
        )
        return existing["id"]

    player = insert_row(
        T_PLAYERS,
        {
            "name": name.strip(),
            "whatsapp": whatsapp,
            "city": city.strip(),
            "is_outside": bool(is_outside),
            "unavailable": unavailable.strip(),
        },
    )

    return player["id"] if player else None


def admin_players(tournament_id):
    st.subheader("Atletas e inscrições")

    cats = get_categories(tournament_id)
    cat_map = {c["name"]: c["id"] for c in cats}

    with st.form("new_player"):
        col1, col2 = st.columns(2)
        name = col1.text_input("Nome do atleta")
        whatsapp = col2.text_input("WhatsApp")

        col3, col4 = st.columns(2)
        city = col3.text_input("Cidade", value="Linhares")
        is_outside = col4.checkbox("Atleta de fora de Linhares")

        unavailable = st.text_area(
            "Restrição de horário",
            placeholder="Ex.: só chega sexta depois de 19h",
        )

        selected_categories = st.multiselect("Categorias", list(cat_map.keys()))

        submitted = st.form_submit_button("Salvar inscrição")

        if submitted:
            if not name.strip():
                st.error("Digite o nome do atleta.")
            elif not selected_categories:
                st.error("Selecione pelo menos uma categoria.")
            else:
                player_id = find_or_create_player(name, whatsapp, city, is_outside, unavailable)
                saved = 0
                warnings = []

                for cat_name in selected_categories:
                    category_id = cat_map[cat_name]
                    cat = get_category(category_id)
                    count = len(get_registrations(tournament_id, category_id))

                    if registration_exists(tournament_id, category_id, player_id):
                        warnings.append(f"{cat_name}: atleta já inscrito.")
                    elif count >= int(cat.get("max_players", 16)):
                        warnings.append(f"{cat_name}: categoria cheia.")
                    else:
                        insert_row(
                            T_REGISTRATIONS,
                            {
                                "tournament_id": tournament_id,
                                "category_id": category_id,
                                "player_id": player_id,
                            },
                        )
                        saved += 1

                if saved:
                    st.success(f"{saved} inscrição(ões) salva(s).")
                if warnings:
                    st.warning(" | ".join(warnings))

                st.rerun()

    rows = []
    for reg in get_registrations(tournament_id):
        p = reg.get("player") or {}
        c = reg.get("category") or {}

        rows.append(
            {
                "Categoria": c.get("name", ""),
                "Atleta": p.get("name", ""),
                "WhatsApp": p.get("whatsapp", ""),
                "Cidade": p.get("city", ""),
                "Origem": "Fora" if p.get("is_outside") else "Linhares",
                "Restrição": p.get("unavailable", ""),
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        st.dataframe(df.sort_values(["Categoria", "Atleta"]), use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum atleta inscrito ainda.")

    admin_import_players_tools(tournament_id)



def admin_import_players_tools(tournament_id):
    st.markdown("---")
    st.subheader("Importações e backup de atletas")

    cats = get_categories(tournament_id)
    cat_map = {c["name"]: c["id"] for c in cats}

    with st.expander("Importar lista de inscritos por texto, TXT, CSV ou PDF", expanded=False):
        if not cat_map:
            st.warning("Crie uma categoria antes de importar atletas.")
        else:
            target_category_name = st.selectbox("Categoria de destino", list(cat_map.keys()), key="bulk_target_category")
            default_city = st.text_input("Cidade padrão", value="Linhares", key="bulk_city")
            default_outside = st.checkbox("Marcar todos como atletas de fora", value=False, key="bulk_outside")
            default_unavailable = st.text_area("Restrição padrão de horário", value="", key="bulk_unavailable")

            uploaded = st.file_uploader(
                "Subir lista em TXT, CSV ou PDF",
                type=["txt", "csv", "pdf"],
                key="bulk_file",
            )

            file_text = extract_text_from_uploaded_file(uploaded) if uploaded else ""

            pasted = st.text_area(
                "Ou cole os nomes aqui, um por linha",
                value=file_text,
                height=180,
                key="bulk_pasted_names",
                placeholder="João Silva\nPedro Santos\nCarlos Oliveira",
            )

            names = extract_names_from_free_text(pasted)

            if names:
                st.caption(f"{len(names)} nome(s) encontrado(s). Revise antes de importar.")
                st.dataframe(pd.DataFrame({"Atleta": names}), use_container_width=True, hide_index=True)
            else:
                st.info("Cole uma lista ou envie um arquivo para visualizar os nomes.")

            if st.button("Importar atletas para a categoria", key="bulk_import_button"):
                category_id = cat_map[target_category_name]
                saved = 0
                repeated = 0
                full = 0

                for name in names:
                    player_id = find_or_create_player_by_name_only(
                        name,
                        city=default_city,
                        is_outside=default_outside,
                        unavailable=default_unavailable,
                    )
                    result = ensure_registration(tournament_id, category_id, player_id)

                    if result is True:
                        saved += 1
                    elif result is False:
                        repeated += 1
                    else:
                        full += 1

                if saved:
                    st.success(f"{saved} atleta(s) importado(s).")
                if repeated:
                    st.warning(f"{repeated} atleta(s) já estavam inscritos.")
                if full:
                    st.error(f"{full} atleta(s) não entraram porque a categoria atingiu o limite.")
                st.rerun()

    with st.expander("Buscar atletas de torneios anteriores / backup", expanded=False):
        tournaments = get_tournaments()
        other_tournaments = [t for t in tournaments if t["id"] != tournament_id]

        if not other_tournaments:
            st.info("Ainda não existe outro torneio para copiar atletas.")
        elif not cat_map:
            st.warning("Crie uma categoria neste torneio antes de copiar atletas.")
        else:
            source_map = {
                f'{t["name"]} • {t["start_date"]} a {t["end_date"]}': t["id"]
                for t in other_tournaments
            }
            source_label = st.selectbox("Torneio de origem", list(source_map.keys()), key="backup_source_tournament")
            source_id = source_map[source_label]

            source_cats = get_categories(source_id)
            source_cat_map = {"Todas as categorias": None}
            source_cat_map.update({c["name"]: c["id"] for c in source_cats})

            source_cat_label = st.selectbox("Categoria de origem", list(source_cat_map.keys()), key="backup_source_category")
            source_cat_id = source_cat_map[source_cat_label]

            target_cat_names = st.multiselect(
                "Categoria(s) de destino neste torneio",
                list(cat_map.keys()),
                key="backup_target_categories",
            )

            source_regs = get_registrations(source_id, source_cat_id)

            preview_rows = []
            for reg in source_regs:
                p = reg.get("player") or {}
                c = reg.get("category") or {}
                preview_rows.append(
                    {
                        "Categoria origem": c.get("name", ""),
                        "Atleta": p.get("name", ""),
                        "Cidade": p.get("city", ""),
                        "Origem": "Fora" if p.get("is_outside") else "Linhares",
                    }
                )

            if preview_rows:
                st.caption(f"{len(preview_rows)} atleta(s) encontrado(s) no backup.")
                st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum atleta encontrado nessa seleção.")

            if st.button("Copiar atletas selecionados para este torneio", key="copy_backup_button"):
                if not target_cat_names:
                    st.error("Escolha pelo menos uma categoria de destino.")
                else:
                    saved = 0
                    repeated = 0
                    full = 0

                    for reg in source_regs:
                        player = reg.get("player")
                        if not player:
                            continue

                        for target_name in target_cat_names:
                            target_category_id = cat_map[target_name]
                            result = ensure_registration(tournament_id, target_category_id, player["id"])

                            if result is True:
                                saved += 1
                            elif result is False:
                                repeated += 1
                            else:
                                full += 1

                    if saved:
                        st.success(f"{saved} inscrição(ões) copiada(s) do backup.")
                    if repeated:
                        st.warning(f"{repeated} inscrição(ões) já existiam.")
                    if full:
                        st.error(f"{full} inscrição(ões) não entraram por limite de categoria.")
                    st.rerun()


def admin_brackets(tournament_id):
    st.subheader("Chaves")

    category_id = category_selector(tournament_id, "admin_bracket_cat")
    if not category_id:
        return

    players = registered_players(tournament_id, category_id)
    st.caption(f"{len(players)} atleta(s) inscritos nesta categoria.")

    if len(players) < 2:
        st.warning("Cadastre pelo menos 2 atletas.")
        return

    name_to_id = {p["name"]: p["id"] for p in players}

    col1, col2, col3 = st.columns(3)

    if col1.button("Sortear chave", use_container_width=True):
        player_ids = [p["id"] for p in players]
        random.shuffle(player_ids)
        generate_bracket(tournament_id, category_id, player_ids)
        st.success("Chave sorteada.")
        st.rerun()

    if col2.button("Apagar chave", use_container_width=True):
        delete_matches_by_category(tournament_id, category_id)
        st.warning("Chave apagada.")
        st.rerun()

    if col3.button("Atualizar avanço", use_container_width=True):
        refresh_bracket(tournament_id, category_id)
        st.success("Avanço atualizado.")
        st.rerun()

    st.markdown("#### Chave manual")
    st.caption("Coloque um atleta por linha. O sistema cria 1x2, 3x4, 5x6...")

    manual_order = st.text_area(
        "Ordem dos atletas",
        value="\n".join([p["name"] for p in players]),
        height=220,
    )

    if st.button("Gerar chave manual"):
        names = [x.strip() for x in manual_order.splitlines() if x.strip()]
        unknown = [name for name in names if name not in name_to_id]

        if unknown:
            st.error("Nomes não encontrados: " + ", ".join(unknown))
        else:
            ordered_ids = [name_to_id[name] for name in names]
            missing = [p["id"] for p in players if p["id"] not in ordered_ids]
            generate_bracket(tournament_id, category_id, ordered_ids + missing)
            st.success("Chave manual gerada.")
            st.rerun()

    df = bracket_df(tournament_id, category_id)
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)

        csv_data = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Exportar chave atual em CSV",
            data=csv_data,
            file_name=f"chave_categoria_{category_id}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.markdown("---")
    st.subheader("Importar chave pronta de fora")

    with st.expander("Subir/colar chave já feita", expanded=False):
        st.caption("Use um confronto por linha. Exemplo: João Silva x Pedro Santos. Também aceita BYE.")

        uploaded_key = st.file_uploader(
            "Subir chave em TXT, CSV ou PDF",
            type=["txt", "csv", "pdf"],
            key=f"external_bracket_file_{category_id}",
        )

        key_file_text = extract_text_from_uploaded_file(uploaded_key) if uploaded_key else ""

        pasted_key = st.text_area(
            "Ou cole a chave aqui",
            value=key_file_text,
            height=220,
            key=f"external_bracket_text_{category_id}",
            placeholder="João Silva x Pedro Santos\nCarlos Oliveira x BYE\nMarcos Lima x André Souza",
        )

        pairs = parse_external_bracket_lines(pasted_key)

        if pairs:
            preview = pd.DataFrame(
                [{"Atleta 1": p1, "Atleta 2": p2} for p1, p2 in pairs]
            )
            st.caption(f"{len(pairs)} confronto(s) encontrado(s).")
            st.dataframe(preview, use_container_width=True, hide_index=True)
        else:
            st.info("Cole confrontos no formato 'Atleta 1 x Atleta 2' para pré-visualizar.")

        col_a, col_b = st.columns(2)

        with col_a:
            if st.button("Gerar chave importada", key=f"generate_external_bracket_{category_id}", use_container_width=True):
                if not pairs:
                    st.error("Nenhum confronto encontrado para importar.")
                else:
                    slots = []
                    imported = 0

                    for p1, p2 in pairs:
                        for player_name in [p1, p2]:
                            if normalize_name(player_name) in ["bye", "wo", "w.o", "w.o."]:
                                slots.append(None)
                                continue

                            player_id = find_or_create_player_by_name_only(player_name, city="Linhares")
                            ensure_registration(tournament_id, category_id, player_id)
                            slots.append(player_id)
                            imported += 1

                    generate_bracket_from_slots(tournament_id, category_id, slots)
                    st.success(f"Chave importada com {len(pairs)} confronto(s) e {imported} atleta(s).")
                    st.rerun()

        with col_b:
            names_from_key = extract_names_from_free_text(pasted_key)
            names_csv = pd.DataFrame({"Atleta": names_from_key}).to_csv(index=False).encode("utf-8")
            st.download_button(
                "Exportar nomes encontrados",
                data=names_csv,
                file_name=f"nomes_chave_categoria_{category_id}.csv",
                mime="text/csv",
                use_container_width=True,
            )


def admin_schedule(tournament_id):
    st.subheader("Programação automática")
    st.info(
        "Regra: 3 quadras, jogos de 1h30, seg-qui 16:00/17:30/19:00/20:30, sexta 15:30/17:00/18:30/20:00/21:30."
    )

    include_weekend = st.checkbox("Incluir sábado e domingo", value=True)

    col1, col2 = st.columns(2)

    if col1.button("Gerar programação automática", use_container_width=True):
        scheduled, pending = generate_schedule(tournament_id, include_weekend)
        if pending:
            st.warning(f"{scheduled} jogos agendados e {pending} ficaram sem horário.")
        else:
            st.success(f"{scheduled} jogos agendados.")
        st.rerun()

    if col2.button("Limpar programação", use_container_width=True):
        clear_schedule(tournament_id)
        st.warning("Programação apagada.")
        st.rerun()

    df = schedule_df(tournament_id)
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("#### Editar jogo manualmente")

    matches = get_matches(tournament_id)

    if matches:
        labels = {
            f'Jogo {m["id"]} • {category_label(m["category_id"])} • {match_label(m)}': m["id"]
            for m in matches
        }

        selected = st.selectbox("Jogo", list(labels.keys()))
        match_id = labels[selected]
        match = get_match(match_id)

        col1, col2, col3 = st.columns(3)

        default_date = (
            datetime.strptime(match["scheduled_date"], "%Y-%m-%d").date()
            if match.get("scheduled_date")
            else date.today()
        )

        new_date = col1.date_input("Data", value=default_date)
        new_time = col2.text_input("Horário", value=match.get("scheduled_time") or "18:00")
        new_court = col3.number_input("Quadra", min_value=1, max_value=3, value=int(match.get("court") or 1))

        if st.button("Salvar edição"):
            update_row(
                T_MATCHES,
                match_id,
                {
                    "scheduled_date": new_date.isoformat(),
                    "scheduled_time": new_time.strip(),
                    "court": int(new_court),
                },
            )
            st.success("Jogo atualizado.")
            st.rerun()


def admin_results(tournament_id):
    st.subheader("Resultados")

    matches = get_matches(tournament_id)

    if not matches:
        st.info("Nenhuma chave gerada.")
        return

    for match in matches:
        with st.expander(
            f'Jogo {match["id"]} • {category_label(match["category_id"])} • {match["round_name"]} • {match_label(match)}'
        ):
            st.write(f"Status: **{match.get('status')}**")

            if match.get("scheduled_date"):
                st.write(
                    f"Programado: **{match['scheduled_date']} às {match['scheduled_time']} • Quadra {match['court']}**"
                )

            options = []

            if match.get("player1_id"):
                options.append((player_label(match["player1_id"]), match["player1_id"]))

            if match.get("player2_id"):
                options.append((player_label(match["player2_id"]), match["player2_id"]))

            if not options:
                st.info("Aguardando definição dos atletas.")
                continue

            score = st.text_input("Placar", value=match.get("score") or "", key=f"score_{match['id']}")
            selected = st.selectbox("Vencedor", [x[0] for x in options], key=f"winner_{match['id']}")
            winner_id = dict(options)[selected]

            col1, col2 = st.columns(2)

            if col1.button("Salvar resultado", key=f"save_{match['id']}", use_container_width=True):
                update_row(
                    T_MATCHES,
                    match["id"],
                    {
                        "winner_id": winner_id,
                        "score": score.strip(),
                        "status": "finalizado",
                    },
                )
                refresh_bracket(tournament_id, match["category_id"])
                st.success("Resultado salvo. Vencedor avançou automaticamente.")
                st.rerun()

            if col2.button("WO para vencedor selecionado", key=f"wo_{match['id']}", use_container_width=True):
                update_row(
                    T_MATCHES,
                    match["id"],
                    {
                        "winner_id": winner_id,
                        "score": "WO",
                        "status": "WO",
                    },
                )
                refresh_bracket(tournament_id, match["category_id"])
                st.success("WO salvo.")
                st.rerun()


def admin_page():
    if not admin_login():
        return

    tournament_id = tournament_selector("admin_tournament")

    tabs = st.tabs(["Torneios", "Categorias", "Atletas", "Chaves", "Programação", "Resultados"])

    with tabs[0]:
        admin_tournaments()

    if tournament_id:
        with tabs[1]:
            admin_categories(tournament_id)
        with tabs[2]:
            admin_players(tournament_id)
        with tabs[3]:
            admin_brackets(tournament_id)
        with tabs[4]:
            admin_schedule(tournament_id)
        with tabs[5]:
            admin_results(tournament_id)


# ============================================================
# APP
# ============================================================

def main():
    st.set_page_config(
        page_title="Tênis Linhares • Torneios",
        page_icon="🎾",
        layout="wide",
    )

    apply_css()
    header()

    try:
        seed_if_empty()
    except Exception as exc:
        st.error("Erro ao conectar no Supabase ou carregar tabelas.")
        st.code(str(exc))
        st.stop()

    menu = st.sidebar.radio("Menu", ["Área pública", "Admin"])
    st.sidebar.caption("App teste separado do site oficial.")

    if menu == "Área pública":
        public_page()
    else:
        admin_page()


if __name__ == "__main__":
    main()
