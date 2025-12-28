import requests
import json
import re
from typing import Optional, Dict, Any
from config.settings import settings
from config.logger import setup_logger

logger = setup_logger(__name__)

class WhatsAppAPI:
    def __init__(self):
        self.base_url = (settings.whatsapp_api_base_url or "").rstrip("/")
        self.token = settings.whatsapp_instance_token
        
        if not self.base_url:
            logger.warning("WHATSAPP_API_BASE_URL não configurado!")
            
    def _get_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-Instance-Token": self.token or ""
        }

    def _clean_number(self, phone: str) -> str:
        """Remove caracteres não numéricos"""
        return re.sub(r"\D", "", str(phone))

    def send_text(self, to: str, text: str) -> bool:
        """
        Envia mensagem de texto simples
        POST /message/text
        """
        if not self.base_url: return False
        
        url = f"{self.base_url}/message/text"
        payload = {
            "to": self._clean_number(to),
            "text": text
        }
        
        try:
            resp = requests.post(url, headers=self._get_headers(), json=payload, timeout=10)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem WhatsApp para {to}: {e}")
            return False

    def send_presence(self, to: str, presence: str = "composing") -> bool:
        """
        Envia status de presença (digitando...)
        POST /message/presence
        Valores: composing, recording, available, unavailable
        """
        if not self.base_url: return False
        
        url = f"{self.base_url}/message/presence"
        payload = {
            "to": self._clean_number(to),
            "presence": presence
        }
        
        try:
            requests.post(url, headers=self._get_headers(), json=payload, timeout=5)
            return True
        except Exception:
            return False

    def get_media_url(self, message_id: str) -> Optional[str]:
        """
        Obtém link para download de mídia
        POST /message/download
        """
        if not self.base_url: return None
        
        url = f"{self.base_url}/message/download"
        payload = {
            "id": message_id,
            "return_link": True,
            "return_base64": False
        }
        
        try:
            resp = requests.post(url, headers=self._get_headers(), json=payload, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                # Tenta pegar fileURL ou url, dependendo do retorno da API
                return data.get("fileURL") or data.get("url")
            else:
                logger.warning(f"⚠️ Erro API Mídia ({resp.status_code}): {resp.text}")
        except Exception as e:
            logger.error(f"Erro ao obter mídia WhatsApp ({message_id}): {e}")
            
        return None

# Instância global
whatsapp = WhatsAppAPI()
