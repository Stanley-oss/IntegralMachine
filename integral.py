from fractions import Fraction
import ast
import astunparse
import json
import copy
import sympy

INTEGRAL_VAR = 'x'

# class FoldConstants(ast.NodeTransformer):
#     """
#     折叠一元负号为一个单独的常量 -1=(-1)
#     """
#     def visit_UnaryOp(self, node):
#         self.generic_visit(node) # 先处理子节点
#         if isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant):
#             value = node.operand.value
#             if isinstance(value, (int,float,Fraction)):
#                 return ast.copy_location(ast.Constant(value=-value),node)
#         return node
    
class ApplyMapping(ast.NodeTransformer):
    """
    把被映射关系应用到积分结果的语法树上
    """
    def __init__(self,mapping_dict):
        self.mapping = mapping_dict
    def visit_Name(self, node):
        if node.id in self.mapping: # 这里放心 x不在mapping中 匹配上的直接替换
            return copy.deepcopy(self.mapping[node.id])
        return node

class IntegralSolver:
    def __init__(self):
        self.rules = json.load(open('rules.json'))

    def str_to_sympy(self,expr):
        """
        把Python风格的字符串表达式转化为Sympy表达式
        """
        return sympy.sympify(expr,evaluate=False,rational=True)

    def ast_to_str(self,ast):
        """
        把AST转化为Python风格的字符串表达式
        """
        return astunparse.unparse(ast).strip()
    
    def str_to_latex(self,expr):
        """
        把Python风格的字符串表达式转化为LaTeX形式的字符串表达式
        """
        return sympy.latex(sympy.sympify(expr,evaluate=True,rational=True))
    
    def ast_to_latex(self,ast):
        """
        把AST转化为LaTeX形式的字符串表达式
        """
        return sympy.latex(sympy.sympify(self.ast_to_str(ast),evaluate=True,rational=True))

    def ast_to_sympy(self,ast):
        """
        把AST转化为Sympy表达式对象
        """
        return self.str_to_sympy(self.ast_to_str(ast))
        
    def str_to_ast(self,expr):
        """
        把Python风格的字符串表达式转化为AST
        """
        return ast.parse(str(self.str_to_sympy(expr)),mode='eval').body

    def ast_expand(self,expr):
        """
        对AST进行多项式乘积展开
        """
        return self.str_to_ast(sympy.expand(self.ast_to_sympy(expr)))

    def ast_apart(self,expr):
        """
        对AST进行部分分式分解
        """
        return self.str_to_ast(sympy.apart(self.ast_to_sympy(expr)))

    def ast_factor(self,expr):
        """
        对AST进行因式分式分解
        """
        return self.str_to_ast(sympy.factor(self.ast_to_sympy(expr)))

    def ast_cancel(self,expr):
        """
        对AST进行合并分式
        """
        return self.str_to_ast(sympy.cancel(self.ast_to_sympy(expr)))

    def ast_diff(self,expr):
        """
        对AST进行求导
        """
        return self.str_to_ast(sympy.diff(self.ast_to_sympy(expr)))

    def ast_equal(self,a,b):
        """
        判断两个ast是否相等
        """
        if type(a) != type(b):
            return False
        if isinstance(a, ast.AST):
            for f in a._fields:
                if not self.ast_equal(getattr(a,f),getattr(b,f)):
                    return False
            return True
        elif isinstance(a, list):
            return len(a) == len(b) and all(self.ast_equal(x,y) for x,y in zip(a,b))
        else:
            return a == b
    
    def match(self,pattern,node,mapping_dict):
        """
        匹配一个模式
        原理：分别拿到模式的AST和节点的AST，递归比较
        如果有遇到变量，则构建mappin_list，记录变量的映射关系
        """
        if isinstance(pattern,ast.Name): # 模式要求一个变量名
            name = pattern.id
            if name == INTEGRAL_VAR: # 要求是积分变量x
                return isinstance(node,ast.Name) and node.id == INTEGRAL_VAR # 节点要求也是积分变量
            else: # 要求是一个常量？(使用除了x以外的所有标识符指代的东西)
                # TODO: 其实这里并没要求x以外的标识符一定表示的是常量 我希望这甚至可以是一个多项式 但是还没支持
                if name in mapping_dict: # 之前出现过这个标识符
                    return self.ast_equal(mapping_dict[name],node) # 则要求映射到的那个东西相同
                else: # 第一次出现这个标识符
                    mapping_dict[name] = node # 仅记录映射关系
                    return True
        if isinstance(pattern,ast.Constant): # 模式要求一个常量
            return isinstance(node,ast.Constant) and pattern.value == node.value
        if isinstance(pattern,ast.UnaryOp): # 模式要求一个元运算符
            if not isinstance(node,ast.UnaryOp) or type(node.op) != type(pattern.op):
                return False
            return self.match(pattern.operand,node.operand,mapping_dict)
        if isinstance(pattern,ast.BinOp): # 模式要求一个二元运算符
            #下面特判模式要求a*x 或 x*a (a为1时的情况)
            if ((isinstance(pattern.left, ast.Name) and isinstance(pattern.right, ast.Name) and pattern.right.id == INTEGRAL_VAR) and # a*x
                (isinstance(node,ast.Name) and node.id == INTEGRAL_VAR)):
                if pattern.left.id in mapping_dict:
                    return self.ast_equal(mapping_dict[pattern.left.id],ast.Constant(value=1))
                else:
                    mapping_dict[pattern.left.id] = ast.Constant(value=1)
                    return True
            if ((isinstance(pattern.right, ast.Name) and isinstance(pattern.left, ast.Name) and pattern.left.id == INTEGRAL_VAR) and  # x*a
                (isinstance(node,ast.Name) and node.id == INTEGRAL_VAR)):
                if pattern.right.id in mapping_dict:
                    return self.ast_equal(mapping_dict[pattern.right.id],ast.Constant(value=1))
                else:
                    mapping_dict[pattern.right.id] = ast.Constant(value=1)
                    return True
            
            if not isinstance(node,ast.BinOp) or type(node.op) != type(pattern.op):
                return False
            return (self.match(pattern.left,node.left,mapping_dict)
                    and self.match(pattern.right,node.right,mapping_dict))
        if isinstance(pattern,ast.Call): # 模式要求一个函数
            if not isinstance(node,ast.Call):
                return False
            if not (isinstance(pattern.func,ast.Name)) or (not isinstance(node.func,ast.Name)):
                return False
            if pattern.func.id != node.func.id:
                return False
            if len(pattern.args) != len(node.args):
                return False
            for p,n in zip(pattern.args,node.args):
                if not self.match(p,n,mapping_dict):
                    return False
            return True
        return False # 没有任何要求，返回不匹配
    
    def judge(self,node,mapping_dict):
        """
        判断一个已经匹配的模式是否还满足额外要求
        目前支持的要求仅有某变量是否大于/等于/不等/小于某个值 多个要求之间可以用and或or(&&,||)连接
        暂时不支持判断更复杂的(判断是否是一个多项式等)
        """
        if isinstance(node,ast.Constant):
            return node.value
        if isinstance(node,ast.Name): # 这里的可玩性很大 这个限制可以是针对语法树层面的 不管是常量还是别的什么
            mapto = mapping_dict.get(node.id) # 映射到被积分式中的那个东西(可能是一个常量或别的)
            if isinstance(mapto,ast.Constant):
                return mapto.value
            else:
                return self.judge(mapto,mapping_dict) # 别的如果是个多项式什么的 递归判断吧
        if isinstance(node,ast.UnaryOp):
            value = self.judge(node.operand,mapping_dict)
            if isinstance(node.op,ast.UAdd):
                return +value
            if isinstance(node.op,ast.USub):
                return -value
            if isinstance(node,ast.Not):
                return not value
        if isinstance(node,ast.BinOp):
            left = self.judge(node.left,mapping_dict)
            right = self.judge(node.right,mapping_dict)
            if isinstance(node.op,ast.Add):
                return left + right
            if isinstance(node.op,ast.Sub):
                return left - right
            if isinstance(node.op,ast.Mult):
                return left * right
            if isinstance(node.op,ast.Div):
                return left / right
            if isinstance(node.op,ast.Pow):
                return left ** right
        if isinstance(node,ast.Compare):
            left = self.judge(node.left,mapping_dict)
            res = True
            for op, comp in zip(node.ops,node.comparators):
                right = self.judge(comp,mapping_dict)
                if isinstance(op,ast.Eq):
                    res = res and left == right
                if isinstance(op,ast.NotEq):
                    res = res and left != right
                if isinstance(op,ast.Gt):
                    res = res and left > right
                if isinstance(op,ast.GtE):
                    res = res and left >= right
                if isinstance(op,ast.LtE):
                    res = res and left <= right
                if isinstance(op,ast.Lt):
                    res = res and left < right
                left = right
            return res
        if isinstance(node,ast.BoolOp):
            if isinstance(node.op,ast.And):
                return all(self.judge(x,mapping_dict) for x in node.values)
            if isinstance(node.op,ast.Or):
                return any(self.judge(x,mapping_dict) for x in node.values)
        
        raise ValueError('Unsupported node type: %s' % type(node))
    
    def try_rules(self,node):
        """
        尝试应用所有规则
        如果有匹配成功的规则，则返回两个变量，第一个变量是积分后的结果ast，第二个变量是应用的规则名称
        如果没有匹配成功的规则，则返回None
        """
        for rule in self.rules:
            pattern = ast.parse(rule['pattern'],mode='eval').body
            mapping_dict = {}
            if self.match(pattern,node,mapping_dict):
                # 匹配成功，再检查限制条件
                cond = rule['cond']
                ok   = True
                if cond:
                    cond_ast = ast.parse(cond.replace("&&"," and ").replace("||"," or "),mode='eval').body
                    ok = self.judge(cond_ast,mapping_dict)
                if ok:
                    res_ast = ast.parse(rule['result'],mode='eval').body
                    res_ast = ApplyMapping(mapping_dict).visit(res_ast)
                    #return res_ast, rule['name'] # 这里可以回溯用了什么规则
                    return res_ast
        print(f"NOT SUPPORTED: {astunparse.unparse(node).strip()}")
        return None

if __name__ == '__main__':
    tests = ["114514",
              "sin(x)/3",
              "0.25*cos(x)+8*x**5",
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
              "x*exp(x)",
              "x*sin(x)",
              "x*cos(x)",
              "(x**3+2*x**2+4*x+1)/(x**2+2*x+1)", # 部分分式
              #"(x**2)*(sin(x)**2)" #连续换元两次真投降了
             ]
    solver = IntegralSolver()

    def test_integral(node): # 测试积分函数 用于提出常数利于匹配规则
        if isinstance(node,ast.Constant): # 为一个常数
            if node.value == 0:
                return ast.Constant(value=0)
            return ast.BinOp(left=node, op=ast.Mult(), right=ast.Name(id=INTEGRAL_VAR, ctx=ast.Load()))
        if isinstance(node,ast.BinOp) and isinstance(node.op,(ast.Add,ast.Sub)): # 两个表达式相加或相减
            lhs = test_integral(node.left)
            rhs = test_integral(node.right)
            if lhs is None or rhs is None: # 到时候积不出来可以调库
                return None
            else:
                return ast.BinOp(left=lhs, op=node.op, right=rhs)
        if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Mult): # 两个表达式相乘 提出常数
            if isinstance(node.left,ast.Constant):
                rhs = test_integral(node.right)
                if rhs is None:
                    return None
                else:
                    return ast.BinOp(left=node.left, op=node.op, right=rhs)
            if isinstance(node.right,ast.Constant):
                lhs = test_integral(node.left)
                if lhs is None:
                    return None
                else:
                    return ast.BinOp(left=node.right, op=node.op, right=lhs)
        if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Div): # 两个表达式相除
            if isinstance(node.left,ast.Constant): # 分子为常数
                if node.left.value == 1: # 先解决1/x和1/(x**c)情况
                    if isinstance(node.right,ast.Name) and node.right.id == INTEGRAL_VAR: # 1/x
                        return ast.Call(ast.Name(id='log', ctx=ast.Load()), [ast.Name(id=INTEGRAL_VAR, ctx=ast.Load())], [])
                    if isinstance(node.right,ast.BinOp) and isinstance(node.right.op,ast.Pow): # 1/(x**c)
                        return test_integral(ast.BinOp(left=node.right.left,
                                                       op=ast.Pow(),
                                                       right=ast.UnaryOp(op=ast.USub(), operand=node.right.right) # x**(-c)
                                                       ))
                else:
                    rhs = test_integral(ast.BinOp(ast.Constant(value=1), ast.Div(), node.right))
                    if rhs is None:
                        return None
                    else:
                        return ast.BinOp(left=node.left,op=ast.Mult(),right=rhs) # 提出分子常数
            if isinstance(node.right,ast.Constant): # 分母为常数
                lhs = test_integral(node.left)
                if lhs is None:
                    return None
                else:
                    return ast.BinOp(left=ast.BinOp(left=ast.Constant(value=1), op=ast.Div(), right=node.right),op=ast.Mult(),right=lhs)
        return solver.try_rules(node)

    lst = []
    lst_name = [[] for _ in tests]

    for expr in tests:
        print("Original expression:",expr)
        orig_ast = solver.str_to_ast(expr)
        # 展示一个积分过程：
        # 看看能不能直接匹配
        try_res = test_integral(orig_ast)
        if try_res:
            print(f"Successfully solved: {solver.ast_to_str(try_res)}")
            lst.append(f"\\int {solver.str_to_latex(expr)} dx = {solver.ast_to_latex(try_res)} + C \\\\")
            continue

        # 尝试展开多项式
        ast_expr = solver.ast_expand(orig_ast)
        print("Expanded expression:",solver.ast_to_str(ast_expr))
        try_res = test_integral(ast_expr)
        if try_res:
            print(f"Successfully solved: {solver.ast_to_str(try_res)}")
            lst.append(f"\\int {solver.str_to_latex(expr)} dx = {solver.ast_to_latex(try_res)} + C \\\\")
            continue
        
        # 尝试分解分式
        ast_expr = solver.ast_apart(orig_ast)
        print("Aparted expression:",solver.ast_to_str(ast_expr))
        try_res = test_integral(ast_expr)
        if try_res:
            print(f"Successfully solved: {solver.ast_to_str(try_res)}")
            lst.append(f"\\int {solver.str_to_latex(expr)} dx = {solver.ast_to_latex(try_res)} + C \\\\")
            continue
        
        # 尝试化简
        ast_expr = solver.ast_cancel(orig_ast)
        print("Canceled expression:",solver.ast_to_str(ast_expr))
        try_res = test_integral(ast_expr)
        if try_res:
            print(f"Successfully solved: {solver.ast_to_str(try_res)}")
            lst.append(f"\\int {solver.str_to_latex(expr)} dx = {solver.ast_to_latex(try_res)} + C \\\\")
            continue

        # 那很没办法了
        print(f"CANNOT SOLVE: {expr}")

    for item in lst:
        print(item)
    
    print(f"Solved {len(lst)} of {len(tests)} expressions.")
