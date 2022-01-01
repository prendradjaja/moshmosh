from moshmosh.extension import Extension
from moshmosh.ast_compat import ast

import itertools


class UnpackDot(Extension):
    identifier = "unpack-dot"

    def rewrite_ast(self, node):
        # return node
        return UnpackDotTransformer(self.activation).visit(node)


# import itertools
# import ast
# from ast import *


class UnpackDotTransformer(ast.NodeTransformer):
    def __init__(self, activation):
        self.activation = activation
        self.ids = itertools.count()

    def visit_Assign(self, node):
        if (
            node.lineno in self.activation
            and isinstance(node.value, ast.Starred)
        ):
            return self.rewrite_node(node)
        else:
            return node

    def rewrite_node(self, node):
        # Replace e.g.
        #   x, y = * right_side()
        # With e.g.
        #   _temp_0 = right_side()
        #   x, y = (_temp_0.x, _temp_0.y)

        # Or, for just one left-hand-side target, replace e.g.
        #   x = * right_side()
        # With e.g.
        #   _temp_0 = right_side()
        #   x = _temp_0.x

        right_side = node.value.value
        right_name = f'_temp_{next(self.ids)}'

        assert len(node.targets) == 1
        target = node.targets[0]
        if isinstance(target, ast.Name):
            left_names = [target.id]
        else:
            left_names = [name_node.id for name_node in target.elts]

        if len(left_names) == 1:
            left_name = left_names[0]
            node.value = ast.Attribute(
                value=ast.Name(id=right_name, ctx=ast.Load()),
                attr=left_name,
                ctx=ast.Load()
            )
        else:
            node.value = ast.Tuple(
                elts=[
                    ast.Attribute(
                        value=ast.Name(id=right_name, ctx=ast.Load()),
                        attr=each,
                        ctx=ast.Load()
                    )
                    for each in left_names
                ],
                ctx=ast.Load()
            )

        return [
            ast.Assign(
                targets=[
                    ast.Name(id=right_name, ctx=ast.Store())
                ],
                value=right_side
            ),
            node,
        ]


def main():
    node = ast.parse(open('example.py').read())

    # transformer = UnpackDotTransformer(True)
    # node = transformer.visit(node)
    # # print('\n----------------------------\n')
    # ast.fix_missing_locations(node)
    # # exec(compile(node, filename="<ast>", mode="exec"))

    # print(ast.dump(node, indent=4))
    # print('\n----------------------------\n')
    # print(ast.unparse(node))

    UnpackDotTransformer(True).visit(node)
    ast.fix_missing_locations(node)
    print(ast.unparse(node))


if __name__ == '__main__':
    main()
