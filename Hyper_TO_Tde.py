import os
import zipfile
from tableauhyperapi import HyperProcess, Connection, Telemetry, TableDefinition, SqlType, Inserter, CreateMode
from tableau_sdk.Extract import Extract  # Requires legacy Tableau SDK

# ====================== CONFIGURATION ======================
INPUT_TWBX_FOLDER = r'C:\Path\To\Your\TWBX_Files'
EXTRACTED_TDE_FOLDER = r'C:\Path\To\Extracted_TDEs'
HYPER_OUTPUT_FOLDER = r'C:\Path\To\Hyper_Files'
LOG_FILE = r'C:\Path\To\conversion_log.txt'

# ====================== TWBX EXTRACTION ======================
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

def process_all_twbx_files():
    """Process all TWBX files in the input folder."""
    with open(LOG_FILE, 'w') as log:
        log.write("TDE Extraction Log\n=================\n")
        
        for file in os.listdir(INPUT_TWBX_FOLDER):
            if file.endswith('.twbx'):
                full_path = os.path.join(INPUT_TWBX_FOLDER, file)
                print(f"\nProcessing TWBX: {file}")
                log.write(f"\nProcessing TWBX: {file}\n")
                
                try:
                    tde_files = extract_tde_from_twbx(full_path, EXTRACTED_TDE_FOLDER)
                    for tde in tde_files:
                        log.write(f"Extracted TDE: {tde}\n")
                        print(f"Extracted TDE: {os.path.basename(tde)}")
                except Exception as e:
                    log.write(f"Error processing {file}: {str(e)}\n")
                    print(f"Error processing {file}: {str(e)}")

# ====================== TDE TO HYPER CONVERSION ======================
def convert_tde_to_hyper(tde_path, hyper_path):
    """Convert a TDE file to Hyper format."""
    try:
        # Step 1: Open the TDE file
        extract = Extract(tde_path)
        if not extract.hasTable('Extract'):
            print(f"No 'Extract' table found in {tde_path}")
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

        print(f"✅ Successfully converted {os.path.basename(tde_path)} → {os.path.basename(hyper_path)}")
        return True
        
    except Exception as e:
        print(f"❌ Error converting {tde_path}: {str(e)}")
        return False
    finally:
        if 'extract' in locals():
            extract.close()

def convert_all_tde_files():
    """Convert all TDE files in the extracted folder to Hyper format."""
    os.makedirs(HYPER_OUTPUT_FOLDER, exist_ok=True)
    
    with open(LOG_FILE, 'a') as log:
        log.write("\n\nTDE to Hyper Conversion Log\n=========================\n")
        
        for root, _, files in os.walk(EXTRACTED_TDE_FOLDER):
            for file in files:
                if file.endswith('.tde'):
                    tde_path = os.path.join(root, file)
                    hyper_filename = file.replace('.tde', '.hyper')
                    hyper_path = os.path.join(HYPER_OUTPUT_FOLDER, hyper_filename)
                    
                    print(f"\nConverting: {file}")
                    log.write(f"\nConverting: {tde_path}\n")
                    
                    success = convert_tde_to_hyper(tde_path, hyper_path)
                    if success:
                        log.write(f"Success: {hyper_path}\n")
                    else:
                        log.write(f"Failed: {tde_path}\n")

# ====================== MAIN EXECUTION ======================
if __name__ == '__main__':
    print("Starting TWBX extraction process...")
    process_all_twbx_files()
    
    print("\nStarting TDE to Hyper conversion process...")
    convert_all_tde_files()
    
    print("\nProcess completed. Check the log file for details:", LOG_FILE)
