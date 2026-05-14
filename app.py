import os
import math
import random
import time
import re
import io
import csv
import unicodedata
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


def execute_query(query, attempts=4):
    """
    Render gratuito + Supabase podem oscilar em algumas leituras.
    Esta função tenta novamente antes de mostrar erro ao usuário.
    """
    last_error = None

    for attempt in range(attempts):
        try:
            return query.execute()
        except Exception as exc:
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(0.7 * (attempt + 1))

    raise last_error


def response_data(resp):
    return getattr(resp, "data", None) or []


def first(rows):
    return rows[0] if rows else None


def insert_row(table, payload):
    rows = response_data(execute_query(sb().table(table).insert(payload)))
    return first(rows)


def update_row(table, row_id, payload):
    return execute_query(sb().table(table).update(payload).eq("id", row_id))


def update_matches_schedule_bulk(schedule_payloads):
    """
    Atualiza a programação em lote.
    Isso evita centenas de chamadas individuais ao Supabase.
    """
    if not schedule_payloads:
        return None

    return execute_query(
        sb()
        .table(T_MATCHES)
        .upsert(schedule_payloads, on_conflict="id")
    )


def delete_matches_by_category(tournament_id, category_id):
    return execute_query(
        sb()
        .table(T_MATCHES)
        .delete()
        .eq("tournament_id", tournament_id)
        .eq("category_id", category_id)
    )


def get_by_id(table, row_id):
    if not row_id:
        return None
    rows = response_data(execute_query(sb().table(table).select("*").eq("id", row_id)))
    return first(rows)


def get_tournaments():
    return response_data(execute_query(sb().table(T_TOURNAMENTS).select("*").order("id", desc=True)))


def get_tournament(tournament_id):
    return get_by_id(T_TOURNAMENTS, tournament_id)


def get_categories(tournament_id):
    return response_data(
        execute_query(
            sb()
            .table(T_CATEGORIES)
            .select("*")
            .eq("tournament_id", tournament_id)
            .order("name")
        )
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
    return response_data(execute_query(q))


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
    return response_data(execute_query(q))


def registration_exists(tournament_id, category_id, player_id):
    rows = response_data(
        execute_query(
            sb()
            .table(T_REGISTRATIONS)
            .select("id")
            .eq("tournament_id", tournament_id)
            .eq("category_id", category_id)
            .eq("player_id", player_id)
        )
    )
    return bool(rows)


def get_player_by_whatsapp(whatsapp):
    if not whatsapp:
        return None
    rows = response_data(execute_query(sb().table(T_PLAYERS).select("*").eq("whatsapp", whatsapp)))
    return first(rows)


def normalize_name(name):
    return re.sub(r"\s+", " ", str(name or "").strip()).lower()


def get_all_players():
    return response_data(execute_query(sb().table(T_PLAYERS).select("*")))


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
            text = "\n".join(pages).strip()
            if not text:
                st.warning(
                    "O PDF foi enviado, mas parece ser imagem/scan sem texto selecionável. "
                    "Cole os nomes/confrontos no campo abaixo ou envie TXT/CSV."
                )
            return text
        except Exception as exc:
            st.error("Não consegui ler esse PDF automaticamente. Tente enviar TXT/CSV ou colar os nomes manualmente.")
            st.code(str(exc))
            return ""

    if name.endswith((".png", ".jpg", ".jpeg", ".webp")):
        try:
            from PIL import Image
            import pytesseract

            image = Image.open(io.BytesIO(raw))
            text = pytesseract.image_to_string(image, lang="por+eng").strip()
            if not text:
                st.warning("A imagem foi enviada, mas não consegui extrair texto. Cole os nomes/confrontos no campo abaixo.")
            return text
        except Exception as exc:
            st.warning(
                "Recebi a imagem, mas o OCR não está disponível neste servidor ou não conseguiu ler. "
                "Para funcionar 100%, prefira PDF com texto, TXT/CSV, ou cole a chave no campo abaixo."
            )
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


def canonical_text(text):
    text = str(text or "").strip().lower()
    text = text.replace("ª", "a").replace("º", "o")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def category_aliases(category_name):
    c = canonical_text(category_name)
    aliases = {c}

    # Atalhos comuns.
    replacements = [
        ("classe", ""),
        ("masculina", "masc"),
        ("masculino", "masc"),
        ("feminina", "fem"),
        ("feminino", "fem"),
    ]

    short = c
    for old, new in replacements:
        short = short.replace(old, new)
    short = re.sub(r"\s+", " ", short).strip()
    aliases.add(short)

    # 1ª Classe Masculina -> 1 masculina, 1 classe, 1 masc, 1a masculina
    m = re.search(r"(\d+)", c)
    if m:
        n = m.group(1)
        aliases.update({
            f"{n} classe masculina",
            f"{n}a classe masculina",
            f"{n} masculino",
            f"{n} mascul",
            f"{n} masc",
            f"{n} classe",
            f"{n}a classe",
            f"{n} classe feminina",
            f"{n}a classe feminina",
            f"{n} feminino",
            f"{n} fem",
        })

    if "iniciante" in c or "iniciantes" in c:
        aliases.update({"iniciante", "iniciantes", "inic"})
    if "dupla" in c:
        aliases.update({"dupla", "duplas"})

    return {a.strip() for a in aliases if a.strip()}


def build_category_matcher(tournament_id):
    cats = get_categories(tournament_id)
    items = []
    for cat in cats:
        for alias in category_aliases(cat["name"]):
            items.append((alias, cat["id"], cat["name"]))
    # mais longo primeiro evita confundir "1 classe" antes de "1 classe masculina"
    items.sort(key=lambda x: len(x[0]), reverse=True)
    return items


def find_category_in_text(text, tournament_id):
    can = canonical_text(text)
    if not can:
        return None

    for alias, cid, cname in build_category_matcher(tournament_id):
        pattern = r"(^|\s)" + re.escape(alias) + r"($|\s)"
        if re.search(pattern, can):
            return {"id": cid, "name": cname, "alias": alias}
    return None


def looks_like_category_header(text):
    can = canonical_text(text)
    words = ["classe", "iniciante", "iniciantes", "dupla", "duplas", "feminina", "feminino", "masculina", "masculino"]
    return any(w in can for w in words) and len(can.split()) <= 6


def get_or_create_category_by_name(tournament_id, name):
    clean = str(name or "").strip()
    if not clean:
        return None

    # tenta encontrar categoria existente por nome parecido
    found = find_category_in_text(clean, tournament_id)
    if found:
        return found["id"], found["name"]

    created = insert_row(
        T_CATEGORIES,
        {
            "tournament_id": tournament_id,
            "name": clean,
            "max_players": 16,
        },
    )
    if created:
        return created["id"], created["name"]
    return None


def split_possible_names(text):
    # Quebra lista do tipo "João, Pedro; Carlos" sem destruir nome composto simples.
    parts = re.split(r"\s*[,;]\s*", str(text or "").strip())
    cleaned = []
    for part in parts:
        name = clean_imported_name(part)
        if name and name.upper() != "BYE":
            cleaned.append(name)
    return cleaned


def extract_names_from_line_without_category(line, category_info=None):
    text = str(line or "").strip()
    if category_info:
        # Remove a categoria do texto e deixa só o nome.
        text = re.sub(re.escape(category_info["name"]), "", text, flags=re.I).strip(" -–—|:;\t")
        text = re.sub(re.escape(category_info["alias"]), "", text, flags=re.I).strip(" -–—|:;\t")
    return split_possible_names(text) or [clean_imported_name(text)]


def parse_mixed_category_list(text, tournament_id, fallback_category_id=None, create_missing_categories=False):
    """
    Entende listas misturadas:
    3ª Classe Masculina
    João
    Pedro

    4ª Classe Masculina: Carlos, Marcos

    Maria - 2ª Classe Feminina
    5ª Classe Masculina - André
    """
    rows = []
    warnings = []
    current_category = None

    raw_text = str(text or "").replace("\r", "\n")
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    # CSV com coluna nome/categoria
    try:
        reader = csv.DictReader(io.StringIO(raw_text))
        if reader.fieldnames:
            name_field = None
            cat_field = None
            for f in reader.fieldnames:
                fcan = canonical_text(f)
                if fcan in ["nome", "name", "atleta", "jogador", "player"]:
                    name_field = f
                if fcan in ["categoria", "category", "classe"]:
                    cat_field = f
            if name_field and cat_field:
                for row in reader:
                    name = clean_imported_name(row.get(name_field, ""))
                    cat_raw = row.get(cat_field, "")
                    cat_info = find_category_in_text(cat_raw, tournament_id)
                    if not cat_info and create_missing_categories and looks_like_category_header(cat_raw):
                        created = get_or_create_category_by_name(tournament_id, cat_raw)
                        if created:
                            cat_info = {"id": created[0], "name": created[1], "alias": canonical_text(created[1])}
                    if name and cat_info:
                        rows.append({"category_id": cat_info["id"], "category": cat_info["name"], "name": name})
                    elif name and fallback_category_id:
                        fallback = get_category(fallback_category_id)
                        rows.append({"category_id": fallback_category_id, "category": fallback["name"], "name": name})
                    elif name:
                        warnings.append(f"Categoria não identificada para: {name}")
                return rows, warnings
    except Exception:
        pass

    for line in lines:
        original = line
        line = re.sub(r"^\s*[\-\*\•]+\s*", "", line).strip()
        if not line:
            continue

        # Categoria: João, Pedro, Carlos
        if ":" in line:
            left, right = line.split(":", 1)
            cat_info = find_category_in_text(left, tournament_id)
            if not cat_info and create_missing_categories and looks_like_category_header(left):
                created = get_or_create_category_by_name(tournament_id, left)
                if created:
                    cat_info = {"id": created[0], "name": created[1], "alias": canonical_text(created[1])}

            if cat_info:
                current_category = cat_info
                for name in split_possible_names(right):
                    rows.append({"category_id": cat_info["id"], "category": cat_info["name"], "name": name})
                continue

        # Linha só com categoria.
        cat_info_line = find_category_in_text(line, tournament_id)
        if cat_info_line and (looks_like_category_header(line) or canonical_text(line) == canonical_text(cat_info_line["name"])):
            current_category = cat_info_line
            continue

        if not cat_info_line and create_missing_categories and looks_like_category_header(line):
            created = get_or_create_category_by_name(tournament_id, line)
            if created:
                current_category = {"id": created[0], "name": created[1], "alias": canonical_text(created[1])}
                continue

        # Nome - Categoria ou Categoria - Nome
        detected = find_category_in_text(line, tournament_id)
        if detected:
            names = extract_names_from_line_without_category(line, detected)
            valid_names = [n for n in names if n and canonical_text(n) != canonical_text(detected["name"]) and n.upper() != "BYE"]
            for name in valid_names:
                rows.append({"category_id": detected["id"], "category": detected["name"], "name": name})
            if valid_names:
                continue

        # Se tem categoria ativa, joga a linha nela.
        if current_category:
            for name in split_possible_names(line):
                rows.append({"category_id": current_category["id"], "category": current_category["name"], "name": name})
            continue

        # Se tiver fallback, usa fallback.
        if fallback_category_id:
            fallback = get_category(fallback_category_id)
            for name in split_possible_names(line):
                rows.append({"category_id": fallback_category_id, "category": fallback["name"], "name": name})
        else:
            name = clean_imported_name(original)
            if name:
                warnings.append(f"Sem categoria identificada: {name}")

    # Remove duplicidade nome+categoria
    unique = []
    seen = set()
    for row in rows:
        key = (row["category_id"], normalize_name(row["name"]))
        if key not in seen and row["name"]:
            seen.add(key)
            unique.append(row)

    return unique, warnings


def parse_bracket_from_pdf_or_text(text):
    """
    Primeiro tenta confrontos com X.
    Se não achar, extrai nomes e organiza 1x2, 3x4...
    """
    pairs = parse_external_bracket_lines(text)
    if pairs:
        return pairs, "confrontos"

    names = extract_names_from_free_text(text)
    pairs = []
    for i in range(0, len(names), 2):
        p1 = names[i]
        p2 = names[i + 1] if i + 1 < len(names) else "BYE"
        pairs.append((p1, p2))

    return pairs, "nomes"


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



def generate_all_brackets_random(tournament_id):
    """
    Gera chaves por categoria, mas em ação única.
    Cada categoria continua com sua própria chave.
    """
    categories = get_categories(tournament_id)
    created = 0
    skipped = []

    for cat in categories:
        players = registered_players(tournament_id, cat["id"])
        if len(players) < 2:
            skipped.append(f'{cat["name"]}: menos de 2 atletas')
            continue

        player_ids = [p["id"] for p in players]
        random.shuffle(player_ids)
        generate_bracket(tournament_id, cat["id"], player_ids)
        created += 1

    return created, skipped


def refresh_all_brackets(tournament_id):
    categories = get_categories(tournament_id)
    updated = 0

    for cat in categories:
        if get_matches(tournament_id, cat["id"]):
            refresh_bracket(tournament_id, cat["id"])
            updated += 1

    return updated


def categories_with_brackets(tournament_id):
    result = []
    for cat in get_categories(tournament_id):
        matches = get_matches(tournament_id, cat["id"])
        if matches:
            result.append(cat)
    return result


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
    execute_query(
        sb()
        .table(T_MATCHES)
        .update(
            {
                "scheduled_date": None,
                "scheduled_time": None,
                "court": None,
            }
        )
        .eq("tournament_id", tournament_id)
    )


def possible_players_for_match_local(match, matches_by_id, cache):
    """
    Retorna todos os atletas que podem aparecer neste jogo,
    usando apenas dados já carregados na memória.
    """
    match_id = match.get("id")
    if match_id in cache:
        return cache[match_id]

    players = set()

    if match.get("player1_id"):
        players.add(match["player1_id"])
    if match.get("player2_id"):
        players.add(match["player2_id"])

    for source_id in [match.get("source1_match_id"), match.get("source2_match_id")]:
        if source_id and source_id in matches_by_id:
            players.update(possible_players_for_match_local(matches_by_id[source_id], matches_by_id, cache))

    cache[match_id] = players
    return players


def get_all_players_map():
    players = get_all_players()
    return {p["id"]: p for p in players}


def generate_schedule(tournament_id, include_weekend=True):
    """
    Geração rápida:
    - carrega torneio, jogos e atletas uma vez;
    - calcula tudo na memória;
    - grava a programação em lote no Supabase;
    - valida conflito de quadra e de atleta possível.
    """
    tournament = get_tournament(tournament_id)
    if not tournament:
        raise ValueError("Torneio não encontrado.")

    clear_schedule(tournament_id)

    slots = build_slots(tournament["start_date"], tournament["end_date"], include_weekend)
    matches = get_matches(tournament_id)
    players_by_id = get_all_players_map()

    if not matches:
        return 0, 0

    matches_by_id = {m["id"]: m for m in matches}
    possible_cache = {}

    used_slots = set()
    player_busy = set()
    match_datetime = {}
    pending = []
    updates = []

    def match_has_outside_fast(match):
        possible_players = possible_players_for_match_local(match, matches_by_id, possible_cache)
        for player_id in possible_players:
            player = players_by_id.get(player_id)
            if player and player.get("is_outside"):
                return True
        return False

    def slot_score(slot, match):
        score = slot["dt"].timestamp()

        # Jogador de fora prioriza sexta/fim de semana.
        if match_has_outside_fast(match):
            if slot["weekday"] == 4:
                score -= 10_000_000
            elif slot["weekday"] in [5, 6]:
                score -= 9_000_000

        return score

    # Rodada por rodada, mas misturando categorias para evitar sobreposição geral.
    matches = sorted(
        matches,
        key=lambda m: (m.get("round_num", 1), m.get("category_id", 0), m.get("position", 0)),
    )

    sorted_slots_cache = {}

    for match in matches:
        assigned = False
        possible_players = possible_players_for_match_local(match, matches_by_id, possible_cache)

        # Cacheia ordenação de slots por tipo de prioridade.
        outside_key = "outside" if match_has_outside_fast(match) else "normal"
        if outside_key not in sorted_slots_cache:
            sorted_slots_cache[outside_key] = sorted(
                slots,
                key=lambda s: (
                    s["dt"].timestamp()
                    - (10_000_000 if outside_key == "outside" and s["weekday"] == 4 else 0)
                    - (9_000_000 if outside_key == "outside" and s["weekday"] in [5, 6] else 0)
                ),
            )

        for slot in sorted_slots_cache[outside_key]:
            slot_key = (slot["date"], slot["time"], slot["court"])

            if slot_key in used_slots:
                continue

            # Impede mesmo atleta possível no mesmo dia/horário,
            # mesmo se ele ainda estiver como "vencedor do jogo".
            if any((pid, slot["date"], slot["time"]) in player_busy for pid in possible_players):
                continue

            # Não agenda próxima fase antes da fase anterior.
            too_early = False
            for source_id in [match.get("source1_match_id"), match.get("source2_match_id")]:
                if source_id and source_id in match_datetime:
                    if slot["dt"] < match_datetime[source_id] + timedelta(minutes=90):
                        too_early = True
                        break

            if too_early:
                continue

            used_slots.add(slot_key)
            match_datetime[match["id"]] = slot["dt"]

            for player_id in possible_players:
                player_busy.add((player_id, slot["date"], slot["time"]))

            updates.append(
                {
                    "id": match["id"],
                    "tournament_id": tournament_id,
                    "category_id": match["category_id"],
                    "round_num": match["round_num"],
                    "round_name": match["round_name"],
                    "position": match["position"],
                    "player1_id": match.get("player1_id"),
                    "player2_id": match.get("player2_id"),
                    "source1_match_id": match.get("source1_match_id"),
                    "source2_match_id": match.get("source2_match_id"),
                    "winner_id": match.get("winner_id"),
                    "score": match.get("score"),
                    "status": match.get("status"),
                    "scheduled_date": slot["date"],
                    "scheduled_time": slot["time"],
                    "court": slot["court"],
                }
            )

            assigned = True
            break

        if not assigned:
            pending.append(match["id"])

    update_matches_schedule_bulk(updates)

    return len(updates), len(pending)


def schedule_conflict_report(tournament_id):
    matches = get_matches(tournament_id)
    matches_by_id = {m["id"]: m for m in matches}
    possible_cache = {}
    players_by_id = get_all_players_map()

    slot_usage = {}
    player_time_usage = {}
    errors = []

    def local_player_label(player_id):
        p = players_by_id.get(player_id)
        return p.get("name", f"Atleta {player_id}") if p else f"Atleta {player_id}"

    for match in matches:
        if not match.get("scheduled_date") or not match.get("scheduled_time"):
            continue

        slot_key = (match["scheduled_date"], match["scheduled_time"], match.get("court"))
        slot_usage.setdefault(slot_key, []).append(match["id"])

        possible_players = possible_players_for_match_local(match, matches_by_id, possible_cache)
        for player_id in possible_players:
            time_key = (player_id, match["scheduled_date"], match["scheduled_time"])
            player_time_usage.setdefault(time_key, []).append(match["id"])

    for slot_key, match_ids in slot_usage.items():
        if len(match_ids) > 1:
            errors.append(
                f"Conflito de quadra: {slot_key[0]} {slot_key[1]} quadra {slot_key[2]} nos jogos {match_ids}"
            )

    for (player_id, day, hour), match_ids in player_time_usage.items():
        if len(match_ids) > 1:
            errors.append(
                f"Possível conflito de atleta: {local_player_label(player_id)} em {day} às {hour}, jogos {match_ids}"
            )

    return errors


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


def weekday_pt(date_text):
    try:
        d = datetime.strptime(date_text, "%Y-%m-%d").date()
    except Exception:
        return "Sem data"

    names = {
        0: "Segunda-feira",
        1: "Terça-feira",
        2: "Quarta-feira",
        3: "Quinta-feira",
        4: "Sexta-feira",
        5: "Sábado",
        6: "Domingo",
    }
    return names.get(d.weekday(), "")


def render_schedule_by_day(df):
    if df.empty:
        st.info("Programação ainda não gerada.")
        return

    scheduled = df[df["Data"].astype(str).str.len() > 0].copy()
    unscheduled = df[df["Data"].astype(str).str.len() == 0].copy()

    if scheduled.empty:
        st.info("Ainda não há jogos com data/horário.")
    else:
        for day in sorted(scheduled["Data"].unique()):
            day_df = scheduled[scheduled["Data"] == day].sort_values(["Horário", "Quadra"])
            st.markdown(f"### {weekday_pt(day)} — {day}")
            st.dataframe(
                day_df[
                    [
                        "Horário",
                        "Quadra",
                        "Categoria",
                        "Fase",
                        "Jogo",
                        "Confronto",
                        "Placar",
                        "Vencedor",
                        "Status",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

    if not unscheduled.empty:
        with st.expander("Jogos sem horário", expanded=False):
            st.dataframe(unscheduled, use_container_width=True, hide_index=True)


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


def render_bracket_visual(tournament_id, category_id):
    matches = get_matches(tournament_id, category_id)
    if not matches:
        st.info("Chave ainda não gerada.")
        return

    rounds = {}
    for match in matches:
        rounds.setdefault(match.get("round_num", 1), []).append(match)

    st.markdown(
        """
        <style>
        .tl-bracket-wrap {
            overflow-x: auto;
            padding-bottom: 14px;
        }
        .tl-bracket {
            display: flex;
            gap: 22px;
            align-items: stretch;
            min-width: 900px;
        }
        .tl-round {
            min-width: 240px;
            display: flex;
            flex-direction: column;
            justify-content: space-around;
            gap: 14px;
        }
        .tl-round-title {
            color: #CCFF00;
            font-weight: 900;
            margin-bottom: 8px;
            text-align: center;
            border-bottom: 1px solid rgba(204,255,0,.25);
            padding-bottom: 6px;
        }
        .tl-match-box {
            position: relative;
            background: rgba(21,28,24,.96);
            border: 1px solid rgba(204,255,0,.30);
            border-radius: 14px;
            padding: 10px;
            box-shadow: 0 8px 18px rgba(0,0,0,.22);
        }
        .tl-match-box:after {
            content: "";
            position: absolute;
            right: -14px;
            top: 50%;
            width: 14px;
            border-top: 1px solid rgba(204,255,0,.35);
        }
        .tl-player-row {
            display: flex;
            justify-content: space-between;
            border-bottom: 1px solid rgba(255,255,255,.08);
            padding: 4px 0;
            color: #f5fff2;
            font-size: 13px;
        }
        .tl-player-row:last-child {
            border-bottom: none;
        }
        .tl-match-meta {
            color: #b8c7b8;
            font-size: 11px;
            margin-top: 5px;
        }
        .tl-winner {
            color: #CCFF00;
            font-weight: 800;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    html = ['<div class="tl-bracket-wrap"><div class="tl-bracket">']

    for round_num in sorted(rounds):
        round_matches = sorted(rounds[round_num], key=lambda m: m.get("position", 0))
        round_title = round_matches[0].get("round_name", f"Rodada {round_num}") if round_matches else f"Rodada {round_num}"
        html.append('<div class="tl-round">')
        html.append(f'<div class="tl-round-title">{round_title}</div>')

        for match in round_matches:
            p1 = player_label(match.get("player1_id"))
            p2 = player_label(match.get("player2_id"))

            if not match.get("player1_id") and match.get("source1_match_id"):
                p1 = f'Vencedor Jogo {match["source1_match_id"]}'
            if not match.get("player2_id") and match.get("source2_match_id"):
                p2 = f'Vencedor Jogo {match["source2_match_id"]}'

            winner = player_label(match.get("winner_id")) if match.get("winner_id") else ""
            score = match.get("score") or ""

            p1_class = "tl-player-row tl-winner" if match.get("winner_id") and match.get("winner_id") == match.get("player1_id") else "tl-player-row"
            p2_class = "tl-player-row tl-winner" if match.get("winner_id") and match.get("winner_id") == match.get("player2_id") else "tl-player-row"

            html.append('<div class="tl-match-box">')
            html.append(f'<div class="{p1_class}"><span>{p1}</span><span>{score if winner == p1 else ""}</span></div>')
            html.append(f'<div class="{p2_class}"><span>{p2}</span><span>{score if winner == p2 else ""}</span></div>')
            meta = f'Jogo {match["id"]}'
            if match.get("scheduled_date"):
                meta += f' - {match["scheduled_date"]} {match.get("scheduled_time","")} Q{match.get("court","")}'
            html.append(f'<div class="tl-match-meta">{meta}</div>')
            html.append('</div>')

        html.append('</div>')

    html.append("</div></div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def build_pdf_table(title, rows, columns, filename_hint="documento"):
    buffer = io.BytesIO()

    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except Exception as exc:
        st.error("Biblioteca de PDF não instalada. Confira se 'reportlab' está no requirements.txt.")
        st.code(str(exc))
        return b""

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=22,
        leftMargin=22,
        topMargin=22,
        bottomMargin=22,
    )
    styles = getSampleStyleSheet()
    elements = [Paragraph(title, styles["Title"]), Spacer(1, 10)]

    data = [columns]
    for row in rows:
        data.append([str(row.get(col, "")) for col in columns])

    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1b301f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#CCFF00")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f3f3")]),
            ]
        )
    )
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def bracket_pdf_bytes(tournament_id, category_id):
    tournament = get_tournament(tournament_id)
    category = get_category(category_id)
    rows = bracket_df(tournament_id, category_id).to_dict("records")
    columns = ["Fase", "Jogo", "Confronto", "Data", "Horário", "Quadra", "Placar", "Vencedor", "Status"]
    title = f'{tournament.get("name", "Torneio")} - {category.get("name", "Categoria")} - Chave'
    return build_pdf_table(title, rows, columns)


def schedule_pdf_bytes(tournament_id):
    tournament = get_tournament(tournament_id)
    rows = schedule_df(tournament_id).to_dict("records")
    columns = ["Data", "Horário", "Quadra", "Categoria", "Fase", "Jogo", "Confronto", "Placar", "Vencedor", "Status"]
    title = f'{tournament.get("name", "Torneio")} - Programação Completa'
    return build_pdf_table(title, rows, columns)


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
            render_schedule_by_day(df)

            pdf_bytes = schedule_pdf_bytes(tournament_id)
            if pdf_bytes:
                st.download_button(
                    "Baixar programação completa em PDF",
                    data=pdf_bytes,
                    file_name=f"programacao_torneio_{tournament_id}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )

    with tab2:
        st.info("As chaves são separadas por categoria. A programação é geral do torneio inteiro.")

        cats_with_brackets = categories_with_brackets(tournament_id)

        if not cats_with_brackets:
            st.info("Nenhuma chave foi gerada ainda.")
        else:
            view_mode = st.radio(
                "Visualização",
                ["Todas as categorias", "Uma categoria"],
                horizontal=True,
                key="public_bracket_view_mode",
            )

            if view_mode == "Todas as categorias":
                for cat in cats_with_brackets:
                    st.markdown(f"## {cat['name']}")
                    render_bracket_visual(tournament_id, cat["id"])

                    pdf_bytes = bracket_pdf_bytes(tournament_id, cat["id"])
                    if pdf_bytes:
                        st.download_button(
                            f"Baixar chave em PDF — {cat['name']}",
                            data=pdf_bytes,
                            file_name=f"chave_{cat['name'].replace(' ', '_')}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            key=f"public_pdf_all_{cat['id']}",
                        )

                    with st.expander(f"Ver tabela detalhada — {cat['name']}", expanded=False):
                        df = bracket_df(tournament_id, cat["id"])
                        st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                labels = {cat["name"]: cat["id"] for cat in cats_with_brackets}
                selected = st.selectbox("Categoria", list(labels.keys()), key="public_single_bracket")
                category_id = labels[selected]

                st.markdown(f"## {selected}")
                render_bracket_visual(tournament_id, category_id)

                pdf_bytes = bracket_pdf_bytes(tournament_id, category_id)
                if pdf_bytes:
                    st.download_button(
                        "Baixar chave em PDF",
                        data=pdf_bytes,
                        file_name=f"chave_categoria_{category_id}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )

                with st.expander("Ver tabela detalhada", expanded=False):
                    df = bracket_df(tournament_id, category_id)
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

    all_regs = get_registrations(tournament_id)
    counts_by_category = {}

    for reg in all_regs:
        category_id = reg.get("category_id")
        counts_by_category[category_id] = counts_by_category.get(category_id, 0) + 1

    rows = []
    for cat in get_categories(tournament_id):
        rows.append(
            {
                "id": cat["id"],
                "Categoria": cat["name"],
                "Limite": cat["max_players"],
                "Inscritos": counts_by_category.get(cat["id"], 0),
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

    with st.expander("Importação inteligente: lista única com categorias misturadas", expanded=True):
        st.caption("Você pode colar tudo junto. Ex.: categoria em uma linha e nomes abaixo; ou Nome - Categoria; ou Categoria: João, Pedro.")

        fallback_options = {"Não importar linhas sem categoria": None}
        fallback_options.update({c["name"]: c["id"] for c in get_categories(tournament_id)})

        fallback_label = st.selectbox(
            "Quando o app não identificar a categoria",
            list(fallback_options.keys()),
            key="mixed_fallback_category",
        )
        fallback_id = fallback_options[fallback_label]

        create_missing = st.checkbox(
            "Criar categoria automaticamente se aparecer uma categoria nova na lista",
            value=False,
            key="mixed_create_missing",
        )

        uploaded_mixed = st.file_uploader(
            "Subir lista única em TXT, CSV ou PDF",
            type=["txt", "csv", "pdf", "png", "jpg", "jpeg", "webp"],
            key="mixed_import_file",
        )
        mixed_file_text = extract_text_from_uploaded_file(uploaded_mixed) if uploaded_mixed else ""

        mixed_text = st.text_area(
            "Ou cole a lista única aqui",
            value=mixed_file_text,
            height=260,
            key="mixed_import_text",
            placeholder="3ª Classe Masculina\nJoão Silva\nPedro Santos\n\n4ª Classe Masculina\nCarlos Oliveira\nMarcos Lima\n\n2ª Classe Feminina: Maria Souza, Ana Paula",
        )

        parsed_rows, parse_warnings = parse_mixed_category_list(
            mixed_text,
            tournament_id,
            fallback_category_id=fallback_id,
            create_missing_categories=create_missing,
        )

        if parsed_rows:
            preview_df = pd.DataFrame(parsed_rows)
            preview_df = preview_df.rename(columns={"category": "Categoria", "name": "Atleta"})
            st.caption(f"{len(parsed_rows)} inscrição(ões) reconhecida(s).")
            st.dataframe(preview_df[["Categoria", "Atleta"]], use_container_width=True, hide_index=True)
        else:
            st.info("Cole ou envie uma lista para o app separar categoria por categoria.")

        if parse_warnings:
            with st.expander("Linhas que precisam de revisão", expanded=False):
                for warning in parse_warnings[:80]:
                    st.write("• " + warning)

        if st.button("Importar lista única organizada automaticamente", key="mixed_import_button", use_container_width=True):
            if not parsed_rows:
                st.error("Nenhuma inscrição reconhecida para importar.")
            else:
                saved = 0
                repeated = 0
                full = 0

                for row in parsed_rows:
                    player_id = find_or_create_player_by_name_only(row["name"], city="Linhares")
                    result = ensure_registration(tournament_id, row["category_id"], player_id)

                    if result is True:
                        saved += 1
                    elif result is False:
                        repeated += 1
                    else:
                        full += 1

                if saved:
                    st.success(f"{saved} inscrição(ões) importada(s).")
                if repeated:
                    st.warning(f"{repeated} inscrição(ões) já existiam.")
                if full:
                    st.error(f"{full} inscrição(ões) não entraram por limite da categoria.")
                st.rerun()


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
                type=["txt", "csv", "pdf", "png", "jpg", "jpeg", "webp"],
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
    st.info(
        "Fluxo oficial: cada categoria tem sua própria chave. "
        "Você pode gerar/importar por categoria ou gerar todas as chaves de uma vez. "
        "A programação é sempre geral do torneio inteiro."
    )

    st.markdown("### Ações gerais de todas as categorias")

    col_all_1, col_all_2 = st.columns(2)

    if col_all_1.button("Sortear chaves de TODAS as categorias", use_container_width=True):
        created, skipped = generate_all_brackets_random(tournament_id)
        if created:
            st.success(f"{created} chave(s) gerada(s), uma para cada categoria com atletas suficientes.")
        if skipped:
            with st.expander("Categorias ignoradas", expanded=False):
                for item in skipped:
                    st.write("• " + item)
        st.rerun()

    if col_all_2.button("Atualizar avanço de TODAS as chaves", use_container_width=True):
        updated = refresh_all_brackets(tournament_id)
        st.success(f"{updated} chave(s) atualizada(s).")
        st.rerun()

    with st.expander("Ver desenho de todas as chaves já geradas", expanded=False):
        cats_with_brackets = categories_with_brackets(tournament_id)
        if not cats_with_brackets:
            st.info("Nenhuma chave gerada ainda.")
        else:
            for cat in cats_with_brackets:
                st.markdown(f"## {cat['name']}")
                render_bracket_visual(tournament_id, cat["id"])

    st.markdown("---")
    st.markdown("### Trabalhar em uma categoria específica")

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
        st.markdown("#### Desenho da chave")
        render_bracket_visual(tournament_id, category_id)

        with st.expander("Ver tabela detalhada da chave", expanded=False):
            st.dataframe(df, use_container_width=True, hide_index=True)

        col_csv, col_pdf = st.columns(2)

        csv_data = df.to_csv(index=False).encode("utf-8")
        col_csv.download_button(
            "Exportar chave atual em CSV",
            data=csv_data,
            file_name=f"chave_categoria_{category_id}.csv",
            mime="text/csv",
            use_container_width=True,
        )

        pdf_bytes = bracket_pdf_bytes(tournament_id, category_id)
        if pdf_bytes:
            col_pdf.download_button(
                "Exportar chave atual em PDF",
                data=pdf_bytes,
                file_name=f"chave_categoria_{category_id}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

    st.markdown("---")
    st.subheader("Importar chave pronta de fora")

    with st.expander("Subir/colar chave já feita", expanded=False):
        st.caption("Use um confronto por linha. Exemplo: João Silva x Pedro Santos. Também aceita BYE. Aceita PDF/TXT/CSV e tenta ler imagem quando o servidor tiver OCR.")

        uploaded_key = st.file_uploader(
            "Subir chave em PDF, imagem, TXT ou CSV",
            type=["txt", "csv", "pdf", "png", "jpg", "jpeg", "webp"],
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

        pairs, import_mode = parse_bracket_from_pdf_or_text(pasted_key)

        if pairs:
            preview = pd.DataFrame(
                [{"Atleta 1": p1, "Atleta 2": p2} for p1, p2 in pairs]
            )
            if import_mode == "confrontos":
                st.caption(f"{len(pairs)} confronto(s) encontrado(s) no arquivo/texto.")
            else:
                st.caption(f"O app não achou confrontos com 'x', então reorganizou {len(pairs)} confronto(s) a partir da ordem dos nomes encontrados.")
            st.dataframe(preview, use_container_width=True, hide_index=True)
        else:
            st.info("Suba um PDF/TXT/CSV da chave ou cole confrontos/nomes. O app tenta reorganizar automaticamente.")

        col_a, col_b = st.columns(2)

        with col_a:
            if st.button("Gerar chave importada e preparar programação", key=f"generate_external_bracket_{category_id}", use_container_width=True):
                if not pairs:
                    st.error("Nenhum atleta/confronto encontrado para importar.")
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
                    st.success(
                        f"Chave reorganizada no site com {len(pairs)} confronto(s) e {imported} atleta(s). Agora já pode ir em Programação e gerar os horários."
                    )
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
        "Regra oficial: a programação é GERAL do torneio inteiro, não por categoria. Usa todas as categorias, quartas/semis/finais, 3 quadras por horário e jogos de 1h30. "
        "O motor carrega os dados uma vez, calcula tudo na memória, evita cruzamento de atleta entre categorias e entrega a semana organizada por dia."
    )

    include_weekend = st.checkbox("Incluir sábado e domingo", value=True)

    col1, col2 = st.columns(2)

    if col1.button("Gerar programação geral da semana inteira", use_container_width=True):
        scheduled, pending = generate_schedule(tournament_id, include_weekend)
        conflicts = schedule_conflict_report(tournament_id)

        if pending:
            st.warning(f"{scheduled} jogos agendados e {pending} ficaram sem horário.")
        else:
            st.success(f"{scheduled} jogos agendados.")

        if conflicts:
            st.error("Atenção: o validador encontrou possíveis conflitos.")
            for item in conflicts[:30]:
                st.write("• " + item)
        else:
            st.success("Validação concluída: nenhum conflito de horário encontrado.")

        st.rerun()

    if col2.button("Limpar programação", use_container_width=True):
        clear_schedule(tournament_id)
        st.warning("Programação apagada.")
        st.rerun()

    df = schedule_df(tournament_id)
    if not df.empty:
        st.markdown("### Programação organizada por dia")
        render_schedule_by_day(df)

        col_pdf, col_check = st.columns(2)

        pdf_bytes = schedule_pdf_bytes(tournament_id)
        if pdf_bytes:
            col_pdf.download_button(
                "Exportar programação completa em PDF",
                data=pdf_bytes,
                file_name=f"programacao_torneio_{tournament_id}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

        if col_check.button("Validar conflitos agora", use_container_width=True):
            conflicts = schedule_conflict_report(tournament_id)
            if conflicts:
                st.error("Conflitos encontrados:")
                for item in conflicts:
                    st.write("• " + item)
            else:
                st.success("Nenhum conflito de horário encontrado.")

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

    try:
        if menu == "Área pública":
            public_page()
        else:
            admin_page()
    except Exception as exc:
        st.error("O Supabase ou o Render oscilou durante esta leitura.")
        st.info("Clique em atualizar a página. Se persistir, faça um novo deploy com cache limpo no Render.")
        st.code(str(exc))


if __name__ == "__main__":
    main()
