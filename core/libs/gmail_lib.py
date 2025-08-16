# myproject/myapp/gmail_lib.py

import imaplib
import email
from email.header import decode_header
import os
import logging
import re # Importiere das 're'-Modul für reguläre Ausdrücke

logger = logging.getLogger(__name__)

class ErrorType:
    """Definiert standardisierte Fehlertypen für GMAIL_LIB_EXCEPTION."""
    LOGIN_FAILED = "login_failed"
    FOLDER_LIST_FAILED = "folder_list_failed"
    FOLDER_SELECT_FAILED = "folder_select_failed"
    SEARCH_FAILED = "search_failed"
    FETCH_FAILED = "fetch_failed"
    COPY_FAILED = "copy_failed"
    MOVE_FAILED = "move_failed"
    DELETE_TO_TRASH_FAILED = "delete_to_trash_failed"
    FILESYSTEM_ERROR = "filesystem_error"
    GMAIL_ERROR = "gmail_error" # Generischer Fehler, wenn spezifischere IMAP-Fehler nicht zutreffen
    UNKNOWN_ERROR = "unknown_error"


class GMAIL_LIB_EXCEPTION(Exception):
    """
    Benutzerdefinierte Ausnahme für Fehler in der GmailLib.
    Typ kann verwendet werden, um spezifische Fehlerszenarien zu identifizieren.
    """
    def __init__(self, type: str, message: str):
        self.type = type
        self.message = message
        super().__init__(f"Type: {self.type}, Message: {self.message}")

    def __str__(self):
        return f"GMAIL_LIB_EXCEPTION(Type: {self.type}, Message: {self.message})"

class GmailLib:
    def __init__(self, user, password):
        """
        Initialisiert die Gmail-Bibliothek.
        Verbindet sich noch nicht mit dem IMAP-Server.
        """
        logger.debug("GmailLib.__init__ gestartet.")
        self.user = user
        self.password = password
        self.mail = None # IMAP-Verbindung wird später aufgebaut
        logger.debug("GmailLib.__init__ beendet.")

    def _login(self):
        """Stellt die Verbindung zu Gmail her und meldet sich an.
        Wirft GMAIL_LIB_EXCEPTION bei Fehlschlag."""
        logger.debug("GmailLib._login gestartet.")
        if self.mail and self.mail.state == 'AUTH':
            logger.debug("Bereits angemeldet.")
            return # Bereits angemeldet, tue nichts
        try:
            self.mail = imaplib.IMAP4_SSL("imap.gmail.com")
            self.mail.login(self.user, self.password)
            logger.info(f"Erfolgreich bei {self.user} angemeldet.")
            logger.debug("GmailLib._login beendet: Erfolg.")
            return # Login erfolgreich
        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP-Fehler beim Login für {self.user}: {e}", exc_info=True)
            logger.debug("GmailLib._login beendet: Fehler.")
            raise GMAIL_LIB_EXCEPTION(type=ErrorType.LOGIN_FAILED, message=f"Login fehlgeschlagen für {self.user}: Prüfe Benutzername/App-Passwort oder IMAP-Aktivierung. ({e})")
        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim Login für {self.user}: {e}", exc_info=True)
            logger.debug("GmailLib._login beendet: Fehler.")
            raise GMAIL_LIB_EXCEPTION(type=ErrorType.UNKNOWN_ERROR, message=f"Unerwarteter Login-Fehler für {self.user}: {e}")

    def _logout(self):
        """Meldet sich vom IMAP-Server ab.
        Wirft GMAIL_LIB_EXCEPTION bei Fehlschlag."""
        logger.debug("GmailLib._logout gestartet.")
        if self.mail:
            try:
                self.mail.logout()
                logger.info("Erfolgreich von Gmail abgemeldet.")
                logger.debug("GmailLib._logout beendet: Erfolg.")
                return # Erfolgreich abgemeldet
            except Exception as e:
                logger.error(f"Fehler beim Logout: {e}", exc_info=True)
                logger.debug("GmailLib._logout beendet: Fehler.")
                raise GMAIL_LIB_EXCEPTION(type=ErrorType.UNKNOWN_ERROR, message=f"Fehler beim Logout: {e}")
        logger.debug("GmailLib._logout beendet: Keine aktive Verbindung.")
        # Wenn keine aktive Verbindung besteht, ist das kein Fehler, sondern der erwartete Zustand.
        # Es ist keine Exception nötig.
        return

    def list_all_folders(self):
        """
        Gibt eine Liste aller Ordner im Gmail-Konto zurück.
        Wirft GMAIL_LIB_EXCEPTION bei IMAP-Fehlern.
        """
        logger.debug("GmailLib.list_all_folders gestartet.")
        try:
            status, folders = self.mail.list()
            if status == "OK":
                folder_names = []
                for folder_line in folders:
                    decoded_line = folder_line.decode('utf-7')
                    # Verwende Regex, um den Ordnernamen innerhalb der letzten doppelten Anführungszeichen zu finden
                    match = re.search(r'"([^"]*)"[^"]*$', decoded_line)
                    if match:
                        folder_name = match.group(1)
                        # Überprüfe auf den \Noselect Flag, um Hierarchie-Container auszuschließen
                        if '\\Noselect' not in decoded_line: 
                            folder_names.append(folder_name)
                    # Andernfalls, wenn kein Regex-Match gefunden wird, versuchen wir den alten Ansatz als Fallback
                    # Dies sollte jedoch mit der neuen Regex-Logik seltener auftreten
                    elif ')' in decoded_line:
                        parts = decoded_line.split(')')
                        if len(parts) > 1:
                            potential_name = parts[-1].strip().strip('"')
                            if potential_name and '\\Noselect' not in decoded_line:
                                folder_names.append(potential_name)
                
                logger.debug(f"GmailLib.list_all_folders beendet: {folder_names}.")
                return folder_names
            else:
                error_msg = folders[0].decode() if folders and isinstance(folders, list) and len(folders) > 0 else "Unbekannte Fehlermeldung beim Auflisten der Ordner."
                logger.error(f"Fehler beim Auflisten der Ordner: {error_msg}")
                logger.debug("GmailLib.list_all_folders beendet: Fehler.")
                raise GMAIL_LIB_EXCEPTION(type=ErrorType.FOLDER_LIST_FAILED, message=f"Fehler beim Auflisten der Ordner: {error_msg}")
        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP-Fehler beim Auflisten der Ordner: {e}", exc_info=True)
            logger.debug("GmailLib.list_all_folders beendet: IMAP-Fehler.")
            raise GMAIL_LIB_EXCEPTION(type=ErrorType.FOLDER_LIST_FAILED, message=f"IMAP-Fehler beim Auflisten der Ordner: {e}")
        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim Auflisten der Ordner: {e}", exc_info=True)
            logger.debug("GmailLib.list_all_folders beendet: Unerwarteter Fehler.")
            raise GMAIL_LIB_EXCEPTION(type=ErrorType.UNKNOWN_ERROR, message=f"Unerwarteter Fehler beim Auflisten der Ordner: {e}")

    def folder_exists(self, folder_name):
        """
        Prüft, ob ein Ordner existiert.
        Wirft GMAIL_LIB_EXCEPTION, wenn das Auflisten der Ordner fehlschlägt.
        """
        logger.debug(f"GmailLib.folder_exists gestartet für Ordner: {folder_name}.")
        try:
            folders = self.list_all_folders()
            exists = folder_name in folders
            logger.debug(f"GmailLib.folder_exists beendet für Ordner '{folder_name}': {exists}.")
            return exists
        except GMAIL_LIB_EXCEPTION: # list_all_folders wirft die Exception, fangen wir hier nicht ab
            raise # Leite die Exception einfach weiter
        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim Prüfen der Ordner-Existenz: {e}", exc_info=True)
            logger.debug("GmailLib.folder_exists beendet: Unerwarteter Fehler.")
            raise GMAIL_LIB_EXCEPTION(type=ErrorType.UNKNOWN_ERROR, message=f"Unerwarteter Fehler beim Prüfen der Ordner-Existenz: {e}")

    def get_message_ids_in_folder(self, folder_name):
        """
        Holt alle Nachrichten-IDs aus einem spezifischen Ordner und sortiert sie absteigend.
        Wirft GMAIL_LIB_EXCEPTION bei IMAP-Fehlern.
        """
        logger.debug(f"GmailLib.get_message_ids_in_folder gestartet für Ordner: {folder_name}.")
        try:
            status, messages_count_raw = self.mail.select(f'"{folder_name}"', readonly=False) # readonly=False für spätere Operationen
            if status != "OK":
                error_msg = messages_count_raw[0].decode() if messages_count_raw and isinstance(messages_count_raw, list) and len(messages_count_raw) > 0 else "Unbekannte Fehlermeldung beim Ordnerauswahl."
                logger.error(f"Fehler beim Auswählen des Ordners '{folder_name}': {error_msg}")
                raise GMAIL_LIB_EXCEPTION(type=ErrorType.FOLDER_SELECT_FAILED, message=f"Fehler beim Auswählen des Ordners '{folder_name}': {error_msg}")

            status, raw_message_ids = self.mail.search(None, "ALL")
            if status != "OK":
                error_msg = raw_message_ids[0].decode() if raw_message_ids and isinstance(raw_message_ids, list) and len(raw_message_ids) > 0 else "Unbekannte Fehlermeldung bei der E-Mail-Suche."
                logger.error(f"Fehler bei der Suche nach E-Mails im Ordner '{folder_name}': {error_msg}")
                raise GMAIL_LIB_EXCEPTION(type=ErrorType.SEARCH_FAILED, message=f"Fehler bei der Suche nach E-Mails im Ordner '{folder_name}': {error_msg}")

            if not raw_message_ids or not isinstance(raw_message_ids, list) or len(raw_message_ids) == 0 or not raw_message_ids[0]:
                logger.info(f"Keine oder ungültige Nachrichten-IDs von mail.search erhalten. Raw Message IDs: {raw_message_ids}")
                return [] # Leere Liste, keine E-Mails zum Verarbeiten

            # Hier ist die Änderung: Sortiere die IDs absteigend
            message_ids = raw_message_ids[0].split()
            # Konvertiere in Integer für korrekte Sortierung und dann zurück in Bytes
            message_ids_int = sorted([int(mid) for mid in message_ids], reverse=True)
            message_ids_sorted = [str(mid).encode('utf-8') for mid in message_ids_int]

            logger.debug(f"GmailLib.get_message_ids_in_folder beendet: {len(message_ids_sorted)} IDs gefunden (absteigend sortiert).")
            return message_ids_sorted
        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP-Fehler beim Abrufen der Nachrichten-IDs aus '{folder_name}': {e}", exc_info=True)
            raise GMAIL_LIB_EXCEPTION(type=ErrorType.SEARCH_FAILED, message=f"IMAP-Fehler beim Abrufen der Nachrichten-IDs aus '{folder_name}': {e}")
        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim Abrufen der Nachrichten-IDs aus '{folder_name}': {e}", exc_info=True)
            raise GMAIL_LIB_EXCEPTION(type=ErrorType.UNKNOWN_ERROR, message=f"Unerwarteter Fehler beim Abrufen der Nachrichten-IDs: {e}")

    def _fetch_email_message(self, msg_id):
        """
        Hilfsmethode: Holt eine E-Mail im Rohformat und parst sie.
        Wirft GMAIL_LIB_EXCEPTION bei IMAP-Fehlern.
        """
        logger.debug(f"GmailLib._fetch_email_message gestartet für msg_id: {msg_id.decode()}.")
        try:
            status, data = self.mail.fetch(msg_id, "(RFC822)")
            if status != "OK" or not data or not isinstance(data, list) or len(data) == 0 or not data[0] or not isinstance(data[0], tuple) or len(data[0]) < 2:
                error_msg = f"Konnte E-Mail mit ID {msg_id.decode()} nicht abrufen oder Daten sind unvollständig. Status: {status}, Data: {data}."
                logger.warning(error_msg) # Log as warning, then raise specific exception
                raise GMAIL_LIB_EXCEPTION(type=ErrorType.FETCH_FAILED, message=error_msg)
            
            raw_email = data[0][1]
            email_message = email.message_from_bytes(raw_email)
            logger.debug(f"GmailLib._fetch_email_message beendet für msg_id: {msg_id.decode()}.")
            return raw_email, email_message
        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP-Fehler beim Abrufen der E-Mail {msg_id.decode()}: {e}", exc_info=True)
            raise GMAIL_LIB_EXCEPTION(type=ErrorType.FETCH_FAILED, message=f"IMAP-Fehler beim Abrufen der E-Mail {msg_id.decode()}: {e}")
        except Exception as e: # Catch any other unexpected exceptions
            logger.error(f"Unerwarteter Fehler beim Abrufen der E-Mail {msg_id.decode()}: {e}", exc_info=True)
            raise GMAIL_LIB_EXCEPTION(type=ErrorType.UNKNOWN_ERROR, message=f"Unerwarteter Fehler beim Abrufen der E-Mail {msg_id.decode()}: {e}")

    def has_attachments(self, msg_id):
        """
        Prüft, ob ein Objekt (E-Mail) Anlagen hat.
        Wirft GMAIL_LIB_EXCEPTION bei IMAP-Fehlern beim Abrufen der E-Mail.
        """
        logger.debug(f"GmailLib.has_attachments gestartet für msg_id: {msg_id.decode()}.")
        try:
            _, email_message = self._fetch_email_message(msg_id)
        except GMAIL_LIB_EXCEPTION as e:
            logger.debug(f"GmailLib.has_attachments beendet: Fehler beim Holen der E-Mail ({e.message}).")
            raise # Leite die Exception einfach weiter

        has_any = False
        for part in email_message.walk():
            if part.get_content_maintype() == "multipart":
                continue
            if part.get("Content-Disposition") is not None:
                has_any = True
                break
        logger.debug(f"GmailLib.has_attachments beendet für msg_id {msg_id.decode()}: {has_any}.")
        return has_any

    def _sanitize_filename(self, filename, max_length=200):
        """Bereinigt Dateinamen von ungültigen Zeichen und kürzt sie."""
        clean_filename = "".join(x for x in filename if x.isalnum() or x in " ._-").strip()
        if not clean_filename:
            return "untitled_file" # Fallback
        clean_filename = clean_filename[:max_length]
        return " ".join(clean_filename.split()).strip()

    def save_email(self, msg_id, save_path_base):
        """
        Speichert ein Objekt (E-Mail) in einem File-Ordner.
        Wirft GMAIL_LIB_EXCEPTION bei Dateisystem- oder Gmail-Fehlern.
        """
        logger.debug(f"GmailLib.save_email gestartet für msg_id: {msg_id.decode()}, path: {save_path_base}.")
        emails_save_path = os.path.join(save_path_base, "E-Mails")
        try:
            if not os.path.exists(emails_save_path):
                os.makedirs(emails_save_path)
                logger.info(f"Lokaler Ordner '{emails_save_path}' wurde erstellt.")
        except Exception as e:
            logger.error(f"Dateisystem-Fehler beim Erstellen des E-Mail-Speicherordners '{emails_save_path}': {e}", exc_info=True)
            raise GMAIL_LIB_EXCEPTION(type=ErrorType.FILESYSTEM_ERROR, message=f"Dateisystem-Fehler beim Erstellen des E-Mail-Speicherordners '{emails_save_path}': {e}")

        try:
            raw_email, email_message = self._fetch_email_message(msg_id) # Diese Methode kann GMAIL_LIB_EXCEPTION werfen
        except GMAIL_LIB_EXCEPTION as e:
            # Fängt spezifischen Gmail-Fehler von _fetch_email_message ab und wirft ihn als GMAIL_ERROR weiter
            raise GMAIL_LIB_EXCEPTION(type=ErrorType.GMAIL_ERROR, message=f"Fehler beim Abrufen der E-Mail zum Speichern: {e.message}")

        subject = email_message.get("Subject", "Ohne Betreff")
        subject_decoded = ""
        for part, encoding in decode_header(subject):
            if isinstance(part, bytes):
                try:
                    subject_decoded += part.decode(encoding or "utf-8")
                except (UnicodeDecodeError, TypeError):
                    subject_decoded += part.decode("latin-1", errors="ignore")
            else:
                subject_decoded += part
        
        email_filename = self._sanitize_filename(subject_decoded)
        email_filename = f"{email_filename}_{msg_id.decode()}.eml" # Eindeutigkeit durch ID
        email_filepath = os.path.join(emails_save_path, email_filename)

        try:
            with open(email_filepath, "wb") as f_email:
                f_email.write(raw_email)
            logger.info(f"E-Mail als '{email_filename}' in '{emails_save_path}' gespeichert.")
            logger.debug("GmailLib.save_email beendet: Erfolg.")
            return # Erfolgreich gespeichert
        except Exception as e:
            logger.error(f"Dateisystem-Fehler beim Speichern der E-Mail '{email_filename}': {e}", exc_info=True)
            logger.debug("GmailLib.save_email beendet: Fehler beim Dateisystem.")
            raise GMAIL_LIB_EXCEPTION(type=ErrorType.FILESYSTEM_ERROR, message=f"Dateisystem-Fehler beim Speichern der E-Mail '{email_filename}': {e}")

    def save_attachments(self, msg_id, save_path_base):
        """
        Speichert alle Anlagen eines Objektes (E-Mail) in einem File-Ordner.
        Wirft GMAIL_LIB_EXCEPTION bei Dateisystem- oder Gmail-Fehlern.
        """
        logger.debug(f"GmailLib.save_attachments gestartet für msg_id: {msg_id.decode()}, path: {save_path_base}.")
        attachments_save_path = os.path.join(save_path_base, "Anlagen")
        try:
            if not os.path.exists(attachments_save_path):
                os.makedirs(attachments_save_path)
                logger.info(f"Lokaler Ordner '{attachments_save_path}' wurde erstellt.")
        except Exception as e:
            logger.error(f"Dateisystem-Fehler beim Erstellen des Anhänge-Speicherordners '{attachments_save_path}': {e}", exc_info=True)
            raise GMAIL_LIB_EXCEPTION(type=ErrorType.FILESYSTEM_ERROR, message=f"Dateisystem-Fehler beim Erstellen des Anhänge-Speicherordners '{attachments_save_path}': {e}")

        try:
            _, email_message = self._fetch_email_message(msg_id) # Diese Methode kann GMAIL_LIB_EXCEPTION werfen
        except GMAIL_LIB_EXCEPTION as e:
            logger.error(f"Fehler beim Abrufen der E-Mail zum Speichern von Anhängen: {e.message}", exc_info=True)
            logger.debug("GmailLib.save_attachments beendet: Fehler beim Abrufen der E-Mail.")
            raise GMAIL_LIB_EXCEPTION(type=ErrorType.GMAIL_ERROR, message=f"Fehler beim Abrufen der E-Mail zum Speichern von Anhängen: {e.message}")

        attachments_saved = 0
        for part in email_message.walk():
            if part.get_content_maintype() == "multipart" or part.get("Content-Disposition") is None:
                continue
            
            filename = part.get_filename()
            if filename:
                clean_filename = self._sanitize_filename(filename)
                # Füge msg_id hinzu, um Dateinamen bei Duplikaten eindeutig zu machen
                # Behalte die ursprüngliche Dateiendung bei
                original_extension = filename.split('.')[-1] if '.' in filename else ''
                if original_extension and len(original_extension) <= 5: # Kurze Endungen behalten
                     final_filename = f"{clean_filename}_{msg_id.decode()}_{attachments_saved}.{original_extension}"
                else: # Sonst keine Endung oder zu lange Endung
                     final_filename = f"{clean_filename}_{msg_id.decode()}_{attachments_saved}"

                filepath = os.path.join(attachments_save_path, final_filename)
                
                try:
                    with open(filepath, "wb") as f_attachment:
                        f_attachment.write(part.get_payload(decode=True))
                    logger.info(f"Anhang '{final_filename}' gespeichert in '{attachments_save_path}'.")
                    attachments_saved += 1
                except Exception as e:
                    logger.error(f"Dateisystem-Fehler beim Speichern des Anhangs '{final_filename}': {e}", exc_info=True)
                    raise GMAIL_LIB_EXCEPTION(type=ErrorType.FILESYSTEM_ERROR, message=f"Dateisystem-Fehler beim Speichern des Anhangs '{final_filename}': {e}")
        
        logger.debug(f"GmailLib.save_attachments beendet für msg_id {msg_id.decode()}: {attachments_saved} Anhänge gespeichert.")
        return # Erfolgreich gespeichert

    def move_object(self, msg_id, source_folder, target_folder):
        """
        Verschiebt ein Objekt (E-Mail) von einem Ordner in einen anderen Ordner.
        Wirft GMAIL_LIB_EXCEPTION bei IMAP-Fehlern.
        """
        logger.debug(f"GmailLib.move_object gestartet für msg_id: {msg_id.decode()} von '{source_folder}' nach '{target_folder}'.")
        try:
            # Stelle sicher, dass der Quellordner ausgewählt ist, um die msg_id zu finden
            self.mail.select(f'"{source_folder}"')
            
            # Kopiere die E-Mail in den Zielordner
            status_copy, response_copy = self.mail.copy(msg_id, f'"{target_folder}"')
            if status_copy != "OK":
                error_msg = response_copy[0].decode() if response_copy and isinstance(response_copy, list) and len(response_copy) > 0 else "Unbekannter Fehler beim Kopieren."
                logger.error(f"Fehler beim Kopieren der E-Mail {msg_id.decode()} nach '{target_folder}': {error_msg}")
                raise GMAIL_LIB_EXCEPTION(type=ErrorType.COPY_FAILED, message=f"Fehler beim Kopieren der E-Mail nach '{target_folder}': {error_msg}")
            
            # Markiere die E-Mail im Quellordner als gelöscht
            status_store, response_store = self.mail.store(msg_id, '+FLAGS', '\\Deleted')
            if status_store != "OK":
                error_msg = response_store[0].decode() if response_store and isinstance(response_store, list) and len(response_store) > 0 else "Unbekannter Fehler beim Markieren als gelöscht."
                logger.warning(f"Warnung: Konnte E-Mail {msg_id.decode()} im Quellordner '{source_folder}' nicht als gelöscht markieren: {error_msg}")
                # Wir werfen hier keine Exception, da das Kopieren erfolgreich war und das Verschieben primärziel ist.
            
            self.mail.expunge() # Wichtig, um die Löschung zu finalisieren
            logger.info(f"E-Mail {msg_id.decode()} erfolgreich von '{source_folder}' nach '{target_folder}' verschoben.")
            logger.debug("GmailLib.move_object beendet: Erfolg.")
            return # Erfolgreich verschoben
        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP-Fehler beim Verschieben der E-Mail {msg_id.decode()}: {e}", exc_info=True)
            raise GMAIL_LIB_EXCEPTION(type=ErrorType.MOVE_FAILED, message=f"IMAP-Fehler beim Verschieben der E-Mail: {e}")
        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim Verschieben der E-Mail {msg_id.decode()}: {e}", exc_info=True)
            raise GMAIL_LIB_EXCEPTION(type=ErrorType.UNKNOWN_ERROR, message=f"Unerwarteter Fehler beim Verschieben der E-Mail: {e}")

    def delete_object_to_trash(self, msg_id, folder_name):
        """
        Löscht ein Objekt (E-Mail) in einem Ordner (verschiebt es in den Papierkorb).
        Wirft GMAIL_LIB_EXCEPTION bei IMAP-Fehlern.
        """
        logger.debug(f"GmailLib.delete_object_to_trash gestartet für msg_id: {msg_id.decode()} in Ordner: {folder_name}.")
        try:
            self.mail.select(f'"{folder_name}"')
            
            trash_folder_name = "Trash" # Default für internationale Konten, wird versucht zu lokalisieren
            try:
                trash_folder_status, trash_folders_raw = self.mail.list('', '%Trash%')
                if trash_folder_status == "OK" and trash_folders_raw:
                    for f_raw in trash_folders_raw:
                        # IMAP LIST response might be in Modified UTF-7. Decode carefully.
                        f_decoded = f_raw.decode('utf-7', errors='ignore')
                        # Heuristik: Check for common localized trash folder names
                        if 'Trash' in f_decoded or 'Papierkorb' in f_decoded:
                            # Extract the actual folder name, which is usually the last part after '"/"' or '") "'
                            parts = f_decoded.split(')"')
                            if len(parts) > 1:
                                potential_name = parts[-1].strip().strip('"')
                                if potential_name:
                                    trash_folder_name = potential_name
                                    break
            except Exception as e:
                logger.warning(f"Konnte lokalen Papierkorb-Ordner nicht zuverlässig finden, nutze Standard 'Trash'. Fehler: {e}")

            status_copy, response_copy = self.mail.copy(msg_id, f'"{trash_folder_name}"')
            if status_copy != "OK":
                error_msg = response_copy[0].decode() if response_copy and isinstance(response_copy, list) and len(response_copy) > 0 else "Unbekannter Fehler beim Kopieren in den Papierkorb."
                logger.error(f"Fehler beim Kopieren der E-Mail {msg_id.decode()} in den Papierkorb '{trash_folder_name}': {error_msg}")
                raise GMAIL_LIB_EXCEPTION(type=ErrorType.DELETE_TO_TRASH_FAILED, message=f"Fehler beim Kopieren in den Papierkorb: {error_msg}")
            
            status_store, response_store = self.mail.store(msg_id, '+FLAGS', '\\Deleted')
            if status_store != "OK":
                error_msg = response_store[0].decode() if response_store and isinstance(response_store, list) and len(response_store) > 0 else "Unbekannter Fehler beim Markieren als gelöscht."
                logger.warning(f"Warnung: Konnte E-Mail {msg_id.decode()} im Ordner '{folder_name}' nicht als gelöscht markieren: {error_msg}")
            
            self.mail.expunge() # Endgültiges Löschen aus dem Quellordner
            logger.info(f"E-Mail {msg_id.decode()} erfolgreich in den Papierkorb verschoben.")
            logger.debug("GmailLib.delete_object_to_trash beendet: Erfolg.")
            return # Erfolgreich gelöscht
        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP-Fehler beim Löschen der E-Mail {msg_id.decode()} in den Papierkorb: {e}", exc_info=True)    
            raise GMAIL_LIB_EXCEPTION(type=ErrorType.DELETE_TO_TRASH_FAILED, message=f"IMAP-Fehler beim Löschen der E-Mail in den Papierkorb: {e}")
        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim Löschen der E-Mail {msg_id.decode()} in den Papierkorb: {e}", exc_info=True)
            raise GMAIL_LIB_EXCEPTION(type=ErrorType.UNKNOWN_ERROR, message=f"Unerwarteter Fehler beim Löschen der E-Mail in den Papierkorb: {e}")
