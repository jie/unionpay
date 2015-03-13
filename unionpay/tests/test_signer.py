# !/usr/bin/env python
# encoding: utf-8
# @author: ZhouYang

import unittest2 as unittest
from signer import Signer


class SignerTest(unittest.TestCase):

    def setup(self):
        pfx_filepath = '../pem/PM_700000000000001_acp.pfx'
        x509_filepath = '../pem/verify_sign_acp.cer'
        password = '111111'
        self.signer = Signer(
            pfx_filepath,
            password,
            x509_filepath,
        )

    def test_sign(self):
        pass

    def test_validate(self):
        pass
