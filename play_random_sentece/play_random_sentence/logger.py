import os
import traceback


class EvLogger(object):
    def __init__(self):
        try:
            os.unlink('/tmp/erez.log')
        except Exception:
            pass

    def _write(self, fmt, *args):
        with open('/tmp/erez.log', 'a+') as f:
            f.write(fmt % args)
            f.write('\n')

    def exception(self, ex):
        self._write('%s' % traceback.format_exc())

    debug = _write
    info = _write


logger = EvLogger()
