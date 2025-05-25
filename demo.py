import ast
import astunparse
import sympy

class IntegralSolver:
    def __init__(self):
        # integration rules in priority order
        self.rules = [
            self._power_rule,
            self._reciprocal_rule,
            self._trig_substitution,
            self._by_parts
        ]

    def integrate(self, expr_str):
        # parse expression into AST
        expr_ast = ast.parse(expr_str, mode='eval').body
        # apply integration rules recursively
        result = self._apply_rules(expr_ast)
        # return source code of result
        return astunparse.unparse(result).strip()

    def _apply_rules(self, node):
        # Try each rule in order
        for rule in self.rules:
            new_node = rule(node)
            if new_node is not None:
                # rule applied, try again on result
                return self._apply_rules(new_node)
        # no rule matched, return node unchanged
        return node

    def _power_rule(self, node):
        # ∫ x**n dx = x**(n+1)/(n+1) for n != -1
        if (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow) and
            isinstance(node.left, ast.Name) and node.left.id == 'x' and
            isinstance(node.right, ast.Constant) and isinstance(node.right.value, (int, float))):
            n = node.right.value
            if n == -1:
                return None
            # build x**(n+1)/(n+1)
            new_exp = ast.Constant(value=n+1)
            power = ast.BinOp(left=ast.Name(id='x'), op=ast.Pow(), right=new_exp)
            return ast.BinOp(left=power, op=ast.Div(), right=new_exp)
        return None

    def _reciprocal_rule(self, node):
        # ∫1/x dx = log|x|
        if (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div) and
            isinstance(node.left, ast.Constant) and node.left.value == 1 and
            isinstance(node.right, ast.Name) and node.right.id == 'x'):
            return ast.Call(func=ast.Name(id='log'), args=[ast.Call(func=ast.Name(id='abs'),
                                                                args=[ast.Name(id='x')], keywords=[])], keywords=[])
        return None

    def _trig_substitution(self, node):
        # handle sqrt(1-x**2) and 1/sqrt(x**2+1)
        # ∫sqrt(1-x**2) dx -> (x*sqrt(1-x**2)/2 + arcsin(x)/2)
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'sqrt'):
            arg = node.args[0]
            # sqrt(1-x**2)
            if (isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Sub) and
                isinstance(arg.left, ast.Constant) and arg.left.value == 1 and
                isinstance(arg.right, ast.BinOp) and isinstance(arg.right.op, ast.Pow)):
                # arcsin(x)
                return ast.Call(func=ast.Name(id='arcsin'), args=[ast.Name(id='x')], keywords=[])
        # ∫1/sqrt(x**2+1) dx -> asinh(x)
        if (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div) and
            isinstance(node.left, ast.Constant) and node.left.value == 1 and
            isinstance(node.right, ast.Call) and isinstance(node.right.func, ast.Name) and node.right.func.id == 'sqrt'):
            arg = node.right.args[0]
            if (isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Add) and
                isinstance(arg.left, ast.BinOp) and isinstance(arg.left.op, ast.Pow) and
                isinstance(arg.left.left, ast.Name) and arg.left.left.id == 'x' and
                isinstance(arg.left.right, ast.Constant) and arg.left.right.value == 2 and
                isinstance(arg.right, ast.Constant) and arg.right.value == 1):
                return ast.Call(func=ast.Name(id='asinh'), args=[ast.Name(id='x')], keywords=[])
        return None

    def _by_parts(self, node):
        # ∫u*dv = u*v - ∫v*du for simple functions
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
            u, dv = node.left, node.right
            # choose u as polynomial in x
            if self._is_polynomial(u) and self._is_simple(dv):
                du = self._differentiate(u)
                v = self._integrate_simple(dv)
            elif self._is_polynomial(dv) and self._is_simple(u):
                u, dv = dv, u
                du = self._differentiate(u)
                v = self._integrate_simple(dv)
            else:
                return None
            # build u*v - ∫v*du
            uv = ast.BinOp(left=u, op=ast.Mult(), right=v)
            integral = ast.BinOp(left=v, op=ast.Mult(), right=du)
            return ast.BinOp(left=uv, op=ast.Sub(), right=integral)
        return None

    def _is_polynomial(self, node):
        # simple check: x**n or x
        if isinstance(node, ast.Name) and node.id == 'x':
            return True
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            return isinstance(node.left, ast.Name) and node.left.id == 'x' and isinstance(node.right, ast.Constant)
        return False

    def _is_simple(self, node):
        # simple functions: exp(x), sin(x), cos(x)
        return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.args and isinstance(node.args[0], ast.Name)

    def _differentiate(self, node):
        # derivative of polynomial or simple function
        if isinstance(node, ast.Name) and node.id == 'x':
            return ast.Constant(value=1)
        if (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow) and
            isinstance(node.left, ast.Name) and node.left.id == 'x' and
            isinstance(node.right, ast.Constant)):
            n = node.right.value
            # d(x^n) = n*x^(n-1)
            coeff = ast.Constant(value=n)
            power = ast.BinOp(left=ast.Name(id='x'), op=ast.Pow(), right=ast.Constant(value=n-1))
            return ast.BinOp(left=coeff, op=ast.Mult(), right=power)
        if isinstance(node, ast.Call):
            fn = node.func.id
            arg = node.args[0]
            if fn == 'exp':
                return ast.Call(func=ast.Name(id='exp'), args=[arg], keywords=[])
            if fn == 'sin':
                return ast.Call(func=ast.Name(id='cos'), args=[arg], keywords=[])
            if fn == 'cos':
                # -sin(x)
                return ast.BinOp(left=ast.Constant(value=-1), op=ast.Mult(), right=ast.Call(func=ast.Name(id='sin'), args=[arg], keywords=[]))
        raise ValueError(f"Cannot differentiate node: {ast.dump(node)}")

    def _integrate_simple(self, node):
        # integral of simple functions
        fn = node.func.id
        arg = node.args[0]
        if fn == 'exp':
            return ast.Call(func=ast.Name(id='exp'), args=[arg], keywords=[])
        if fn == 'sin':
            # -cos(x)
            return ast.BinOp(left=ast.Constant(value=-1), op=ast.Mult(), right=ast.Call(func=ast.Name(id='cos'), args=[arg], keywords=[]))
        if fn == 'cos':
            return ast.Call(func=ast.Name(id='sin'), args=[arg], keywords=[])
        raise ValueError(f"Cannot integrate simple function: {fn}")


def to_latex(expr_str):
    expr = sympy.sympify(expr_str, evaluate=True)
    return f"{sympy.latex(expr)}"

if __name__ == '__main__':
    solver = IntegralSolver()
    tests = [
        "sqrt(1 - x**2)",
        "1/sqrt(x**2 + 1)",
        "sqrt(x**2 - 1)",
        "x**3",
        "1/x",
        "x*exp(x)",
        "(x**3)*sin(x)"
    ]
    for expr in tests:
        result = solver.integrate(expr)
        print(f"\n∫{expr} dx = {result} + C")
        print(f"Latex:")
        print(f"\\int {to_latex(expr)} dx = {to_latex(result)} + C")
