#!/usr/bin/env python3
"""
Gui 1 tin nhan DATA-ONLY (KHONG kem key "notification") qua Firebase Cloud
Messaging HTTP v1 API toi 1 topic - danh thuc app "San Chia Giai" VA GUI
KEM LUON du lieu ky moi nhat (field "latest_draw", JSON da stringify) de
app khong can goi mang doc lai GitHub lan nao nua. App tu quyet dinh co
hien thong bao hay khong (qua ShareDrawMachine + NotificationService) -
script nay CHI danh thuc + mang du lieu di kem, khong tu quyet dinh gi ca.

Can bien moi truong:
  GOOGLE_APPLICATION_CREDENTIALS_JSON - noi dung THO (raw JSON, khong phai
    duong dan file) cua service account key, tai tu Firebase Console >
    Project settings > Service accounts > Generate new private key.
    Luu duoi dang GitHub Secret ten FCM_SERVICE_ACCOUNT_JSON.

Cach dung:
  python3 send_fcm_push.py --topic chiagiai_updates --json data/full_results.json
"""
import argparse
import json
import os
import sys

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/firebase.messaging"]

# FCM gioi han data payload ~4KB - 1 ky (kem bang 7 giai) thuong chi ~0.5-1KB
# nen an toan, nhung neu vuot han thi bo qua phan dinh kem, chi gui tin
# danh thuc suong (app se tu goi mang doc lai GitHub nhu binh thuong).
MAX_PAYLOAD_BYTES = 3500


def get_access_token(sa_info: dict) -> str:
    creds = service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)
    creds.refresh(Request())
    return creds.token


def load_latest_draw(json_path: str):
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            rows = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"CANH BAO: khong doc duoc {json_path}: {e} -- se gui tin danh thuc suong", file=sys.stderr)
        return None
    if not rows:
        return None
    return rows[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="chiagiai_updates")
    ap.add_argument("--json", default="data/full_results.json", help="File chua ky moi nhat de dinh kem")
    args = ap.parse_args()

    raw = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if not raw:
        print("LOI: thieu bien moi truong GOOGLE_APPLICATION_CREDENTIALS_JSON", file=sys.stderr)
        sys.exit(1)

    try:
        sa_info = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"LOI: GOOGLE_APPLICATION_CREDENTIALS_JSON khong phai JSON hop le: {e}", file=sys.stderr)
        sys.exit(1)

    project_id = sa_info["project_id"]
    token = get_access_token(sa_info)

    data = {"type": "wake_check"}
    latest = load_latest_draw(args.json)
    if latest is not None:
        # separators gon nhat co the de tiet kiem byte trong gioi han FCM.
        packed = json.dumps(latest, ensure_ascii=False, separators=(",", ":"))
        if len(packed.encode("utf-8")) <= MAX_PAYLOAD_BYTES:
            data["latest_draw"] = packed
        else:
            print(f"CANH BAO: ky {latest.get('draw_id')} vuot {MAX_PAYLOAD_BYTES} byte -- "
                  f"chi gui tin danh thuc suong, app se tu doc lai GitHub", file=sys.stderr)

    url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    payload = {
        "message": {
            "topic": args.topic,
            # CHI "data", KHONG co key "notification" -> Android se KHONG
            # tu hien thong bao gi ca. App tu quyet dinh trong PushService.
            "data": data,
            "android": {"priority": "high"},
        }
    }
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; UTF-8",
        },
        json=payload,
        timeout=20,
    )
    print(f"FCM response: {resp.status_code} {resp.text}")
    resp.raise_for_status()


if __name__ == "__main__":
    main()
