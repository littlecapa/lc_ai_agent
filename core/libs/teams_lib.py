# =====================================
# file: myproject/myapp/teams_lib.py
# =====================================
"""
TeamsLib — minimal, production-ready wrapper around Microsoft Graph
for extracting Microsoft Teams channel messages and attachments.

Parallels the GmailLib interface you already use:
- _login() / _logout()
- folder_exists() analogue is channel_exists()
- get_message_ids_in_folder() analogue is get_message_ids_in_channel()
- has_attachments(msg_id)
- save_attachments(msg_id, save_path)
- save_message(msg_id, save_path)  # saves text

Authentication modes supported:
1) Device Code Flow (delegated user) — simplest for interactive use.
2) Client Credentials (application) — service principal; requires
   proper Graph application permissions and tenant admin consent.

Required Graph permissions (minimum, depending on auth mode):
- Delegated: Channel.ReadBasic.All, ChannelMessage.Read.All, Files.Read.All
- Application: ChannelMessage.Read.All, Files.Read.All

Note: Attachments in Teams messages are typically references to SharePoint /
OneDrive files. This lib resolves and downloads those where possible.
"""

from __future__ import annotations
import logging
import os
import time
import json
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
AUTH_MSAL_AVAILABLE = True
try:
    import msal  # type: ignore
except Exception:  # pragma: no cover
    AUTH_MSAL_AVAILABLE = False


class ErrorType(Enum):
    AUTH = "AUTH"
    API = "API"
    IO = "IO"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMIT = "RATE_LIMIT"
    UNKNOWN = "UNKNOWN"


class TEAMS_LIB_EXCEPTION(Exception):
    def __init__(self, message: str, err_type: ErrorType = ErrorType.UNKNOWN, status: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.err_type = err_type
        self.status = status


@dataclass
class AuthConfig:
    tenant_id: str
    client_id: str
    authority: Optional[str] = None  # if None, will be built from tenant_id
    client_secret: Optional[str] = None  # required for client credentials flow
    use_device_code: bool = True
    scopes: Optional[List[str]] = None  # only used for delegated flow

    def build_authority(self) -> str:
        if self.authority:
            return self.authority
        return f"https://login.microsoftonline.com/{self.tenant_id}"


class TeamsLib:
    def __init__(self, auth: AuthConfig, session: Optional[requests.Session] = None):
        self.auth = auth
        self.session = session or requests.Session()
        self._access_token: Optional[str] = None
        self._cached_team_ids_by_name: Dict[str, str] = {}
        self._cached_channel_ids_by_name: Dict[Tuple[str, str], str] = {}

    # ---------------------- auth ----------------------
    def _login(self) -> None:
        logger.debug("TeamsLib: starting login.")
        if not AUTH_MSAL_AVAILABLE:
            raise TEAMS_LIB_EXCEPTION(
                "msal package is not installed. pip install msal",
                ErrorType.AUTH,
            )
        authority = self.auth.build_authority()

        if self.auth.use_device_code:
            app = msal.PublicClientApplication(self.auth.client_id, authority=authority)
            scopes = self.auth.scopes or [
                "Channel.ReadBasic.All",
                "ChannelMessage.Read.All",
                "Files.Read.All",
            ]
            flow = app.initiate_device_flow(scopes=scopes)
            if "user_code" not in flow:
                raise TEAMS_LIB_EXCEPTION("Failed to create device flow.", ErrorType.AUTH)
            logger.info("To authenticate, go to %s and enter code: %s", flow["verification_uri"], flow["user_code"])
            result = app.acquire_token_by_device_flow(flow)
        else:
            # Client Credentials flow
            if not self.auth.client_secret:
                raise TEAMS_LIB_EXCEPTION("client_secret required for client-credentials flow", ErrorType.AUTH)
            app = msal.ConfidentialClientApplication(
                self.auth.client_id,
                authority=authority,
                client_credential=self.auth.client_secret,
            )
            result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])  # type: ignore

        if "access_token" not in result:
            raise TEAMS_LIB_EXCEPTION(
                f"Auth failed: {result.get('error_description', 'unknown')}",
                ErrorType.AUTH,
            )
        self._access_token = result["access_token"]
        logger.debug("TeamsLib: login successful.")

    def _logout(self) -> None:
        # Nothing to do for stateless tokens; kept for API parity
        logger.debug("TeamsLib: logout (noop).")

    # ---------------------- helpers ----------------------
    def _headers(self) -> Dict[str, str]:
        if not self._access_token:
            raise TEAMS_LIB_EXCEPTION("Not authenticated", ErrorType.AUTH)
        return {"Authorization": f"Bearer {self._access_token}"}

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        for attempt in range(5):
            resp = self.session.request(method, url, headers=self._headers(), timeout=60, **kwargs)
            if resp.status_code == 429:
                # Rate limit: respect Retry-After
                retry_after = int(resp.headers.get("Retry-After", "2"))
                logger.warning("Graph 429 rate limited. Sleeping %s seconds (attempt %s)", retry_after, attempt + 1)
                time.sleep(retry_after)
                continue
            if 500 <= resp.status_code < 600:
                logger.warning("Graph %s error. Retrying (attempt %s)", resp.status_code, attempt + 1)
                time.sleep(1 + attempt)
                continue
            if not resp.ok:
                raise TEAMS_LIB_EXCEPTION(
                    f"Graph API error {resp.status_code}: {resp.text[:500]}", ErrorType.API, status=resp.status_code
                )
            return resp
        raise TEAMS_LIB_EXCEPTION("Exceeded retries for Graph API call", ErrorType.RATE_LIMIT)

    # ---------------------- IDs lookup ----------------------
    def get_team_id_by_name(self, team_display_name: str) -> str:
        if team_display_name in self._cached_team_ids_by_name:
            return self._cached_team_ids_by_name[team_display_name]
        url = f"{GRAPH_BASE}/me/joinedTeams" if self.auth.use_device_code else f"{GRAPH_BASE}/teams"
        # Filter by displayName (client-side due to Graph restrictions on application endpoint)
        teams: List[Dict] = []
        next_url = url
        while next_url:
            resp = self._request("GET", next_url)
            data = resp.json()
            teams.extend(data.get("value", []))
            next_url = data.get("@odata.nextLink")
        for t in teams:
            if t.get("displayName") == team_display_name:
                team_id = t.get("id")
                if team_id:
                    self._cached_team_ids_by_name[team_display_name] = team_id
                    return team_id
        raise TEAMS_LIB_EXCEPTION(f"Team '{team_display_name}' not found", ErrorType.NOT_FOUND)

    def get_channel_id_by_name(self, team_id: str, channel_display_name: str) -> str:
        cache_key = (team_id, channel_display_name)
        if cache_key in self._cached_channel_ids_by_name:
            return self._cached_channel_ids_by_name[cache_key]
        url = f"{GRAPH_BASE}/teams/{team_id}/channels"
        channels: List[Dict] = []
        next_url = url
        while next_url:
            resp = self._request("GET", next_url)
            data = resp.json()
            channels.extend(data.get("value", []))
            next_url = data.get("@odata.nextLink")
        for c in channels:
            if c.get("displayName") == channel_display_name:
                channel_id = c.get("id")
                if channel_id:
                    self._cached_channel_ids_by_name[cache_key] = channel_id
                    return channel_id
        raise TEAMS_LIB_EXCEPTION(f"Channel '{channel_display_name}' not found in team {team_id}", ErrorType.NOT_FOUND)

    # ---------------------- listing & access ----------------------
    def channel_exists(self, team_id: str, channel_id: str) -> bool:
        url = f"{GRAPH_BASE}/teams/{team_id}/channels/{channel_id}"
        try:
            _ = self._request("GET", url)
            return True
        except TEAMS_LIB_EXCEPTION as e:
            if e.status == 404:
                return False
            raise

    def get_message_ids_in_channel(self, team_id: str, channel_id: str) -> List[str]:
        """Returns a list of message IDs (root messages only)."""
        url = f"{GRAPH_BASE}/teams/{team_id}/channels/{channel_id}/messages?$top=50"
        msg_ids: List[str] = []
        next_url = url
        while next_url:
            resp = self._request("GET", next_url)
            data = resp.json()
            for m in data.get("value", []):
                if m.get("messageType") == "message":
                    if m.get("id"):
                        msg_ids.append(m["id"])
            next_url = data.get("@odata.nextLink")
        return msg_ids

    def get_message(self, team_id: str, channel_id: str, message_id: str) -> Dict:
        url = f"{GRAPH_BASE}/teams/{team_id}/channels/{channel_id}/messages/{message_id}"
        resp = self._request("GET", url)
        return resp.json()

    def has_attachments(self, message: Dict) -> bool:
        attachments = message.get("attachments", [])
        return bool(attachments)

    # ---------------------- saving ----------------------
    def save_message(self, message: Dict, save_path: str) -> None:
        os.makedirs(os.path.join(save_path, "E-Mails"), exist_ok=True)  # keeping folder names consistent with Gmail side
        msg_id = message.get("id", "unknown")
        created = message.get("createdDateTime", "")
        from_user = (message.get("from", {}) or {}).get("user", {}) or {}
        author = from_user.get("displayName") or from_user.get("id") or "unknown"
        subject = (message.get("subject") or "").strip()
        content = (message.get("body", {}) or {}).get("content") or ""
        filename = f"{created.replace(':', '-')}_{msg_id}.txt"
        full_path = os.path.join(save_path, "E-Mails", filename)
        try:
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(f"Author: {author}\n")
                f.write(f"Created: {created}\n")
                if subject:
                    f.write(f"Subject: {subject}\n")
                f.write("\n--- MESSAGE BODY (HTML or text) ---\n\n")
                f.write(content)
            logger.debug("Saved message %s to %s", msg_id, full_path)
        except OSError as e:
            raise TEAMS_LIB_EXCEPTION(f"Failed to write message file: {e}", ErrorType.IO)

    def save_attachments(self, message: Dict, save_path: str) -> None:
        os.makedirs(os.path.join(save_path, "Anlagen"), exist_ok=True)
        msg_id = message.get("id", "unknown")
        attachments = message.get("attachments", []) or []
        for att in attachments:
            try:
                self._download_attachment(att, save_path)
            except TEAMS_LIB_EXCEPTION as e:
                logger.warning("Could not download attachment for message %s: %s", msg_id, e.message)

    def _download_attachment(self, att: Dict, save_path: str) -> None:
        atype = att.get("@odata.type")
        name = att.get("name") or "attachment"
        if atype == "#microsoft.graph.fileAttachment":
            content_bytes = att.get("contentBytes")
            if not content_bytes:
                raise TEAMS_LIB_EXCEPTION("Empty fileAttachment content", ErrorType.API)
            import base64
            data = base64.b64decode(content_bytes)
            path = os.path.join(save_path, "Anlagen", name)
            with open(path, "wb") as f:
                f.write(data)
            logger.debug("Saved fileAttachment to %s", path)
        elif atype == "#microsoft.graph.referenceAttachment":
            # Reference to a SharePoint/OneDrive file — try to resolve and download original if permitted
            url = att.get("previewUrl") or att.get("sourceUrl")
            if not url:
                raise TEAMS_LIB_EXCEPTION("referenceAttachment missing URL", ErrorType.API)
            # In many cases these URLs require auth; try session with bearer
            resp = self.session.get(url, headers=self._headers(), timeout=60)
            if resp.status_code == 200:
                path = os.path.join(save_path, "Anlagen", name)
                with open(path, "wb") as f:
                    f.write(resp.content)
                logger.debug("Saved referenceAttachment to %s", path)
            else:
                # Fallback: store a .url pointer file
                pointer = os.path.join(save_path, "Anlagen", f"{name}.url.txt")
                with open(pointer, "w", encoding="utf-8") as f:
                    f.write(url)
                logger.info("Stored reference URL for attachment at %s (HTTP %s)", pointer, resp.status_code)
        else:
            raise TEAMS_LIB_EXCEPTION(f"Unsupported attachment type: {atype}", ErrorType.API)

    # ---------------------- checkpoint (local) ----------------------
    def load_checkpoint(self, save_path: str) -> Dict:
        path = os.path.join(save_path, ".teams_checkpoint.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_checkpoint(self, save_path: str, data: Dict) -> None:
        path = os.path.join(save_path, ".teams_checkpoint.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)



