import streamlit as st
from lxml import etree
import re
import os
from collections import defaultdict

# ================================
# Page Config
# ================================
st.set_page_config(
    page_title="Vehicle Diagnostic System",
    page_icon="🚗",
    layout="wide"
)

# ================================
# Initialize Session State
# ================================
if 'xml_loaded' not in st.session_state:
    st.session_state.xml_loaded = False
if 'root' not in st.session_state:
    st.session_state.root = None
if 'diag_index' not in st.session_state:
    st.session_state.diag_index = None
if 'history' not in st.session_state:
    st.session_state.history = []
if 'query' not in st.session_state:
    st.session_state.query = ''
if 'should_search' not in st.session_state:
    st.session_state.should_search = False

# ================================
# File Upload Section
# ================================
st.title("🚗 Vehicle Diagnostic System Query")

if not st.session_state.xml_loaded:
    st.markdown("### 📁 Upload Your XML Data Dictionary")
    st.info("Upload your vehicle diagnostic XML file to begin querying.")
    
    uploaded_file = st.file_uploader(
        "Choose an XML file",
        type=['xml'],
        help="Upload your data_dictionary.xml file"
    )
    
    if uploaded_file is not None:
        try:
            with st.spinner("🔄 Loading XML file..."):
                # Parse XML from uploaded file
                tree = etree.parse(uploaded_file)
                st.session_state.root = tree.getroot()
                st.session_state.xml_loaded = True
                st.success("✅ XML file loaded successfully!")
                st.rerun()
        except Exception as e:
            st.error(f"❌ Error loading XML: {str(e)}")
            st.stop()
    else:
        st.warning("⬆️ Please upload an XML file to continue")
        st.stop()

# ================================
# Parse & Index by ObjectID
# ================================
def build_diagnostic_index(root):
    """Build a comprehensive index linking ObjectIDs across all three sections"""
    index = {
        'data_objects': {},
        'exceptions': {},
        'metadata': {},
        'bus_types': set(),
        'manufacturers': set(),
        'flash_codes': {},
        'severity_levels': set()
    }
    
    # Index DataObjects
    for elem in root.xpath('.//DataObjects'):
        obj_id = elem.get('ObjectID')
        if obj_id:
            index['data_objects'][obj_id] = {
                'description': elem.get('Description', ''),
                'unit_text': elem.get('UnitText', ''),
            }
    
    # Index ExceptionMetadata
    for elem in root.xpath('.//ExceptionMetadata'):
        obj_id = elem.get('ObjectID')
        if obj_id:
            flash_code = elem.get('FlashCode', '')
            severity = elem.get('SeverityID', '')
            
            index['exceptions'][obj_id] = {
                'corrective_action': elem.get('CorrectiveAction', ''),
                'flash_code': flash_code,
                'severity': severity,
            }
            
            if flash_code:
                index['flash_codes'][flash_code] = obj_id
            if severity:
                index['severity_levels'].add(severity)
    
    # Index DataPointMetadata
    for elem in root.xpath('.//DataPointMetadata'):
        obj_id = elem.get('ObjectID')
        if obj_id:
            manufacturer = elem.get('ManufacturerAndModel', '')
            bus_type = elem.get('BusType', '')
            
            index['metadata'][obj_id] = {
                'manufacturer': manufacturer,
                'firmware': elem.get('FirmwareVersion', ''),
                'bus_type': bus_type,
            }
            
            if bus_type:
                index['bus_types'].add(bus_type)
            if manufacturer:
                index['manufacturers'].add(manufacturer)
    
    return index

# Build index if not already done
if st.session_state.diag_index is None and st.session_state.root is not None:
    with st.spinner("📊 Indexing diagnostic data by ObjectID..."):
        st.session_state.diag_index = build_diagnostic_index(st.session_state.root)

diag_index = st.session_state.diag_index
root = st.session_state.root

# ================================
# Optional AI Integration
# ================================
USE_AI = False
client = None

try:
    GROQ_API_KEY = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
    if GROQ_API_KEY:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        USE_AI = True
except:
    pass

def ask_ai_about_diagnostic(object_id, question):
    """Use AI to provide more detailed analysis"""
    if not USE_AI or not client:
        return None
    
    try:
        diag = get_complete_diagnostic(object_id)
        
        context = f"""
ObjectID: {object_id}

Signal: {diag['data_object'].get('description', 'N/A') if diag['data_object'] else 'N/A'}
Unit: {diag['data_object'].get('unit_text', 'N/A') if diag['data_object'] else 'N/A'}

Corrective Action: {diag['exception'].get('corrective_action', 'N/A') if diag['exception'] else 'N/A'}
Flash Code: {diag['exception'].get('flash_code', 'N/A') if diag['exception'] else 'N/A'}
Severity: {diag['exception'].get('severity', 'N/A') if diag['exception'] else 'N/A'}

Manufacturer: {diag['metadata'].get('manufacturer', 'N/A') if diag['metadata'] else 'N/A'}
Firmware: {diag['metadata'].get('firmware', 'N/A') if diag['metadata'] else 'N/A'}
Bus Type: {diag['metadata'].get('bus_type', 'N/A') if diag['metadata'] else 'N/A'}
"""
        
        prompt = f"""You are a vehicle diagnostic expert. Based on this diagnostic data:

{context}

Question: {question}

Provide a clear, practical answer."""
        
        chat = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=500
        )
        
        return chat.choices[0].message.content
    except:
        return None

# ================================
# Diagnostic Query Functions
# ================================
def get_complete_diagnostic(object_id):
    """Get complete diagnostic info for an ObjectID across all three sections"""
    result = {
        'object_id': object_id,
        'data_object': diag_index['data_objects'].get(object_id),
        'exception': diag_index['exceptions'].get(object_id),
        'metadata': diag_index['metadata'].get(object_id)
    }
    return result

def search_by_description(search_term):
    """Search in DataObject descriptions"""
    results = []
    for obj_id, data in diag_index['data_objects'].items():
        if search_term.lower() in data['description'].lower():
            results.append(obj_id)
    return results

def search_by_flash_code(flash_code):
    """Find ObjectID by FlashCode"""
    return diag_index['flash_codes'].get(flash_code)

def get_by_manufacturer(manufacturer):
    """Get all ObjectIDs for a specific manufacturer"""
    results = []
    for obj_id, data in diag_index['metadata'].items():
        if manufacturer.lower() in data['manufacturer'].lower():
            results.append(obj_id)
    return results

def get_by_bus_type(bus_type):
    """Get all ObjectIDs using a specific BusType"""
    results = []
    for obj_id, data in diag_index['metadata'].items():
        if data['bus_type'] == bus_type:
            results.append(obj_id)
    return results

def format_diagnostic_report(object_id):
    """Format a complete diagnostic report for an ObjectID"""
    diag = get_complete_diagnostic(object_id)
    
    report = f"## 🔍 Diagnostic Report for ObjectID: **{object_id}**\n\n"
    
    # Section 1: Data Signal
    if diag['data_object']:
        report += "### 📊 Signal Description\n"
        report += f"**Description:** {diag['data_object']['description']}\n\n"
        if diag['data_object']['unit_text']:
            report += f"**Unit:** {diag['data_object']['unit_text']}\n\n"
    else:
        report += "### 📊 Signal Description\n❌ No data found\n\n"
    
    # Section 2: Fault/Exception
    if diag['exception']:
        report += "### ⚠️ Diagnostic Information\n"
        report += f"**Corrective Action:** {diag['exception']['corrective_action']}\n\n"
        if diag['exception']['flash_code']:
            report += f"**Flash Code:** `{diag['exception']['flash_code']}`\n\n"
        if diag['exception']['severity']:
            report += f"**Severity:** {diag['exception']['severity']}\n\n"
    else:
        report += "### ⚠️ Diagnostic Information\n❌ No exception data found\n\n"
    
    # Section 3: Hardware/Firmware
    if diag['metadata']:
        report += "### 🔧 Hardware & Firmware\n"
        report += f"**Manufacturer & Model:** {diag['metadata']['manufacturer']}\n\n"
        if diag['metadata']['firmware']:
            report += f"**Firmware Version:** `{diag['metadata']['firmware']}`\n\n"
        if diag['metadata']['bus_type']:
            report += f"**Bus Type:** {diag['metadata']['bus_type']}\n\n"
    else:
        report += "### 🔧 Hardware & Firmware\n❌ No metadata found\n\n"
    
    return report

# ================================
# Query Handler
# ================================
def handle_query(question):
    if not question.strip():
        return "Please enter a question.", "warning"
    
    q_lower = question.lower()
    
    # Stats queries
    if "how many" in q_lower:
        if "bus type" in q_lower or "bustype" in q_lower:
            count = len(diag_index['bus_types'])
            return f"✅ Found **{count}** unique Bus Types: {', '.join(sorted(diag_index['bus_types']))}", "success"
        
        if "manufacturer" in q_lower:
            count = len(diag_index['manufacturers'])
            return f"✅ Found **{count}** manufacturers", "info"
        
        if "object" in q_lower or "signal" in q_lower:
            count = len(diag_index['data_objects'])
            return f"✅ Found **{count}** data objects/signals", "success"
        
        if "flash code" in q_lower or "fault" in q_lower:
            count = len(diag_index['flash_codes'])
            return f"✅ Found **{count}** flash codes", "success"
    
    # List queries
    if "list" in q_lower or "show all" in q_lower:
        if "bus type" in q_lower or "bustype" in q_lower:
            bus_types = sorted(diag_index['bus_types'])
            return f"**All Bus Types ({len(bus_types)}):**\n\n`{', '.join(bus_types)}`", "success"
        
        if "manufacturer" in q_lower:
            manufacturers = sorted(diag_index['manufacturers'])
            return f"**All Manufacturers ({len(manufacturers)}):**\n\n" + "\n".join([f"- {m}" for m in manufacturers[:20]]), "info"
        
        if "severity" in q_lower:
            severities = sorted(diag_index['severity_levels'])
            return f"**All Severity Levels:**\n\n`{', '.join(severities)}`", "info"
    
    # ObjectID lookup
    match = re.search(r'object\s*id[:\s]+(\w+)', q_lower)
    if match:
        obj_id = match.group(1)
        return format_diagnostic_report(obj_id), "info"
    
    # Flash code lookup
    match = re.search(r'flash\s*code[:\s]+(\w+)', q_lower)
    if match:
        flash_code = match.group(1)
        obj_id = search_by_flash_code(flash_code)
        if obj_id:
            return format_diagnostic_report(obj_id), "info"
        else:
            return f"❌ Flash code '{flash_code}' not found", "error"
    
    # Bus type lookup
    match = re.search(r'bus\s*type[:\s]+(\d+)', q_lower)
    if match:
        bus_type = match.group(1)
        obj_ids = get_by_bus_type(bus_type)
        if obj_ids:
            result = f"✅ Found **{len(obj_ids)}** objects using Bus Type {bus_type}\n\n"
            for obj_id in obj_ids[:5]:
                data = diag_index['data_objects'].get(obj_id, {})
                result += f"- **ObjectID {obj_id}:** {data.get('description', 'N/A')[:100]}\n"
            if len(obj_ids) > 5:
                result += f"\n... and {len(obj_ids) - 5} more"
            return result, "info"
        else:
            return f"❌ No objects found for Bus Type {bus_type}", "error"
    
    # Manufacturer search
    if "manufacturer" in q_lower or "cummins" in q_lower or "clever" in q_lower:
        search_term = q_lower.replace("manufacturer", "").strip()
        for manufacturer in diag_index['manufacturers']:
            if search_term in manufacturer.lower() or manufacturer.lower() in search_term:
                obj_ids = get_by_manufacturer(manufacturer)
                result = f"✅ Found **{len(obj_ids)}** objects for **{manufacturer}**\n\n"
                for obj_id in obj_ids[:5]:
                    data = diag_index['data_objects'].get(obj_id, {})
                    result += f"- **ObjectID {obj_id}:** {data.get('description', 'N/A')[:100]}\n"
                if len(obj_ids) > 5:
                    result += f"\n... and {len(obj_ids) - 5} more"
                return result, "info"
    
    # Description search
    search_terms = [word for word in q_lower.split() if len(word) > 4]
    if search_terms:
        for term in search_terms:
            obj_ids = search_by_description(term)
            if obj_ids:
                result = f"✅ Found **{len(obj_ids)}** signals matching '{term}'\n\n"
                for obj_id in obj_ids[:5]:
                    data = diag_index['data_objects'].get(obj_id, {})
                    result += f"- **ObjectID {obj_id}:** {data.get('description', 'N/A')[:100]}\n"
                if len(obj_ids) > 5:
                    result += f"\n... and {len(obj_ids) - 5} more. Try 'ObjectID {obj_ids[5]}' for details."
                return result, "info"
    
    # Try AI for complex questions
    if USE_AI and any(word in q_lower for word in ["why", "how", "what should", "explain", "help", "troubleshoot"]):
        for term in search_terms:
            obj_ids = search_by_description(term)
            if obj_ids:
                ai_response = ask_ai_about_diagnostic(obj_ids[0], question)
                if ai_response:
                    return f"🤖 **AI Analysis:**\n\n{ai_response}\n\n---\n\n**Related ObjectID:** {obj_ids[0]}", "success"
    
    return "❌ Query not understood. Try: 'How many bus types?' or 'Show ObjectID 12345' or 'Flash code 523'", "error"

# ================================
# Main UI (only if XML loaded)
# ================================
st.markdown("**Search vehicle performance data, faults, and hardware info using ObjectID**")

# Sidebar
with st.sidebar:
    st.header("📊 System Overview")
    st.metric("Data Signals", len(diag_index['data_objects']))
    st.metric("Exception Codes", len(diag_index['exceptions']))
    st.metric("Flash Codes", len(diag_index['flash_codes']))
    st.metric("Bus Types", len(diag_index['bus_types']))
    st.metric("Manufacturers", len(diag_index['manufacturers']))
    
    if USE_AI:
        st.success("🤖 AI Mode: Enabled")
    else:
        st.info("🔍 Search Mode: XPath")
    
    st.markdown("---")
    
    # Add reload button
    if st.button("🔄 Load New XML File", use_container_width=True):
        st.session_state.xml_loaded = False
        st.session_state.root = None
        st.session_state.diag_index = None
        st.session_state.history = []
        st.rerun()
    
    st.markdown("---")
    st.header("💡 Example Queries")
    
    examples = [
        "How many bus types are present?",
        "List all manufacturers",
        "Show bus type 38",
        "Search for engine oil pressure",
        "Search for brake",
        "Flash code 523",
    ]
    
    if USE_AI:
        examples.extend([
            "Why would engine oil pressure be low? (AI)",
            "How do I troubleshoot brake issues? (AI)"
        ])
    
    for example in examples:
        if st.button(example, key=example, use_container_width=True):
            st.session_state.query = example
            st.session_state.should_search = True
    
    st.markdown("---")
    st.info("💡 **Tip:** Use ObjectID to link signals → faults → hardware")

# Main query interface
col1, col2 = st.columns([3, 1])

with col1:
    query = st.text_input(
        "Ask a question:",
        value=st.session_state.query,
        placeholder="e.g., How many bus types? or Show ObjectID 12345 or Flash code 523",
        key="query_input"
    )

with col2:
    st.write("")
    st.write("")
    search_clicked = st.button("🔍 Search", type="primary", use_container_width=True)

# Handle search
if search_clicked or st.session_state.should_search:
    st.session_state.should_search = False
    
    if query:
        with st.spinner("Searching..."):
            answer, status = handle_query(query)
        
        # Display answer
        if status == "success":
            st.success(answer)
        elif status == "info":
            st.info(answer)
        elif status == "warning":
            st.warning(answer)
        else:
            st.error(answer)
        
        # Add to history
        st.session_state.history.insert(0, {
            'query': query,
            'answer': answer,
            'status': status
        })
        st.session_state.history = st.session_state.history[:10]

# Show history
if st.session_state.history:
    st.markdown("---")
    st.subheader("📜 Recent Queries")
    
    for i, item in enumerate(st.session_state.history[:5]):
        with st.expander(f"Q: {item['query']}", expanded=(i==0)):
            st.markdown(item['answer'])

# Footer
st.markdown("---")
st.caption("🔗 Three-Layer Architecture: DataObjects → ExceptionMetadata → DataPointMetadata (linked by ObjectID)")
