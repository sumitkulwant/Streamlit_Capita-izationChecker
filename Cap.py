import streamlit as st
import ollama  # Or use Groq as shown below

def ask_ai_with_xml_context(user_query, index):
    """
    Sends the XML index and the user query to the AI.
    The AI decides how to answer.
    """
    # 1. Create a compact version of your XML data for the AI to read
    # We send the summaries so we don't hit memory limits
    context_summary = f"""
    You are a Vehicle Diagnostic Expert. Use this XML data to answer:
    - Total Signals: {len(index['data_objects'])}
    - Total Bus Types: {len(index['bus_types'])}
    - Manufacturers: {', '.join(list(index['manufacturers'])[:10])}
    - Unique Bus IDs: {', '.join(list(index['bus_types']))}
    """

    # 2. Call the AI (Example using local Ollama, swap for Groq if preferred)
    prompt = f"Context: {context_summary}\n\nUser Question: {user_query}"
    
    try:
        # If using Groq, use client.chat.completions.create here
        response = ollama.generate(model='llama3', prompt=prompt)
        return response['response'], "success"
    except Exception as e:
        return f"AI Error: {e}", "error"

# In your Main UI, update the search block:
if query:
    with st.spinner("AI is thinking..."):
        # No more hardcoded "if hi" checks!
        answer, status = ask_ai_with_xml_context(query, st.session_state.diag_index)
        
        if status == "success":
            st.markdown(answer)
        else:
            st.error(answer)
