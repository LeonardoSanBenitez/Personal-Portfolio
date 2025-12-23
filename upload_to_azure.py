import os
import dotenv
from azure.storage.blob import BlobServiceClient

dotenv.load_dotenv()

# Hardcoded SAS URL for the container $web
AZURE_SAS_URL = os.getenv("AZURE_SAS_URL")
assert len(AZURE_SAS_URL) > 0, "AZURE_SAS_URL environment variable not set"

LOCAL_FOLDER = "v1"  # This fodler name is not uploaded to Azure
REMOTE_FOLDER = "."

# Create BlobServiceClient using SAS URL
blob_service_client = BlobServiceClient(
    account_url=AZURE_SAS_URL.split("?", 1)[0],
    credential=AZURE_SAS_URL.split("?", 1)[1]
)
container_client = blob_service_client.get_container_client(REMOTE_FOLDER)

for root, dirs, files in os.walk(LOCAL_FOLDER):
    for file_name in files:
        local_file_path = os.path.join(root, file_name)
        relative_path = os.path.relpath(local_file_path, start=LOCAL_FOLDER).replace("\\", "/")
        blob_client = container_client.get_blob_client(relative_path)
        
        # Upload and overwrite if blob exists
        with open(local_file_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)
        
        print(f"Uploaded: {relative_path}")