"""
Módulo de Histórico Persistente e Rotatividade Geográfica
Garante que leads já coletados em buscas anteriores NUNCA sejam repetidos,
e gerencia a rotação automática de regiões e cidades do Brasil.
"""

import os
import re
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Any, Optional, Tuple

from config import OUTPUT_DIR, BASE_DIR, BRAZIL_REGIONS

HISTORY_FILE = OUTPUT_DIR / ".lead_history.json"
_lock = threading.Lock()


def normalize_text(text: str) -> str:
    """Normaliza texto removendo pontuação e espaços extras para comparação."""
    if not text:
        return ""
    cleaned = re.sub(r'[^\w\s]', '', text.lower())
    return re.sub(r'\s+', ' ', cleaned).strip()


def extract_phone_digits(raw_phone: str) -> str:
    """Extrai apenas dígitos de um telefone."""
    if not raw_phone:
        return ""
    digits = re.sub(r'\D', '', str(raw_phone))
    # Remove 55 inicial se tiver para normalizar número nacional
    if digits.startswith("55") and len(digits) >= 12:
        return digits[2:]
    return digits


class LeadHistoryManager:
    """
    Controla o histórico persistente de leads capturados e o cursor de regiões.
    """

    def __init__(self, history_path: Path = HISTORY_FILE):
        self.history_path = history_path
        self.known_phones: Set[str] = set()
        self.known_names: Set[str] = set()
        self.known_maps_urls: Set[str] = set()
        self.region_cursor: int = 0
        self.total_leads_ever: int = 0
        self.last_updated: Optional[str] = None
        self._load()

    def _load(self):
        """Carrega o histórico do arquivo JSON se existir."""
        if not self.history_path.exists():
            return

        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.known_phones = set(data.get("known_phones", []))
                self.known_names = set(data.get("known_names", []))
                self.known_maps_urls = set(data.get("known_maps_urls", []))
                self.region_cursor = data.get("region_cursor", 0)
                self.total_leads_ever = data.get("total_leads_ever", len(self.known_names))
                self.last_updated = data.get("last_updated")
        except Exception as e:
            print(f"⚠️ Aviso ao carregar histórico: {e}")

    def _save(self):
        """Salva o estado atual no arquivo JSON."""
        try:
            data = {
                "region_cursor": self.region_cursor,
                "total_leads_ever": len(self.known_names),
                "last_updated": datetime.utcnow().isoformat() + "Z",
                "known_phones": list(self.known_phones),
                "known_names": list(self.known_names),
                "known_maps_urls": list(self.known_maps_urls),
            }
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Erro ao salvar histórico: {e}")

    def is_duplicate(
        self,
        name: str,
        phone: Optional[str] = None,
        maps_url: Optional[str] = None,
        extra_excluded_phones: Optional[Set[str]] = None,
        extra_excluded_names: Optional[Set[str]] = None,
    ) -> bool:
        """
        Verifica instantaneamente se o lead já foi coletado em execuções anteriores.
        Retorna True se já existir no histórico.
        """
        norm_name = normalize_text(name)
        phone_digits = extract_phone_digits(phone or "")

        # 1. Checagem por telefone
        if phone_digits and len(phone_digits) >= 8:
            if phone_digits in self.known_phones:
                return True
            if extra_excluded_phones and phone_digits in extra_excluded_phones:
                return True

        # 2. Checagem por nome normalizado
        if norm_name and norm_name in self.known_names:
            return True
        if norm_name and extra_excluded_names and norm_name in extra_excluded_names:
            return True

        # 3. Checagem por URL do Google Maps
        if maps_url and maps_url in self.known_maps_urls:
            return True

        return False

    def add_lead(self, lead: Dict[str, Any]):
        """Adiciona um lead ao histórico persistente."""
        with _lock:
            name = lead.get("name", "")
            phone = lead.get("phone") or lead.get("whatsapp_site") or ""
            maps_url = lead.get("maps_url", "")

            norm_name = normalize_text(name)
            phone_digits = extract_phone_digits(phone)

            if norm_name:
                self.known_names.add(norm_name)
            if phone_digits and len(phone_digits) >= 8:
                self.known_phones.add(phone_digits)
            if maps_url:
                self.known_maps_urls.add(maps_url)

    def add_leads_batch(self, leads: List[Dict[str, Any]]):
        """Adiciona um lote de leads e persiste no disco."""
        with _lock:
            for lead in leads:
                name = lead.get("name", "")
                phone = lead.get("phone") or lead.get("whatsapp_site") or ""
                maps_url = lead.get("maps_url", "")

                norm_name = normalize_text(name)
                phone_digits = extract_phone_digits(phone)

                if norm_name:
                    self.known_names.add(norm_name)
                if phone_digits and len(phone_digits) >= 8:
                    self.known_phones.add(phone_digits)
                if maps_url:
                    self.known_maps_urls.add(maps_url)

            self.total_leads_ever = len(self.known_names)
            self._save()

    def get_next_regions(self, count: int = 50) -> Tuple[List[str], int]:
        """
        Retorna a próxima fatia de regiões a serem varridas a partir do cursor atual,
        garantindo rotatividade contínua e sem repetição.
        """
        total_regions = len(BRAZIL_REGIONS)
        if total_regions == 0:
            return [], 0

        with _lock:
            start_idx = self.region_cursor % total_regions
            selected = []
            
            for i in range(count):
                idx = (start_idx + i) % total_regions
                selected.append(BRAZIL_REGIONS[idx])

            # Atualiza o cursor para a próxima execução
            next_cursor = (start_idx + count) % total_regions
            self.region_cursor = next_cursor
            self._save()

            return selected, start_idx

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas da memória histórica."""
        return {
            "total_unique_leads_in_history": len(self.known_names),
            "total_unique_phones": len(self.known_phones),
            "current_region_cursor": self.region_cursor,
            "total_configured_regions": len(BRAZIL_REGIONS),
            "last_updated": self.last_updated,
        }


# Instância global de histórico
lead_history = LeadHistoryManager()
