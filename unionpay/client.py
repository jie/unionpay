# !/usr/bin/env python
# encoding: utf-8
# @author: ZhouYang

import zlib
import base64
import datetime
import requests
from . import error
import logging
from .signer import Signer
try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode
from .util.helper import make_submit_form

logger = logging.getLogger(__name__)


class TradeType(object):
    pay = '01'
    query = '00'
    revoke = '31'
    refund = '04'
    auth = '02'
    auth_revoke = '32'
    auth_complete = '03'
    auth_complete_revoke = '33'
    file_transfer = '76'
    # 00：查询交易
    # 01：消费
    # 02：预授权
    # 03：预授权完成
    # 04：退货
    # 05：圈存
    # 11：代收
    # 12：代付
    # 13：账单支付
    # 14：转账（保留）
    # 21：批量交易
    # 22：批量查询
    # 31：消费撤销
    # 32：预授权撤销
    # 33：预授权完成撤销
    # 71：余额查询
    # 72：实名认证-建立绑定关系
    # 73：账单查询
    # 74：解除绑定关系
    # 75：查询绑定关系
    # 77：发送短信验证码交易
    # 78：开通查询交易
    # 79：开通交易
    # 94：IC卡脚本通知


BizType = {
    '000101': '基金业务之股票基金',
    '000102': '基金业务之货币基金',
    '000201': 'B2C网关支付',
    '000301': '认证支付2.0',
    '000302': '评级支付',
    '000401': '代付',
    '000501': '代收',
    '000601': '账单支付',
    '000801': '跨行收单',
    '000901': '绑定支付',
    '000902': 'Token支付',
    '001001': '订购',
    '000202': 'B2B',
}


class ChannelType(object):

    Desktop = '07'
    Mobile = '08'


class AccType(object):
    card = '01'
    passbook = '02'
    iccard = '03'


class payCardType(object):

    unknown = '00'
    debit_card = '01'
    credit_card = '02'
    quasi_credit_acct = '03'
    all_in_one_card = '04'
    prepaid_acct = '05'
    semi_prepaid_acct = '06'


class UnionpayClient(object):

    version = "5.0.0"
    encoding = 'UTF-8'
    signMethod = "01"

    def __init__(self, config, timeout=30, verify=False, **kwargs):
        '''
        @config:    the unionpay config object
        @timeout:   request timeout seconds
        @verify:    should verify ssl certification pem
        '''
        self.config = config
        self.timeout = timeout
        self.verify = verify
        self.signer = Signer.getSigner(config)

    @staticmethod
    def get_txn_time():
        return datetime.datetime.now().strftime('%Y%m%d%H%M%S')

    @staticmethod
    def get_timeout(self, trade_time=None, expire_minutes=10):
        '''
        @trade_time:        trade time
        @expire_minutes:    order expire minutes
        '''
        cur_trade_time = trade_time or datetime.datetime.now()
        cur_trade_time += datetime.timedelta(minutes=expire_minutes)
        return cur_trade_time.strftime('%Y%m%d%H%M%S')

    def post(self, addr, data, **kwargs):
        data.update(signature=urlencode({'signature': data['signature']})[10:])
        request_data = Signer.simple_urlencode(data)
        print(request_data)
        response = requests.post(
            addr,
            data=request_data,
            timeout=self.timeout,
            verify=self.verify,
            headers={'content-type': 'application/x-www-form-urlencoded'}
        )
        if response.status_code != requests.codes.ok:
            msg = "[UPACP]request error: %s, reason: %s" \
                % (response.status_code, response.reason)
            raise error.UnionpayError(msg)
        return response.content

    def async_post(self, addr, data, **kwargs):
        pass

    def send_packet(self, addr, data, **kwargs):
        raw_content = self.post(addr, data)
        data = self.signer.parse_arguments(raw_content.decode('utf-8'))
        if data['respCode'] != '00':
            logger.error(raw_content)
            msg = '[UPACP]respCode: %s orderid: %s' % (
                data['respCode'], data.get('orderId'))
            raise error.UnionpayError(msg)
        self.signer.validate(data)
        return data

    def pay(self, txnamt, orderid, currency_code='156', biz_type="000201", front_url=None, **kwargs):
        '''
        @txnamt:            trade money amount
        @orderid:           trade order id
        @currency_code:     currency code: 156-RMB
        @biz_type:          idk
        @channel_type:      trade channel: 07-DESKTOP, 08-MOBILE
        @front_url:         browser jump url
        @order_time:        order submit time
        '''
        order_time = kwargs.get('order_time')
        expire_minutes = kwargs.get('expire_minutes')
        data = {
            'version': self.version,
            'encoding': self.encoding,
            'signMethod': self.signMethod,
            'txnType': TradeType.pay,
            'txnSubType': '01',
            'bizType': biz_type,
            'channelType': ChannelType.Mobile,
            'backUrl': self.config.backend_url,
            'accessType': '0',
            'merId': self.config.merchant_id,
            'orderId': orderid,
            'txnTime': kwargs.get('order_time', self.get_txn_time()),
            'txnAmt': txnamt,
            'currencyCode': currency_code,
            'payTimeout': self.get_timeout(order_time, expire_minutes),
            'customerIp': kwargs.get('customer_ip'),
            'orderDesc': kwargs.get('order_desc')
        }
        logger.debug('[REQ-PAY]%s' % data)

        data = self.signer.filter_params(data)
        sign_result = self.signer.sign(data)
        if not sign_result:
            raise error.UnionpayError('Sign data error')
        return self.send_packet(self.config.app_trans_url, data)

    def query(self, orderid, order_time, query_id=None, **kwargs):
        data = {
            'version': self.version,
            'encoding': self.encoding,
            'signMethod': self.signMethod,
            'txnType': TradeType.query,
            'txnSubType': "00",
            'bizType': "000000",
            'accessType': "0",
            'merId': self.config.merchant_id,
            'txnTime': order_time,
            'orderId': orderid
        }
        logger.debug('[REQ-QUERY]%s' % data)
        if query_id:
            data['queryId'] = query_id
        sign_result = self.signer.sign(data)

        if not sign_result:
            raise error.UnionpayError('Sign data error')
        resp = self.send_packet(self.config.back_trans_url, data)
        if resp['origRespCode'] != '00':
            raise error.UnionpayError('origRespCode error')
        return resp

    def refund(self, refund_orderid, orig_orderid, order_time, amount, **kwargs):
        data = {
            'version': self.version,
            'encoding': self.encoding,
            'signMethod': self.signMethod,
            'txnType': TradeType.refund,
            'txnSubType': '00',
            'bizType': "000201",
            'channelType': kwargs.get('channel_type', '07'),
            'backUrl': self.config.backend_url,
            'accessType': "0",
            'merId': self.config.merchant_id,
            'orderId': refund_orderid,
            'origQryId': orig_orderid,
            'txnTime': order_time,
            'txnAmt': amount
        }
        logger.debug('[REQ-REFUND]%s' % data)
        sign_result = self.signer.sign(data)

        if not sign_result:
            raise error.UnionpayError('Sign data error')
        return self.send_packet(self.config.back_trans_url, data)

    def revoke(self, revoke_orderid, orderid, amount, **kwargs):
        data = {
            'version': self.version,
            'encoding': self.encoding,
            'signMethod': self.signMethod,
            'txnType': TradeType.revoke,
            'txnSubType': '00',
            'bizType': "000201",
            'channelType': kwargs.get('channel_type', '07'),
            'backUrl': self.config.backend_url,
            'accessType': "0",
            'merId': self.config.merchant_id,
            'orderId': revoke_orderid,
            'origQryId': orderid,
            'txnTime': self.get_txn_time(),
            'txnAmt': amount
        }
        logger.debug('[REQ-REVOKE]%s' % data)
        sign_result = self.signer.sign(data)

        if not sign_result:
            raise error.UnionpayError('Sign data error')
        return self.send_packet(self.config.back_trans_url, data)

    def auth(self, txnamt, orderid, **kwargs):
        '''
        @txnamt:            trade money amount
        @orderid:           trade order id
        @currency_code:     currency code: 156-RMB
        @biz_type:          idk
        @channel_type:      trade channel: 07-DESKTOP, 08-MOBILE
        @front_url:         browser jump url
        '''
        data = {
            'version': self.version,
            'encoding': self.encoding,
            'signMethod': self.signMethod,
            'txnType': TradeType.auth,
            'txnSubType': '01',
            'bizType': '000201',
            'channelType': ChannelType.Mobile,
            'backUrl': self.config.backend_url,
            'accessType': '0',
            'merId': self.config.merchant_id,
            'orderId': orderid,
            'txnTime': self.get_txn_time(),
            'txnAmt': txnamt,
            'currencyCode': '156',
            'customerIp': kwargs.get('customer_ip'),
            'orderDesc': kwargs.get('order_desc')
        }

        logger.debug('[REQ-AUTH]%s' % data)

        data = self.signer.filter_params(data)
        sign_result = self.signer.sign(data)
        if not sign_result:
            raise error.UnionpayError('Sign data error')
        return self.send_packet(self.config.app_trans_url, data)

    def auth_revoke(self, amount, revoke_orderid, orderid, **kwargs):
        data = {
            'version': self.version,
            'encoding': self.encoding,
            'signMethod': self.signMethod,
            'txnType': TradeType.auth_revoke,
            'txnSubType': '00',
            'bizType': "000201",
            'channelType': kwargs.get('channel_type', '07'),
            'backUrl': self.config.backend_url,
            'accessType': "0",
            'merId': self.config.merchant_id,
            'orderId': revoke_orderid,
            'origQryId': orderid,
            'txnTime': self.get_txn_time(),
            'txnAmt': amount
        }
        logger.debug('[REQ-AUTH-REVOKE]%s' % data)
        sign_result = self.signer.sign(data)

        if not sign_result:
            raise error.UnionpayError('Sign data error')
        return self.send_packet(self.config.back_trans_url, data)

    def auth_complete(self, amount, orderid, orig_orderid, **kwargs):
        data = {
            'version': self.version,
            'encoding': self.encoding,
            'signMethod': self.signMethod,
            'txnType': TradeType.auth_complete,
            'txnSubType': '00',
            'bizType': '000201',
            'channelType': ChannelType.Mobile,
            'backUrl': self.config.backend_url,
            'accessType': '0',
            'merId': self.config.merchant_id,
            'orderId': orderid,
            'txnTime': self.get_txn_time(),
            'txnAmt': amount,
            'currencyCode': '156',
            'customerIp': kwargs.get('customer_ip'),
            'orderDesc': kwargs.get('order_desc'),
            'origQryId': orig_orderid
        }

        logger.debug('[REQ-AUTH-COMPLETE]%s' % data)
        data = self.signer.filter_params(data)
        sign_result = self.signer.sign(data)
        if not sign_result:
            raise error.UnionpayError('Sign data error')
        return self.send_packet(self.config.app_trans_url, data)

    def auth_complete_revoke(self, amount, orderid, orig_orderid, **kwargs):
        data = {
            'version': self.version,
            'encoding': self.encoding,
            'signMethod': self.signMethod,
            'txnType': TradeType.auth_complete_revoke,
            'txnSubType': '00',
            'bizType': '000201',
            'channelType': ChannelType.Mobile,
            'backUrl': self.config.backend_url,
            'accessType': '0',
            'merId': self.config.merchant_id,
            'orderId': orderid,
            'txnTime': self.get_txn_time(),
            'txnAmt': amount,
            'currencyCode': '156',
            'customerIp': kwargs.get('customer_ip'),
            'orderDesc': kwargs.get('order_desc'),
            'origQryId': orig_orderid
        }

        logger.debug('[REQ-AUTH-COMPLETE-REVOKE]%s' % data)
        data = self.signer.filter_params(data)
        sign_result = self.signer.sign(data)
        if not sign_result:
            raise error.UnionpayError('Sign data error')
        return self.send_packet(self.config.app_trans_url, data)

    def file_transfer(self, file_type, settle_date, filepath='.', merchant_id=None, prefix=None, **kwargs):
        # merchant_id = '700000000000001' for test
        merchant_id = merchant_id or self.config.merchant_id
        data = {
            'version': self.version,
            'encoding': self.encoding,
            'signMethod': self.signMethod,
            'txnType': TradeType.file_transfer,
            'txnSubType': '01',
            'bizType': '000000',
            'channelType': ChannelType.Mobile,
            'backUrl': self.config.backend_url,
            'accessType': '0',
            'merId': merchant_id,
            'txnTime': self.get_txn_time(),
            'settleDate': settle_date,
            'fileType': file_type
        }

        logger.debug('[REQ-FILE-TRANSFER]%s' % data)
        data = self.signer.filter_params(data)
        sign_result = self.signer.sign(data)
        if not sign_result:
            raise error.UnionpayError('Sign data error')
        resp = self.send_packet(self.config.file_trans_url, data)
        file_content = base64.b64decode(resp['fileContent'])
        files = self.signer.save_file_data(
            settle_date, zlib.decompress(file_content), filepath, merchant_id=merchant_id)
        linedata = self.signer.reader_file_data(files, settle_date)
        return linedata


class UnionpayWapClient(UnionpayClient):

    def pay(self, txnamt, orderid, currency_code='156', biz_type="000201", front_url=None, **kwargs):
        order_time = kwargs.get('order_time')
        expire_minutes = kwargs.get('expire_minutes')
        data = {
            'version': self.version,
            'encoding': self.encoding,
            'signMethod': self.signMethod,
            'txnType': TradeType.pay,
            'txnSubType': '01',
            'bizType': biz_type,
            'channelType': ChannelType.Desktop,
            'backUrl': self.config.backend_url,
            'accessType': '0',
            'merId': self.config.merchant_id,
            'orderId': orderid,
            'txnTime': self.get_txn_time(),
            'txnAmt': txnamt,
            'currencyCode': currency_code,
            'payTimeout': self.get_timeout(order_time, expire_minutes),
            'customerIp': kwargs.get('customer_ip'),
            'orderDesc': kwargs.get('order_desc')
        }
        logger.debug('[REQ-PAY]%s' % data)

        if not front_url:
            raise error.UnionpayError('must set front_url when desktop')

        data.update(frontUrl=front_url)
        data = self.signer.filter_params(data)
        sign_result = self.signer.sign(data)
        if not sign_result:
            raise error.UnionpayError('Sign data error')
        data['signature'] = data['signature'].decode('utf-8')
        return make_submit_form(data, self.config.front_trans_url)

    def auth(self, txnamt, orderid, front_url=None, **kwargs):
        data = {
            'version': self.version,
            'encoding': self.encoding,
            'signMethod': self.signMethod,
            'txnType': TradeType.auth,
            'txnSubType': '01',
            'bizType': '000201',
            'channelType': ChannelType.Mobile,
            'backUrl': self.config.backend_url,
            'accessType': '0',
            'merId': self.config.merchant_id,
            'orderId': orderid,
            'txnTime': self.get_txn_time(),
            'txnAmt': txnamt,
            'currencyCode': '156',
            'customerIp': kwargs.get('customer_ip'),
            'orderDesc': kwargs.get('order_desc')
        }

        if not front_url:
            raise error.UnionpayError('must set front_url when desktop')

        data.update(frontUrl=front_url)
        data = self.signer.filter_params(data)
        sign_result = self.signer.sign(data)
        if not sign_result:
            raise error.UnionpayError('Sign data error')
        data['signature'] = data['signature'].decode('utf-8')
        return make_submit_form(data, self.config.front_trans_url)


def main():
    import sys
    from util.helper import load_config, make_order_id
    config = load_config(sys.argv[1])
    # pay
    # orderid = make_order_id('TESTPAY')
    # response = UnionpayWapClient(config).pay(
    #     25, orderid, front_url='http://zhouyang.me/front')

    # query
    # response = UnionpayClient(config).query(
    #     'TESTAUTH20151112160025',
    #     '20151112160025'
    # )

    # revoke
    # orderid = make_order_id('TESTREVOKE')
    # response = UnionpayClient(config).revoke(
    #     orderid,
    #     '201511121421433768498',
    #     20
    # )

    # refund
    # orderid = make_order_id('TESTREFUND')
    # response = UnionpayClient(config).refund(
    #     orderid,
    #     '201511121426015315048',
    #     '20151112142601',
    #     5
    # )

    # auth
    # orderid = make_order_id('TESTAUTH')
    # response = UnionpayWapClient(config).auth(
    #     1000,
    #     orderid,
    #     front_url='http://zhouyang.me/front'
    # )

    # auth_revoke
    # orderid = make_order_id('TESTAUTHREVOKE')
    # response = UnionpayClient(config).auth_revoke(
    #     orderid,
    #     '201511121509455397448',
    #     1000
    # )

    # auth_complete
    # orderid = make_order_id('TESTAUTHCOMPLETE')
    # print(orderid)
    # response = UnionpayClient(config).auth_complete(
    #     1000,
    #     orderid,
    #     '201511121600253932498'
    # )

    # auth_complete_revoke
    # orderid = make_order_id('TESTAUTHCCRE')
    # response = UnionpayClient(config).auth_complete_revoke(
    #     1000,
    #     orderid,
    #     '201511121602513936818'
    # )

    # file transfer
    response = UnionpayClient(config).file_transfer(
        file_type='00',
        settle_date='0119',
        merchant_id='700000000000001'
    )

    print('RES:%s' % response)

if __name__ == '__main__':
    main()
