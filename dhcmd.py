import cmd
import sys


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
        print('hello')


if __name__ == '__main__':
    DHMain().cmdloop()
