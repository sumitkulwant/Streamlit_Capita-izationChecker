import gradio as gr
from lxml import etree
from groq import Groq
import re
import os

# ================================
# Configuration
# ================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)
XML_FILE = "data_dictionary.xml"

# Load XML
tree = etree.parse(XML_FILE)
root = tree.getroot()

# ================================
# Query Functions
# ================================
def get_all_bustypes():
    bustypes = set(root.xpath('//@BusType'))
    return sorted(bustypes)

def get_elements_by_bustype(bustype):
    return root.xpath(f'//*[@BusType="{bustype}"]')

def element_to_string(elem):
    return etree.tostring(elem, pretty_print=True, encoding='unicode')

def ask_llm(context, question):
    prompt = f"""You are a CAN Data Dictionary expert.
Answer based ONLY on this XML context:

{context}

Question: {question}"""
    
    chat = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=1000
    )
    
    return chat.choices[0].message.content

def handle_query(question):
    q_lower = question.lower()
    
    # Count BusTypes
    if "how many" in q_lower and "bustype" in q_lower:
        bustypes = get_all_bustypes()
        return f"✅ Found {len(bustypes)} unique BusTypes"
    
    # List BusTypes
    if ("list" in q_lower or "show all" in q_lower) and "bustype" in q_lower:
        bustypes = get_all_bustypes()
        return f"All {len(bustypes)} BusTypes:\n{', '.join(bustypes)}"
    
    # Specific BusType
    match = re.search(r'bustype[:\s]+(\d+)', q_lower)
    if match:
        bustype = match.group(1)
        elements = get_elements_by_bustype(bustype)
        if not elements:
            return f"❌ BusType {bustype} not found"
        
        result = f"✅ Found {len(elements)} elements with BusType={bustype}\n\n"
        for elem in elements[:3]:
            result += element_to_string(elem) + "\n" + "="*50 + "\n"
        
        if len(elements) > 3:
            result += f"\n... and {len(elements) - 3} more elements"
        
        return result
    
    # Fallback to LLM
    return "Please ask about BusTypes, PGNs, or specific signals."

# ================================
# Gradio Interface
# ================================
with gr.Blocks(title="CAN Data Dictionary AI") as demo:
    gr.Markdown("# 🚗 CAN Data Dictionary AI")
    gr.Markdown("Ask questions about your XML data dictionary!")
    
    with gr.Row():
        with gr.Column(scale=2):
            query = gr.Textbox(
                label="Your Question",
                placeholder="e.g., How many BusTypes are present?",
                lines=2
            )
            search_btn = gr.Button("🔍 Search", variant="primary")
        
        with gr.Column(scale=1):
            gr.Markdown("### 💡 Examples")
            gr.Examples(
                examples=[
                    "How many BusTypes are present?",
                    "List all BusTypes",
                    "Show BusType 38",
                    "What's in BusType 47?"
                ],
                inputs=query
            )
    
    output = gr.Textbox(label="Answer", lines=15)
    
    search_btn.click(fn=handle_query, inputs=query, outputs=output)
    query.submit(fn=handle_query, inputs=query, outputs=output)

demo.launch()
