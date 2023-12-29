from abc import ABC, abstractmethod
from requests import request, exceptions
from urllib.parse import urljoin


class VaultConnection:

    def __init__(self, vault_host, vault_token):
        self.vault_host = vault_host
        self.__vault_token = vault_token
        self.token_renew()

    def get_storage(self, name, version):
        if version == 1:
            return VaultStorageV1(name, self)
        elif version == 2:
            return VaultStorageV2(name, self)
        else:
            raise VaultStorageVersionError

    def query(self, method, path):
        headers = {'X-Vault-Token': self.__vault_token}
        url = urljoin(f'https://{self.vault_host}/v1/', path)
        try:
            vault_response = request(method, url, headers=headers)
            vault_response.raise_for_status()
            response_json = vault_response.json()
        except exceptions.RequestException as e:
            raise VaultException('Vault connection error', repr(e))
        if 'errors' in response_json:
            raise VaultException(response_json)
        return response_json

    def token_renew(self):
        response_json = self.query('POST', 'auth/token/renew-self')
        if response_json['auth']['client_token'] != self.__vault_token:
            raise VaultTokenError
        return


class AbstractVaultStorage(ABC):

    def __init__(self, name, vault_connection: VaultConnection):
        self.name = name
        if isinstance(vault_connection, VaultConnection):
            self.vault_connection = vault_connection
        else:
            raise VaultStorageError

    @abstractmethod
    def list_keys(self, keys_path):
        pass

    @abstractmethod
    def get_keys(self, keys_path):
        pass

    def get_key(self, keys_path, key_name):
        try:
            return self.get_keys(keys_path).get(key_name)
        except KeyError:
            return None


class VaultStorageV1(AbstractVaultStorage):

    def list_keys(self, keys_path):
        path = f'{self.name}/{keys_path}'
        response_json = self.vault_connection.query('LIST', path)
        try:
            return response_json['data']['keys']
        except KeyError:
            return None

    def get_keys(self, keys_path):
        path = f'{self.name}/{keys_path}'
        response_json = self.vault_connection.query('GET', path)
        try:
            return response_json['data']
        except KeyError:
            return None


class VaultStorageV2(AbstractVaultStorage):

    def list_keys(self, keys_path):
        path = f'{self.name}/metadata/{keys_path}'
        response_json = self.vault_connection.query('LIST', path)
        try:
            return response_json['data']['keys']
        except KeyError:
            return None

    def get_keys(self, keys_path):
        path = f'{self.name}/data/{keys_path}'
        response_json = self.vault_connection.query('GET', path)
        try:
            return response_json['data']['data']
        except KeyError:
            return None


class VaultException(Exception):
    message = 'Unknown Vault Exception'

    def __init__(self, *args, **kwargs):
        if not (args or kwargs):
            args = (self.message,)
        super().__init__(*args, **kwargs)


class VaultStorageVersionError(VaultException):
    message = 'Wrong Vault Storage version'


class VaultTokenError(VaultException):
    message = 'Unknown Vault token received on renew'


class VaultStorageError(TypeError, VaultException):
    message = 'Wrong Vault Storage class'
