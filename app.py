import streamlit as st
import requests
import json
import base64
import os
from PIL import Image

# --- CONFIGURATION GLOBALE ---
# ATTENTION : Clé exposée pour la démonstration. À remplacer par une variable d'environnement !
MA_CLE_API = "AIzaSyBt3NPchJeCZ003rWXFYMMzm88RPhURPfE" 
MODEL_ID = "gemini-flash-lite-latest" 
HISTORY_FILE = "tasks_history.json" 
POINTS_PAR_TACHE = 10 

st.set_page_config(page_title="Agent Ménage", page_icon="🧹", layout="wide")
st.title("🧹 Agent Ménage (MVP Complet)")

# --- SCHÉMA JSON REQUIS ---
# Structure finale pour l'attribution et la planification (UX)
SCHEMA_TACHE = {
    "type": "object",
    "properties": {
        "taches": {
            "type": "array",
            "description": "Liste des tâches de ménage trouvées dans l'image.",
            "items": {
                "type": "object",
                "properties": {
                    "nom_tache": {"type": "string", "description": "Nom court de la tâche."},
                    "temps_estime_min": {"type": "integer", "description": "Temps estimé en minutes."},
                    "priorite": {"type": "string", "description": "Niveau de priorité (Haute, Moyenne, Basse)."},
                    "description_detaillee": {"type": "string", "description": "Les 2-3 étapes pour accomplir cette tâche."},
                    "attribution": {"type": "string", "description": "Nom de la personne à qui la tâche est attribuée."},
                    "moment_suggerer": {"type": "string", "description": "Suggestion de moment pour effectuer la tâche."}
                },
                "required": ["nom_tache", "temps_estime_min", "priorite", "description_detaillee", "attribution", "moment_suggerer"]
            }
        }
    },
    "required": ["taches"]
}


# --- FONCTIONS DE GESTION DE DONNÉES (PERSISTANCE) ---

def load_data():
    """Charge l'historique des tâches (persistance)."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []

def save_data(new_tasks=None):
    """Fusionne les nouvelles tâches et sauvegarde."""
    if new_tasks:
        # Initialise les nouvelles tâches à PENDING
        for task in new_tasks:
            task['status'] = 'PENDING'
        st.session_state.history.extend(new_tasks)
        
    with open(HISTORY_FILE, 'w') as f:
        json.dump(st.session_state.history, f, indent=4)
    
    return True

def reset_history():
    """SUPPRIME le fichier d'historique (pour les tests)."""
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)
    st.session_state.history = []
    st.rerun() # Redémarre l'application

def mark_as_done(index):
    """Marque une tâche comme 'DONE' et met à jour."""
    if st.session_state.history[index]['status'] == 'PENDING':
        st.session_state.history[index]['status'] = 'DONE'
        save_data()
        st.rerun() # Force la mise à jour du tableau de bord

def calculate_score(history):
    """Calcule le score et le temps travaillé par utilisateur."""
    scores = {}
    for task in history:
        person = task.get('attribution', 'Inconnu')
        if person not in scores:
            scores[person] = {"done": 0, "pending": 0, "total_time": 0}
        
        if task.get('status') == 'DONE':
            scores[person]['done'] += POINTS_PAR_TACHE
        else:
            scores[person]['pending'] += POINTS_PAR_TACHE
        
        scores[person]['total_time'] += task.get('temps_estime_min', 0)
    return scores


# --- FONCTIONS DE COMMUNICATION API ---

def image_to_base64(uploaded_file):
    return base64.b64encode(uploaded_file.getvalue()).decode()

def ask_gemini(prompt, image_file=None):
    # L'URL est le nom standard du modèle qui a fonctionné
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_ID}:generateContent?key={MA_CLE_API}"
    
    # Correction de l'erreur 400 (Changement de nom de clé)
    config = {
        "responseMimeType": "application/json", 
        "responseSchema": SCHEMA_TACHE
    }
    
    parts = [{"text": prompt}]
    
    if image_file:
        img_b64 = image_to_base64(uploaded_file=image_file)
        parts.append({"inline_data": {"mime_type": image_file.type, "data": img_b64}})
    
    # La clé 'generationConfig' est la clé correcte pour l'API REST
    payload = {
        "contents": [{"parts": parts}], 
        "generationConfig": config
    }
    headers = {'Content-Type': 'application/json'}
    
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    
    if response.status_code == 200:
        try:
            json_text = response.json()['candidates'][0]['content']['parts'][0]['text']
            return json.loads(json_text) 
        except Exception as e:
            return {"error": f"Erreur de décodage JSON. {e}. Réponse brute: {response.text}"}
    else:
        return {"error": f"Erreur Google ({response.status_code}) : {response.text}"}


# --- INITIALISATION DE L'ÉTAT ET DU SCORE ---
if 'history' not in st.session_state:
    st.session_state.history = load_data()

scores = calculate_score(st.session_state.history)


# --- INTERFACE UTILISATEUR PRINCIPALE ---

st.sidebar.title("🏆 Scoreboard")
st.sidebar.markdown("---")
sorted_scores = sorted(scores.items(), key=lambda item: item[1]['done'], reverse=True)

if sorted_scores:
    for name, data in sorted_scores:
        st.sidebar.metric(f"Score de {name}", f"{data['done']} pts")
        st.sidebar.caption(f"⏱️ {data['total_time']} min travaillées / {data['pending'] // POINTS_PAR_TACHE * POINTS_PAR_TACHE} pts en attente")
else:
    st.sidebar.info("Lancez une analyse pour établir le score.")
    
st.sidebar.markdown("---")
st.sidebar.button("🗑️ Réinitialiser l'Historique", on_click=reset_history)


col1, col2 = st.columns([1, 1.5])

with col1:
    st.markdown("## ⚙️ Nouvelle Analyse & Planning")
    st.markdown("---")
    
    noms_foyer = st.text_input("👥 Noms du foyer (séparés par une virgule)", value="Paul, Marie")
    disponibilite = st.selectbox("⏰ Moment d'exécution suggéré", ["Ce soir après 19h", "Demain matin avant 9h", "Ce week-end (samedi matin)"])
    
    base_prompt = f"Analyse l'image. Liste 3 tâches. Attribue chaque tâche équitablement à une des personnes suivantes : {noms_foyer}. Utilise la disponibilité '{disponibilite}' pour suggérer un moment d'exécution pour chaque tâche."

    user_text = st.text_area("Prompt à l'IA", value=base_prompt, height=100)
    user_img = st.file_uploader("Photo du désordre", type=['png', 'jpg', 'jpeg'])
    btn = st.button("Analyser et Attribuer 👥", type="primary")

with col2:
    if btn:
        if user_img:
            st.image(user_img, width=200)
            with st.spinner('Analyse et planification en cours...'):
                res = ask_gemini(user_text, user_img)
                
                if isinstance(res, dict) and 'error' in res:
                    st.error(res['error'])
                elif isinstance(res, dict) and 'taches' in res:
                    save_data(res['taches'])
                    st.success("Tâches enregistrées. Tableau de bord mis à jour !")
                    st.rerun() 
                else:
                    st.error("Format de réponse inattendu.")
        else:
            st.warning("Il faut une photo !")

# --- SECTION HISTORIQUE ---
st.markdown("---")
st.markdown("## 📋 Tâches en Cours et Terminées")

# On affiche les tâches en cours
pending_tasks = [t for t in st.session_state.history if t.get('status') == 'PENDING']
completed_tasks = [t for t in st.session_state.history if t.get('status') == 'DONE']


if pending_tasks:
    st.subheader(f"🔴 {len(pending_tasks)} Tâches en Attente")
    for i, tache in enumerate(st.session_state.history):
        if tache.get('status') == 'PENDING':
            # Checkbox pour marquer comme fait, liée à l'index de la tâche dans l'historique global
            st.checkbox(
                f"[{tache.get('attribution')} | {tache.get('temps_estime_min')} min] {tache.get('nom_tache')}", 
                key=f"task_done_{i}",
                on_change=mark_as_done,
                args=(i,)
            )
            st.caption(f"Planifié: **{tache.get('moment_suggerer')}** - Priorité: {tache.get('priorite')}")
            st.caption(f"Détail: {tache.get('description_detaillee')}")
            st.markdown("---")


if completed_tasks:
    st.subheader(f"✅ Tâches Terminées ({len(completed_tasks)})")
    # Affiche les 5 dernières tâches terminées
    for tache in completed_tasks[-5:]: 
        st.markdown(f"- ~~{tache.get('nom_tache')}~~ par **{tache.get('attribution')}** ({tache.get('temps_estime_min')} min)")

if not st.session_state.history:
    st.info("Aucune tâche enregistrée. Lancez une analyse pour commencer !")