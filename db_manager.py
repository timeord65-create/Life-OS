from datetime import date

def get_today_habit_logs():
    """Récupère la liste des noms d'habitudes complétées aujourd'hui."""
    today_str = date.today().isoformat()
    client = get_supabase_client()
    if client:
        try:
            res = client.table("habit_logs").select("habit_name").eq("date", today_str).eq("completed", True).execute()
            return [row["habit_name"] for row in (res.data or [])]
        except Exception:
            pass
    
    # Fallback SQLite local
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS habit_logs (
                habit_name TEXT,
                date TEXT,
                completed INTEGER DEFAULT 1,
                PRIMARY KEY (habit_name, date)
            )
        """)
        c.execute("SELECT habit_name FROM habit_logs WHERE date = ? AND completed = 1", (today_str,))
        rows = c.fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception:
        return []

def toggle_habit_log(habit_name: str, is_completed: bool, xp_reward: int = 15):
    """Enregistre ou retire la validation du jour et met à jour l'XP."""
    today_str = date.today().isoformat()
    client = get_supabase_client()
    
    if client:
        try:
            if is_completed:
                client.table("habit_logs").upsert({
                    "habit_name": habit_name,
                    "date": today_str,
                    "completed": True
                }, on_conflict="habit_name,date").execute()
                add_xp(xp_reward)
            else:
                client.table("habit_logs").delete().eq("habit_name", habit_name).eq("date", today_str).execute()
                add_xp(-xp_reward)
        except Exception as e:
            st.error(f"Erreur Supabase Habitudes : {e}")

    # Synchronisation SQLite locale
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS habit_logs (
                habit_name TEXT,
                date TEXT,
                completed INTEGER DEFAULT 1,
                PRIMARY KEY (habit_name, date)
            )
        """)
        if is_completed:
            c.execute("""
                INSERT INTO habit_logs (habit_name, date, completed) 
                VALUES (?, ?, 1)
                ON CONFLICT(habit_name, date) DO UPDATE SET completed = 1
            """, (habit_name, today_str))
        else:
            c.execute("DELETE FROM habit_logs WHERE habit_name = ? AND date = ?", (habit_name, today_str))
        conn.commit()
        conn.close()
    except Exception:
        pass