from abc import ABC
from io import StringIO
from moshmosh.rewrite_helper import ast_to_literal
import ast
import abc
import typing as t
import re

_extension_pragma_re = re.compile(
    r'#\s*(?P<action>[+-])(?P<ext>[^(\s]+)\s*(\((?P<params>.*)\))?\s*$')


class Activation:
    """This sort of instances tell us
    whether an extension is enabled at a specific line number"""

    def __init__(self):
        self.intervals = []

    def enable(self, line: int):
        intervals = self.intervals
        if not intervals:
            intervals.append(line)
            return
        if isinstance(intervals[-1], int):
            # already enabled
            return

        intervals.append(line)

    def disable(self, line: int):
        intervals = self.intervals
        if not intervals or isinstance(intervals[-1], range):
            # already disabled
            return
        enable_line = intervals.pop()
        intervals.append(range(enable_line, line))

    def __contains__(self, item):
        for each in self.intervals:
            if isinstance(each, int):
                if item >= each:
                    return True
            else:
                assert isinstance(each, range)
                if item in each:
                    return True
        return False


class ExtensionNotFoundError(Exception):
    pass


class ExtensionMeta(type):
    def __new__(mcs, name, bases, ns: dict):
        if ns.get('_root', False):
            return super().__new__(mcs, name, bases, ns)
        bases = tuple(filter(lambda it: Extension is not it, bases))

        ret: t.Type[RealExtension] = type(name, (*bases, RealExtension), ns)
        Registered.extensions[ret.identifier()] = ret

        return ret


class RealExtension:
    """
    An abstraction among syntax extensions
    """

    @property
    @abc.abstractmethod
    def activation(self) -> Activation:
        raise NotImplemented

    @activation.setter
    @abc.abstractmethod
    def activation(self, value):
        raise NotImplemented

    @classmethod
    @abc.abstractmethod
    def identifier(cls):
        "A string to indicate the class of extension instance."
        raise NotImplemented

    @abc.abstractmethod
    def rewrite(self, node: ast.AST):
        "A function to perform AST level rewriting"
        raise NotImplemented


class Extension(metaclass=ExtensionMeta):
    """automatically extension"""

    _root = True

    @property
    @abc.abstractmethod
    def activation(self) -> Activation:
        raise NotImplemented

    @activation.setter
    @abc.abstractmethod
    def activation(self, value):
        raise NotImplemented

    @classmethod
    @abc.abstractmethod
    def identifier(cls):
        "A string to indicate the class of extension instance."
        raise NotImplemented

    @abc.abstractmethod
    def rewrite(self, node: ast.AST):
        "A function to perform AST level rewriting"
        raise NotImplemented


class Registered:
    extensions: t.Dict[str, t.Type[Extension]] = {}


def extract_pragmas(lines):
    """
    Traverse the source codes and extract out the scope of
    every extension.
    """
    # bind to local for faster visiting in the loop
    extension_pragma_re = _extension_pragma_re
    registered = Registered.extensions
    extension_builder: t.Dict[object, Extension] = {}

    for i, line in enumerate(lines):
        pragma = extension_pragma_re.match(line)
        if pragma:
            pragma = pragma.groupdict()
            action = pragma['action']
            extension = pragma['ext']
            params = pragma['params'] or ''
            params = (param.strip() for param in params.split(','))
            params = tuple(i for i in params if i)
            try:
                ext_cls = registered[extension]
            except KeyError:
                # TODO: add source code position info
                raise ExtensionNotFoundError(extension)
            key = (ext_cls, params)

            ext = extension_builder.get(key, None)
            if ext is None:
                try:
                    ext = extension_builder[key] = ext_cls(*params)
                except Exception as e:
                    raise
            lineno = i + 1
            if action == "+":
                ext.activation.enable(lineno)
            else:
                ext.activation.disable(lineno)

    return list(extension_builder.values())


def perform_extension(source_code):
    # FIXME: Haskell-like syntax extension system
    node = ast.parse(source_code)
    extensions = extract_pragmas(StringIO(source_code))

    for each in extensions:
        node = each.rewrite(node)
        ast.fix_missing_locations(node)

    literal = ast_to_literal(node)
    string_io = StringIO()
    string_io.write("""
import ast as _ast
def _literal_to_ast(literal):
    '''
    Convert a python literal to an AST.
    '''
    if isinstance(literal, dict):
        ctor = literal.pop('constructor')
        ctor = getattr(_ast, ctor)
        return ctor(**{k: _literal_to_ast(v) for k, v in literal.items()})

    if isinstance(literal, list):
        return list(map(_literal_to_ast, literal))

    return literal

    """)
    string_io.write('\n')
    string_io.write('__literal__ = ')
    string_io.write(repr(literal))
    string_io.write('\n')
    string_io.write('__ast__ = _literal_to_ast(__literal__)\n')
    string_io.write('__code__ = compile(__ast__, __file__, "exec")\n')
    string_io.write('exec(__code__, globals())\n')
    code = string_io.getvalue()
    from .extension_register import clear_cache
    clear_cache()
    return code
