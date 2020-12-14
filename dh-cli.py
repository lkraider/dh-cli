import cmd
import json
import uuid
import shutil
import argparse
import dataclasses
import urllib.parse
import urllib.request

from dataclasses import dataclass, field

OPTS = {}


@dataclass(frozen=True)
class DHAPI:
    key: str
    cmd: str
    format: str = 'json'
    account: str = None
    unique_id: uuid.UUID = field(default_factory=uuid.uuid4)

    url: str = 'https://api.dreamhost.com/'

    def args_dict(self):
        args = dataclasses.asdict(self)
        args.pop('url')
        return {k: v for k, v in args.items() if v is not None}


class DHCmd(cmd.Cmd):

    def emptyline(self):
        pass

    def do_login(self, arg):
        pass

    def do_exit(self, arg):
        return True


class DHMain(DHCmd):

    prompt = 'dh % '

    def do_dns(self, arg):
        return DNS().cmdloop()


class DNS(DHCmd):

    prompt = 'dh.dns % '
    _cache = {}
    _zones = []

    def do_ls(self, arg):
        self.refresh_records()
        _print_columns(self._zones)

    def refresh_records(self):
        if self._cache:
            return
        cmd = 'dns-list_records'
        self._cache = _make_request(cmd)
        self._parse_cache()

    def _parse_cache(self):
        self._zones = sorted(set(k['zone'] for k in self._cache['data']))


def _print_columns(values, col_align=8):
    max_width = shutil.get_terminal_size((80, 20)).columns
    value_width = max(len(i) for i in values)
    col_width = value_width + (col_align - value_width % col_align)
    col_layout = '{:<%s}' % col_width
    max_cols = max_width // col_width
    for i, v in enumerate(values):
        end = '' if (i + 1) % max_cols else '\n'
        print(col_layout.format(v), end=end)
    if not end:
        print('\n', end='')


def _make_request(cmd: str, opts: dict=None, **kwargs):
    opts = opts or OPTS
    api = DHAPI(cmd=cmd, **opts)
    kwargs.update(api.args_dict())
    url = _build_url(api.url, kwargs)
    req = urllib.request.Request(url)
    print(req.full_url)
    res = urllib.request.urlopen(req)
    data = json.load(res)
    return data


def _build_url(url: str, args: dict) -> str:
    url_parts = list(urllib.parse.urlparse(url))
    url_parts[4] = urllib.parse.urlencode(args)
    return urllib.parse.urlunparse(url_parts)


def _send_request(req) -> str:
    res = urllib.request.urlopen(req)
    body = res.read().decode('UTF-8')
    return body


def _make_args():
    parser = argparse.ArgumentParser(description='DreamHost API CLI')
    parser.add_argument('--api-key', dest='key', default='6SHU5P2HLDAYECUM')
    return parser.parse_args()


if __name__ == '__main__':
    args = _make_args()
    OPTS = vars(args)
    DHMain().cmdloop()
