import streamlit as st
import pandas as pd
import os
import json
import google.generativeai as genai
import database as db

# Page Configuration
st.set_page_config(
    page_title="AI Purchase & Ledger Hub",
    layout="wide",
    page_icon="📈"
)

# --- CONFIG & GEMINI AI SETUP ---
# Fetch API key from Streamlit secrets or environment variables
api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
else:
    st.warning("⚠️ GEMINI_API_KEY not found in Streamlit Secrets. AI extraction feature will be disabled until configured.")

def extract_bill_with_ai(uploaded_file_bytes, file_type):
    """Uses Gemini 2.5 Flash to extract structured JSON from bill images/PDFs."""
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        # Save temporary file for Gemini processing
        temp_filename = f"temp_bill.{file_type}"
        with open(temp_filename, "wb") as f:
            f.write(uploaded_file_bytes.getbuffer())
            
        uploaded_file_ref = genai.upload_file(temp_filename)
        
        prompt = """
        Analyze this purchase bill and extract the details strictly into the following JSON format:
        {
          "party_name": "Vendor Name",
          "invoice_number": "INV-123",
          "date": "YYYY-MM-DD",
          "total_amount": 000.00,
          "items": [
            {
              "item_name": "Item Description",
              "category": "Raw Material or General",
              "quantity": 1.0,
              "rate": 000.00
            }
          ]
        }
        Return ONLY valid JSON. No extra text or markdown code blocks outside JSON structure if possible.
        """
        
        response = model.generate_content([uploaded_file_ref, prompt])
        # Clean response text to ensure valid JSON parsing
        text_response = response.text.strip()
        if text_response.startswith("```json"):
            text_response = text_response[7:-3].strip()
            
        data = json.loads(text_response)
        
        # Clean up temp file
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
            
        return data
    except Exception as e:
        st.error(f"AI Extraction Error: {str(e)}")
        return None

# --- SIDEBAR CONTROLS & UPLOADER ---
st.sidebar.title("🛠️ Controls & Ingestion")
selected_month = st.sidebar.selectbox("Filter Month / Period", ["All Time", "September 2026", "August 2026", "July 2026"])

st.sidebar.markdown("---")
st.sidebar.subheader("📥 Upload New Purchase Bill")
uploaded_file = st.sidebar.file_uploader("Upload Bill (PDF, PNG, JPG)", type=["pdf", "png", "jpg"])

if uploaded_file and api_key:
    if st.sidebar.button("🤖 Process Bill with AI"):
        with st.spinner("Extracting data via Gemini AI..."):
            file_extension = uploaded_file.name.split(".")[-1].lower()
            extracted_data = extract_bill_with_ai(uploaded_file, file_extension)
            
            if extracted_data:
                st.sidebar.success("Extraction Successful!")
                # Push into SQLite Database
                success, msg = db.process_new_bill(
                    party_name=extracted_data.get("party_name", "Unknown Vendor"),
                    invoice_no=extracted_data.get("invoice_number", "INV-MISC"),
                    bill_date=extracted_data.get("date", pd.Timestamp.today().strftime('%Y-%m-%d')),
                    items_list=extracted_data.get("items", []),
                    total_amount=float(extracted_data.get("total_amount", 0.0))
                )
                if success:
                    st.sidebar.success("✅ Saved to Database & Ledger Updated!")
                    st.rerun()
                else:
                    st.sidebar.error(f"Database Error: {msg}")

# --- MAIN DASHBOARD HEADER ---
st.title("🏢 Company Purchase & Ledger Command Center")
st.markdown("Automated AI bill parsing, dynamic party ledgers, and real-time item price tracking.")

# --- TABS CONFIGURATION ---
tab1, tab2, tab3 = st.tabs(["📊 Overview", "📑 Party-Wise Ledgers", "🏷️ Item Price Tracker"])

# --- TAB 1: OVERVIEW ---
with tab1:
    ledger_df
