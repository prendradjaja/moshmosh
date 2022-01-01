from moshmosh.extension import Extension
from moshmosh.ast_compat import ast


class ObjShorthand(Extension):
    identifier = "obj-shorthand"

    def rewrite_ast(self, node):
        # return node
        return ObjShorthandTransformer(self.activation).visit(node)


# import ast
# from ast import *


class ObjShorthandTransformer(ast.NodeTransformer):
    def __init__(self, activation):
        self.activation = activation

    def visit_Call(self, node):
        if (
            node.lineno in self.activation
            and isinstance(node.func, ast.Name)
            and node.func.id == 'obj'
        ):
            return self.rewrite_node(node)
        else:
            return node

    def rewrite_node(self, node):
        name_args, other_args = partition(node.args, lambda arg: isinstance(arg, ast.Name))
        assert len(other_args) == 0
        node.args = other_args
        names = [arg.id for arg in name_args]
        kwargs = [
            ast.keyword(
                arg=name,
                value=ast.Name(id=name, ctx=ast.Load())
            )
            for name in names
        ]
        node.keywords.extend(kwargs)
        return node


def partition(lst, pred):
    matches =    [x for x in lst if pred(x)]
    nonmatches = [x for x in lst if not pred(x)]
    return matches, nonmatches


def main():
    class MockActivation:
        def __contains__(self, item):
            return True


    node = ast.parse(open('example.py').read())

    # transformer = ObjShorthandTransformer(True)
    # node = transformer.visit(node)
    # # print('\n----------------------------\n')
    # ast.fix_missing_locations(node)
    # # exec(compile(node, filename="<ast>", mode="exec"))

    # print(ast.dump(node, indent=4))
    # print('\n----------------------------\n')
    # print(ast.unparse(node))

    ObjShorthandTransformer(MockActivation()).visit(node)
    ast.fix_missing_locations(node)
    print(ast.unparse(node))


if __name__ == '__main__':
    main()
