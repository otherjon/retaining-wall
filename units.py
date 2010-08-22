#!/usr/bin/python

import math, re

class Error(Exception): pass


class Units(object):
  def __init__(self, data, unit_order=None, as_latex=True, **kwargs):
    """
    Input:
      data (str or Units object)
        (str) unit name, e.g. 'lb/ft^2' or 'L*atm/mol/K'
        (Units object) data to copy
      unit_order (list or tuple):
        ordered list containing unit names in the order they should be sorted
        for display
      ndigits (int): number of significant digits for display
    """
    ndigits = kwargs.get('ndigits', 3)
    self.as_latex = as_latex
    self.ndigits = ndigits
    self.unit_order = unit_order
    if unit_order is None:
      self.order_func = None
    else:
      # listed units sort in the order listed, unlisted units sort last
      self.order_func = lambda a: (
        a[0] in self.unit_order and (self.unit_order.index(a[0]), a[0]) or
        (len(self.unit_order), a[0]) )
      
    if isinstance(data, Units):
      if 'ndigits' in kwargs:
        self.ndigits = kwargs['ndigits']
      else:
        self.ndigits = data.ndigits
      self.u = data.u.copy()
      self.magnitude = data.magnitude
      self.unit_order = data.unit_order
      self.order_func = data.order_func
      self.as_latex = data.as_latex
    else:
      data = str(data)
      m = re.match('[-.0-9]+', data)
      self.magnitude = float(m.group(0))
      data = re.sub('\s', '', data[len(m.group(0)):])
      if not data:
        # dimensionless unit
        self.u = {}
        return
      
      terms = re.split(r'[/*]', data)
      operators = re.findall(r'[/*]', data)
      u = self.RootUnitAndExponent(terms[0])
      for i in range(len(operators)):
        term, op = terms[i+1], operators[i]
        thisunit = self.RootUnitAndExponent(term)
        if op == '/':
          for element in thisunit:
            thisunit[element] = -1 * thisunit[element]
        for element in thisunit:
          u.setdefault(element, 0)
          u[element] += thisunit[element]
      self.u = u

  def RootUnitAndExponent(self, s):
    """
    Input: s (str) = a single unit with optional exponent, e.g. "lb" or "ft^2"
    Output: a dictionary mapping unit names to exponents, e.g. {'ft': 2}
    """
    if s.find('^') == -1:
      return {s: 1}
    caret_position = s.find('^')
    unit = s[:caret_position]
    exponent = int(s[caret_position+1:])
    return {unit: exponent}

  def __float__(self):
    if self.u == {}:
      return self.magnitude
    raise Error("Can't evaluate dimensioned unit (%s) as a dimensionless float"
                % self)
  
  def __trunc__(self):
    if self.u == {}:
      return int(self.magnitude)
    raise Error("Can't evaluate dimensioned unit (%s) as a dimensionless int"
                % self)
  
  def __abs__(self):
    if self.u == {}:
      return abs(self.magnitude)
    raise Error("Can't take absolute value of dimensioned unit (%s)" % self)
  
  def __add__(self, other):
    if type(other) in (int, float) and self.u != {}:
      raise Error("Can't add raw numbers to dimensioned units (%s)" % self)
    result = self.__class__(self)
    if type(other) in (int, float):
      result.magnitude = self.magnitude + other
    else:
      if self.u != other.u:
        raise Error("Can't add units of different types (%s + %s)" %
                    (self, other))
      result.magnitude = self.magnitude + other.magnitude
    return result

  def __radd__(self, other):
    return self + other

  def __neg__(self):
    result = self.__class__(self)
    result.magnitude = -result.magnitude
    return result
  
  def __sub__(self, other):
    return self + (-other)
    
  def __rsub__(self, other):
    return -self + other
    
  def __rmul__(self, other):
    return self * other

  def __mul__(self, other):
    order = self.unit_order
    ndigits = self.ndigits
    if order is None and isinstance(other, Units):
      order = other.unit_order
    result = self.__class__(self, unit_order=order)
    if isinstance(other, Units):
      result.ndigits = max(result.ndigits, other.ndigits)
      result.magnitude = self.magnitude * other.magnitude
      for element in other.u:
        result.u.setdefault(element, 0)
        result.u[element] += other.u[element]
        if result.u[element] == 0:
          del result.u[element]
    else:
      result.magnitude = self.magnitude * other
    return result

  def __pow__(self, other):
    if type(other) is not int:
      raise Error("Can't raise units to non-integer power (%s)" % other)
    result = self.__class__(self)
    result.magnitude = self.magnitude ** other
    for unit in result.u:
      result.u[unit] *= other
    return result
    
  def __div__(self, other):
    if type(other) in (int, float):
      # Units-object / 2.0
      result = self.__class__(self)
      result.magnitude = self.magnitude / other
      return result

    # Both self and other are Units-objects
    order = self.unit_order
    ndigits = self.ndigits
    if order is None:
      order = other.unit_order
    result = self.__class__(self,  unit_order=order)
    result.ndigits = max(result.ndigits, other.ndigits)
    result.magnitude = self.magnitude / other.magnitude
    for element in other.u:
      result.u.setdefault(element, 0)
      result.u[element] -= other.u[element]
      if result.u[element] == 0:
        del result.u[element]
    return result

  def __rdiv__(self, other):
    if type(other) in (int, float):
      # 1.0 / Units-object
      result = self.__class__(self)
      result.magnitude = float(other) / self.magnitude
      for unit, exponent in result.u.items():
        result.u[unit] = -exponent
      return result

  def __gt__(self, other):
    if len(self.u) == 0:
      return self.magnitude > other
    if not isinstance(other, Units):
      raise Error("Can't compare dimensioned units (%s) with dimensionless "
                  "number (%s)" % (self, other))
    if self.u != other.u:
      raise Error("Can't compare units of different dimensions (%s vs. %s)" %
                  (self, other))
    return self.magnitude > other.magnitude

  def __ge__(self, other):
    if len(self.u) == 0:
      return self.magnitude >= other
    if not isinstance(other, Units):
      raise Error("Can't compare dimensioned units (%s) with dimensionless "
                  "number (%s)" % (self, other))
    if self.u != other.u:
      raise Error("Can't compare units of different dimensions (%s vs. %s)" %
                  (self, other))
    return self.magnitude >= other.magnitude

  def __lt__(self, other):
    return not (self >= other)
  def __le__(self, other):
    return not (self > other)

  def __str__(self):
    pos, neg = {}, {}
    for k in self.u:
      if self.u[k] > 0:
        pos[k] = self.u[k]
      elif self.u[k] < 0:
        neg[k] = -1 * self.u[k]
      else:
        pass

    numerator_elts, denominator_elts = [], []
    for element in pos:
      exponent = ''
      if pos[element] != 1:
        exponent = '^%d' % pos[element]
      if self.as_latex:
        if exponent:
          numerator_elts.append((element, r'\mbox{%s} \ensuremath{{\!}%s}' %
                                 (element, exponent)))
        else:
          numerator_elts.append((element, r'\mbox{%s}' % element))
      else:
        numerator_elts.append((element, '%s%s' % (element, exponent)))
    for element in neg:
      exponent = ''
      if neg[element] != 1:
        exponent = '^%d' % neg[element]
      if self.as_latex:
        if exponent:
          denominator_elts.append((element, r'\mbox{%s} \ensuremath{{\!}%s}' %
                                   (element, exponent)))
        else:
          denominator_elts.append((element, r'\mbox{%s}' % element))
      else:
        denominator_elts.append((element, '%s%s' % (element, exponent)))
    # sort numerator_elts and denominator_elts by self.unit_order
    numerator_elts.sort(key=self.order_func)
    denominator_elts.sort(key=self.order_func)

    mag_str = ('%.' + str(self.ndigits) + 'f') % self.magnitude
    if self.as_latex:
      separator = r'\,'
    else:
      separator = ''
    if denominator_elts:
      return '%s%s %s / %s' % (mag_str, separator,
        ' * '.join([data for sortkey, data in numerator_elts]),
        ' / '.join([data for sortkey, data in denominator_elts]))
    else:
      return '%s%s %s' % (mag_str, separator,
        ' * '.join([data for sortkey, data in numerator_elts]))

class Degrees(Units):
  def __init__(self, deg, ndigits=1, **kwargs):
    self.u = {}
    self.unit_order = None
    self.order_func = None
    if isinstance(deg, Degrees):
      self.degrees = deg.degrees
      self.ndigits = deg.ndigits
    elif type(deg) in (int, float):
      self.degrees = deg
      self.ndigits = ndigits
    else:
      raise Error("Can't initialize degrees with type %s" %
                  deg.__class__.__name__)
    self.magnitude = self.degrees

  def __float__(self):
    return self.radians()

  def radians(self):
    return math.pi * self.magnitude / 180.0

  def __str__(self):
    if abs(int(self.magnitude) - self.magnitude) < .0001:
      return r'\ensuremath{%d ^{\circ}}' % self.magnitude
    return ((r'\ensuremath{%.' + str(self.ndigits) + 'f ^{\circ}}') %
            self.magnitude)

  def __add__(self, other):
    value = self.magnitude
    if type(other) is float:
      value += 180.0 / math.pi * other
    elif isinstance(other, Degrees):
      value += other.magnitude
    else:
      raise Error("Can't add '%s' to 'Degrees'" % other.__class__.__name__)
    return Degrees(value)

  def __neg__(self):
    return Degrees(-1.0 * self.magnitude)
