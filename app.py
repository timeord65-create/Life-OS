import streamlit as st
from datetime import datetime, date
import db_manager as db

st.set_page_config(
    page_title="Life OS — Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Chargement du profil utilisateur & de l'XP
profile = db.get_profile()

# En-tête
col_header_1, col_header_2 = st.columns([3, 1])
with col_header_1:
    st.title(f"{profile['avatar']} Life OS — Tableau de Bord")
    today_fr = datetime.now().strftime("%A %d %B %Y").capitalize()
    st.caption(f"📅 Aujourd'hui : **{today_fr}** | Statut : En pleine progression 🚀")

with col_header_2:
    st.metric("Série active (Streak)", f"🔥 {profile['streak']} jours", delta="Régularité")

st.divider()

# ==========================================
# BARRE DE PROGRESSION & NIVEAU XP
# ==========================================
st.markdown(f"### ⚡ Progression du Niveau : **Niveau {profile['level']} — {profile['title']}**")

col_xp_bar, col_xp_val = st.columns([5, 1])
with col_xp_bar:
    st.progress(
        profile["progress"],
        text=f"{profile['xp_in_level']} / {profile['xp_needed']} XP requis pour le Niveau {profile['level'] + 1}"
    )
with col_xp_val:
    st.markdown(f"**Total : `{profile['total_xp']} XP`**")

st.divider()

# ==========================================
# SECTION HABITUDES & OBJECTIFS DU JOUR
# ==========================================
col_habits, col_quick_access = st.columns([3, 2])

with col_habits:
    st.subheader("✅ Habitudes & Rituels du Jour (+15 XP)")
    habits_list = db.get_all_habits()
    completed_today = db.get_today_habit_logs()

    if not habits_list:
        st.info("Aucune habitude configurée.")
    else:
        done_count = 0
        for h in habits_list:
            h_name = h["name"] if isinstance(h, dict) else str(h)
            is_done = h_name in completed_today
            if is_done:
                done_count += 1

            # Checkbox dynamique
            checked = st.checkbox(
                f"{h_name}",
                value=is_done,
                key=f"dash_hab_{h_name}"
            )

            # Enregistrement immédiat si modification
            if checked != is_done:
                db.toggle_habit_log(h_name, checked, xp_reward=15)
                st.rerun()

        # Ratio d'accomplissement du jour
        ratio = (done_count / len(habits_list)) if habits_list else 0.0
        st.caption(f"🎯 Habitudes validées aujourd'hui : **{done_count}/{len(habits_list)}** ({int(ratio*100)}%)")

with col_quick_access:
    st.subheader("🚀 Accès Rapides")
    
    with st.container(border=True):
        st.markdown("🍳 **Cuisine & Planning Repas**")
        st.caption("Consulte ton planning de la semaine, génère ta liste de courses ou vide ton frigo.")
        st.page_link("pages/4_🍳_Planning_Courses_Placard.py", label="Ouvrir le Hub Cuisine", icon="🍳")

    with st.container(border=True):
        st.markdown("🔋 **Sommeil & Énergie**")
        st.caption("Enregistre ta nuit pour valider tes points de forme.")
        st.page_link("pages/6_🔋_Energie_Sommeil_Recup.py", label="Suivi Énergie & Récupération", icon="🔋")

    with st.container(border=True):
        st.markdown("💰 **Finances & Budget**")
        st.caption("Visualise tes dépenses et suis ton épargne.")
        st.page_link("pages/2_💰_Finances_Budget.py", label="Gestion Budget", icon="💰")

st.divider()

# ==========================================
# WIDGETS STATUT GLOBAL
# ==========================================
st.subheader("📊 Métriques & Statuts Clés")

m1, m2, m3, m4 = st.columns(4)
m1.metric(label="Niveau", value=f"Lvl {profile['level']}", delta=profile['title'])
m2.metric(label="XP Total", value=f"{profile['total_xp']} pts", delta="+15 par habitude")
m3.metric(label="Régularité", value=f"{profile['streak']} j", delta="En cours")
m4.metric(label="Espace Actuel", value="Coloc / Maison", delta="Synchronisé")