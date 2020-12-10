import cmd
import uuid
import argparse

from dataclasses import dataclass, field

OPTS = {}


@dataclass(frozen=True)
class DH_API:
    key: str
    cmd: str
    url: str = 'https://api.dreamhost.com/'
    format: str = 'json'
    account: str = None
    unique_id: uuid.UUID = field(default_factory=uuid.uuid4)


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

    def do_ls(self, arg):
        cmd = 'dns-list_records'
        print(_make_request(cmd))


def _make_request(cmd, opts=None):
    opts = opts or OPTS
    return DH_API(cmd=cmd, **opts)


def _make_args():
    parser = argparse.ArgumentParser(description='DreamHost API CLI')
    parser.add_argument('--api-key', dest='key', default='6SHU5P2HLDAYECUM')
    return parser.parse_args()


if __name__ == '__main__':
    args = _make_args()
    OPTS = vars(args)
    DHMain().cmdloop()
