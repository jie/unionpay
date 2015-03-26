# !/usr/bin/env python
# encoding: utf-8
# @author: ZhouYang

import json
import logging
import tornado.auth
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
from tornado.options import define, options
from signer import Signer
from util.helper import load_config


define("port", default=8080, help="run on the given port", type=int)
define("notify_url", default="/notify", help="notify url", type=str)
define("config", default="settings.yaml", help="config path", type=str)


class NotifyHandler(tornado.web.RequestHandler):

    @property
    def signer(self):
        return self.application.settings['signer']

    def get_all_arguments(self):
        names = self.request.arguments.keys()
        arguments = {}
        for name in names:
            arguments[name] = self.get_argument(name)
        return arguments

    def handle_notify(self, data):
        logging.info(data)
        return json.dumps({'status': 'ok', 'code': 0})

    def post(self):
        data = self.get_all_arguments()
        self.signer.validate(data)
        response = self.handle_notify(data)
        self.write(response)

    def get(self):
        self.finish()


class Application(tornado.web.Application):

    def __init__(self, config, notify_url='/notify'):
        notify_url = notify_url or config.notify_url
        handlers = [
            (r"%s$" % notify_url, NotifyHandler),
        ]
        settings = dict(
            debug=True,
            config=config,
            signer=self.get_signer(config)
        )
        tornado.web.Application.__init__(self, handlers, **settings)

    def get_signer(self, config):
        return Signer.getSigner(config)


def main():
    tornado.options.parse_command_line()
    config = load_config(options.config)
    application = Application(
        config,
        notify_url=options.notify_url
    )
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == '__main__':
    main()
