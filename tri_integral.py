import integral
solver = integral.IntegralSolver()
INTEGRAL_VAR = "x" 
import json
import ast
import astor
import sympy
#尝试展开，分解，化简，换元
#规则会大多数基于恒等变形 如：降次
tests = ["x*sin(x)",
         "sin(x)**2",
         "cos(x)**2",
         "sin(x)*cos(x)",
         "cos(2*x)**2",
         "tan(x)**2",
         ]
def check_tri_integral(expr):
    tri_functions = {"sin", "cos", "tan", "cot", "sec", "csc"}
    try:
        trees = ast.parse(expr, mode='eval')
    except SyntaxError:
        return False
    for node in ast.walk(trees):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in tri_functions:
                return True
            
    return False

class TriTransformation():
    def __init__(self):
        self.rules = json.load(open("triangle_transformation.json"))
        for rule in self.rules:
            rule["pattern"] = ast.parse(rule["pattern"], mode='eval').body
            rule["result"] = ast.parse(rule["result"], mode='eval').body

    def dfs(self,node):      #TODO 跟搜索方法有些差距
        for rules in self.rules:
            mapping = {}
            if self.match(rules["pattern"], node, mapping):
                print("Applying rule:", rules["name"])
                return self.replace(node, rules["result"], mapping)
        for field, value in ast.iter_fields(node):
            if isinstance(value, ast.AST):
                new_node = self.dfs(value)
                setattr(node, field, new_node)
            elif isinstance(value, list):
                new_list = []
                for item in value:
                    if isinstance(item, ast.AST):
                        new_list.append(self.dfs(item))
                    else:
                        new_list.append(item)
                setattr(node, field, new_list)

        return node

           
    def is_constant(self, node):
        if isinstance(node, ast.Constant):
            return True
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return self.is_constant(node.operand)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            return self.is_constant(node.left) and self.is_constant(node.right)
        return False

    def match(self,pattern,node,mapping_dict):
        """
        匹配一个模式
        原理:分别拿到模式的AST和节点的AST,递归比较
        如果有遇到变量,则构建mappin_list,记录变量的映射关系
        """
        if isinstance(pattern,ast.Name): # 模式要求一个变量名
            name = pattern.id
            if name == INTEGRAL_VAR: # 要求是积分变量x
                return isinstance(node,ast.Name) and node.id == INTEGRAL_VAR # 节点要求也是积分变量
            else: # 要求是一个常量（使用除了x以外的所有标识符指代的东西）
                # 检查节点是否是常数表达式
                if not self.is_constant(node):
                    return False  # 不是常数,匹配失败
                if name in mapping_dict: # 之前出现过这个标识符
                    return self.ast_equal(mapping_dict[name],node) # 则要求映射到的那个东西相同
                else: # 第一次出现这个标识符
                    mapping_dict[name] = node # 仅记录映射关系
                    return True
                
    def replace(self, result_expr, mapping):
        for key, val in mapping.items():
            result_expr = result_expr.replace(key, val)
        return ast.parse(result_expr, mode='eval').body

    def transform_expr(self, expr):
        try:
            tree = ast.parse(expr, mode='eval')
        except:
            return expr

        new_tree = self.dfs(tree.body)
        return astor.to_source(new_tree).strip()




def test_tri_integral(node, visited=None):

    if visited is None:
        visited = set()  # 初始化已访问节点集合

    # 检查是否已经访问过当前节点，防止无限递归
    if id(node) in visited:
        return None
    visited.add(id(node))  # 标记当前节点为已访问

    if isinstance(node, ast.Constant):  # 常数
        if node.value == 0:
            return ast.Constant(value=0)
        return ast.BinOp(
            left=node,
            op=ast.Mult(),
            right=ast.Name(id=INTEGRAL_VAR, ctx=ast.Load())
        )
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):  # 加法或减法
        lhs = test_tri_integral(node.left, visited)
        rhs = test_tri_integral(node.right, visited)
        if lhs is None or rhs is None:
            return None
        return ast.BinOp(left=lhs, op=node.op, right=rhs)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):  # 乘法
        if isinstance(node.left, ast.Constant):
            rhs = test_tri_integral(node.right, visited)
            if rhs is None:
                return None
            return ast.BinOp(left=node.left, op=node.op, right=rhs)
        if isinstance(node.right, ast.Constant):
            lhs = test_tri_integral(node.left, visited)
            if lhs is None:
                return None
            return ast.BinOp(left=node.right, op=node.op, right=lhs)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):  # 除法
        if isinstance(node.left, ast.Constant):  # 分子为常数
            if node.left.value == 1:  # 处理 1/x 和 1/(x**c)
                if isinstance(node.right, ast.Name) and node.right.id == INTEGRAL_VAR:
                    return ast.Call(
                        func=ast.Name(id='log', ctx=ast.Load()),
                        args=[ast.Name(id=INTEGRAL_VAR, ctx=ast.Load())],
                        keywords=[]
                    )
                if isinstance(node.right, ast.BinOp) and isinstance(node.right.op, ast.Pow):
                    return test_tri_integral(
                        ast.BinOp(
                            left=node.right.left,
                            op=ast.Pow(),
                            right=ast.UnaryOp(op=ast.USub(), operand=node.right.right)
                        ),
                        visited
                    )
            else:
                rhs = test_tri_integral(ast.BinOp(left=ast.Constant(value=1), op=ast.Div(), right=node.right), visited)
                if rhs is None:
                    return None
                return ast.BinOp(left=node.left, op=node.op, right=rhs)
        if isinstance(node.right, ast.Constant):  # 分母为常数
            lhs = test_tri_integral(node.left, visited)
            if lhs is None:
                return None
            return ast.BinOp(
                left=ast.BinOp(left=ast.Constant(value=1), op=ast.Div(), right=node.right),
                op=ast.Mult(),
                right=lhs
            )
    return solver.try_rules(node)  # 调用规则匹配


# 集成三角变换和积分
TriTransformer = TriTransformation()
lst = []
#lst_name = [[] for _ in tests]
for expr in tests:
    if check_tri_integral(expr):  
        orig_ast = solver.str_to_ast(expr)  
        transformed_expr = TriTransformer.transform_expr(expr)  # 三角变换，跟test_tri_integral函数有重复部分
        node = ast.parse(transformed_expr, mode="eval").body  # 解析变换后的表达式
        try_res = test_tri_integral(node)  # 尝试积分
        if try_res:
            print(f"Successfully solved: {solver.ast_to_str(try_res)}")
            lst.append(f"\\int {solver.str_to_latex(expr)} dx = {solver.ast_to_latex(try_res)} + C \\\\")
            continue
        else:
            print(f"Failed to solve: {expr}")

for i in lst:
    print(i)