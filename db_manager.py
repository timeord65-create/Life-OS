import sqlite3
import json
import os
from datetime import datetime, timedelta
import pandas as pd

DB_FILE = "life_os.db"

# Barème d'expérience
XP_RULES = {
    "task_done": 35,        # Tâche terminée
    "habit_done": 20,       # Habitude validée
    "workout_run": 50,      # Séance de sport
    "recipe_cooked": 30,    # Repas cuisiné / courses
}

def get_level_info(total_xp: int):
    """Calcule le niveau, le titre et la progression vers le prochain niveau."""
    # Formule RPG simple : niveau = racine carrée ou paliers de 100 XP
    level = int(total_xp // 150) + 1
    xp_in_level = total_xp % 150
    xp_needed = 150
    progress = xp_in_level / xp_needed
    
    titles = [
        "🌱 Novice Ambitieux",
        "⚡ Apprenti Discipliné",
        "🔥 Guerrier du Focus",
        "🥋 Maître de la Routine",
        "🏆 Champion de la Productivité",
        "👑 Titan du Life OS",
        "🌌 Légende Vivante"
    ]
    title_idx = min(level - 1, len(titles) - 1)
    return {
        "level": level,
        "title": titles[title_idx],
        "total_xp": total_xp,
        "xp_in_level": xp_in_level,
        "xp_needed": xp_needed,
        "progress": progress
    }

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Table profil RPG / XP
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            id INTEGER PRIMARY KEY DEFAULT 1,
            total_xp INTEGER DEFAULT 0,
            streak_days INTEGER DEFAULT 0,
            last_active_date TEXT
        )
    """)
    c.execute("INSERT OR IGNORE INTO user_profile (id, total_xp, streak_days, last_active_date) VALUES (1, 0, 0, '')")

    # Tables standard
    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            priority TEXT,
            done INTEGER DEFAULT 0,
            date_created TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS habit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            habit_name TEXT,
            date TEXT,
            status INTEGER DEFAULT 1
        )
    """)
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
        CREATE TABLE IF NOT EXISTS workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sport TEXT,
            duration INTEGER,
            distance REAL,
            rpe INTEGER,
            notes TEXT,
            date TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            portions INTEGER,
            prep_time TEXT,
            calories TEXT,
            ingredients TEXT,
            instructions TEXT,
            source_url TEXT,
            date_added TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS placard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE,
            en_stock INTEGER DEFAULT 1
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS meal_plan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_of_week TEXT,
            meal_time TEXT,
            recipe_title TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_xp(points: int):
    """Ajoute des points d'XP au joueur."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT total_xp, streak_days, last_active_date FROM user_profile WHERE id = 1")
    row = c.fetchone()
    if row:
        xp, streak, last_date = row
        new_xp = xp + points
        # Calcul streak
        if last_date != today:
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            if last_date == yesterday:
                streak += 1
            elif last_date == "":
                streak = 1
            else:
                streak = 1
            last_date = today
        c.execute("UPDATE user_profile SET total_xp = ?, streak_days = ?, last_active_date = ? WHERE id = 1", (new_xp, streak, last_date))
    conn.commit()
    conn.close()

def get_profile():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT total_xp, streak_days, last_active_date FROM user_profile WHERE id = 1")
    row = c.fetchone()
    conn.close()
    if row:
        xp, streak, last_date = row
        info = get_level_info(xp)
        info["streak"] = streak
        return info
    return {"level": 1, "title": "🌱 Novice", "total_xp": 0, "xp_in_level": 0, "xp_needed": 150, "progress": 0.0, "streak": 0}