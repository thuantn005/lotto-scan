#!/usr/bin/env python3
"""
Gui 1 tin nhan DATA-ONLY (KHONG kem key "notification") qua Firebase Cloud
Messaging HTTP v1 API toi 1 topic - danh thuc app "San Chia Giai" chay lai
kiem tra ngam (JackpotCheckService.runCheck()). App tu quyet dinh co hien
thong bao hay khong (qua ShareDrawMachine + NotificationService) - script
nay CHI danh thuc, khong tu quyet dinh gi ca.

Can bien moi truong:
  GOOGLE_APPLICATION_CREDENTIALS_JSON - noi dung THO (raw JSON, khong phai
    duong dan file) cua service account key, tai tu Firebase Console >
    Project settings > Service accounts > Generate new private key.
    Luu duoi dang GitHub Secret ten FCM_SERVICE_ACCOUNT_JSON.

Cach dung:
  python3 send_fcm_push.py --topic chiagiai_updates
"""
import argparse
import json
import os
import sys

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/firebase.messaging"]


def get_access_token(sa_info: dict) -> str:
    creds = service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)
    creds.refresh(Request())
    return creds.token


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="chiagiai_updates")
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

    url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    payload = {
        "message": {
            "topic": args.topic,
            # CHI "data", KHONG co key "notification" -> Android se KHONG
            # tu hien thong bao gi ca. App tu quyet dinh trong PushService.
            "data": {"type": "wake_check"},
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
