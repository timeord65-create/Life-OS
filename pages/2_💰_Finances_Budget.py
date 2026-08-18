import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Finances & Budget", page_icon="💰", layout="wide")
DB_FILE = "life_os.db"

st.title("💰 Suivi Financier & Budget")

# Formulaire d'ajout
with st.expander("➕ Enregistrer une transaction", expanded=False):
    c1, c2, c3 = st.columns(3)
    with c1:
        t_type = st.selectbox("Type", ["Dépense", "Revenu"])
        amount = st.number_input("Montant (€)", min_value=0.0, step=10.0)
    with c2:
        cat = st.selectbox("Catégorie", ["Loyer / Charges", "Alimentation", "Transport", "Loisirs / Sorties", "Sport / Équipement", "Salaire / Bourse", "Épargne"])
    with c3:
        t_date = st.date_input("Date", datetime.now())
        
    if st.button("Enregistrer la transaction", type="primary") and amount > 0:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO transactions (type, category, amount, date) VALUES (?, ?, ?, ?)",
                  (t_type, cat, amount, t_date.strftime("%Y-%m-%d")))
        conn.commit()
        conn.close()
        st.success("Transaction ajoutée !")
        st.rerun()

st.divider()

conn = sqlite3.connect(DB_FILE)
df = pd.read_sql_query("SELECT id, type, category, amount, date FROM transactions ORDER BY date DESC", conn)
conn.close()

if not df.empty:
    total_rev = df[df["type"] == "Revenu"]["amount"].sum()
    total_dep = df[df["type"] == "Dépense"]["amount"].sum()
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Revenus totaux", f"{total_rev:,.2f} €")
    m2.metric("Dépenses totales", f"{total_dep:,.2f} €")
    m3.metric("Solde net", f"{(total_rev - total_dep):,.2f} €")
    
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        df_dep = df[df["type"] == "Dépense"]
        if not df_dep.empty:
            fig_pie = px.pie(df_dep, values="amount", names="category", title="Répartition des dépenses", hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)
    with col_chart2:
        st.subheader("Dernières opérations")
        st.dataframe(df, use_container_width=True)
else:
    st.info("Aucune transaction enregistrée.")