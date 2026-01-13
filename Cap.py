import streamlit as st
from lxml import etree
import re
from collections import defaultdict

# ================================
# Page Configuration
# ================================
st.set_page_config(page_title="Vehicle Diagnostic AI", page_icon="🚗", layout="wide")

# ================================
# Session State Initialization
# ================================
if 'diag_index' not in st.session_state:
    st.session_state.diag_index = None
if 'history' not in st.session_state:
    st.session_state.history = []

# ================================
# Core Logic: XML Indexing
# ================================
def build_index(file):
    """Parses XML and builds a fast lookup dictionary."""
    try:
        tree = etree.parse(file)
        root = tree.getroot()
        
        index = {
            'objects': {},      # ObjectID -> Description
            'exceptions': {},   # ObjectID -> Fault Info
            'metadata': defaultdict(list), # ObjectID -> [Hardware Info]
            'bus_types': set(),
            'manufacturers': set(),
            'flash_to_id': {}
        }

        # 1. Index DataObjects (Signals)
        for elem in root.xpath('.//DataObjects'):
            oid = elem.get('ObjectID')
            if oid:
                index['objects'][oid] = {
                    'name': elem.get('Name', ''),
                    'desc': elem.get('Description', ''),
                    'unit': elem.get('UnitText', '')
                }

        # 2. Index Exceptions (Faults)
        for elem in root.xpath('.//ExceptionMetadata'):
            oid = elem.get('ObjectID')
            if oid:
                index['exceptions'][oid] = {
                    'action': elem.get('CorrectiveAction', ''),
                    'flash': elem.get('FlashCode', ''),
                    'severity': elem.get('SeverityID', '')
                }
                if elem.get('FlashCode'):
                    index['flash_to_id'][elem.get('FlashCode')] = oid

        # 3. Index Metadata (Hardware)
        for elem in root.xpath('.//DataPointMetadata'):
            oid = elem.get('ObjectID')
            bt = elem.get('BusType', '')
            mf = elem.get('ManufacturerAndModel', '')
            if oid:
                index['metadata'][oid].append({
                    'bus_type': bt,
                    'mfg': mf,
                    'fw': elem.get('FirmwareVersion', '')
                })
                if bt: index['bus_types'].add(bt)
                if mf: index['manufacturers'].add(mf)
        
        return index
    except Exception as e:
        st.error(f"XML Error: {e}")
        return None

# ================================
# Conversational Query Handler
# ================================
def process_chat(query, index):
    q = query.lower().strip()
    
    # 1. Greetings
    if q in ['hi', 'hello', 'hey', 'help']:
        return "👋 **Hello!** I'm your Diagnostic Assistant. Ask me about **ObjectIDs**, **Bus Types**, or search for symptoms like **'Brake'** or **'Engine'**."

    # 2. "How many" Queries
    if "how many" in q or "count" in q:
        if "bus type" in q or "bustype" in q:
            # Check for specific ObjectID within the "how many" query
            id_match = re.search(r'(\d{4,})', q)
            if id_match:
                oid = id_match.group(1)
                bts = {m['bus_type'] for m in index['metadata'].get(oid, []) if m['bus_type']}
                return f"✅ ObjectID **{oid}** uses **{len(bts)}** unique Bus Types: `{', '.join(sorted(bts))}`" if bts else f"❌ No Bus Types found for ID {oid}."
            return f"✅ There are **{len(index['bus_types'])}** unique Bus Types in this file: `{', '.join(sorted(index['bus_types']))}`"
        
        if "manufacturer" in q:
            return f"✅ Total unique manufacturers: **{len(index['manufacturers'])}**."

    # 3. Direct ID Lookup
    id_match = re.search(r'(\d{5,})', q)
    if id_match:
        oid = id_match.group(1)
        if oid in index['objects'] or oid in index['metadata']:
            res = f"### 🔍 Report for ObjectID: {oid}\n\n"
            # Signal Info
            obj = index['objects'].get(oid, {})
            res += f"**Description:** {obj.get('desc', 'N/A')}\n\n"
            # Fault Info
            exc = index['exceptions'].get(oid, {})
            if exc:
                res += f"⚠️ **Fault Info:** {exc['action']} (Flash: `{exc['flash']}`)\n\n"
            # Hardware Info
            meta = index['metadata'].get(oid, [])
            if meta:
                res += "**🔧 Associated Hardware:**\n"
                for m in meta[:5]:
                    res += f"- {m['mfg']} (Bus: {m['bus_type']})\n"
            return res
        return f"❌ ObjectID **{oid}** not found in the database."

    # 4. Keyword Search (Symptoms)
    search_words = [w for w in q.split() if len(w) > 3 and w not in ['show', 'find', 'search']]
    if search_words:
        term = search_words[0]
        matches = [oid for oid, data in index['objects'].items() if term in data['desc'].lower()]
        if matches:
            res = f"🔍 Found **{len(matches)}** results for '{term}':\n\n"
            for oid in matches[:5]:
                res += f"- **ID {oid}**: {index['objects'][oid]['desc']}\n"
            return res

    return "❌ I didn't quite get that. Try asking 'How many bus types?' or enter an ObjectID like '2000275'."

# ================================
# Main User Interface
# ================================
st.title("🚗 XML Diagnostic Chatbot")

uploaded_file = st.sidebar.file_uploader("Upload data_dictionary.xml", type="xml")

if uploaded_file:
    if st.session_state.diag_index is None:
        st.session_state.diag_index = build_index(uploaded_file)
    
    index = st.session_state.diag_index
    
    # Simple Stats Bar
    cols = st.columns(3)
    cols[0].metric("Signals", len(index['objects']))
    cols[1].metric("Bus Types", len(index['bus_types']))
    cols[2].metric("Manufacturers", len(index['manufacturers']))

    # Chat Input
    user_input = st.chat_input("Ask about an ObjectID, Bus Type, or symptom...")
    
    if user_input:
        response = process_chat(user_input, index)
        st.session_state.history.append({"q": user_input, "a": response})

    # Display Chat History
    for chat in reversed(st.session_state.history):
        with st.chat_message("user"): st.write(chat['q'])
        with st.chat_message("assistant"): st.markdown(chat['a'])
else:
    st.info("Please upload the XML file in the sidebar to start.")
