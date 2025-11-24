import streamlit as st
import requests
import json
import base64
import os
from PIL import Image

# --- CONFIGURATION GLOBALE ---
# IMPORTANT : Collez votre NOUVELLE clé API autorisée ici !
MA_CLE_API = "AIzaSyCLD0iHr4mEPDJqKl8ugG7nKUfUynTpeSM" 
MODEL_ID = "gemini-flash-lite-latest" 
POINTS_PAR_TACHE = 10 

st.set_page_config(page_title="Agent Ménage", page_icon="🧹", layout="wide")
st.title("🧹 Agent Ménage (Version Foyer Séparé)")


# --- FONCTIONS DE GESTION DE DONNÉES (PERSISTANCE MULTI-FOYER) ---

def get_history_filename(foyer_id):
    """Retourne le nom de fichier basé sur l'ID du foyer."""
    if not foyer_id:
        # Fallback pour éviter les erreurs si le champ est vide
        return "tasks_history_default.json" 
    return f"tasks_history_{foyer_id.lower()}.json"

def load_data(foyer_id):
    """Charge l'historique des tâches depuis le fichier JSON spécifique au foyer."""
    filename = get_history_filename(foyer_id)
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []

def save_data(foyer_id, new_tasks=None):
    """Fusionne les nouvelles tâches et sauvegarde dans le fichier spécifique."""
    filename = get_history_filename(foyer_id)
    
    if new_tasks:
        # Si de nouvelles tâches sont soumises, on les ajoute à la session
        for task in new_tasks:
            task['status'] = 'PENDING'
        st.session_state.history.extend(new_tasks)
        
    with open(filename, 'w') as f:
        json.dump(st.session_state.history, f, indent=4)
    return True

def reset_history(foyer_id):
    """Supprime le fichier d'historique du foyer et réinitialise l'état."""
    filename = get_history_filename(foyer_id)
    if os.path.exists(filename):
        os.remove(filename)
    st.session_state.history = []
    st.rerun() 

def mark_as_done(index, foyer_id):
    """Marque une tâche comme 'DONE' et sauvegarde."""
    # L'index 'i' est l'index dans la liste st.session_state.history
    if st.session_state.history[index]['status'] == 'PENDING':
        st.session_state.history[index]['status'] = 'DONE'
        save_data(foyer_id) # Utilise le foyer_id pour cibler le bon fichier
        st.rerun()

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


# --- SCHÉMA JSON REQUIS ---
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

def image_to_base64(uploaded_file):
    return base64.b64encode(uploaded_file.getvalue()).decode()

def ask_gemini(prompt, image_file=None):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_ID}:generateContent?key={MA_CLE_API}"
    
    config = {"responseMimeType": "application/json", "responseSchema": SCHEMA_TACHE}
    parts = [{"text": prompt}]
    
    if image_file:
        img_b64 = image_to_base64(uploaded_file=image_file)
        parts.append({"inline_data": {"mime_type": image_file.type, "data": img_b64}})
    
    payload = {"contents": [{"parts": parts}], "generationConfig": config}
    headers = {'Content-Type': 'application/json'}
    
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    
    if response.status_code == 200:
        try:
            json_text = response.json()['candidates'][0]['content']['parts'][0]['text']
            return json.loads(json_text) 
        except Exception as e:
            # Souvent causé par un JSON mal formé ou tronqué
            return {"error": f"Erreur de décodage JSON. Réponse brute: {response.text}"}
    else:
        # Affiche le code d'erreur (403 si la clé n'est pas bonne)
        return {"error": f"Erreur Google ({response.status_code}) : {response.text}"}


# --- INTERFACE UTILISATEUR PRINCIPALE ---

# Initialisation de l'état (nécessaire pour le load_data dynamique)
if 'history' not in st.session_state:
    st.session_state.history = []
if 'current_foyer_id' not in st.session_state:
    st.session_state.current_foyer_id = "famille_test"

# --- SIDEBAR & SCOREBOARD ---

scores = calculate_score(st.session_state.history)

st.sidebar.title("🏆 Scoreboard")
st.sidebar.markdown("---")
sorted_scores = sorted(scores.items(), key=lambda item: item[1]['done'], reverse=True)

if sorted_scores:
    for name, data in sorted_scores:
        st.sidebar.metric(f"Score de {name}", f"{data['done']} pts")
        st.sidebar.caption(f"⏱️ {data['total_time']} min travaillées / {data['pending'] // POINTS_PAR_TACHE * POINTS_PAR_TACHE} pts en attente")
else:
    st.sidebar.info("Lancez une analyse pour établir le score.")
    
# Réinitialisation du foyer actif pour l'interface
foyer_id_for_reset = st.session_state.current_foyer_id
st.sidebar.markdown("---")
st.sidebar.button("🗑️ Réinitialiser l'Historique de ce Foyer", on_click=reset_history, args=(foyer_id_for_reset,))


col1, col2 = st.columns([1, 1.5])

with col1:
    st.markdown("## ⚙️ Nouvelle Analyse & Planning")
    st.markdown("---")
    
    # CHAMP D'ENTRÉE DE L'ID DU FOYER (Détermine le fichier de sauvegarde)
    foyer_id = st.text_input(
        "🔑 ID Unique du Foyer (Ex: dupont_2025)",
        value=st.session_state.current_foyer_id,
        key='foyer_input' # Pour le lier à l'état de la session
    )
    
    # Si l'ID du foyer change, on recharge les données !
    if st.session_state.current_foyer_id != foyer_id:
        st.session_state.history = load_data(foyer_id)
        st.session_state.current_foyer_id = foyer_id
        st.rerun() # Recharge l'interface pour afficher le nouvel historique
    
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
                    # SAUVEGARDE DANS LE FICHIER SPÉCIFIQUE AU FOYER
                    save_data(foyer_id, res['taches']) 
                    st.success("Tâches enregistrées. Tableau de bord mis à jour !")
                    st.rerun() 
                else:
                    st.error("Format de réponse inattendu.")
        else:
            st.warning("Il faut une photo !")

# --- SECTION HISTORIQUE ---
st.markdown("---")
st.markdown(f"## 📋 Tâches pour le Foyer : {st.session_state.current_foyer_id}")

pending_tasks = [t for t in st.session_state.history if t.get('status') == 'PENDING']
completed_tasks = [t for t in st.session_state.history if t.get('status') == 'DONE']


if pending_tasks:
    st.subheader(f"🔴 {len(pending_tasks)} Tâches en Attente")
    for i, tache in enumerate(st.session_state.history):
        if tache.get('status') == 'PENDING':
            # Appel à mark_as_done avec l'ID du foyer
            st.checkbox(
                f"[{tache.get('attribution')} | {tache.get('temps_estime_min')} min] {tache.get('nom_tache')}", 
                key=f"task_done_{i}",
                on_change=mark_as_done,
                args=(i, foyer_id,) # Argument clé : l'ID du foyer
            )
            st.caption(f"Planifié: **{tache.get('moment_suggerer')}** - Priorité: {tache.get('priorite')}")
            st.caption(f"Détail: {tache.get('description_detaillee')}")
            st.markdown("---")


if completed_tasks:
    st.subheader(f"✅ Tâches Terminées ({len(completed_tasks)})")
    for tache in completed_tasks[-5:]: 
        st.markdown(f"- ~~{tache.get('nom_tache')}~~ par **{tache.get('attribution')}** ({tache.get('temps_estime_min')} min)")

if not st.session_state.history:
    st.info("Aucune tâche enregistrée. Entrez un ID de Foyer et lancez une analyse.")