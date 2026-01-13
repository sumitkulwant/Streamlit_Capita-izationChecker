import streamlit as st
from lxml import etree
import re
import os
from collections import defaultdict

# ================================
# Page Config
# ================================
st.set_page_config(page_title="Vehicle Diagnostic System", page_icon="🚗", layout="wide")

# ================================
# Initialize Session State
# ================================
if 'diag_index' not in st.session_state:
    st.session_state.diag_index = None

# ================================
# Helper Functions
# ================================
def build_diagnostic_index(uploaded_file):
    """Builds the index once and stores it in session state"""
    try:
        tree = etree.parse(uploaded_file)
        root = tree.getroot()
        
        index = {
            'data_objects': {},
            'exceptions': {},
            'metadata': defaultdict(list),
            'bus_types': set(),
            'manufacturers': set(),
            'flash_codes': {}
        }

        for elem in root.xpath('.//DataObjects'):
            obj_id = elem.get('ObjectID')
            if obj_id:
                index['data_objects'][obj_id] = {
                    'description': elem.get('Description', ''),
                    'unit_text': elem.get('UnitText', ''),
                }

        for elem in root.xpath('.//ExceptionMetadata'):
            obj_id = elem.get('ObjectID')
            if obj_id:
                index['exceptions'][obj_id] = {
                    'corrective_action': elem.get('CorrectiveAction', ''),
                    'flash_code': elem.get('FlashCode', ''),
                    'severity': elem.get('SeverityID', ''),
                }
                if elem.get('FlashCode'):
                    index['flash_codes'][elem.get('FlashCode')] = obj_id

        for elem in root.xpath('.//DataPointMetadata'):
            obj_id = elem.get('ObjectID')
            if obj_id:
                bus_type = elem.get('BusType', '')
                mfg = elem.get('ManufacturerAndModel', '')
                index['metadata'][obj_id].append({
                    'manufacturer': mfg,
                    'firmware': elem.get('FirmwareVersion', ''),
                    'bus_type': bus_type,
                })
                if bus_type: index['bus_types'].add(bus_type)
                if mfg: index['manufacturers'].add(mfg)
        
        return index
    except Exception as e:
        st.error(f"Error indexing XML: {e}")
        return None

def format_report(obj_id, index):
    """Restored the detailed report formatting you liked"""
    if obj_id not in index['data_objects'] and obj_id not in index['metadata']:
        return f"❌ ObjectID **{obj_id}** not found.", "error"
    
    data = index['data_objects'].get(obj_id, {})
    exc = index['exceptions'].get(obj_id, {})
    meta = index['metadata'].get(obj_id, [])

    report = f"## 🔍 Diagnostic Report for ObjectID: **{obj_id}**\n\n"
    report += f"### 📊 Signal Description\n**Description:** {data.get('description', 'N/A')}\n"
    report += f"**Unit:** {data.get('unit_text', 'N/A')}\n\n"
    
    if exc:
        report += "### ⚠️ Diagnostic Information\n"
        report += f"**Corrective Action:** {exc.get('corrective_action', 'N/A')}\n"
        report += f"**Flash Code:** `{exc.get('flash_code', 'N/A')}` | **Severity:** {exc.get('severity', 'N/A')}\n\n"
    
    if meta:
        report += "### 🔧 Hardware & Firmware\n"
        for i, m in enumerate(meta[:5], 1):
            report += f"{i}. **{m['manufacturer']}** (Firmware: `{m['firmware']}` | Bus: {m['bus_type']})\n"
    
    return report, "info"

# ================================
# Main UI Logic
# ================================
st.title("🚗 Vehicle Diagnostic System Query")

# File Upload (Always check if index exists)
if st.session_state.diag_index is None:
    uploaded_file = st.file_uploader("Upload data_dictionary.xml", type=['xml'])
    if uploaded_file:
        with st.spinner("🔄 Indexing Data..."):
            st.session_state.diag_index = build_diagnostic_index(uploaded_file)
            st.rerun()
    st.stop()

# Short reference
index = st.session_state.diag_index

# --- Sidebar Metrics (Older UI Style) ---
with st.sidebar:
    st.header("📊 System Overview")
    st.metric("Signals", len(index['data_objects']))
    st.metric("Flash Codes", len(index['flash_codes']))
    st.metric("Bus Types", len(index['bus_types']))
    
    if st.button("🔄 Clear & Load New File"):
        st.session_state.diag_index = None
        st.rerun()

# --- Search Interface ---
query = st.text_input("Ask about an ObjectID, Bus Type, or Symptom:", placeholder="e.g. 2000275 or 'Brake'")

if query:
    q_lower = query.lower().strip()
    
    # Greeting handling
    if q_lower in ['hi', 'hello', 'hey']:
        st.info("👋 Hello! Enter an ObjectID or keyword to get started.")
    
    # Stats: How many bus types
    elif "how many" in q_lower and ("bus" in q_lower or "bustype" in q_lower):
        id_match = re.search(r'(\d{5,})', q_lower)
        if id_match:
            oid = id_match.group(1)
            bts = {m['bus_type'] for m in index['metadata'].get(oid, []) if m['bus_type']}
            st.success(f"✅ ObjectID **{oid}** has **{len(bts)}** unique bus types: `{', '.join(sorted(bts))}`")
        else:
            st.success(f"✅ Total unique Bus Types in system: **{len(index['bus_types'])}**")

    # ID Lookup
    elif re.search(r'(\d{5,})', q_lower):
        oid = re.search(r'(\d{5,})', q_lower).group(1)
        report, status = format_report(oid, index)
        st.info(report)

    # Keyword Search
    else:
        results = [oid for oid, d in index['data_objects'].items() if q_lower in d['description'].lower()]
        if results:
            st.write(f"🔍 Found {len(results)} matches:")
            for oid in results[:5]:
                st.write(f"- **ID {oid}**: {index['data_objects'][oid]['description']}")
        else:
            st.error("❌ No matches found. Try searching for a specific ObjectID.")
