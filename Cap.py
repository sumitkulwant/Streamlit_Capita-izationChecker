import streamlit as st
from lxml import etree
import re
from collections import defaultdict

# ================================
# Core Logic: Data Indexing
# ================================
def build_index(file):
    """Indexes the entire XML into memory for instant lookup."""
    try:
        tree = etree.parse(file)
        root = tree.getroot()
        
        index = {
            'signals': {},      # ObjectID -> Description
            'faults': {},       # ObjectID -> Corrective Action
            'metadata': defaultdict(list), # ObjectID -> List of HW Configs
            'bus_types': set(),
            'manufacturers': set()
        }

        # 1. Map Data Signal Descriptions
        for elem in root.xpath('.//DataObjects'):
            oid = elem.get('ObjectID')
            if oid:
                index['signals'][oid] = elem.get('Description', 'No description available')

        # 2. Map Faults/Corrective Actions
        for elem in root.xpath('.//ExceptionMetadata'):
            oid = elem.get('ObjectID')
            if oid:
                index['faults'][oid] = {
                    'action': elem.get('CorrectiveAction', 'N/A'),
                    'flash': elem.get('FlashCode', 'N/A')
                }

        # 3. Map ALL Metadata (Crucial for multi-bus IDs)
        for elem in root.xpath('.//DataPointMetadata'):
            oid = elem.get('ObjectID')
            bt = elem.get('BusType', '')
            if oid:
                index['metadata'][oid].append({
                    'bus': bt,
                    'mfg': elem.get('ManufacturerAndModel', 'N/A'),
                    'fw': elem.get('FirmwareVersion', 'N/A')
                })
                if bt: index['bus_types'].add(bt)
                if elem.get('ManufacturerAndModel'): 
                    index['manufacturers'].add(elem.get('ManufacturerAndModel'))
        
        return index
    except Exception as e:
        st.error(f"Error reading XML: {e}")
        return None

# ================================
# Generalized Search Handler
# ================================
def generalized_search(query, index):
    q = query.strip()
    
    # Check if the query is a number (ObjectID)
    if q.isdigit():
        target_id = q
        
        # Pull everything associated with this ID
        signal = index['signals'].get(target_id, "Signal not found")
        fault = index['faults'].get(target_id, {})
        hw_configs = index['metadata'].get(target_id, [])
        unique_buses = sorted(list(set(m['bus'] for m in hw_configs if m['bus'])))

        # Display result
        st.markdown(f"### 📋 Analysis for ID: `{target_id}`")
        st.info(f"**Description:** {signal}")
        
        if fault:
            st.warning(f"⚠️ **Fault Action:** {fault['action']} (Flash Code: `{fault['flash']}`)")
            
        if hw_configs:
            st.success(f"🚌 **Bus Types Found ({len(unique_buses)}):** {', '.join(unique_buses)}")
            with st.expander("View Hardware/Firmware Details"):
                for cfg in hw_configs:
                    st.write(f"- **{cfg['mfg']}** | FW: `{cfg['fw']}` | Bus: {cfg['bus']}")
        else:
            st.error("No hardware metadata found for this ID.")
            
    else:
        # If it's text, search descriptions
        matches = [oid for oid, desc in index['signals'].items() if q.lower() in desc.lower()]
        if matches:
            st.write(f"🔍 Found **{len(matches)}** IDs matching '{q}':")
            for m in matches[:10]:
                st.button(f"ID {m}: {index['signals'][m][:100]}...", on_click=lambda id=m: generalized_search(id, index))
        else:
            st.error("No results found. Please enter a valid ObjectID or Keyword.")

# ================================
# Streamlit UI
# ================================
st.set_page_config(page_title="General XML Search", layout="wide")

if 'index' not in st.session_state:
    st.session_state.index = None

uploaded_file = st.sidebar.file_uploader("Upload XML", type="xml")

if uploaded_file:
    if not st.session_state.index:
        st.session_state.index = build_index(uploaded_file)
    
    idx = st.session_state.index
    
    # Sidebar Overview
    st.sidebar.metric("Unique Bus Types", len(idx['bus_types']))
    st.sidebar.metric("Unique Signals", len(idx['signals']))
    
    user_query = st.text_input("Enter any ObjectID or keyword:")
    
    if user_query:
        generalized_search(user_query, idx)
else:
    st.info("Upload the XML file to begin searching.")
