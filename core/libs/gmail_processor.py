# myproject/myapp/gmail_processor.py

import logging, os
from .gmail_lib import GmailLib, GMAIL_LIB_EXCEPTION, ErrorType # Importiere die Klasse und die Exception

logger = logging.getLogger(__name__)

def run_email_automation(user, password, source_folder, target_folder, save_path):
    logger.debug("run_email_automation (Orchestrator) gestartet.")
    
    # GmailLib.save_attachments und GmailLib.save_email erwarten den Basispfad (save_path)
    # und erstellen selbst die Unterordner 'Anlagen' und 'E-Mails'.
    
    gmail_client = None # Initialisiere als None für den finally-Block
    
    try:
        gmail_client = GmailLib(user, password)
        
        # 1. Login-Versuch. Wenn dies fehlschlägt, wird eine GMAIL_LIB_EXCEPTION geworfen.
        logger.debug("Versuche Login zur GmailLib.")
        gmail_client._login()
        logger.debug("Login erfolgreich.")
    
        # 2. Ordner-Existenzprüfungen
        # Die folder_exists-Methode in GmailLib wirft GMAIL_LIB_EXCEPTION bei IMAP-Fehlern.
        # Wenn der Ordner einfach nicht existiert (Rückgabe False), wird das hier behandelt.
        logger.debug(f"Prüfe Existenz des Quellordners: '{source_folder}'")
        if not gmail_client.folder_exists(source_folder):
            logger.error(f"Quellordner '{source_folder}' existiert nicht in Gmail.")
            return False, f"Fehler: Quellordner '{source_folder}' existiert nicht in Gmail."
        
        logger.debug(f"Prüfe Existenz des Zielordners: '{target_folder}'")
        if not gmail_client.folder_exists(target_folder):
            logger.error(f"Zielordner '{target_folder}' existiert nicht in Gmail.")
            return False, f"Fehler: Zielordner '{target_folder}' existiert nicht in Gmail. Bitte erstellen Sie ihn."

        # 3. Nachrichten-IDs aus dem Quellordner holen
        # Diese Methode wirft GMAIL_LIB_EXCEPTION bei IMAP-Fehlern.
        logger.debug(f"Hole Nachrichten-IDs aus Ordner '{source_folder}'.")
        message_ids = gmail_client.get_message_ids_in_folder(source_folder)
        
        if not message_ids:
            logger.info(f"Keine neuen E-Mails im Ordner '{source_folder}' gefunden, die verarbeitet werden müssen.")
            return True, f"Keine neuen E-Mails im Ordner '{source_folder}' gefunden, die verarbeitet werden müssen."
        
        success = False
        processed_count = 0
        total_emails = len(message_ids)
        logger.info(f"Beginne mit der Verarbeitung von {total_emails} E-Mails.")

        for msg_id in message_ids:
                logger.debug(f"Verarbeite E-Mail mit ID {msg_id.decode()}.")
                
                # Anhänge speichern
                if gmail_client.has_attachments(msg_id): # has_attachments kann GMAIL_LIB_EXCEPTION werfen
                    try:
                        gmail_client.save_attachments(msg_id, save_path)
                        logger.info(f"Anhänge von E-Mail {msg_id.decode()} erfolgreich gespeichert.")
                    except GMAIL_LIB_EXCEPTION as e:
                        logger.warning(f"Konnte Anhänge von E-Mail {msg_id.decode()} nicht speichern: {e.message}")
                        # Dieser Fehler ist spezifisch für den Anhang; Prozess wird nicht abgebrochen.
                else:
                    logger.debug(f"E-Mail {msg_id.decode()} hat keine Anhänge.")

                gmail_client.save_email(msg_id, save_path)
                logger.info(f"E-Mail {msg_id.decode()} erfolgreich gespeichert.")

                gmail_client.move_object(msg_id, source_folder, target_folder)
                processed_count += 1
                logger.debug(f"E-Mail mit ID {msg_id.decode()} erfolgreich verarbeitet und verschoben.")

        final_message = f"{processed_count} von {total_emails} E-Mails erfolgreich verarbeitet und verschoben."
        success = True
        logger.info(final_message)

    except GMAIL_LIB_EXCEPTION as e:
        final_message = f"Fehler bei der Verarbeitung von E-Mail {msg_id.decode()}: {e.message}"
        # Dies fängt Fehler ab, die spezifisch für die aktuelle E-Mail-Verarbeitung sind
        logger.error(final_message, exc_info=True)
        # Hier wird der Fehler geloggt, aber die Schleife fährt mit der nächsten E-Mail fort.
    except Exception as e:
        final_message = f"Unerwarteter Fehler bei der Verarbeitung von E-Mail {msg_id.decode()}: {e}"
        logger.error(final_message, exc_info=True)
    finally:
        # Sicherstellen, dass die Verbindung immer geschlossen wird, falls gmail_client erfolgreich instanziiert wurde
        if gmail_client:
            try:
                gmail_client._logout() # Diese Methode wirft jetzt Exception bei Fehlschlag
            except GMAIL_LIB_EXCEPTION as e:
                logger.error(f"Fehler beim Abmelden von Gmail: {e.message}", exc_info=True)
            except Exception as e:
                logger.error(f"Unerwarteter Fehler beim Abmelden von Gmail: {e}", exc_info=True)
        logger.debug("run_email_automation (Orchestrator) beendet.")

    return success, final_message # Konsistente Rückgabe: (bool, message)
