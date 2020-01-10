import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta
from http import HTTPStatus
from time import mktime
from urllib.parse import urlencode

import requests

from . import PaymentException

# DEFAULT_BASE_API_URL = 'https://api.trustpay.eu/api/oauth2/token'
DEFAULT_BASE_API_URL = 'https://api.trustpay.eu'


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

    access_token_expiration_time: datetime

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
                      transform_data_func: callable):
        post_params = transform_data_func(data)

        r = requests.post(self._generate_url(endpoint), headers=headers, data=post_params)
        print(r)
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
        print(result)
        # save token ttl
        # self.access_token_expiration_time = datetime.now() + timedelta(seconds=result["expires-in"])
        return result["access_token"]

    def account_details(self):
        endpoint = '/ApiBanking/GetAccountDetails'
        data = {'AccountId': self.username}
        headers = self._prepare_headers()
        result = self._send_request(endpoint, data, headers, json.dumps)
        return result

    # def get_balance(self) -> dict:
    #     '''
    #     Response example: {
    #         'available_balance': '4063.27',
    #         'reservations': 0,
    #         'real_balance': 4063.27}
    #     '''
    #     endpoint = '/v1/transaction/getBalance'
    #
    #     data = {
    #         "username": self.username}
    #
    #     result = self._send_request(endpoint, data)
    #
    #     return result

    def send_money(self, amount: float, currency: str, recipient: str, account: str,
                   details: str) -> dict:
        '''
        Transfer money from merchant account to recipient account

        :param amount: Amount of money
        :param currency: Currency (only EUR is available)
        :param recipient: Name of the recipient
        :param account: IBAN account number of recipient
        :param details: Details (description) of the transfer
        :return: Mistertango API response

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
        endpoint = '/v1/transaction/sendMoney'
        if currency not in SUPPORTED_CURRENCIES:
            # TODO: raise relevant error instead default
            raise AttributeError(
                'Currency not supported. Please use any from this list: {}'.format(
                    SUPPORTED_CURRENCIES))

        data = {
            "username": self.username,
            "amount": amount,
            "currency": currency,
            "recipient": recipient,
            "account": account,
            "details": details}

        headers = self._prepare_headers()

        # TODO: error handling
        result = self._send_request(endpoint, data, headers)

        return result
