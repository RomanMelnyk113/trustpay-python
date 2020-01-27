import base64
import hashlib
import hmac
import json
import uuid
from datetime import date, datetime
from http import HTTPStatus
from time import mktime
from typing import Optional
from urllib.parse import urlencode
from sepaxml import SepaTransfer
from . import order_xml_string

import requests

from . import PaymentException

# DEFAULT_BASE_API_URL = 'https://api.trustpay.eu/api/oauth2/token'
DEFAULT_BASE_API_URL = 'https://api.trustpay.eu'
SUPPORTED_CURRENCIES = ['EUR']


# https://doc.trustpay.eu/?curl&ShowAPIBanking=true
class Trustpay:
    # account ID
    aid: str

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

    def __init__(self, password, username, secret_key=None, aid=None, api_url=None):
        self.secret_key = secret_key
        self.aid = aid
        self.password = password
        self.username = username

        self.api_url = api_url or DEFAULT_BASE_API_URL

        self.access_token = self.get_access_token()

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
            return {
                'Authorization': authorization,
                'Content-Type': 'text/json'
            }

        base_auth = base64.b64encode(f"{self.username}:{self.password}".encode("utf-8"))
        authorization = f"Basic {base_auth.decode()}"

        return {
            'Authorization': authorization,
            'Content-Type': 'application/x-www-form-urlencoded'
        }

    def _generate_url(self, endpoint):
        return self.api_url + endpoint

    def _send_request(self, endpoint: str, data: dict, headers: dict,
                      transform_data_func: Optional[callable]):
        if transform_data_func is not None:
            post_params = transform_data_func(data)
        else:
            post_params = data
        print("post_params")
        print(post_params)

        r = requests.post(self._generate_url(endpoint), headers=headers, data=post_params)
        print(r.text)
        if r.status_code != HTTPStatus.OK:
            raise PaymentException('Trustpay error: {}'.format(r.text))

        return json.loads(r.text)

    def get_access_token(self) -> str:
        '''
        API Response example: {
            "access_token":"L3_DbiQdateYLPYmp31AHEeErRzF84SVRcyr5Zw4jgw3CqDZjn4dbmVilTQx6dh_8ZbPztJGQh-9",
            "token-type":"bearer",
        }

        :return access_token:str
        '''
        if self.access_token:
            return self.access_token

        endpoint = '/api/oauth2/token'

        data = {"grant_type": "client_credentials"}

        headers = self._prepare_headers(with_access_token=False)

        result = self._send_request(endpoint, data, headers, urlencode)
        return result["access_token"]

    def account_details(self) -> dict:
        '''

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
        '''
        endpoint = '/ApiBanking/GetAccountDetails'
        data = {'AccountId': self.aid}
        headers = self._prepare_headers()
        result = self._send_request(endpoint, data, headers, json.dumps)
        return result['AccountDetails']

    def send_money(
            self,
            amount: int,
            currency: str,
            recipient: str,
            account: str,
            bank_bik: str,
            details: str
    ) -> dict:
        '''
        Transfer money from merchant account to recipient account
        https://doc.trustpay.eu/?php#ab-create-order

        :param amount: Amount of money in cents
        :param currency: Currency (only EUR is available)
        :param recipient: Name of the recipient
        :param account: IBAN account number of recipient
        :param details: Details (description) of the transfer
        :return: Trustpay API response

        Example: {
            "status": true,
            "api": {
              "version": "string",
              "title": "string"
            },
            "message": "string",
            "data": "string",
            "duration": 0}
        '''
        if currency not in SUPPORTED_CURRENCIES:
            # TODO: raise relevant error instead default
            raise AttributeError(
                'Currency not supported. Please use any from this list: {}'.format(
                    SUPPORTED_CURRENCIES))

        endpoint = '/ApiBanking/CreateOrder'

        # account_details = self.account_details()
        account_details = {
            "AccountId": "121212121",
            "AccountName": "UCHA KIPIANI",
            "IBAN": "LT083510001468166897",
            "CurrencyCode": "EUR",
        }
        code = str(uuid.uuid4()).replace("-", "")[:12]
        config = {
            "MessageId": f"{account_details['AccountId']}-{code}",
            "CreationDateTime": datetime.today().isoformat().split('.')[0],
            "RequestedExecutionDate": date.today().isoformat(),
            "DebtorName": account_details['AccountName'],
            "DebtorAccount": account_details['AccountId'],
            "Currency": currency,
            "Amount": amount,
            "CreditorBankBic": bank_bik,
            "CreditorName": recipient,
            "CreditorAccount": account,
            "Description": details,
        }
        order_data = order_xml_string.format(**config).replace(" ", "").replace("\n", " ")
        print(order_data)

        # config = {
        #     "name": account_details['AccountName'],
        #     "IBAN": account_details['IBAN'],
        #     "BIC": "TPAYSKBX",  # TODO: get BIK code ?????
        #     "batch": False,
        #     "currency": account_details['CurrencyCode'],  # ISO 4217
        # }
        # sepa = SepaTransfer(config, clean=True)
        #
        # payment = {
        #     "name": recipient,
        #     "IBAN": account,
        #     "BIC": bank_bik,
        #     "amount": amount,  # in cents
        #     "execution_date": date.today(),
        #     "description": details,
        #     # "endtoend_id": str(uuid.uuid1())  # optional
        # }
        # sepa.add_payment(payment)
        #
        # data = sepa.export(validate=True)
        data_to_send = {
            "Xml": order_data
        }
        return data_to_send
        # headers = self._prepare_headers()

        # TODO: error handling
        # result = self._send_request(endpoint, data_to_send, headers, json.dumps)
        # print(result)
        # print(result.text)
        return result
