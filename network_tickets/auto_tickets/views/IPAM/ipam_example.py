#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import ipaddress
import sys
import requests
from requests.auth import HTTPBasicAuth

# ====== 你只需要改这里 ======
BASE_URL = "http://10.0.1.183"            
APP_ID   = "Netcare"                       # API App ID
USERNAME = "p7869"
PASSWORD = "Cmhk941"
                       
# ===========================

VERIFY_TLS = True     # 自签证书可临时 False（不推荐）
TIMEOUT = 15


def parse_cidr(cidr: str):
    """Return (network_address_str, prefixlen_int) from CIDR."""
    try:
        net = ipaddress.ip_network(cidr, strict=True)
    except ValueError as e:
        raise ValueError(f"Invalid CIDR '{cidr}': {e}")
    return str(net.network_address), int(net.prefixlen), net


def get_user_token() -> str:
    """POST /api/{app}/user/ -> token (Basic Auth)."""
    url = f"{BASE_URL}/api/{APP_ID}/user/"
    r = requests.post(
        url,
        auth=HTTPBasicAuth(USERNAME, PASSWORD),
        headers={"Accept": "application/json"},
        verify=VERIFY_TLS,
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    if not data.get("success"):
        raise RuntimeError(f"Auth failed: {data}")
    return data["data"]["token"]


def get_parent_subnet_id_by_cidr(token: str, parent_cidr: str) -> str:
    """
    GET /api/{app}/subnets/cidr/{subnet}/
    Many phpIPAM deployments accept {subnet} like '172.31.255.0/24' (URL-encoded),
    but some work better with /cidr/{ip}/{mask}/.
    We'll use /cidr/{ip}/{mask}/ to avoid encoding issues.
    """
    ip, mask, _ = parse_cidr(parent_cidr)
    url = f"{BASE_URL}/api/{APP_ID}/subnets/cidr/{ip}/{mask}/"

    r = requests.get(
        url,
        headers={"Accept": "application/json", "phpipam-token": token},
        verify=VERIFY_TLS,
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    if not data.get("success"):
        raise RuntimeError(f"Parent CIDR lookup failed: {data}")

    rows = data.get("data")
    if isinstance(rows, dict):
        rows = [rows]
    if not rows:
        raise RuntimeError(f"Parent subnet not found for CIDR={parent_cidr}")

    if len(rows) > 1:
        ids = [x.get("id") for x in rows]
        raise RuntimeError(
            f"Multiple parent subnets matched CIDR={parent_cidr}. IDs={ids}. "
            f"Please disambiguate (e.g., by choosing the correct one in UI or by section)."
        )

    return rows[0]["id"]


def create_subnet(token: str, child_cidr: str, section_id: int, master_subnet_id: str) -> dict:
    """POST /api/{app}/subnets/ with subnet+mask+sectionId+masterSubnetId."""
    child_ip, child_mask, _ = parse_cidr(child_cidr)

    url = f"{BASE_URL}/api/{APP_ID}/subnets/"
    payload = {
        "subnet": child_ip,
        "mask": child_mask,
        "sectionId": int(section_id),
        "masterSubnetId": str(master_subnet_id),
        # "isFolder": 0,  # 默认 0，不传也可以
    }

    r = requests.post(
        url,
        json=payload,
        headers={"Accept": "application/json", "phpipam-token": token},
        verify=VERIFY_TLS,
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def validate_child_within_parent(parent_net, child_net):
    """Ensure child subnet is inside parent subnet."""
    if parent_net.version != child_net.version:
        raise ValueError("Parent and child IP versions do not match (IPv4 vs IPv6).")
    if not child_net.subnet_of(parent_net):
        raise ValueError(f"Child {child_net} is NOT inside parent {parent_net}.")
    if child_net.prefixlen < parent_net.prefixlen:
        raise ValueError(f"Child {child_net} is larger than parent {parent_net}.")


def build_arg_parser():
    p = argparse.ArgumentParser(description="phpIPAM: create subnet by parent CIDR + child CIDR + sectionId")
    p.add_argument("--parent", required=True, help="Parent CIDR, e.g. 172.31.255.0/24")
    p.add_argument("--child", required=True, help="Child CIDR to create, e.g. 172.31.255.64/28")
    p.add_argument("--section-id", required=True, type=int, help="Section ID, e.g. 4")
    p.add_argument("--insecure", action="store_true", help="Disable TLS verification (self-signed cert testing)")
    return p


def main():
    global VERIFY_TLS
    args = build_arg_parser().parse_args()
    if args.insecure:
        VERIFY_TLS = False

    try:
        parent_ip, parent_mask, parent_net = parse_cidr(args.parent)
        child_ip, child_mask, child_net = parse_cidr(args.child)
        validate_child_within_parent(parent_net, child_net)

        token = get_user_token()
        print("[+] Token OK")

        master_id = get_parent_subnet_id_by_cidr(token, args.parent)
        print(f"[+] Parent {args.parent} -> masterSubnetId = {master_id}")

        resp = create_subnet(token, args.child, args.section_id, master_id)

        if resp.get("success"):
            # phpIPAM 通常会返回 id / message
            new_id = resp.get("id") or (resp.get("data") or {}).get("id")
            print(f"[✓] Subnet created: {args.child}  (sectionId={args.section_id}, masterSubnetId={master_id})")
            if new_id:
                print(f"[✓] New subnet ID: {new_id}")
        else:
            print(f"[✗] API error: {resp}")
            sys.exit(2)

    except requests.exceptions.HTTPError as e:
        # 把响应体也打出来，方便你定位（比如重复、无权限、冲突）
        try:
            body = e.response.text
        except Exception:
            body = ""
        print(f"[!] HTTP error: {e}\n[!] Response: {body}")
        sys.exit(3)
    except Exception as e:
        print(f"[!] Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
