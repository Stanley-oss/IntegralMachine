from fractions import Fraction
import ast
import astunparse
import json
import copy
import sympy
from latex2sympy2 import latex2sympy
import re

INTEGRAL_VAR = 'x'


class FoldConstants(ast.NodeTransformer):
    """
    折叠一元负号为一个单独的常量 -1=(-1)
    """

    def visit_UnaryOp(self, node):
        self.generic_visit(node)  # 先处理子节点
        if isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant):
            value = node.operand.value
            if isinstance(value, (int, float, Fraction)):
                return ast.copy_location(ast.Constant(value=-value), node)
        return node


class ApplyMapping(ast.NodeTransformer):
    """
    把被映射关系应用到积分结果/三角恒等变换的语法树上
    """

    def __init__(self, mapping_dict):
        self.mapping = mapping_dict

    def visit_Name(self, node):
        if node.id in self.mapping:  # 这里放心 x不在mapping中 匹配上的直接替换
            return copy.deepcopy(self.mapping[node.id])
        return node

    def generic_visit(self, node):
        return super().generic_visit(node)


def ast_equal(a, b):
    """
        判断两个ast是否相等
        """
    if type(a) != type(b):
        return False
    if isinstance(a, ast.AST):
        for f in a._fields:
            if not ast_equal(getattr(a, f), getattr(b, f)):
                return False
        return True
    elif isinstance(a, list):
        return len(a) == len(b) and all(ast_equal(x, y) for x, y in zip(a, b))
    else:
        return a == b


class TrigTransform(ast.NodeTransformer):
    def __init__(self):
        self.rules = json.load(open("triangle_transformation.json", encoding='utf-8'))

    def match(self, pattern, expr, mapping_dict):
        if isinstance(pattern, ast.Name):
            if pattern.id == INTEGRAL_VAR:
                return isinstance(expr, ast.Name) and expr.id == INTEGRAL_VAR
            if pattern.id not in mapping_dict:
                mapping_dict[pattern.id] = None
                return True
            else:
                return ast_equal(mapping_dict[pattern.id], expr)
        if isinstance(pattern, ast.Constant):
            return isinstance(expr, ast.Constant) and pattern.value == expr.value
        if isinstance(pattern, ast.BinOp) and isinstance(expr, ast.BinOp):
            if type(pattern.op) is type(expr.op):
                if isinstance(pattern.op, (ast.Add, ast.Mult)):  # 加法或乘法交换律
                    return (self.match(pattern.left, expr.left, mapping_dict.copy()) and self.match(pattern.right,
                                                                                                    expr.right,
                                                                                                    mapping_dict)) or \
                        (self.match(pattern.left, expr.right, mapping_dict.copy()) and self.match(pattern.right,
                                                                                                  expr.left,
                                                                                                  mapping_dict))
                else:
                    return self.match(pattern.left, expr.left, mapping_dict) and self.match(pattern.right, expr.right,
                                                                                            mapping_dict)
        if isinstance(pattern, ast.UnaryOp) and isinstance(expr, ast.UnaryOp) and type(pattern.op) is type(expr.op):
            return self.match(pattern.operand, expr.operand, mapping_dict)
        if isinstance(pattern, ast.Call) and isinstance(expr, ast.Call):
            if isinstance(pattern.func, ast.Name) and isinstance(expr.func,
                                                                 ast.Name) and pattern.func.id == expr.func.id:
                if len(pattern.args) == len(expr.args):
                    for p, n in zip(pattern.args, expr.args):
                        if not self.match(p, n, mapping_dict):
                            return False
                    return True
        return False

    def judge(self, cond, mapping):
        if not cond:
            return True
        import math
        namespace = {**vars(math)}
        for k, v in mapping.items():
            if isinstance(v, ast.Constant):
                namespace[k] = v.value
        try:
            return bool(eval(cond, {__builtins__: {}}, namespace))
        except Exception:
            # 无法评估的条件直接通过让他替换
            return True

    def generic_visit(self, node):
        node = super().generic_visit(node)
        try:
            for rule in self.rules:
                pattern = ast.parse(rule['pattern'], mode='eval').body
                mapping = {}
                if self.match(pattern, node, mapping) and self.judge(rule.get('cond', ''), mapping):
                    result = ast.parse(rule['result'], mode='eval').body
                    return ApplyMapping(mapping).visit(result)
            return node
        except Exception:
            return node


class IntegralSolver:
    def __init__(self):
        self.rules = json.load(open("rules.json"))  # 读取规则

    def str_to_sympy(self, expr):
        """
        把Python风格的字符串表达式转化为Sympy表达式
        """
        return sympy.sympify(expr, evaluate=False, rational=True)

    def ast_to_str(self, ast):
        """
        把AST转化为Python风格的字符串表达式
        """
        return astunparse.unparse(ast).strip()

    def str_to_latex(self, expr):
        """
        把Python风格的字符串表达式转化为LaTeX形式的字符串表达式
        """
        return sympy.latex(sympy.sympify(expr, evaluate=True, rational=True))

    def ast_to_latex(self, ast):
        """
        把AST转化为LaTeX形式的字符串表达式
        """
        return sympy.latex(sympy.sympify(self.ast_to_str(ast), evaluate=True, rational=True))

    def ast_to_sympy(self, ast):
        """
        把AST转化为Sympy表达式对象
        """
        return self.str_to_sympy(self.ast_to_str(ast))

    def str_to_ast(self, expr):
        """
        把Python风格的字符串表达式转化为AST
        """
        return FoldConstants().visit(ast.parse(str(self.str_to_sympy(expr)), mode='eval').body)
    
    def latex_to_str(self, latex):
        """
        把LaTeX形式的字符串表达式转化为Python风格的字符串表达式
        """
        prefix_pattern = r"^(\\\\?int)"
        suffix_pattern = r"(d\s?x)$"
        latex = re.sub(prefix_pattern, '', latex, flags=re.IGNORECASE)
        latex = re.sub(suffix_pattern, '', latex, flags=re.IGNORECASE)
        return str(latex2sympy(latex))

    def ast_expand(self, expr):
        """
        对AST进行多项式乘积展开
        """
        return self.str_to_ast(sympy.expand(self.ast_to_sympy(expr)))

    def ast_apart(self, expr):
        """
        对AST进行部分分式分解
        """
        try:
            aparted = sympy.apart(self.ast_to_sympy(expr))
        except:
            return None
        return self.str_to_ast(aparted)

    def ast_factor(self, expr):
        """
        对AST进行因式分式分解
        """
        return self.str_to_ast(sympy.factor(self.ast_to_sympy(expr)))

    def ast_cancel(self, expr):
        """
        对AST进行合并分式
        """
        return self.str_to_ast(sympy.cancel(self.ast_to_sympy(expr)))

    def ast_diff(self, expr):
        """
        对AST进行求导
        """
        return self.str_to_ast(sympy.diff(self.ast_to_sympy(expr)))

    def is_constant(self, node):
        """
        检查节点是否为常数表达式（不包含任何变量）
        """
        if isinstance(node, ast.Constant):
            return True
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return self.is_constant(node.operand)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            return self.is_constant(node.left) and self.is_constant(node.right)
        return False

    def match(self, pattern, node, mapping_dict):
        """
        匹配一个模式
        原理:分别拿到模式的AST和节点的AST,递归比较
        如果有遇到变量,则构建mapping_list,记录变量的映射关系
        """
        if isinstance(pattern, ast.Name):  # 模式要求一个变量名
            name = pattern.id
            if name == INTEGRAL_VAR:  # 要求是积分变量x
                return isinstance(node, ast.Name) and node.id == INTEGRAL_VAR  # 节点要求也是积分变量
            else:  # 要求是一个常量（使用除了x以外的所有标识符指代的东西）
                # 检查节点是否是常数表达式
                if not self.is_constant(node):
                    return False  # 不是常数,匹配失败
                if name in mapping_dict:  # 之前出现过这个标识符
                    return ast_equal(mapping_dict[name], node)  # 则要求映射到的那个东西相同
                else:  # 第一次出现这个标识符
                    mapping_dict[name] = node  # 仅记录映射关系
                    return True

        if isinstance(pattern, ast.Constant):  # 模式要求一个常量
            return isinstance(node, ast.Constant) and pattern.value == node.value
        if isinstance(pattern, ast.UnaryOp):  # 模式要求一个元运算符
            if not isinstance(node, ast.UnaryOp) or type(node.op) != type(pattern.op):
                return False
            return self.match(pattern.operand, node.operand, mapping_dict)
        if isinstance(pattern, ast.BinOp):  # 模式要求一个二元运算符
            # 下面特判模式要求a*x 或 x*a (a为1或-1时的情况)
            if isinstance(pattern.left, ast.Name) and isinstance(pattern.right,
                                                                 ast.Name) and pattern.right.id == INTEGRAL_VAR:  # a*x
                if isinstance(node, ast.Name) and node.id == INTEGRAL_VAR:  # x
                    if pattern.left.id in mapping_dict:
                        return ast_equal(mapping_dict[pattern.left.id], ast.Constant(value=1))
                    else:
                        mapping_dict[pattern.left.id] = ast.Constant(value=1)
                        return True
                if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and isinstance(node.operand,
                                                                                                  ast.Name) and node.operand.id == INTEGRAL_VAR:  # -x
                    if pattern.left.id in mapping_dict:
                        return ast_equal(mapping_dict[pattern.left.id], ast.Constant(value=-1))
                    else:
                        mapping_dict[pattern.left.id] = ast.Constant(value=-1)
                        return True
            if isinstance(pattern.right, ast.Name) and isinstance(pattern.left,
                                                                  ast.Name) and pattern.left.id == INTEGRAL_VAR:  # x*a
                if isinstance(node, ast.Name) and node.id == INTEGRAL_VAR:  # x
                    if pattern.right.id in mapping_dict:
                        return ast_equal(mapping_dict[pattern.right.id], ast.Constant(value=1))
                    else:
                        mapping_dict[pattern.right.id] = ast.Constant(value=1)
                        return True
                if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and isinstance(node.operand,
                                                                                                  ast.Name) and node.operand.id == INTEGRAL_VAR:  # -x
                    if pattern.right.id in mapping_dict:
                        return ast_equal(mapping_dict[pattern.right.id], ast.Constant(value=-1))
                    else:
                        mapping_dict[pattern.right.id] = ast.Constant(value=-1)
                        return True

            if not isinstance(node, ast.BinOp) or type(node.op) != type(pattern.op):
                return False
            return (self.match(pattern.left, node.left, mapping_dict)
                    and self.match(pattern.right, node.right, mapping_dict))
        if isinstance(pattern, ast.Call):  # 模式要求一个函数
            if not isinstance(node, ast.Call):
                return False
            if not (isinstance(pattern.func, ast.Name)) or (not isinstance(node.func, ast.Name)):
                return False
            if pattern.func.id != node.func.id:
                return False
            if len(pattern.args) != len(node.args):
                return False
            for p, n in zip(pattern.args, node.args):
                if not self.match(p, n, mapping_dict):
                    return False
            return True
        return False  # 没有任何要求,返回不匹配

    def judge(self, node, mapping_dict):
        """
        判断一个已经匹配的模式是否还满足额外要求
        目前支持的要求仅有某变量是否大于/等于/不等/小于某个值 多个要求之间可以用and或or(&&,||)连接
        """
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            map_to = mapping_dict.get(node.id)  # 映射到被积分式中的那个东西(是一个常量)
            if isinstance(map_to, ast.Constant):
                return map_to.value
            else:
                return self.judge(map_to, mapping_dict)  # 别的如果是个多项式什么的 递归判断吧
        if isinstance(node, ast.UnaryOp):
            value = self.judge(node.operand, mapping_dict)
            if isinstance(node.op, ast.UAdd):
                return +value
            if isinstance(node.op, ast.USub):
                return -value
            if isinstance(node, ast.Not):
                return not value
        if isinstance(node, ast.BinOp):
            left = self.judge(node.left, mapping_dict)
            right = self.judge(node.right, mapping_dict)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Pow):
                return left ** right
        if isinstance(node, ast.Compare):
            left = self.judge(node.left, mapping_dict)
            res = True
            for op, comp in zip(node.ops, node.comparators):
                right = self.judge(comp, mapping_dict)
                if isinstance(op, ast.Eq):
                    res = res and left == right
                if isinstance(op, ast.NotEq):
                    res = res and left != right
                if isinstance(op, ast.Gt):
                    res = res and left > right
                if isinstance(op, ast.GtE):
                    res = res and left >= right
                if isinstance(op, ast.LtE):
                    res = res and left <= right
                if isinstance(op, ast.Lt):
                    res = res and left < right
                left = right
            return res
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                return all(self.judge(x, mapping_dict) for x in node.values)
            if isinstance(node.op, ast.Or):
                return any(self.judge(x, mapping_dict) for x in node.values)

        raise ValueError('Unsupported node type: %s' % type(node))

    def try_rules(self, node):
        """
        尝试应用所有规则
        如果有匹配成功的规则,则返回两个变量,第一个变量是积分后的结果ast,第二个变量是应用的规则名称
        如果没有匹配成功的规则,则返回None
        """
        for rule in self.rules:
            pattern = ast.parse(rule['pattern'], mode='eval').body
            mapping_dict = {}
            if self.match(pattern, node, mapping_dict):
                # 匹配成功,再检查限制条件
                cond = rule['cond']
                ok = True
                if cond:
                    cond_ast = ast.parse(cond.replace("&&", " and ").replace("||", " or "), mode='eval').body
                    ok = self.judge(cond_ast, mapping_dict)
                if ok:
                    res_ast = ast.parse(rule['result'], mode='eval').body
                    res_ast = ApplyMapping(mapping_dict).visit(res_ast)
                    return res_ast, rule['name']
        return None

    def dfs(self, node, procedure):
        """
        实现积化和差 提出常数等操作并搜索尝试应用规则
        """
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):  # 积化和差（但是没用，因为结果没化简，应该需要再调用sympy化简）
            is_func = lambda node, func: isinstance(node, ast.Call) and isinstance(node.func,
                                                                                   ast.Name) and node.func.id == func
            cpy = lambda node: copy.deepcopy(node)
            lhs = node.left
            rhs = node.right

            # sin(A)*sin(B) -> 1/2(cos(A-B) - cos(A+B))
            if is_func(lhs, "sin") and is_func(rhs, "sin"):
                A = lhs.args[0]
                B = rhs.args[0]
                cos_A_sub_B = ast.Call(func=ast.Name(id="cos", ctx=ast.Load()),
                                       args=[ast.BinOp(left=cpy(A), op=ast.Sub(), right=cpy(B))],
                                       keywords=[])
                cos_A_add_B = ast.Call(func=ast.Name(id="cos", ctx=ast.Load()),
                                       args=[ast.BinOp(left=cpy(A), op=ast.Add(), right=cpy(B))],
                                       keywords=[])
                transformed_ast = self.ast_cancel(
                    ast.BinOp(left=ast.BinOp(left=ast.Constant(value=1), op=ast.Div(), right=ast.Constant(value=2)),
                              op=ast.Mult(),
                              right=ast.BinOp(left=cos_A_sub_B, op=ast.Sub(), right=cos_A_add_B)))
                procedure.append({"rule": "Trig Identities: sin(A)*sin(B) -> 1/2(cos(A-B) - cos(A+B))",
                                  "before": self.ast_to_latex(node),
                                  "after": self.ast_to_latex(transformed_ast)})
                return self.dfs(transformed_ast, procedure)

            # cos(A)*cos(B) -> 1/2(cos(A-B) + cos(A+B))
            if is_func(lhs, "cos") and is_func(rhs, "cos"):
                A = lhs.args[0]
                B = rhs.args[0]
                sin_A_sub_B = ast.Call(func=ast.Name(id="cos", ctx=ast.Load()),
                                       args=[ast.BinOp(left=cpy(A), op=ast.Sub(), right=cpy(B))],
                                       keywords=[])
                sin_A_add_B = ast.Call(func=ast.Name(id="cos", ctx=ast.Load()),
                                       args=[ast.BinOp(left=cpy(A), op=ast.Add(), right=cpy(B))],
                                       keywords=[])
                transformed_ast = self.ast_cancel(
                    ast.BinOp(left=ast.BinOp(left=ast.Constant(value=1), op=ast.Div(), right=ast.Constant(value=2)),
                              op=ast.Mult(),
                              right=ast.BinOp(left=sin_A_sub_B, op=ast.Add(), right=sin_A_add_B)))
                procedure.append({"rule": "Trig Identities: cos(A)*cos(B) -> 1/2(cos(A-B) + cos(A+B))",
                                  "before": self.ast_to_latex(node),
                                  "after": self.ast_to_latex(transformed_ast)})
                return self.dfs(transformed_ast, procedure)

            # sin(A)*cos(B) -> 1/2(sin(A+B) + sin(A-B))
            if is_func(lhs, "sin") and is_func(rhs, "cos"):
                A = lhs.args[0]
                B = rhs.args[0]
                sin_A_sub_B = ast.Call(func=ast.Name(id="sin", ctx=ast.Load()),
                                       args=[ast.BinOp(left=cpy(A), op=ast.Sub(), right=cpy(B))],
                                       keywords=[])
                sin_A_add_B = ast.Call(func=ast.Name(id="sin", ctx=ast.Load()),
                                       args=[ast.BinOp(left=cpy(A), op=ast.Add(), right=cpy(B))],
                                       keywords=[])
                transformed_ast = self.ast_cancel(
                    ast.BinOp(left=ast.BinOp(left=ast.Constant(value=1), op=ast.Div(), right=ast.Constant(value=2)),
                              op=ast.Mult(),
                              right=ast.BinOp(left=sin_A_sub_B, op=ast.Add(), right=sin_A_add_B)))
                procedure.append({"rule": "Trig Identities: sin(A)*cos(B) -> 1/2(sin(A+B) + sin(A-B))",
                                  "before": self.ast_to_latex(node),
                                  "after": self.ast_to_latex(transformed_ast)})
                return self.dfs(transformed_ast, procedure)

            # cos(A)*sin(B) -> 1/2(sin(A+B) - sin(A-B))
            if is_func(lhs, "cos") and is_func(rhs, "sin"):
                A = lhs.args[0]
                B = rhs.args[0]
                sin_A_sub_B = ast.Call(func=ast.Name(id="sin", ctx=ast.Load()),
                                       args=[ast.BinOp(left=cpy(A), op=ast.Sub(), right=cpy(B))],
                                       keywords=[])
                sin_A_add_B = ast.Call(func=ast.Name(id="sin", ctx=ast.Load()),
                                       args=[ast.BinOp(left=cpy(A), op=ast.Add(), right=cpy(B))],
                                       keywords=[])
                transformed_ast = self.ast_cancel(
                    ast.BinOp(left=ast.BinOp(left=ast.Constant(value=1), op=ast.Div(), right=ast.Constant(value=2)),
                              op=ast.Mult(),
                              right=ast.BinOp(left=sin_A_sub_B, op=ast.Sub(), right=sin_A_add_B)))
                procedure.append({"rule": "Trig Identities: cos(A)*sin(B) -> 1/2(sin(A+B) - sin(A-B))",
                                  "before": self.ast_to_latex(node),
                                  "after": self.ast_to_latex(transformed_ast)})
                return self.dfs(transformed_ast, procedure)

        if isinstance(node, ast.Constant):  # 为一个常数
            if node.value == 0:
                return ast.Constant(value=0)

            procedure.append({"rule": "Constant Rule: a -> ax",
                              "before": self.ast_to_latex(node),
                              "after": self.ast_to_latex(ast.BinOp(left=node, op=ast.Mult(),
                                                                   right=ast.Name(id=INTEGRAL_VAR, ctx=ast.Load())))})
            return ast.BinOp(left=node, op=ast.Mult(), right=ast.Name(id=INTEGRAL_VAR, ctx=ast.Load()))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):  # 提出一个单独的负号
            return ast.BinOp(left=ast.Constant(value=-1), op=ast.Mult(), right=self.dfs(node.operand, procedure))
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):  # 两个表达式相加或相减
            lhs = self.dfs(node.left, procedure)
            rhs = self.dfs(node.right, procedure)
            if lhs is None or rhs is None:  # 到时候积不出来可以调库
                return None
            else:
                return ast.BinOp(left=lhs, op=node.op, right=rhs)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):  # 两个表达式相乘 提出常数
            # if isinstance(node.left,ast.Constant):
            if self.is_constant(node.left):
                rhs = self.dfs(node.right, procedure)
                if rhs is None:
                    return None
                else:
                    return ast.BinOp(left=node.left, op=node.op, right=rhs)
            # if isinstance(node.right,ast.Constant):
            if self.is_constant(node.right):
                lhs = self.dfs(node.left, procedure)
                if lhs is None:
                    return None
                else:
                    return ast.BinOp(left=node.right, op=node.op, right=lhs)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):  # 两个表达式相除
            if isinstance(node.left, ast.Constant):  # 分子为常数
                if node.left.value == 1:  # 先解决1/x和1/(x**c)情况
                    if isinstance(node.right, ast.Name) and node.right.id == INTEGRAL_VAR:  # 1/x
                        procedure.append({"rule": "Reciprocal Rule: 1/x -> log(x)",
                                          "before": self.ast_to_latex(node),
                                          "after": self.ast_to_latex(ast.Call(ast.Name(id='log', ctx=ast.Load()), [
                                              ast.Name(id=INTEGRAL_VAR, ctx=ast.Load())], []))})
                        return ast.Call(ast.Name(id='log', ctx=ast.Load()), [ast.Name(id=INTEGRAL_VAR, ctx=ast.Load())],
                                        [])
                    if isinstance(node.right, ast.BinOp) and isinstance(node.right.op, ast.Pow):  # 1/(x**c)
                        procedure.append({"rule": "Power Rule: 1/(x**c) -> 1/c * x**(c-1)",
                                          "before": self.ast_to_latex(node),
                                          "after": self.ast_to_latex(ast.BinOp(left=node.right.left,
                                                                               op=ast.Pow(),
                                                                               right=ast.UnaryOp(op=ast.USub(),
                                                                                                 operand=node.right.right)))})  # x**(-c)
                        return self.dfs(ast.BinOp(left=node.right.left,
                                                  op=ast.Pow(),
                                                  right=ast.UnaryOp(op=ast.USub(), operand=node.right.right)),
                                        procedure)
                else:
                    rhs = self.dfs(ast.BinOp(ast.Constant(value=1), ast.Div(), node.right), procedure)
                    if rhs is None:
                        return None
                    else:
                        return ast.BinOp(left=node.left, op=ast.Mult(), right=rhs)  # 提出分子常数
            if isinstance(node.right, ast.Constant):  # 分母为常数
                lhs = self.dfs(node.left, procedure)
                if lhs is None:
                    return None
                else:
                    return ast.BinOp(left=ast.BinOp(left=ast.Constant(value=1), op=ast.Div(), right=node.right),
                                     op=ast.Mult(), right=lhs)
        apply_rules_res = self.try_rules(node)
        if apply_rules_res:
            transformed_ast, rule_name = apply_rules_res
            procedure.append({"rule": rule_name,
                              "before": self.ast_to_latex(node),
                              "after": self.ast_to_latex(transformed_ast)})
            return transformed_ast
        return None

    def integral(self, expr):
        """
        对Python表达式进行积分
        """
        result = {
            "answer": None,
            "procedure": []
        }
        orig_ast = self.str_to_ast(expr)
        dfs_res = self.dfs(orig_ast, result["procedure"])
        if dfs_res:
            result["answer"] = f"\\int {self.str_to_latex(expr)} dx = {self.ast_to_latex(dfs_res)}"
            return result

        # Polynomial Expansion
        transformed_ast = self.ast_expand(orig_ast)
        dfs_res = self.dfs(transformed_ast, result["procedure"])
        if dfs_res:
            result["procedure"].append({"rule": "Polynomial Expansion",
                                        "before": self.ast_to_latex(orig_ast),
                                        "after": self.ast_to_latex(transformed_ast)})
            result["answer"] = f"\\int {self.str_to_latex(expr)} dx = {self.ast_to_latex(dfs_res)}"
            return result

        # Apart Expression
        transformed_ast = self.ast_apart(orig_ast)
        if transformed_ast is not None:
            dfs_res = self.dfs(transformed_ast, result["procedure"])
            if dfs_res:
                result["procedure"].append({"rule": "Apart Expression",
                                            "before": self.ast_to_latex(orig_ast),
                                            "after": self.ast_to_latex(transformed_ast)})
                result["answer"] = f"\\int {self.str_to_latex(expr)} dx = {self.ast_to_latex(dfs_res)}"
                return result

        # Simplification
        transformed_ast = self.ast_cancel(orig_ast)
        dfs_res = self.dfs(transformed_ast, result["procedure"])
        if dfs_res:
            result["procedure"].append({"rule": "Simplification",
                                        "before": self.ast_to_latex(orig_ast),
                                        "after": self.ast_to_latex(transformed_ast)})
            result["answer"] = f"\\int {self.str_to_latex(expr)} dx = {self.ast_to_latex(dfs_res)}"
            return result

        return None
    

if __name__ == '__main__':
    tests = ["114514",
             "sin(-x)",
             "x*exp(x)",
             "sin(x)/3",
             "0.25*cos(x)+8*x**5",
             "0.5 * sin(3 * x) + sin((-1)*x)",
             "5+x",
             "(2*x+3)**2",
             "x**2+x**3",
             "sqrt(1-x**2)",
             "1/(4*x+3)",
             "exp(3*x)",
             "1/(5*x + 2)",
             "sin(4*x)",
             "cos(-2*x)",
             "tan(x)",
             "1/cos(x)**2",
             "x*sin(x)",
             "x*cos(x)",
             "(x**3+2*x**2+4*x+1)/(x**2+2*x+1)",
             "(x**2+2*x+1)/(x**2+2*x+1)**2",
             "-2*x**2+3*x-x*exp(x)",
             "-sin(x)",
             "(0.5 * (sin((x + (2 * x))) + sin((x - (2 * x)))))",
             "x*sin(x)",
             "sin(x)**2",
             "cos(x)**2",
             "cos(x*2)**2",
             "tan(x)**2",
             "cos(x)**2 + sin(x)**2",
             "1 + tan(x)**2",
             "1 - cos(x)**2",
             "cos(x)*sin(x)",
             "sin(x)*cos(2*x)",
             "cos(x)*cos(3*x)",
             "sin(x)*sin(5*x)",
             #  "(x**2)*(sin(x)**2)" #连续换元两次真投降了
             ]
    solver = IntegralSolver()
    trig_transformer = TrigTransform()

    for expr in tests:
        res = solver.integral(expr)
        if res:
            print(f"{res}")
        else:
            print(f"{expr}")

