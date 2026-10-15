import requests
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class NelsiusPayClient:
    def __init__(self):
        self.api_key = getattr(settings, 'NELSIUS_API_KEY', '') or getattr(settings, 'NELSIUS_SECRET_KEY', '') or ''
        self.base_url = getattr(settings, 'NELSIUS_BASE_URL', 'https://api.nelsiuspay.com/api/v1').rstrip('/')
        self.headers = {
            'X-Api-Key': self.api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    def initiate_checkout(
        self,
        amount: int | float,
        reference: str,
        customer_email: str,
        customer_name: str = "",
        customer_phone: str = "",
        description: str = "Paiement GSD Alliance",
        return_url: str = "",
        webhook_url: str = ""
    ) -> dict:
        """
        Initialise une session de paiement NelsiusPay (MTN MoMo, Orange Money, Wave, Cartes Visa/Mastercard).
        Retourne l'URL de paiement vers laquelle rediriger le client.
        """
        payload = {
            "amount": int(amount),
            "currency": "XAF",
            "reference": reference,
            "customer_email": customer_email,
            "customer_name": customer_name or customer_email,
            "customer_phone": customer_phone or "",
            "description": description,
        }
        if return_url:
            payload["return_url"] = return_url
        if webhook_url:
            payload["webhook_url"] = webhook_url

        checkout_endpoint = f"{self.base_url}/checkout"

        try:
            logger.info(f"[NelsiusPay] Envoi requête checkout vers {checkout_endpoint} pour réf: {reference}")
            response = requests.post(checkout_endpoint, json=payload, headers=self.headers, timeout=12)
            
            # Diagnostic & log
            logger.info(f"[NelsiusPay] Réponse [{response.status_code}]: {response.text}")
            
            try:
                res_data = response.json()
            except Exception:
                res_data = {"raw": response.text}

            if response.status_code in [200, 201]:
                # Format standard NelsiusPay: { "payment_url": "...", "transaction_id": "...", ... }
                checkout_url = (
                    res_data.get('payment_url') 
                    or res_data.get('checkout_url')
                    or res_data.get('data', {}).get('payment_url')
                    or res_data.get('data', {}).get('checkout_url')
                )
                return {
                    "success": True,
                    "checkout_url": checkout_url,
                    "transaction_id": res_data.get('transaction_id') or res_data.get('data', {}).get('id'),
                    "data": res_data,
                }
            else:
                error_msg = res_data.get('message') or res_data.get('error') or response.text
                logger.warning(f"[NelsiusPay] Échec initiation checkout: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "status_code": response.status_code,
                    "data": res_data,
                }

        except requests.RequestException as exc:
            logger.error(f"[NelsiusPay] Exception réseau lors du checkout: {str(exc)}")
            return {
                "success": False,
                "error": f"Erreur de communication avec NelsiusPay: {str(exc)}",
            }

    def verify_payment(self, reference: str) -> dict:
        """
        Vérifie le statut d'un paiement auprès de NelsiusPay via sa référence.
        """
        verify_endpoint = f"{self.base_url}/payments/{reference}"
        try:
            response = requests.get(verify_endpoint, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                status_raw = data.get('status') or data.get('data', {}).get('status')
                is_paid = status_raw in ['SUCCESS', 'PAID', 'COMPLETED', 'success', 'paid']
                return {
                    "success": True,
                    "is_paid": is_paid,
                    "status": status_raw,
                    "data": data,
                }
            return {
                "success": False,
                "error": f"Code HTTP {response.status_code}: {response.text}",
            }
        except Exception as exc:
            logger.error(f"[NelsiusPay] Erreur vérification paiement {reference}: {str(exc)}")
            return {"success": False, "error": str(exc)}

# Instance singleton
nelsius_client = NelsiusPayClient()
