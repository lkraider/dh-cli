import cmd
import json
import uuid
import shutil
import logging
import argparse
import collections
import dataclasses
import urllib.parse
import urllib.request

from dataclasses import dataclass, field

OPTS = {'key', }

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


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


@dataclass
class DNSRecord:

    account_id: str
    zone: str
    record: str
    type: str
    value: str
    comment: str
    editable: str

    _editable_types = ['A', 'CNAME', 'NS', 'PTR', 'NAPTR', 'SRV', 'TXT', 'AAAA']
    has_changes = False
    error = None

    def print_table(self):
        row_layout = '  {name:<12}:  {value}'
        for f in dataclasses.fields(self):
            print(row_layout.format(name=f.name, value=getattr(self, f.name)))


class DNSTree:

    tree: dict = None
    path: list = None

    def __init__(self, tree=None, path=None):
        self.tree = tree or {}
        self.path = path or []

    def keys(self, path: str=None) -> collections.abc.KeysView:
        return self.view(path).keys()

    def values(self, path: str=None) -> collections.abc.ValuesView:
        return self.view(path).values()

    def items(self, path: str=None) -> collections.abc.ItemsView:
        return self.view(path).items()

    def view(self, path: str=None) -> dict:
        return self._recursive_view(self.tree, self.get_fullpath(path))

    def get_record(self, path: str=None) -> DNSRecord:
        entries = self.view(path).values()
        if len(entries) > 1:
            raise DNSTreeMultipleRecordsFound(self.show_fullpath(path))
        record = list(entries)[0]
        if not isinstance(record, DNSRecord):
            raise DNSTreeNotARecord(self.show_fullpath(path))
        return record

    def get_fullpath(self, path: str=None) -> list:
        root = [] if path and path.startswith('/') else self.path
        subpath = list(filter(None, path.split('/'))) if path else []
        fullpath = root + subpath
        return fullpath

    def show_fullpath(self, path: str=None) -> str:
        return '/' + '/'.join(self.get_fullpath(path))

    @classmethod
    def _recursive_view(cls, data: dict, path: list, parent: str=None) -> dict:
        if isinstance(data, DNSRecord):
            return {parent: data}
        path = path.copy()
        key = path.pop(0) if path else None
        if key is not None:
            if key not in data:
                raise DNSTreePathNotFound(key)
            if not isinstance(data[key], dict) and path:
                raise DNSTreePathNotFound('/'.join([key] + path))
            return cls._recursive_view(data[key], path, key)
        return data

    def update(self, response_data):
        data = response_data
        zones, records, names = set(), set(), list()
        for k in data:
            zones.add(k['zone'])
            records.add((k['zone'], k['record']))
            names.append((k['record'], self._format_name(k), DNSRecord(**k)))
        self.tree = {
            zone: {
                record[1]: {name[1]: name[2]
                for name in names if name[0] == record[1]}
                for record in records if record[0] == zone}
                for zone in zones
        }

    @staticmethod
    def _format_name(record, limit=15):
        type_ = record['type']
        value = record['value'].replace(' ', '_').replace('/', '_')
        split = (round((limit-2)/2+0.5), round((limit-2)/2-0.5))
        value = len(value)>limit and value[:split[0]]+'..'+value[-split[1]:] or value
        return '{}_{}'.format(type_, value)


class DNSTreePathNotFound(Exception):
    pass

class DNSTreeMultipleRecordsFound(Exception):
    pass

class DNSTreeNotARecord(Exception):
    pass


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

    _prompt = 'dh.dns {} % '
    _cache = {}
    _tree = DNSTree()

    @property
    def prompt(self):
        path = self._tree.path
        return self._prompt.format(path[-1] if path else '/')

    def do_cd(self, arg):
        self.refresh_records()
        if arg == '..':
            self._tree.path.pop()
            return
        elif arg == '/':
            self._tree.path.clear()
            return
        try:
            self._tree.view(arg)
            self._tree.path = self._tree.get_fullpath(arg)
        except DNSTreePathNotFound as path:
            print('cd: no such zone or record: {}'.format(arg))

    def do_ls(self, arg):
        self.refresh_records()
        try:
            keys = sorted(self._tree.keys(arg))
            _print_columns(keys)
        except DNSTreePathNotFound as path:
            print('ls: no such zone or record: {}'.format(path))

    def do_pwd(self, arg):
        if arg:
            print('pwd: too many arguments')
            return
        print(self._tree.show_fullpath())

    def do_cat(self, arg):
        self.refresh_records()
        try:
            record = self._tree.get_record(arg)
            record.print_table()
        except DNSTreeNotARecord as path:
            print('cat: {}: is not a record'.format(path))
        except DNSTreeMultipleRecordsFound as path:
            print('cat: {}: has multiple records'.format(path))
        except DNSTreePathNotFound as path:
            print('cat: no such zone or record: {}'.format(path))

    def do_edit(self, arg):
        self.refresh_records()
        # TODO
        pass

    def do_add(self, arg):
        self.refresh_records()
        # TODO
        pass

    def refresh_records(self):
        if self._cache:
            return
        cmd = 'dns-list_records'
        self._cache = _make_request(cmd)
        self.parse_cache()

    def parse_cache(self):
        if self._cache.get('result') != 'success':
            logger.error('DreamHost API response error')
            return
        self._tree.update(self._cache['data'])


def _print_columns(values: list, col_align: int=8):
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
    logger.debug(req.full_url)
    res = urllib.request.urlopen(req)
    data = json.load(res)
    logger.debug(data.get('result'))
    return data


def _build_url(url: str, args: dict) -> str:
    url_parts = list(urllib.parse.urlparse(url))
    url_parts[4] = urllib.parse.urlencode(args)
    return urllib.parse.urlunparse(url_parts)


def _make_args():
    parser = argparse.ArgumentParser(description='DreamHost API CLI')
    parser.add_argument('--api-key', dest='key', default='6SHU5P2HLDAYECUM')
    parser.add_argument('--verbose', '-v', action='store_true')
    return parser.parse_args()


if __name__ == '__main__':
    args = _make_args()
    OPTS = {k: getattr(args, k) for k in OPTS}
    logger.level = logging.DEBUG if args.verbose else logging.WARNING
    DHMain().cmdloop()
