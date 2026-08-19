import os
import sqlite3
import streamlit as st
from supabase import create_client, Client

def get_secret(key: str):
    if key in st.secrets:
        return st.secrets[key]
    return os.getenv(key)

supabase_url = get_secret("SUPABASE_URL")
supabase_key = get_secret("SUPABASE_KEY")

@st.cache_resource
def get_supabase_client():
    if supabase_url and supabase_key:
        try:
            return create_client(supabase_url, supabase_key)
        except Exception:
            return None
    return None

def init_db():
    """Initialise les tables locales de secours si nécessaire."""
    try:
        conn = sqlite3.connect("life_os.db")
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT,
                category TEXT,
                amount REAL,
                date TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                category TEXT,
                frequency TEXT
            )
        """)
        conn.commit()
        conn.close()
    except Exception:
        pass

def get_title_for_level(lvl: int) -> str:
    """Attribue un rang RPG selon le niveau."""
    if lvl < 3:
        return "🌱 Débutant"
    elif lvl < 6:
        return "⚔️ Aventurier"
    elif lvl < 10:
        return "🛡️ Chevalier"
    elif lvl < 15:
        return "🔥 Champion"
    else:
        return "👑 Légende"

def format_profile_dict(raw: dict = None) -> dict:
    """Construit un dictionnaire complet avec toutes les variables attendues par l'interface."""
    raw = raw or {}
    total_xp = int(raw.get("xp", 0) or 0)
    xp_per_level = 100
    level = max(1, (total_xp // xp_per_level) + 1)
    xp_in_level = total_xp % xp_per_level
    streak = int(raw.get("streak", 0) or 0)

    return {
        "id": 1,
        "xp": total_xp,
        "total_xp": total_xp,
        "xp_in_level": xp_in_level,
        "xp_needed": xp_per_level,
        "level": level,
        "title": raw.get("title") or get_title_for_level(level),
        "streak": streak,
        "avatar": raw.get("avatar", "🧙‍♂️")
    }

def get_profile() -> dict:
    """Récupère le profil complet depuis Supabase avec repli sécurisé."""
    client = get_supabase_client()
    if not client:
        return format_profile_dict()
    try:
        res = client.table("user_profile").select("*").eq("id", 1).execute()
        if res.data:
            return format_profile_dict(res.data[0])
        
        # Insertion d'une ligne initiale si la table est vide
        init_raw = {"id": 1, "xp": 0, "level": 1}
        client.table("user_profile").insert(init_raw).execute()
        return format_profile_dict(init_raw)
    except Exception:
        return format_profile_dict()

# Alias de compatibilité
get_user_profile = get_profile

def add_xp(amount: int):
    """Ajoute de l'XP et recalcule le profil."""
    client = get_supabase_client()
    prof = get_profile()
    new_total_xp = prof["total_xp"] + amount
    new_level = max(1, (new_total_xp // 100) + 1)

    if client:
        try:
            client.table("user_profile").upsert({
                "id": 1,
                "xp": new_total_xp,
                "level": new_level
            }).execute()
        except Exception as e:
            print(f"Erreur update XP : {e}")

    return new_total_xp, new_level