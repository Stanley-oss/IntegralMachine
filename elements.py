import string
from math import gcd

class Expression(object):
  """
  抽象类,不实例化
  """
  def __init__(self):
    raise Exception("Expression is an abstract class")

  def reciprocal(self):
    return Fraction(Number(1), self)

  def simplified(self):
    return self

  def __eq__(self, other):
    """
    TODO Consider what this means.
         Are expressions equal that simplify to the same thing?
    """
    return self.__repr__() == other.__repr__()

  def __ne__(self, other):
    return not self.__eq__(other)

  def is_a(self, theclass):
    """ 
    Utility method to clean up strategies.
    Used like this
    x = Number(1)
    x.is_a(Number) -> True
    """
    return isinstance(self, theclass)

  def latex(self):
    """
    Convert an expression into its LaTeX representation
    for displaying.
    """
    raise Exception("latex not implemented for %s" % self)


class Number(Expression):
  """
  A basic element containg a single number.
  """
  def __init__(self, n):
    """
    Takes a single number `n` which is the value of this Number.
    """
    self.n = n

  def __repr__(self):
    return "{!r}".format(self.n)

  def latex(self):
    return "{!r}".format(self.n)


class VariableSet(object):
    def __init__(self):
        self.var_x = Variable(self)
        self.lookup = {self.var_x: 'x'}

    def variable(self, symbol=None):
        #返回唯一变量x，这里默认写出来的变量就是x了 也就是我们表达式仅用x字母
        return self.var_x

    def symbol_for(self, var):
        return self.lookup[var]

    def variable_for(self, symbol):
        if symbol == 'x':
            return self.var_x
        return None

class Variable(Expression):
    def __init__(self, vset):
        if not isinstance(vset, VariableSet):
            raise Exception('Variable instantiated without VariableSet')
        self.vset = vset

    def symbol(self):
        return self.vset.symbol_for(self)

    def __repr__(self):
        return "{0}".format(self.symbol())

    def latex(self):
        return "{0}".format(self.symbol())

class Sum(Expression):
  """
  An expression representing the sum of two sub-expressions.
  """
  def __init__(self, a, b):
    """
    a and b are the left and right operands of the sum 'a + b'.
    """
    self.a = a
    self.b = b

  #化简操作
  def simplified(self):
    a = self.a.simplified()
    b = self.b.simplified()
    #数字间操作
    if a.is_a(Number) and b.is_a(Number):
      return Number(a.n + b.n)
    else:
      return Sum(a, b)

  def __repr__(self):
    return "(%s + %s)" %(self.a, self.b)

  def latex(self):
    return "(%s + %s)" %(self.a.latex(), self.b.latex())


class Product(Expression):
  """
  An expression representing the product of two sub-expressions.
  """
  def __init__(self, a, b):
    """
    a and b are the left and right operands of the sum 'a + b'.
    """
    self.a = a
    self.b = b

  def simplified(self):
    a = self.a.simplified()
    b = self.b.simplified()
    # If both operands are numbers, then multiply their values.
    if a.is_a(Number) and b.is_a(Number):
      return Number(a.n * b.n)
    else:
      return Product(a, b)

  def __repr__(self):
    return "(%s * %s)" %(self.a, self.b)

  def latex(self):
    return "%s \cdot %s" %(self.a.latex(), self.b.latex())


class Fraction(Expression):
  """
  An expression representing a fraction.
  """
  def __init__(self, numr, denr):
    """
    Create the fraction (numr / denr).
    """
    self.numr = numr
    self.denr = denr

  def reciprocal(self):
    return Fraction(self.denr, self.numr)

  def simplified(self):
    numr = self.numr.simplified()
    denr = self.denr.simplified()

    if numr.is_a(Number) and denr.is_a(Number):
      this_gcd = gcd(numr.n, denr.n)
      numr = Number(numr.n / this_gcd)
      denr = Number(denr.n / this_gcd)

    if denr == Number(1):
      return numr
    else:
      return Fraction(numr, denr)

  def __repr__(self):
    return "(%s / %s)" %(self.numr, self.denr)

  def latex(self):
    return "\\frac{%s}{%s}" %(self.numr.latex(), self.denr.latex())


class Power(Expression):
  def __init__(self, base, exponent):
    """
    `base` to the power `exponent`.
    """
    self.base     = base
    self.exponent = exponent

  def simplified(self):
    base     = self.base.simplified()
    exponent = self.exponent.simplified()
    if base.is_a(Number) and exponent.is_a(Number):
      return Number(base.n ** exponent.n)
    else:
      return Power(base, exponent)

  def __repr__(self):
    return "(%s ^ %s)" %(self.base, self.exponent)

  def latex(self) :
    return "{%s}^{%s}" %(self.base.latex(), self.exponent.latex())


class Logarithm(Expression):
  def __init__(self, arg, base="euler"):
    """
    The logarithm base `base` of `arg`.
    """
    self.arg = arg
    self.base = base

  def simplified(self):
    return Logarithm(self.arg.simplified(), self.base)

  def __repr__(self):
    if self.base == "euler" :
      return "log(%s)" %(self.arg)
    else :
      return "log_(%s) %s" %(self.arg, self.base)

  def latex(self):
    if self.base == "euler" :
      return "\log{%s}" %(self.arg.latex())
    else :
      return "log_{%s}{%s}" %(self.arg.latex(), self.base.latex())


class Integral(Expression):
  """
  An expression represent a single integral.
  """
  def __init__(self, exp, var):
    """
    The integral of `exp` with respect to the variable `var`.
    """
    self.exp = exp
    self.var = var

  def simplified(self):
    return Integral(self.exp.simplified(), self.var.simplified())

  def __repr__(self):
    return "int[%s]d%s" %(self.exp, self.var)

  def latex(self):
    return "\\int{%s}\;d%s" %(self.exp.latex(), self.var.latex())

  