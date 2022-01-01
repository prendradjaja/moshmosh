from moshmosh.extension import Extension
from moshmosh.ast_compat import ast

import itertools


class Only(Extension):
    identifier = "only-block"

    def rewrite_ast(self, node):
        # The pattern used by thautwarm's extensions is to set self.visitor in
        # the __init__() instead of using a local variable. My visitor is
        # stateful. I'm not sure if the Extension (Only) object gets reused,
        # so to be safe I'm using a local variable.
        visitor = OnlyTransformer(self.activation)
        node = visitor.visit(node)
        node.body = visitor.only_defs + node.body
        return node


class OnlyTransformer(ast.NodeTransformer):
    def __init__(self, activation):
        self.activation = activation
        self.only_defs = []
        self.ids = itertools.count()

    def visit_With(self, node):
        if (
            node.lineno in self.activation
            and len(node.items) == 1
            and (context := node.items[0].context_expr)
            and isinstance(context, ast.Call)
            and isinstance(context.func, ast.Name)
            and context.func.id == 'only'
        ):
            return self.desugar_only(node)
        else:
            return node

    def desugar_only(self, with_node):
        # print(ast.dump(with_node, indent=4))

        call = with_node.items[0].context_expr
        assert len(call.keywords) == 0, 'Not yet supported for only(): only(x=y) for arg renaming'
        assert all(isinstance(arg, ast.Name) for arg in call.args), 'Invalid syntax for only(): Bare expression not allowed as parameter'

        name = f'_only_block_{next(self.ids)}'
        call.func.id = name

        args = [ast.arg(arg=arg.id) for arg in call.args]
        for arg in args:
            ast.copy_location(arg, with_node)

        definition = ast.FunctionDef(
            name=name,
            args=ast.arguments(
                posonlyargs=[],
                args=args,
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[]
            ),
            body=with_node.body,
            decorator_list=[],
            lineno=99999, # TODO
            col_offset=99999,  # TODO
        )
        self.only_defs.append(definition)

        if with_node.items[0].optional_vars:  # with ... as ...:
            optional_vars = with_node.items[0].optional_vars
            assert isinstance(optional_vars, ast.Name), 'Not yet supported for only(): Destructuring assignment'
            target = with_node.items[0].optional_vars.id
            result = ast.Assign(
                targets=[
                    ast.Name(id=target, ctx=ast.Store())
                ],
                value=call
            )
            ast.copy_location(result, with_node)
            return result
        else:  # with ...:  # (no 'as')
            result = ast.Expr(value=call)
            ast.copy_location(result, with_node)
            return result
