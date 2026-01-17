import zipfile
import os
import tempfile
import re
from datetime import datetime
import time
import argparse

def extract_txt_from_zip(zip_file, start_date, end_date):
    try:
        with tempfile.TemporaryDirectory() as tmpdirname:
            txt_file_path = extract_files_from_zip(zip_file, tmpdirname)
            if txt_file_path:
                return read_and_filter_txt(txt_file_path, start_date, end_date)
            else:
                return None
    except zipfile.BadZipFile:
        return None

def extract_files_from_zip(zip_file, extract_to):
    try:
        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
            txt_files = [
                os.path.join(root, file)
                for root, _, files in os.walk(extract_to)
                for file in files if file.endswith('.txt')
            ]
            return txt_files[0] if txt_files else None
    except Exception as e:
        return None

def read_and_filter_txt(txt_file_path, start_date, end_date):
    for encoding in ['utf-8', 'utf-8-sig', 'utf-16', 'latin-1']:
        try:
            start_date = datetime.strptime(start_date, "%d/%m/%Y")
            end_date = datetime.strptime(end_date, "%d/%m/%Y")

            trimmed_text = ""
            include_message = False
            with open(txt_file_path, "r", encoding=encoding) as file:
                for line in file:
                    match = re.match(r"(\d{2}/\d{2}/\d{4})", line)
                    if match:
                        date_str = match.group(1)
                        message_date = datetime.strptime(date_str, "%d/%m/%Y")
                        include_message = start_date <= message_date <= end_date

                    if include_message:
                        trimmed_text += line

            print(">")
            print(trimmed_text)
            return trimmed_text
        except UnicodeDecodeError:
            continue
    return None

def main():
    start_time = time.time()
    
    # print("[ Whatsapp Analyser ]")
    parser = argparse.ArgumentParser(description='Extract')
    parser.add_argument('--start_date', type=str, required=True, help='Start date in DD/MM/YYYY format')
    parser.add_argument('--end_date', type=str, required=True, help='End date in DD/MM/YYYY format')
    parser.add_argument('--zip_path', type=str, required=True, help='Path to the WhatsApp chat zip file')
    
    args = parser.parse_args()
    
    start_date = args.start_date
    end_date = args.end_date
    zip_path = args.zip_path

    #zip_file = "./m.zip"
    #print(zip_file)
    #extract_txt_from_zip(zip_file,"21/01/25","27/01/25")
    #print("----------")
    #print(zip_path, start_date, end_date)
    #print("----------")
    
    extract_txt_from_zip(zip_path,start_date,end_date)

    end_time = time.time()
    elapsed_time = end_time - start_time
    #print(f"Execution completed in {elapsed_time:.2f} seconds.")


if __name__ == "__main__":
    main()
