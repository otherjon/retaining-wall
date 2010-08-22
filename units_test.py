#!/usr/bin/python

import unittest
from units import Units

class UnitsTest(unittest.TestCase):
  def testInstantiation(self):
    u = Units('1.0 lb/ft^2', ndigits=1, as_latex=False)
    self.assertEqual(u.u['lb'], 1)
    self.assertEqual(u.u['ft'], -2)
    self.assertEqual(str(u), '1.0 lb / ft^2')

    u = Units('1 lb / ft^2', ndigits=2, as_latex=False)
    self.assertEqual(u.u['lb'], 1)
    self.assertEqual(u.u['ft'], -2)
    self.assertEqual(str(u), '1.00 lb / ft^2')

  def testMultiplication(self):
    u1 = Units('2 lb/ft^2', as_latex=False)
    u2 = Units('3 ft', as_latex=False)
    u3 = u1 * u2
    self.assertEqual(u3.u['lb'], 1)
    self.assertEqual(u3.u['ft'], -1)
    self.assertEqual(str(u3), '6.000 lb / ft')

    u1 = Units('5 lb/ft^2', ('lb', 'ft'), as_latex=False)
    u2 = Units('7.0 ft^3', as_latex=False)
    u3 = u1 * u2
    self.assertEqual(u3.u['lb'], 1)
    self.assertEqual(u3.u['ft'], 1)
    self.assertEqual(str(u3), '35.000 lb * ft')

    # test Units * float and float * Units
    self.assertEqual(str(u3 * 0.2), '7.000 lb * ft')
    self.assertEqual(str(0.2 * u3), '7.000 lb * ft')
    
  def testDivision(self):
    u1 = Units('224 lb/ft^2', as_latex=False)
    u2 = Units('2.24 lb/kg', as_latex=False)
    u3 = u1 / u2
    self.assertEqual(u3.u['kg'], 1)
    self.assertEqual(u3.u['ft'], -2)
    self.assertEqual(str(u3), '100.000 kg / ft^2')

    u1 = Units('10 mi / h', as_latex=False)
    u2 = Units('5280 ft / mi', as_latex=False)
    u3 = Units('3600 sec / h', as_latex=False)
    u4 = u1 * u2 / u3

    self.assertEqual(str(u4), '14.667 ft / sec')

    # test Units / float
    self.assertEqual(str(u4/2), '7.333 ft / sec')

    u1 = Units('0.9144 m / yd', as_latex=False)
    u2 = 1.0 / u1
    self.assertEqual(str(u2), '1.094 yd / m')
    
    
if __name__ == '__main__':
  unittest.main()
