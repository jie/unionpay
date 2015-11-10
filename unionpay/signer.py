# !/usr/bin/env python
# encoding: utf-8
# @author: ZhouYang

'''
Unionpay using http://www.cfca.com.cn/ PKCS12 format PEM
and an X509 format cert for validate signature
'''


import logging
import base64
try:
    import urlparse
except ImportError:
    from urllib.parse import urlparse
from hashlib import sha1
from OpenSSL import crypto
from OpenSSL.crypto import FILETYPE_PEM


logger = logging.getLogger(__name__)


class Signer(object):

    def __init__(self, pfx_filepath, password, x509_filepath, digest_method='sha1', **kwargs):
        '''
        @pfx_filepath:      pfx file path
        @password:          pfx pem password
        @x509_filepath:     x509 file path
        @digest_method:     default digest method is sha1
        '''
        self.digest_method = digest_method
        self.PKCS12 = self.loadPKCS12(pfx_filepath, password)
        self.X509 = self.loadX509(x509_filepath)

    @classmethod
    def getSigner(cls, config):
        '''
        @config: unionpay config object
        '''
        signer = cls(
            config.pfx_filepath,
            config.password,
            config.x509_filepath,
            config.digest_method
        )
        return signer

    @staticmethod
    def loadPKCS12(filepath, password):
        '''
        @filepath: the pfx file path
        @password: the password of pfx file
        '''
        f = file(filepath, 'rb').read()
        return crypto.load_pkcs12(f, password)

    @staticmethod
    def loadX509(filepath, filetype=FILETYPE_PEM):
        '''
        @filepath: the cert file path
        @password: the cert type
        '''
        f = file(filepath, 'rb').read()
        return crypto.load_certificate(filetype, f)

    @staticmethod
    def simple_urlencode(params, sort=True):
        '''
        @params: a map type will convert to url args
        @sort: if sorted method will used to sort params
        '''
        data = Signer.filter_params(params)
        items = sorted(
            data.iteritems(), key=lambda d: d[0]) if sort else data.items()

        results = []
        for item in items:
            results.append("%s=%s" % (item[0], str(item[1])))
        return '&'.join(results)

    @staticmethod
    def parse_arguments(raw):
        '''
        @raw: raw data to parse argument
        '''
        data = {}
        qs_params = urlparse.parse_qs(raw)
        for name in qs_params.keys():
            data[name] = qs_params.get(name)[-1]
        return data

    @staticmethod
    def filter_params(params):
        '''
        Remove None or empty argments
        '''
        if not params:
            return dict()

        cp_params = params.copy()
        for key in cp_params.keys():
            value = cp_params[key]
            if value is None or len(str(value)) == 0:
                cp_params.pop(key)
        return cp_params

    @staticmethod
    def sign_by_soft(private_key, sign_digest, digest_method='sha1'):
        '''
        @private_key: the private_key get from PKCS12 pem
        @sign_digest: the hash value of urlencoded string
        @digest_method: the unionpay using sha1 digest string
        '''
        return crypto.sign(private_key, sign_digest, digest_method)

    def sign(self, data):
        '''
        @data: a dict ready for sign, should not contain "signature" key name
        Return base64 encoded signature and set signature to data argument
        '''
        cert_id = self.PKCS12.get_certificate().get_serial_number()
        data['certId'] = str(cert_id)
        string_data = self.simple_urlencode(data)
        sign_digest = sha1(string_data).hexdigest()
        private_key = self.PKCS12.get_privatekey()
        soft_sign = self.sign_by_soft(
            private_key, sign_digest, self.digest_method)
        base64sign = base64.b64encode(soft_sign)
        data['signature'] = base64sign
        return base64sign

    def validate(self, data):
        '''
        @data: a dict ready for sign, must contain "signature" key name
        '''
        signature = data.pop('signature')
        signature = signature.replace(' ', '+')
        signature = base64.b64decode(signature)
        if 'fileContent' in data and data['fileContent']:
            file_content = data['fileContent'].replace(' ', '+')
            data.update(fileContent=file_content)
        stringData = self.simple_urlencode(data)
        digest = sha1(stringData).hexdigest()
        crypto.verify(self.X509, signature, digest, self.digest_method)
