# !/usr/bin/env python
# encoding: utf-8
# @author: ZhouYang


from datetime import datetime


class ObjectDict(dict):

    '''
    Copy from tornado.util
    '''

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        self[name] = value


def make_submit_form(data, front_trans_url):
    item_template = """<input type="hidden" name="{key}" id="{key}" value="{value}" />"""
    input_fields = ""
    for k, v in data.items():
        if v:
            input_fields += item_template.format(key=k, value=v, name=k)

    submit_form_template = """
        <html><head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8"/></head><body>
        <form id="form" action="{action}" method="{method}">{input_fields}</form></body>
        <script type="text/javascript">
            document.getElementById("form").submit();
        </script>
        </html>"""

    form_kwargs = {
        'action': front_trans_url,
        'method': 'POST',
        'input_fields': input_fields
    }
    return submit_form_template.format(**form_kwargs)


def load_config(filepath):
    import yaml
    try:
        yaml_map = yaml.load(open(filepath, 'r'))
    except Exception as e:
        exit("[Config] yaml format error: {}".format(e))
    return ObjectDict(yaml_map)


def make_order_id(prefix):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return "{prefix}{timestamp}".format(prefix=prefix, timestamp=timestamp)


class LineObject(object):

    """
    using for upacp file
    """

    def __init__(self, line):
        self.line = line
        self._parse_line()

    def _parse_line(self):
        self.txnTime = self._get_txn_time()
        self.txnAmt = self._get_txn_amt()
        self.orderId = self._get_order_id()
        self.merId = self._get_merchant_id()

    def _get_txn_time(self):
        return self.line[36: 46]

    def _get_txn_amt(self):
        return self.line[65: 77]

    def _get_order_id(self):
        return self.line[106: 138]

    def _get_merchant_id(self):
        return self.line[245: 260]
