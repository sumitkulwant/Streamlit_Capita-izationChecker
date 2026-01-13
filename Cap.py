import streamlit as st
from lxml import etree
from groq import Groq
import re
import os

# ================================
# Page Config
# ================================
st.set_page_config(
    page_title="CAN Data Dictionary AI",
    page_icon="🚗",
    layout="wide"
)

# ================================
# API Key - Try multiple sources
# ================================
GROQ_API_KEY = "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"

# Try Streamlit secrets first
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except:
    pass

# Try environment variable
if not GROQ_API_KEY:
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# If still no key, ask user
if not GROQ_API_KEY:
    st.error("⚠️ GROQ_API_KEY not found!")
    st.markdown("""
    **To fix this:**
    1. Go to Streamlit Cloud dashboard
    2. Click on your app → ⚙️ Settings
    3. Go to "Secrets" section
    4. Add:
    ```
    GROQ_API_KEY = "your_groq_api_key_here"
    ```
    5. Save and redeploy
    """)
    st.stop()

try:
    client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    st.error(f"Failed to initialize Groq client: {e}")
    st.stop()

# ================================
# Load XML (Cached)
# ================================
@st.cache_resource
def load_xml(xml_file):
    """Load and cache XML in memory"""
    try:
        tree = etree.parse(xml_file)
        root = tree.getroot()
        return tree, root
    except Exception as e:
        st.error(f"Error loading XML: {e}")
        return None, None

# Check for XML file
XML_FILE = "data_dictionary.xml"
if not os.path.exists(XML_FILE):
    st.error(f"❌ XML file '{XML_FILE}' not found!")
    st.info("Please upload your data_dictionary.xml file")
    
    uploaded_file = st.file_uploader("Upload your data_dictionary.xml", type=['xml'])
    if uploaded_file:
        try:
            with open(XML_FILE, 'wb') as f:
                f.write(uploaded_file.getbuffer())
            st.success("✅ XML uploaded! Reloading...")
            st.rerun()
        except Exception as e:
            st.error(f"Upload failed: {e}")
    st.stop()

with st.spinner("🔄 Loading XML..."):
    tree, root = load_xml(XML_FILE)

if root is None:
    st.error("Failed to load XML. Please check the file format.")
    st.stop()

# ================================
# XPath Query Functions
# ================================
@st.cache_data
def get_all_bustypes():
    try:
        bustypes = set(root.xpath('//@BusType'))
        return sorted(bustypes)
    except:
        return []

def get_elements_by_bustype(bustype):
    try:
        return root.xpath(f'//*[@BusType="{bustype}"]')
    except:
        return []

def get_elements_by_pgn(pgn):
    try:
        return root.xpath(f'//*[@PGN="{pgn}"]')
    except:
        return []

def search_text_in_xml(search_term):
    try:
        xpath = f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{search_term.lower()}')]"
        return root.xpath(xpath)
    except:
        return []

def element_to_string(elem):
    try:
        return etree.tostring(elem, pretty_print=True, encoding='unicode')
    except:
        return str(elem)

# ================================
# LLM Query
# ================================
def ask_llm(context, question):
    try:
        prompt = f"""You are a CAN Data Dictionary expert.
Answer based ONLY on this XML context:

{context[:4000]}

Question: {question}"""
        
        with st.spinner("🤖 Analyzing with AI..."):
            chat = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=1000
            )
        
        return chat.choices[0].message.content
    except Exception as e:
        return f"❌ Error calling AI: {str(e)}"

# ================================
# Query Handler
# ================================
def handle_query(question):
    if not question.strip():
        return "Please enter a question.", "warning"
    
    q_lower = question.lower()
    
    # Count BusTypes
    if "how many" in q_lower and "bustype" in q_lower:
        bustypes = get_all_bustypes()
        return f"✅ Found **{len(bustypes)}** unique BusTypes", "success"
    
    # List BusTypes
    if ("list" in q_lower or "show all" in q_lower) and "bustype" in q_lower:
        bustypes = get_all_bustypes()
        if len(bustypes) > 50:
            return f"All **{len(bustypes)}** BusTypes:\n\n`{', '.join(bustypes[:50])}` ... and {len(bustypes)-50} more", "success"
        return f"All **{len(bustypes)}** BusTypes:\n\n`{', '.join(bustypes)}`", "success"
    
    # Specific BusType
    match = re.search(r'bustype[:\s]+(\d+)', q_lower)
    if match:
        bustype = match.group(1)
        elements = get_elements_by_bustype(bustype)
        if not elements:
            return f"❌ BusType {bustype} not found", "error"
        
        result = f"✅ Found **{len(elements)}** elements with BusType={bustype}\n\n"
        for i, elem in enumerate(elements[:3], 1):
            result += f"**Element {i}:**\n```xml\n{element_to_string(elem)[:500]}\n```\n"
        
        if len(elements) > 3:
            result += f"\n... and {len(elements) - 3} more elements"
        
        return result, "info"
    
    # PGN query
    match = re.search(r'pgn[:\s]+(\w+)', q_lower)
    if match:
        pgn = match.group(1).upper()
        elements = get_elements_by_pgn(pgn)
        if not elements:
            return f"❌ PGN {pgn} not found", "error"
        
        result = f"✅ Found **{len(elements)}** elements with PGN={pgn}\n\n"
        for i, elem in enumerate(elements[:3], 1):
            result += f"**Element {i}:**\n```xml\n{element_to_string(elem)[:500]}\n```\n"
        
        return result, "info"
    
    # Complex query - use LLM
    search_terms = [word for word in q_lower.split() if len(word) > 3]
    if search_terms:
        results = []
        for term in search_terms[:2]:
            found = search_text_in_xml(term)
            results.extend(found)
        
        if results:
            unique_results = list({id(e): e for e in results}.values())
            context = "\n\n".join([element_to_string(e)[:500] for e in unique_results[:10]])
            answer = ask_llm(context, question)
            return answer, "success"
    
    return "❌ Could not understand query. Try examples from the sidebar.", "error"

# ================================
# Streamlit UI
# ================================
st.title("🚗 CAN Data Dictionary AI")
st.markdown("Ask questions about your XML data dictionary using natural language!")

# Sidebar
with st.sidebar:
    st.header("📊 Quick Stats")
    bustypes = get_all_bustypes()
    st.metric("Total BusTypes", len(bustypes))
    
    st.header("💡 Example Queries")
    examples = [
        "How many BusTypes are present?",
        "List all BusTypes",
        "Show BusType 38",
        "What's in PGN 65226?",
        "Which signals use PSI?",
        "Show brake system signals"
    ]
    
    for example in examples:
        if st.button(example, key=example, use_container_width=True):
            st.session_state.query = example
            st.session_state.should_search = True

# Initialize session state
if 'history' not in st.session_state:
    st.session_state.history = []
if 'query' not in st.session_state:
    st.session_state.query = ''
if 'should_search' not in st.session_state:
    st.session_state.should_search = False

# Query input
query = st.text_input(
    "Ask a question:",
    value=st.session_state.query,
    placeholder="e.g., How many BusTypes are present?",
    key="query_input"
)

# Handle search
if st.button("🔍 Search", type="primary") or st.session_state.should_search:
    st.session_state.should_search = False
    
    if query:
        # Get answer
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
        
        # Keep only last 10
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
st.markdown("Built with Streamlit + Groq + lxml | [View Source](https://github.com/yourusername/xml-query-app)")
