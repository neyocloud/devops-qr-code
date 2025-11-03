# main.py
from typing import Optional
from io import BytesIO
from urllib.parse import urlparse
import hashlib
import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
import qrcode

from dotenv import load_dotenv
load_dotenv()

app = FastAPI(title="QR → S3 Generator", version="1.3.1")

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- AWS config (supports both naming styles) ---
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_BUCKET = os.getenv("AWS_BUCKET_NAME")
AWS_KEY = os.getenv("AWS_ACCESS_KEY") or os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET = os.getenv("AWS_SECRET_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY")

# Force Signature V4 + virtual-hosted style
boto_cfg = Config(signature_version="s3v4", s3={"addressing_style": "virtual"})

s3 = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_KEY,
    aws_secret_access_key=AWS_SECRET,
    config=boto_cfg,
)

# --- Helpers ---
def region_aware_public_url(bucket: str, key: str, region: str) -> str:
    # Public URL only works if bucket policy allows it (yours likely doesn't). Presigned always works.
    if region == "us-east-1":
        return f"https://{bucket}.s3.amazonaws.com/{key}"
    return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"

def safe_key_from_url(url: str) -> str:
    parsed = urlparse(url)
    host_path = f"{parsed.netloc}{parsed.path}".strip("/").replace("/", "_")
    if not host_path:
        host_path = "root"
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    return f"qr_codes/{host_path}_{digest}.png"

# --- Models ---
class QRRequest(BaseModel):
    url: Optional[str] = None

# --- Routes ---
@app.get("/")
def root():
    return {"status": "ok", "service": "qr-generator", "docs": "/docs"}

@app.get("/env-check")
def env_check():
    return {
        "AWS_ACCESS_KEY set": bool(AWS_KEY),
        "AWS_SECRET_KEY set": bool(AWS_SECRET),
        "AWS_REGION": AWS_REGION,
        "AWS_BUCKET_NAME": AWS_BUCKET,
    }

@app.get("/s3-diagnose")
def s3_diagnose():
    """
    Head bucket + write a tiny object WITHOUT ACLs (works with BucketOwnerEnforced) + SigV4 presign.
    """
    if not AWS_BUCKET:
        raise HTTPException(status_code=500, detail="AWS_BUCKET_NAME is not set")
    try:
        hb = s3.head_bucket(Bucket=AWS_BUCKET)
        key = "healthchecks/diagnostic.txt"
        s3.put_object(
            Bucket=AWS_BUCKET,
            Key=key,
            Body=b"diag-ok\n",
            ContentType="text/plain",
            CacheControl="public, max-age=60",
        )
        presigned = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": AWS_BUCKET, "Key": key},
            ExpiresIn=300,
        )
        return {
            "ok": True,
            "configured_region": AWS_REGION,
            "bucket_head_result": str(hb),
            "presigned_get": presigned,
        }
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"S3 diagnose error: {e}")

@app.post("/generate-qr/")
async def generate_qr(
    req: Optional[QRRequest] = None,
    url: Optional[str] = Query(default=None, description="URL to encode (alternative to JSON body)"),
):
    """
    Generate a QR for the URL and upload to S3 (no ACLs).
    Accepts JSON body: {"url": "..."} OR query param: ?url=...
    """
    final_url = (req.url if (req and req.url) else url)
    if not final_url:
        raise HTTPException(status_code=400, detail="Provide 'url' in JSON body or as ?url=...")
    if not (final_url.startswith("http://") or final_url.startswith("https://")):
        raise HTTPException(status_code=400, detail="url must start with http:// or https://")
    if not AWS_BUCKET:
        raise HTTPException(status_code=500, detail="AWS_BUCKET_NAME is not set")

    key = safe_key_from_url(final_url)

    # Build QR image
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(final_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = BytesIO()
    img.save(buf, format="PNG")
    body = buf.getvalue()

    try:
        # Put object WITHOUT ACLs (compatible with ObjectOwnership=BucketOwnerEnforced)
        s3.put_object(
            Bucket=AWS_BUCKET,
            Key=key,
            Body=body,
            ContentType="image/png",
            CacheControl="public, max-age=31536000, immutable",
        )

        public_url = region_aware_public_url(AWS_BUCKET, key, AWS_REGION)  # may not be publicly readable
        presigned_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": AWS_BUCKET, "Key": key},
            ExpiresIn=900,  # 15 minutes
        )

        return {
            "ok": True,
            "bucket": AWS_BUCKET,
            "key": key,
            "public_url": public_url,
            "presigned_url": presigned_url,  # always openable
            "source_url": final_url,
        }

    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"S3 error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
