import os
import json
import requests
import datetime
import time
import sys
import urllib3
import logging
from io import StringIO

# Suppress the InsecureRequestWarning that occurs when using verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Set up logging
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f"crawler_export_{timestamp}.log"
log_filepath = os.path.join(os.path.dirname(__file__), log_filename)

# Configure logging to write to both file and console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filepath),
        logging.StreamHandler(sys.stdout)
    ]
)

# Helper function to log messages instead of print
def log_info(message):
    logging.info(message)
    
# Define the folder relative to the script
folder_path = os.path.join(os.path.dirname(__file__), "C:\Hubtech\github\crawler\storage\dior")

# API endpoints
api_url = "https://localhost:7114/api/ProductCatalog/RawProduct"
provision_api_url = "https://localhost:7114/api/ProductCatalog/RawProduct/{key}/Provision"

# Configuration
max_retries = 3
retry_delay = 2  # seconds
timeout = 30     # seconds

log_info("=== Scanning files and sending only those with NON-EMPTY products arrays ===")
log_info(f"POST endpoint: {api_url}")
log_info(f"Provision endpoint template: {provision_api_url}")
log_info(f"Log file: {log_filepath}")
log_info("Note: Only logging failed API requests (status != 200)")

# Counters for summary
total_files = 0
files_sent = 0
files_provisioned = 0

# Process each JSON file
for index, file_name in enumerate(sorted(os.listdir(folder_path)), start=1):
    if file_name.endswith(".json"):
        total_files += 1
        file_path = os.path.join(folder_path, file_name)
        
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                json_data = json.load(file)
                
                # Log seq and file name
                log_info(f"{index}. {file_name}")

                # Process files with non-empty products arrays
                # non_empty_product_files += 1
                
                # Generate key with prefix, date, and file name
                file_base_name = file_name.replace(".json", "")
                code = f"{file_base_name}"
                
                # Debug info
                json_content = json.dumps(json_data)
                content_size = sys.getsizeof(json_content) / (1024 * 1024)  # Size in MB
                
                # log_info("\n" + "="*80)
                # log_info(f"File: {file_name}")
                # log_info(f"Code: {code}")
                # log_info(f"Content size: {content_size:.2f} MB")
                
                # Create the properly structured request body
                request_body = {
                    "code": code,
                    "jsonContent": json_content
                }
                
                # log_info(f"\n1. Sending file {file_name} to API...")
                
                # Retry logic for POST request
                file_sent_success = False
                
                for attempt in range(max_retries):
                    try:
                        # Send the POST request 
                        response = requests.post(
                            api_url, 
                            json=request_body, 
                            verify=False,
                            timeout=timeout,
                            headers={"accept": "text/plain", "Content-Type": "application/json"}
                        )
                        
                        if response.status_code == 200:
                            # Success - only minimal logging
                            # log_info(f"POST successful for {file_name}")
                            file_sent_success = True
                            files_sent += 1
                            break  # Success, exit retry loop
                        else:
                            # Failed request - detailed logging
                            log_info(f"POST failed with status code: {response.status_code}, {response.text}")
                            
                    except requests.exceptions.ConnectionError as e:
                        log_info(f"Connection error on POST attempt {attempt+1}/{max_retries}: {e}")
                        if attempt < max_retries - 1:
                            log_info(f"Retrying in {retry_delay} seconds...")
                            time.sleep(retry_delay)
                        else:
                            log_info(f"Failed to POST file {file_name} after {max_retries} attempts")
                    
                    except Exception as e:
                        log_info(f"Unexpected error on POST attempt {attempt+1}/{max_retries}: {e}")
                        if attempt < max_retries - 1:
                            log_info(f"Retrying in {retry_delay} seconds...")
                            time.sleep(retry_delay)
                        else:
                            log_info(f"Failed to POST file {file_name} after {max_retries} attempts")
                
                # If POST was successful, make the PUT request to the provision endpoint
                if file_sent_success:
                    # log_info(f"\n2. Provisioning file {file_name} with code: {code}")
                    
                    # Construct the provision URL with the key
                    provision_url = provision_api_url.format(key=code)
                    
                    # Retry logic for PUT request
                    for attempt in range(max_retries):
                        try:
                            # Send the PUT request to provision endpoint
                            provision_response = requests.put(
                                provision_url,
                                verify=False,
                                timeout=timeout,
                                headers={"accept": "text/plain", "Content-Type": "application/json"}
                            )
                            
                            if provision_response.status_code == 200:
                                # Success - only minimal logging
                                # log_info(f"Provision successful for {file_name}")
                                files_provisioned += 1
                                break  # Success, exit retry loop
                            else:
                                # Failed request - detailed logging
                                log_info(f"Provision failed with status code: {provision_response.status_code}, {provision_response.text}")
                                
                        except requests.exceptions.ConnectionError as e:
                            log_info(f"Connection error on provision attempt {attempt+1}/{max_retries}: {e}")
                            if attempt < max_retries - 1:
                                log_info(f"Retrying in {retry_delay} seconds...")
                                time.sleep(retry_delay)
                            else:
                                log_info(f"Failed to provision file {file_name} after {max_retries} attempts")
                        
                        except Exception as e:
                            log_info(f"Unexpected error on provision attempt {attempt+1}/{max_retries}: {e}")
                            if attempt < max_retries - 1:
                                log_info(f"Retrying in {retry_delay} seconds...")
                                time.sleep(retry_delay)
                            else:
                                log_info(f"Failed to provision file {file_name} after {max_retries} attempts")
        
        except Exception as e:
            log_info(f"Error processing file {file_name}: {e}")
            logging.exception(f"Detailed exception info for {file_name}:")

log_info("\n=== Summary ===")
log_info(f"Total JSON files: {total_files}")
log_info(f"Files successfully sent (POST): {files_sent}")
log_info(f"Files successfully provisioned (PUT): {files_provisioned}")
log_info("Processing complete.")

# Also save summary to a separate summary file with same timestamp
summary_filename = f"crawler_summary_{timestamp}.txt"
summary_filepath = os.path.join(os.path.dirname(__file__), summary_filename)
with open(summary_filepath, 'w') as summary_file:
    summary_file.write("=== CRAWLER EXPORT SUMMARY ===\n\n")
    summary_file.write(f"Date/Time: {timestamp}\n")
    summary_file.write(f"Log file: {log_filename}\n\n")
    summary_file.write(f"Total JSON files: {total_files}\n")
    summary_file.write(f"Files successfully sent (POST): {files_sent}\n")
    summary_file.write(f"Files successfully provisioned (PUT): {files_provisioned}\n\n")
    summary_file.write(f"Full log file: {log_filename}\n")

log_info(f"Summary file saved: {summary_filepath}")
