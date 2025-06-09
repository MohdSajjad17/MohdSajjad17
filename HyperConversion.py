import os
import zipfile
import streamlit as st
from tableauhyperapi import HyperProcess, Connection, Telemetry, TableDefinition, SqlType, Inserter, CreateMode
from tableau_sdk.Extract import Extract  # Requires legacy Tableau SDK

# ====================== STREAMLIT APP ======================
st.set_page_config(page_title="TWBX to Hyper Converter", layout="wide")
st.title("📁 TWBX to Hyper Converter")

# ====================== CONFIGURATION ======================
with st.expander("⚙️ Configuration", expanded=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        INPUT_TWBX_FOLDER = st.text_input("Input TWBX Folder", r"C:\Path\To\Your\TWBX_Files")
    with col2:
        EXTRACTED_TDE_FOLDER = st.text_input("Extracted TDE Folder", r"C:\Path\To\Extracted_TDEs")
    with col3:
        HYPER_OUTPUT_FOLDER = st.text_input("Hyper Output Folder", r"C:\Path\To\Hyper_Files")

# Initialize session state
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'log_messages' not in st.session_state:
    st.session_state.log_messages = []

# ====================== FUNCTIONS ======================
def log_message(message):
    """Add message to log and display in Streamlit."""
    st.session_state.log_messages.append(message)
    st.experimental_rerun()

def extract_tde_from_twbx(twbx_path, output_root):
    """Extract all TDE files from a TWBX workbook."""
    twbx_name = os.path.splitext(os.path.basename(twbx_path))[0]
    twbx_extract_dir = os.path.join(output_root, twbx_name)
    os.makedirs(twbx_extract_dir, exist_ok=True)

    with zipfile.ZipFile(twbx_path, 'r') as zip_ref:
        zip_ref.extractall(twbx_extract_dir)

    tde_paths = []
    for root, _, files in os.walk(twbx_extract_dir):
        for file in files:
            if file.endswith('.tde'):
                tde_full_path = os.path.join(root, file)
                tde_paths.append(tde_full_path)

    return tde_paths

def convert_tde_to_hyper(tde_path, hyper_path):
    """Convert a TDE file to Hyper format."""
    try:
        # Step 1: Open the TDE file
        extract = Extract(tde_path)
        if not extract.hasTable('Extract'):
            log_message(f"⚠️ No 'Extract' table found in {os.path.basename(tde_path)}")
            return False
            
        table = extract.getTable('Extract')
        schema = table.getTableDefinition()

        # Step 2: Define schema for Hyper
        hyper_schema = TableDefinition(table_name='Extract')
        
        type_mapping = {
            0: SqlType.bool(),         # Boolean
            1: SqlType.double(),       # Double
            2: SqlType.big_int(),      # Integer
            3: SqlType.text(),         # String
            4: SqlType.date(),         # Date
            5: SqlType.timestamp(),    # DateTime
            6: SqlType.text(),         # Spatial (mapped to text as fallback)
        }

        for i in range(schema.getColumnCount()):
            col_name = schema.getColumnName(i)
            col_type = schema.getColumnType(i)
            hyper_schema.add_column(col_name, type_mapping.get(col_type, SqlType.text()))

        # Step 3: Write to Hyper
        with HyperProcess(telemetry=Telemetry.SEND_USAGE_DATA_TO_TABLEAU) as hyper:
            with Connection(hyper.endpoint, hyper_path, CreateMode.CREATE_AND_REPLACE) as connection:
                connection.catalog.create_table(hyper_schema)
                
                with Inserter(connection, hyper_schema) as inserter:
                    row = table.nextRow()
                    while row:
                        values = []
                        for i in range(schema.getColumnCount()):
                            values.append(row.getData(i))
                        inserter.add_row(values)
                        row = table.nextRow()
                    inserter.execute()

        log_message(f"✅ Successfully converted {os.path.basename(tde_path)} → {os.path.basename(hyper_path)}")
        return True
        
    except Exception as e:
        log_message(f"❌ Error converting {os.path.basename(tde_path)}: {str(e)}")
        return False
    finally:
        if 'extract' in locals():
            extract.close()

def process_files():
    """Main processing function."""
    st.session_state.processing = True
    st.session_state.log_messages = []
    
    # Create output directories if they don't exist
    os.makedirs(EXTRACTED_TDE_FOLDER, exist_ok=True)
    os.makedirs(HYPER_OUTPUT_FOLDER, exist_ok=True)
    
    log_message("🚀 Starting TWBX extraction process...")
    
    # Process TWBX files
    twbx_files = [f for f in os.listdir(INPUT_TWBX_FOLDER) if f.endswith('.twbx')]
    if not twbx_files:
        log_message("ℹ️ No TWBX files found in input directory")
        st.session_state.processing = False
        return
    
    for file in twbx_files:
        full_path = os.path.join(INPUT_TWBX_FOLDER, file)
        log_message(f"\n🔍 Processing TWBX: {file}")
        
        try:
            tde_files = extract_tde_from_twbx(full_path, EXTRACTED_TDE_FOLDER)
            for tde in tde_files:
                log_message(f"📤 Extracted TDE: {os.path.basename(tde)}")
        except Exception as e:
            log_message(f"⚠️ Error processing {file}: {str(e)}")
    
    # Convert TDE to Hyper
    log_message("\n🔄 Starting TDE to Hyper conversion process...")
    
    tde_files = []
    for root, _, files in os.walk(EXTRACTED_TDE_FOLDER):
        for file in files:
            if file.endswith('.tde'):
                tde_files.append(os.path.join(root, file))
    
    if not tde_files:
        log_message("ℹ️ No TDE files found for conversion")
        st.session_state.processing = False
        return
    
    for tde_path in tde_files:
        hyper_filename = os.path.basename(tde_path).replace('.tde', '.hyper')
        hyper_path = os.path.join(HYPER_OUTPUT_FOLDER, hyper_filename)
        convert_tde_to_hyper(tde_path, hyper_path)
    
    log_message("\n🏁 Process completed!")
    st.session_state.processing = False

# ====================== UI COMPONENTS ======================
if st.button("🚀 Start Conversion", disabled=st.session_state.processing):
    process_files()

# Progress and logs
st.subheader("📝 Processing Log")
log_container = st.container()

if st.session_state.log_messages:
    with log_container:
        for message in st.session_state.log_messages:
            if message.startswith("✅"):
                st.success(message)
            elif message.startswith("⚠️") or message.startswith("❌"):
                st.error(message)
            elif message.startswith("ℹ️"):
                st.info(message)
            else:
                st.write(message)

# Status indicator
if st.session_state.processing:
    st.warning("⏳ Processing in progress... Please wait.")
else:
    st.success("💤 Ready to process")

# Instructions
with st.expander("📋 Instructions"):
    st.markdown("""
    **How to use this tool:**
    1. Set your input/output folders in the configuration section
    2. Click the "Start Conversion" button
    3. Monitor progress in the log section
    
    **Requirements:**
    - Tableau Extract API (32-bit Python required)
    - Tableau Hyper API (`pip install tableauhyperapi`)
    - Python 3.6+ (32-bit for TDE reading)
    
    **Notes:**
    - The app will create all necessary output folders
    - Each TWBX will be extracted to its own subfolder
    - All Hyper files will be placed in the output folder
    """)
