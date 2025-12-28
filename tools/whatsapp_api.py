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
            
    def _get_headers(self):
        # Tenta cobrir vários padrões de auth de APIs de WhatsApp
        return {
            "Content-Type": "application/json",
            "apikey": self.token,
            "token": self.token,
            "Authorization": f"Bearer {self.token}",
            "X-Instance-Token": self.token # Header específico confirmado no teste
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

    def get_media_base64(self, message_id: str) -> Optional[Dict[str, str]]:
        """
        Obtém mídia em Base64
        POST /message/download
        Retorna dict com 'base64' e 'mimetype'
        """
        if not self.base_url: return None
        
        url = f"{self.base_url}/message/download"
        payload = {
            "id": message_id,
            "return_link": False,
            "return_base64": True
        }
        
        try:
            resp = requests.post(url, headers=self._get_headers(), json=payload, timeout=30) # Timeout maior para download
            if resp.status_code == 200:
                data = resp.json()
                # A API retorna { success: true, data: { base64: "...", mimetype: "..." } }
                if data.get("success") and "data" in data:
                    return data["data"]
                # Ou pode retornar direto no root se a versão for diferente
                if "base64" in data:
                    return data
            else:
                logger.warning(f"⚠️ Erro API Mídia ({resp.status_code}): {resp.text[:200]}")
        except Exception as e:
            logger.error(f"Erro ao obter mídia WhatsApp ({message_id}): {e}")
            
        return None

# Instância global
whatsapp = WhatsAppAPI()
