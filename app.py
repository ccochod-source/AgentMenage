import streamlit as st
import google.generativeai as genai
import time
import json
import os

# --- 1. CONFIGURATION API ---
MY_API_KEY = "AIzaSyAmk1Onnp_vwJX6F-wmtn9OD-1vxECgAqE"
api_key = st.secrets["GEMINI_API_KEY"]
os.environ["GEMINI_API_KEY"] = api_key
genai.configure(api_key=api_key)
st.set_page_config(page_title="Majordome AI", page_icon="🤖", layout="centered")

# --- 2. RÉCUPÉRATION DES MODÈLES ---
try:
    model_list = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            model_list.append(m.name)
    model_list.sort()
except Exception as e:
    st.error(f"Erreur API : {e}")
    model_list = ["models/gemini-1.5-flash"]

# --- 3. BARRE LATÉRALE ---
with st.sidebar:
    st.header("🧠 Cerveau IA")
    selected_model = st.selectbox("Modèle :", model_list, index=0 if model_list else 0)
    
    st.markdown("---")
    st.header("⚙️ Réglages Famille")
    membres = st.text_input("Membres", "Papa, Maman, Léo, Julie").split(',')
    taches = st.text_area("Tâches", "Poubelles\nPlantes\nCourrier").split('\n')
    
    membres = [m.strip() for m in membres if m.strip()]
    taches = [t.strip() for t in taches if t.strip()]

# --- 4. GESTION ÉTAT (AUTO-RÉPARATION ICI) ---
STATE_FILE = "famille_state.json"

def load_state():
    # État par défaut propre
    default_state = {"semaine": 1, "chat": [{"role": "assistant", "content": "👋 Je suis prêt. Envoie une photo !"}]}
    
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                saved = json.load(f)
                
                # --- BLOC DE RÉPARATION ---
                # Si l'ancien fichier a "chat_history" au lieu de "chat", on convertit
                if "chat_history" in saved:
                    saved["chat"] = saved.pop("chat_history")
                # Si "semaine_actuelle" existe, on renomme en "semaine"
                if "semaine_actuelle" in saved:
                    saved["semaine"] = saved.pop("semaine_actuelle")
                
                # Vérification finale
                if "chat" not in saved: saved["chat"] = []
                if "semaine" not in saved: saved["semaine"] = 1
                
                return saved
        except:
            pass # Si fichier cassé, on renvoie le défaut
            
    return default_state

def save_state():
    with open(STATE_FILE, 'w') as f: json.dump(st.session_state.state, f)

# Initialisation SÉCURISÉE
if 'state' not in st.session_state:
    st.session_state.state = load_state()

# --- 5. LOGIQUE MÉTIER ---
def get_rotation_planning(semaine, membres, taches):
    if not membres: return []
    planning = []
    for i, t in enumerate(taches):
        p = membres[(i + semaine) % len(membres)]
        planning.append({"Tâche": t, "Attribué à": p})
    return planning

# Boutons sidebar
with st.sidebar:
    st.metric("Semaine", st.session_state.state["semaine"])
    if st.button("Semaine Suivante ⏩"):
        st.session_state.state["semaine"] += 1
        st.session_state.state["chat"].append({"role": "assistant", "content": f"🔔 Changement de semaine n°{st.session_state.state['semaine']} !"})
        save_state()
        st.rerun()
    
    # Bouton de secours ultime
    if st.button("🗑️ Réinitialiser tout"):
        if os.path.exists(STATE_FILE): os.remove(STATE_FILE)
        st.session_state.state = load_state()
        st.rerun()

# --- 6. INTERFACE CHAT ---
st.title("🤖 Majordome Familial")

# Affichage sécurisé
for msg in st.session_state.state["chat"]:
    with st.chat_message(msg["role"]): st.markdown(msg["content"])

# INPUT FICHIER
uploaded_file = st.file_uploader("📎 Média", type=['mp4', 'mov', 'jpg', 'png'], label_visibility="collapsed")

if uploaded_file:
    with st.chat_message("user"): st.write(f"Envoi : {uploaded_file.name}")
    
    file_path = f"temp_{uploaded_file.name}"
    with open(file_path, "wb") as f: f.write(uploaded_file.getbuffer())

    with st.spinner("Analyse..."):
        try:
            gst_file = genai.upload_file(path=file_path)
            while gst_file.state.name == "PROCESSING":
                time.sleep(2)
                gst_file = genai.get_file(gst_file.name)
            
            if gst_file.state.name == "FAILED": raise ValueError("Erreur Google")

            prompt = "Analyse ce fichier (Ménage ou Frigo). Réponds format WhatsApp court."
            
            model = genai.GenerativeModel(selected_model)
            response = model.generate_content([gst_file, prompt])
            
            st.session_state.state["chat"].append({"role": "user", "content": "📹 *Média envoyé*"})
            st.session_state.state["chat"].append({"role": "assistant", "content": response.text})
            save_state()
            os.remove(file_path)
            st.rerun()

        except Exception as e:
            st.error(f"Erreur : {e}")
            if os.path.exists(file_path): os.remove(file_path)

# INPUT TEXTE
if prompt := st.chat_input("Message..."):
    st.session_state.state["chat"].append({"role": "user", "content": prompt})
    
    resp = ""
    if any(w in prompt.lower() for w in ["qui", "planning", "poubelle"]):
        planning = get_rotation_planning(st.session_state.state["semaine"], membres, taches)
        resp = f"📅 **Semaine {st.session_state.state['semaine']}** :\n"
        for item in planning: resp += f"- {item['Tâche']} : **{item['Attribué à']}**\n"
    else:
        try:
            model = genai.GenerativeModel(selected_model)
            resp = model.generate_content(prompt).text
        except Exception as e: resp = f"Erreur API : {e}"

    st.session_state.state["chat"].append({"role": "assistant", "content": resp})
    save_state()
    st.rerun()