import os
import sys
import dotenv
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import HttpResponseError, ClientAuthenticationError

dotenv.load_dotenv()

# Hardcoded SAS URL for the container $web
AZURE_SAS_URL = os.getenv("AZURE_SAS_URL")
assert AZURE_SAS_URL, "AZURE_SAS_URL environment variable not set"

def check_sas_not_expired(sas_url: str):
    parsed = urlparse(sas_url)
    qs = parse_qs(parsed.query)
    se_vals = qs.get("se") or qs.get("Se") or qs.get("SE")  # look for expiration param
    if not se_vals:
        # can't find expiry in SAS token -- proceed but warn
        print("Warning: could not find 'se' (expiry) parameter in SAS URL; will rely on runtime errors.")
        return
    se = se_vals[0]
    # normalize Z timezone
    if se.endswith("Z"):
        se_clean = se[:-1]
        tz = timezone.utc
    else:
        se_clean = se
        tz = None
    # try parsing with and without fractional seconds
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            expiry = datetime.strptime(se_clean, fmt)
            if tz:
                expiry = expiry.replace(tzinfo=tz)
            break
        except ValueError:
            expiry = None
    if expiry is None:
        print(f"Warning: couldn't parse SAS expiry value '{se}'. Will rely on runtime errors.")
        return
    now = datetime.now(timezone.utc)
    if now >= expiry:
        print(f"ERROR: SAS token expired at {expiry.isoformat()}. Please refresh AZURE_SAS_URL.")
        sys.exit(1)

check_sas_not_expired(AZURE_SAS_URL)


#########
import os
import sys
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.core.exceptions import HttpResponseError, ClientAuthenticationError

# SAS and expiry check omitted for brevity — keep your existing logic

LOCAL_FOLDER = "v1"
REMOTE_FOLDER = "."  # $web container

blob_service_client = BlobServiceClient(
    account_url=AZURE_SAS_URL.split("?", 1)[0],
    credential=AZURE_SAS_URL.split("?", 1)[1]
)
container_client = blob_service_client.get_container_client(REMOTE_FOLDER)

for root, dirs, files in os.walk(LOCAL_FOLDER):
    for file_name in files:
        local_file_path = os.path.join(root, file_name)
        relative_path = os.path.relpath(local_file_path, start=LOCAL_FOLDER).replace("\\", "/")

        # Determine a sensible content type from file extension
        ext = os.path.splitext(file_name)[1].lower()
        if ext == ".html":
            content_type = "text/html"
        elif ext == ".css":
            content_type = "text/css"
        elif ext == ".js":
            content_type = "application/javascript"
        elif ext in (".png", ".jpg", ".jpeg", ".gif", ".svg"):
            # map images
            content_type = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".gif": "image/gif",
                ".svg": "image/svg+xml",
            }[ext]
        else:
            # fallback (optional: use python’s mimetypes module)
            content_type = "application/octet-stream"

        blob_client = container_client.get_blob_client(relative_path)

        try:
            with open(local_file_path, "rb") as data:
                blob_client.upload_blob(
                    data,
                    overwrite=True,
                    content_settings=ContentSettings(content_type=content_type)
                )
            print(f"Uploaded: {relative_path} with Content-Type {content_type}")
        except ClientAuthenticationError as e:
            print("ERROR: authentication failed while uploading.", e)
            sys.exit(1)
        except HttpResponseError as e:
            status = getattr(e, "status_code", None)
            if status == 403 or "SAS" in str(e) or "expired" in str(e).lower():
                print("ERROR: SAS token invalid or expired.", status, e)
                sys.exit(1)
            raise
