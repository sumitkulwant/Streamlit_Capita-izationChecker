import pandas as pd
import re
from collections import defaultdict
import streamlit as st
from io import BytesIO

st.set_page_config(page_title="Capitalization Checker", layout="wide")
st.title("📝 Capitalization Checker in XML")

# File uploader
file = st.file_uploader("📂 Upload an XML file", type=["xml"])

if file:
    try:
        # Read the uploaded file content once
        file_content = file.read()
        file_buffer = BytesIO(file_content)

        # Read both DataFrames from the same buffer
        data_objects_df = pd.read_xml(BytesIO(file_content), xpath=".//DataObjects", parser="etree")[["ObjectID", "Name", "Description"]]
        exception_metadata_df = pd.read_xml(BytesIO(file_content), xpath=".//ExceptionMetadata", parser="etree")[["ObjectID", "CorrectiveAction"]]

        # Merge both sections
        merged_df = pd.merge(data_objects_df, exception_metadata_df, on="ObjectID", how="outer")

        # Regex to match lowercase words starting after space, /, -, or (
        #pattern = r"((?:\s|-|/|\()[a-z]\w*)"
        pattern = r'((?:\s|-|/|\(|"|\'\')[a-z]\w*)'
        regex = re.compile(pattern)

        # Dictionary to map matched words to their ObjectIDs
        word_to_object_ids = defaultdict(set)

        # Columns to check
        columns_to_check = ["Name", "Description", "CorrectiveAction"]

        # Loop through the DataFrame and extract matches
        for _, row in merged_df.iterrows():
            object_id = str(row["ObjectID"])
            for col in columns_to_check:
                text = row.get(col)
                if pd.notna(text):
                    matches = regex.findall(text)
                    for match in matches:
                        cleaned_word = match.strip()
                        word_to_object_ids[cleaned_word].add(object_id)

        # Convert the results into a DataFrame
        output_df = pd.DataFrame([
            {"Word": word, "ObjectIDs": ", ".join(sorted(word_to_object_ids[word]))}
            for word in sorted(word_to_object_ids)
        ])

        if not output_df.empty:
            st.success(f"✅ Found {len(output_df)} unique lowercase issues.")
            st.dataframe(output_df, use_container_width=True)
        else:
            st.info("🎉 No lowercase capitalization issues found!")

    except Exception as e:
        st.error(f"❌ Error parsing file: {e}")
else:
    st.warning("📄 Please upload an XML file to begin.")
