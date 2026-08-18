import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os
import sqlite3

st.set_page_config(page_title="Investissement & Épargne", page_icon="📈", layout="wide")

st.title("📈 Simulateur d'Investissement & Intérêts Composés")
st.caption("Visualise la puissance des intérêts composés et planifie ta stratégie d'investissement (DCA).")

col_inputs, col_graph = st.columns([1, 2])

with col_inputs:
    st.subheader("⚙️ Paramètres de projection")
    
    capital_initial = st.number_input("Capital de départ (€)", min_value=0, value=1000, step=200)
    apport_mensuel = st.number_input("Versement mensuel (€ / mois)", min_value=0, value=200, step=50)
    duree_annees = st.slider("Durée de l'investissement (années)", min_value=1, max_value=40, value=15)
    taux_annuel = st.slider("Rendement annuel moyen estimé (%)", min_value=1.0, max_value=15.0, value=8.0, step=0.5,
                            help="Exemple : ~7-8% pour un ETF Monde historique net d'inflation.")
    inflation = st.slider("Taux d'inflation annuel estimé (%)", min_value=0.0, max_value=8.0, value=2.0, step=0.5)

# Calculs mois par mois
mois_total = duree_annees * 12
taux_mensuel = (1 + taux_annuel / 100) ** (1 / 12) - 1
taux_mensuel_net = (1 + (taux_annuel - inflation) / 100) ** (1 / 12) - 1

dates = []
capital_verse = []
valeur_totale = []
valeur_ajustee_inflation = []

cap_verse_acc = capital_initial
val_acc = capital_initial
val_inf_acc = capital_initial

for m in range(mois_total + 1):
    if m > 0:
        val_acc = (val_acc + apport_mensuel) * (1 + taux_mensuel)
        val_inf_acc = (val_inf_acc + apport_mensuel) * (1 + taux_mensuel_net)
        cap_verse_acc += apport_mensuel
    
    dates.append(m / 12)
    capital_verse.append(cap_verse_acc)
    valeur_totale.append(val_acc)
    valeur_ajustee_inflation.append(val_inf_acc)

df_simu = pd.DataFrame({
    "Année": dates,
    "Versements": capital_verse,
    "Capital Brut": valeur_totale,
    "Capital Net Inflation": valeur_ajustee_inflation
})

gain_interets = valeur_totale[-1] - capital_verse[-1]

with col_graph:
    st.subheader("📊 Croissance du portefeuille")
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Versé", f"{capital_verse[-1]:,.0f} €".replace(",", " "))
    m2.metric("Intérêts Gagnés", f"+{gain_interets:,.0f} €".replace(",", " "), delta=f"x{valeur_totale[-1]/max(capital_verse[-1],1):.1f}")
    m3.metric(f"Valeur finale à {duree_annees} ans", f"{valeur_totale[-1]:,.0f} €".replace(",", " "))

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_simu["Année"], y=df_simu["Versements"], mode='lines', name='Total Versé', line=dict(color='#64748b', dash='dash')))
    fig.add_trace(go.Scatter(x=df_simu["Année"], y=df_simu["Capital Net Inflation"], mode='lines', name='Valeur réelle (Net inflation)', line=dict(color='#f59e0b')))
    fig.add_trace(go.Scatter(x=df_simu["Année"], y=df_simu["Capital Brut"], mode='lines', name='Capital Brut', line=dict(color='#10b981', width=3), fill='tonexty'))

    fig.update_layout(
        template="plotly_dark",
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis_title="Années",
        yaxis_title="Montant (€)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# Règle des 4% / Rente passive
st.subheader("🏖️ Rente Passive potentielle (Règle des 4%)")
col_r1, col_r2 = st.columns(2)
with col_r1:
    rente_annuelle = valeur_totale[-1] * 0.04
    rente_mensuelle = rente_annuelle / 12
    st.info(f"💡 Avec un capital de **{valeur_totale[-1]:,.0f} €**, un retrait durable de 4% par an représente une rente de **{rente_mensuelle:,.0f} € / mois** sans toucher au capital d'origine.")
with col_r2:
    st.markdown("""
    **Stratégie DCA (Dollar Cost Averaging) :**
    - Investir un montant régulier chaque mois réduit l'impact de la volatilité des marchés.
    - La capitalisation des intérêts accélère fortement à partir de la 8ème-10ème année.
    """)