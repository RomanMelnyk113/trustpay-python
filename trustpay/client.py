import base64
import hashlib
import hmac
import json
import uuid
import logging
import requests

from datetime import date, datetime
from http import HTTPStatus
from typing import Optional
from urllib.parse import urlencode
from . import order_xml_string


from . import PaymentException

# DEFAULT_BASE_API_URL = 'https://api.trustpay.eu/api/oauth2/token'
DEFAULT_BASE_API_URL = "https://api.trustpay.eu"
SUPPORTED_CURRENCIES = ["EUR"]

logger = logging.getLogger(__name__)


# https://doc.trustpay.eu/?curl&ShowAPIBanking=true
class Trustpay:
    # account ID
    aid: str
    
    # project ID
    pid: str

    # secret key
    secret_key: str

    # password
    password: str

    # username
    username: str

    # api endpoint
    api_url: str

    # access token
    access_token: str = None

    # debug
    debug: bool = False

    def __init__(
        self, password, username, secret_key=None, aid=None, api_url=None, debug=False
    ):
        self.secret_key = secret_key
        self.aid = aid
        self.password = password
        self.username = username

        self.api_url = api_url or DEFAULT_BASE_API_URL

        self.access_token = self.get_access_token()
        self.debug = debug

    def create_merchant_signature(self, aid, amount, currency, reference):
        # A message is created as concatenation of parameter values in this specified order:
        # Merchant redirect to TrustPay: AID, AMT, CUR, and REF

        message = str(aid).encode("utf-8")
        message += str(amount).encode("utf-8")
        message += str(currency).encode("utf-8")
        message += str(reference).encode("utf-8")
        return self.sign(message)

    def check_trustpay_signature(self, signature, trustpay_signature):
        return trustpay_signature == signature

    def sign(self, message):
        try:
            key = self.secret_key

            # HMAC-SHA-256 code (32 bytes) is generated using a key obtained from TrustPay
            code = hmac.new(key, message, hashlib.sha256)

            # Then the code is converted to a string to be a hexadecimal representation of the code
            hex = code.hexdigest()

            # Return 64 upper chars
            return hex.upper()
        except TypeError:
            return None

    def _prepare_headers(self, with_access_token=True):
        # signature = self._make_signature(nonce, data, endpoint)
        if with_access_token:
            access_token = self.get_access_token()
            authorization = f"bearer {access_token}"
            return {"Authorization": authorization, "Content-Type": "text/json"}

        base_auth = base64.b64encode(f"{self.username}:{self.password}".encode("utf-8"))
        authorization = f"Basic {base_auth.decode()}"

        return {
            "Authorization": authorization,
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def _generate_url(self, endpoint):
        return self.api_url + endpoint

    def _send_request(
        self,
        endpoint: str,
        data: dict,
        headers: dict,
        transform_data_func: Optional[callable],
    ):
        if transform_data_func is not None:
            post_params = transform_data_func(data)
        else:
            post_params = data

        if self.debug:
            logger.info(
                f"Trustpay request: url={self._generate_url(endpoint)}; body={post_params}"
            )
        r = requests.post(
            self._generate_url(endpoint), headers=headers, data=post_params
        )
        if self.debug:
            logger.info(f"Trustpay reponse: {r.text}")
        if r.status_code != HTTPStatus.OK:
            raise PaymentException(
                "Trustpay error: {}. Error code: {}".format(r.text, r.status_code)
            )

        return json.loads(r.text)

    def get_access_token(self) -> str:
        """
        API Response example: {
            "access_token":"L3_DbiQdateYLPYmp31AHEeErRzF84SVRcyr5Zw4jgw3CqDZjn4dbmVilTQx6dh_8ZbPztJGQh-9",
            "token-type":"bearer",
        }

        :return access_token:str
        """
        if self.access_token:
            return self.access_token

        endpoint = "/api/oauth2/token"

        data = {"grant_type": "client_credentials"}

        headers = self._prepare_headers(with_access_token=False)

        result = self._send_request(endpoint, data, headers, urlencode)
        return result["access_token"]

    def account_details(self) -> dict:
        """

        API Response example:
        {
            'AccountDetails': {
                'AccountId': 2107920199,
                'IBAN': 'SK1799329999999999999999',
                'AccountName': 'SOME NAME',
                'AccountOwnerName': 'SOME MORE NAME',
                'AccountType': 'Individual',
                'CanCreateInternalOrder': True,
                'CanCreateBankWireOrder': True,
                'CurrencyCode': 'EUR',
                'AccountingBalance': '9999.99',
                'DisposableBalance': '8888.88',
                'FeeBalance': '4.50',
                'MinimalBalance': '200.00'
            }
        }
        """
        endpoint = "/ApiBanking/GetAccountDetails"
        data = {"AccountId": self.aid}
        headers = self._prepare_headers()
        result = self._send_request(endpoint, data, headers, json.dumps)
        return result["AccountDetails"]

    def send_money(
        self,
        amount: float,
        currency: str,
        recipient: str,
        account: str,
        details: str,
        bank_bik: str = "NOTPROVIDED",
    ) -> dict:
        """
        Transfer money from merchant account to recipient account
        https://doc.trustpay.eu/?php#ab-create-order

        :param amount: Amount of money
        :param currency: Currency (only EUR is available)
        :param recipient: Name of the recipient
        :param account: IBAN account number of recipient
        :param details: Details (description) of the transfer
        :return: OrderId

        Trustpay API response
        Example: {
            "OrderId": 123123
            }
        """
        if currency not in SUPPORTED_CURRENCIES:
            # TODO: raise relevant error instead default
            raise AttributeError(
                "Currency not supported. Please use any from this list: {}".format(
                    SUPPORTED_CURRENCIES
                )
            )

        endpoint = "/ApiBanking/CreateOrder"

        account_details = self.account_details()
        code = str(uuid.uuid4()).replace("-", "")[:12]
        config = {
            "MessageId": f"{account_details['AccountId']}-{code}",
            "CreationDateTime": datetime.today().isoformat().split(".")[0],
            "RequestedExecutionDate": date.today().isoformat(),
            "DebtorName": account_details["AccountName"],
            "DebtorAccount": account_details["AccountId"],
            "Currency": currency,
            "Amount": amount,
            "CreditorBankBic": bank_bik,
            "CreditorName": recipient,
            "CreditorAccount": account,
            "Description": details,
        }
        order_data = order_xml_string.format(**config).replace("\n", " ")

        data_to_send = {"Xml": order_data}
        headers = self._prepare_headers()

        # TODO: error handling
        return self._send_request(endpoint, data_to_send, headers, json.dumps)
    
    def create_payment(
        self,
        code: str,
        amount: float,
        currency: str,
        merchant_reference: str,
        notification_url: str,
        success_url: str,
        error_url: str,
        **kwargs
    ) -> dict:
        """
        Create a card payment request to Trustpay.

        :param amount: Amount of money
        :param currency: Currency (only EUR is available)
        :param debtor_name: Name of the debtor
        :param debtor_address: Address of the debtor
        :param merchant_reference: Merchant reference for the payment
        :param notification_url: Callback URL for notifications
        :return: Response from Trustpay API
        """
        endpoint = "/api/Payments/Payment"

        payload = {
            "PaymentMethod": code,
            "MerchantIdentification": {
                "ProjectId": self.aid  # Assuming pid is the project ID
            },
            "PaymentInformation": {
                "Amount": {
                    "Amount": amount,
                    "Currency": currency
                },
                "IsRedirect": True,
                "Localization": "EN",
                "References": {
                    "MerchantReference": merchant_reference
                },
                # "CardTransaction": {
                #     "PaymentType": "Purchase"
                # }
            },
            "CallbackUrls": {
                "Notification": notification_url,
                "Success": success_url,
                "Error": error_url
            }
        }
        if code.lower() == "trustly".lower():
            payload["PaymentInformation"]["Country"] = kwargs.get("country", "US")
            payload["PaymentInformation"]["Debtor"] = {
                "FirstName": kwargs.get("first_name", ""),
                "LastName": kwargs.get("last_name", ""),
                "Identification": {
                    "Id": kwargs.get("email", ""),
                },
                "Email": kwargs.get("email", ""),
            }
        if code.lower() == "InstantBankTransferFI".lower():
            payload["PaymentInformation"]["Debtor"] = {
                "Email": kwargs.get("email", ""),
            }

        headers = self._prepare_headers()
        return self._send_request(endpoint, payload, headers, json.dumps)
    
    def refund_payment(
        self,
        amount: float,
        currency: str,
        reference: str,
        payment_request_id: int,
        notification_url: str = None,
    ) -> dict:
        """
        Refund a previously processed payment
        
        :param amount: Amount to refund (must not exceed original payment amount)
        :param currency: Currency of the refund (same as original payment)
        :param reference: Reference for the refund transaction
        :param payment_request_id: Payment request ID from the original transaction
        :param notification_url: Optional notification URL for refund status
        :return: Dictionary with refund result
        
        Example response:
        {
            "ResultCode": 0
        }
        """
        if currency not in SUPPORTED_CURRENCIES:
            raise AttributeError(
                "Currency not supported. Please use any from this list: {}".format(
                    SUPPORTED_CURRENCIES
                )
            )

        endpoint = "/mapi5/Wire/PayPopup"
        payment_type = 8  # Payment type for refunds
        
        # Create signature for refund (includes PaymentRequestId)
        # Format: AccountId/Amount/Currency/Reference/PaymentType/PaymentRequestId
        signature_data = f"{self.aid}/{amount:.2f}/{currency}/{reference}/{payment_type}/{payment_request_id}"
        message = signature_data.encode("utf-8")
        signature = self.sign(message)
        
        # Prepare refund data
        data = {
            "AccountId": self.aid,
            "Amount": f"{amount:.2f}",
            "Currency": currency,
            "Reference": reference,
            "PaymentType": payment_type,
            "PaymentRequestId": payment_request_id,
            "Signature": signature,
        }
        
        if notification_url:
            data["NotificationUrl"] = notification_url
            
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        if self.debug:
            logger.info(f"Trustpay refund request: {data}")
            
        # Use requests directly since this is a background call, not a redirect
        r = requests.post(
            self._generate_url(endpoint), headers=headers, data=data
        )
        
        if self.debug:
            logger.info(f"Trustpay refund response: {r.text}")
            
        if r.status_code != HTTPStatus.OK:
            raise PaymentException(
                "Trustpay refund error: {}. Error code: {}".format(r.text, r.status_code)
            )

        return json.loads(r.text)
