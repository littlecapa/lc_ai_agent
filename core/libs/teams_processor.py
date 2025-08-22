from __future__ import annotations
import logging
from typing import Tuple

from .teams_lib import TeamsLib, TEAMS_LIB_EXCEPTION, AuthConfig

logger = logging.getLogger(__name__)


def run_channel_automation(
    tenant_id: str,
    client_id: str,
    client_secret: str | None,
    team_name_or_id: str,
    channel_name_or_id: str,
    save_path: str,
    use_device_code: bool = True,
) -> Tuple[bool, str]:
    """
    Extracts all root messages (and their attachments) from the given Teams channel
    and stores them under save_path / {E-Mails, Anlagen}.

    Args
    ----
    tenant_id, client_id, client_secret : Azure AD app credentials
    team_name_or_id : Either the display name of the Team or its GUID
    channel_name_or_id : Either the display name of the Channel or its GUID
    save_path : base directory where 'E-Mails/' and 'Anlagen/' will be created
    use_device_code : toggle between delegated (True) and application flow (False)
    """
    logger.debug("run_channel_automation (Teams Orchestrator) started.")

    client = None
    success = False
    final_message = ""

    try:
        auth = AuthConfig(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            use_device_code=use_device_code,
        )
        client = TeamsLib(auth)

        logger.debug("Attempting Teams login.")
        client._login()
        logger.debug("Teams login successful.")

        # Resolve IDs if names were provided
        if team_name_or_id.count("-") == 4:  # naive GUID check
            team_id = team_name_or_id
        else:
            logger.debug("Resolving team id by name: %s", team_name_or_id)
            team_id = client.get_team_id_by_name(team_name_or_id)

        if channel_name_or_id.count("-") == 4:
            channel_id = channel_name_or_id
        else:
            logger.debug("Resolving channel id by name: %s", channel_name_or_id)
            channel_id = client.get_channel_id_by_name(team_id, channel_name_or_id)

        logger.debug("Checking channel existence: team=%s channel=%s", team_id, channel_id)
        if not client.channel_exists(team_id, channel_id):
            logger.error("Channel '%s' not found in Team '%s'", channel_name_or_id, team_name_or_id)
            return False, f"Fehler: Kanal '{channel_name_or_id}' existiert nicht im Team '{team_name_or_id}'."

        # Load checkpoint (last processed message ids)
        checkpoint = client.load_checkpoint(save_path)
        processed_ids = set(checkpoint.get("processed_ids", []))

        logger.debug("Fetching message ids from channel.")
        message_ids = client.get_message_ids_in_channel(team_id, channel_id)
        if not message_ids:
            logger.info("Keine neuen Nachrichten im Kanal gefunden.")
            return True, "Keine neuen Nachrichten im Kanal gefunden."

        total = len(message_ids)
        processed = 0
        logger.info("Beginne mit der Verarbeitung von %s Nachrichten.", total)

        for mid in message_ids:
            if mid in processed_ids:
                logger.debug("Überspringe bereits verarbeitete Nachricht %s", mid)
                continue
            try:
                msg = client.get_message(team_id, channel_id, mid)
                if client.has_attachments(msg):
                    try:
                        client.save_attachments(msg, save_path)
                        logger.info("Anhänge zu Nachricht %s gespeichert.", mid)
                    except TEAMS_LIB_EXCEPTION as e:
                        logger.warning("Konnte Anhänge zu %s nicht speichern: %s", mid, e.message)
                else:
                    logger.debug("Nachricht %s hat keine Anhänge.", mid)

                client.save_message(msg, save_path)
                logger.info("Nachricht %s gespeichert.", mid)

                processed += 1
                processed_ids.add(mid)
            except TEAMS_LIB_EXCEPTION as e:
                logger.error("Fehler bei Nachricht %s: %s", mid, e.message, exc_info=True)
            except Exception as e:  # pragma: no cover
                logger.error("Unerwarteter Fehler bei Nachricht %s: %s", mid, e, exc_info=True)

        checkpoint["processed_ids"] = list(processed_ids)
        client.save_checkpoint(save_path, checkpoint)

        final_message = f"{processed} von {total} Nachrichten verarbeitet."
        success = True
        logger.info(final_message)

    except TEAMS_LIB_EXCEPTION as e:
        final_message = f"Fehler in Teams-Orchestrierung: {e.message}"
        logger.error(final_message, exc_info=True)
    except Exception as e:  # pragma: no cover
        final_message = f"Unerwarteter Fehler in Teams-Orchestrierung: {e}"
        logger.error(final_message, exc_info=True)
    finally:
        if client:
            try:
                client._logout()
            except Exception as e:  # pragma: no cover
                logger.error("Fehler beim Logout: %s", e, exc_info=True)
        logger.debug("run_channel_automation (Teams Orchestrator) beendet.")

    return success, final_message
