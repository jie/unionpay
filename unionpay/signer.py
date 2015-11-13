# !/usr/bin/env python
# encoding: utf-8
# @author: ZhouYang

'''
Unionpay using http://www.cfca.com.cn/ PKCS12 format PEM
and an X509 format cert for validate signature
'''


import logging
import base64
import os.path
try:
    from urlparse import parse_qs
except ImportError:
    from urllib.parse import parse_qs

from hashlib import sha1
from OpenSSL import crypto
from OpenSSL.crypto import FILETYPE_PEM
from datetime import datetime
from zipfile import ZipFile
from util.helper import LineObject


logger = logging.getLogger(__name__)


class TradeFlowType:
    # 全渠道商户一般交易明细流水文件
    Normal = 'ZM_'
    # 全渠道商户差错交易明细流水文件
    Error = 'ZME_'
    # 全渠道商户周期交易明细流水文件
    Periodic = 'PED_'
    # 全渠道周期商户差错交易明细流水文件
    PeriodicError = 'PEDERR_'


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
        f = open(filepath, 'rb').read()
        return crypto.load_pkcs12(f, password)

    @staticmethod
    def loadX509(filepath, filetype=FILETYPE_PEM):
        '''
        @filepath: the cert file path
        @password: the cert type
        '''
        f = open(filepath, 'rb').read()
        return crypto.load_certificate(filetype, f)

    @staticmethod
    def simple_urlencode(params, sort=True):
        '''
        @params: a map type will convert to url args
        @sort: if sorted method will used to sort params
        '''
        data = Signer.filter_params(params)
        items = sorted(
            data.items(), key=lambda d: d[0]) if sort else data.items()

        results = []
        for item in items:
            results.append("%s=%s" % (item[0], item[1]))
        s = '&'.join(results)
        return s.encode('utf-8')

    @staticmethod
    def parse_arguments(raw):
        '''
        @raw: raw data to parse argument
        '''
        data = {}
        qs_params = parse_qs(str(raw))
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
        for key in params.keys():
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

    @staticmethod
    def accept_filetype(f, merchant_id):
        '''
        @f:             filename
        @merchant_id:   merchant id    
        '''
        res = False
        if (TradeFlowType.Normal in f
                or TradeFlowType.Error in f
                or TradeFlowType.Periodic in f
                or TradeFlowType.PeriodicError in f) and f.endswith(merchant_id):
            res = True
        return res

    @staticmethod
    def save_file_data(settle_date, data, temp_path, merchant_id, temp_prefix='unionpay_'):
        '''
        @settle_date:   like 1216 for generate filename
        @data:          fileContent from request
        @temp_path:     save data to a temp path

        '''
        timeRandomString = datetime.now().strftime("%Y%m%d%H%M%S")
        path = os.path.join(
            temp_path, "%s%s%s" % (temp_prefix, datetime.now().year, settle_date))

        if not os.path.exists(path):
            os.mkdir(path)

        fileWholePath = "%s/SMT_%s.zip" % (path, timeRandomString)
        with open(fileWholePath, 'wb') as f:
            f.write(data)
        logger.debug("temp file <%s> created！" % fileWholePath)
        zfile = ZipFile(fileWholePath, 'r')
        zfile.extractall(path)
        files_list = zfile.infolist()
        logger.debug("file <%s> unziped！" % ','.join(zfile.namelist()))
        zfile.close()
        logger.debug("balance file <%s> saved!" % path)
        os.unlink(fileWholePath)
        logger.debug("temp file deleted")

        balance_files = []

        for item in files_list:
            if Signer.accept_filetype(item.filename, merchant_id):
                balance_files.append(os.path.join(path, item.filename))
        return balance_files

    @staticmethod
    def reader_file_data(files_list, settle_date):
        insert_params = []
        for item in files_list:
            Signer.parse_line(settle_date, item, insert_params)

        return insert_params

    @staticmethod
    def parse_line(settle_date, item, params_list):
        with open(item, 'rb') as f:
            for field in f.readlines():
                line = LineObject(field)
                params = {
                    'settle_date': settle_date,
                    'txnType': line.txnType,
                    'orderId': line.orderId,
                    'queryId': line.queryId,
                    'txnAmt': line.txnAmt,
                    'merId': line.merId,
                    'data': field
                }
                params_list.append(params)
