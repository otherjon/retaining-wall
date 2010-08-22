#!/usr/bin/python

"""
Segmental retaining wall (SRW) analysis tools.

Author: Jon Snitow  (github: otherjon or otherjonvb)
Author: Victor Shnayder
Date: 2010-08-11W
"""

from math import *
import re, os, sys, time

from units import Degrees, Units

class Error(Exception): pass

def ordinal(n):
  """
  Args: n (int) - any integer (or anything convertible to an integer)
  Returns: the ordinal (e.g. 0th, 3rd, 22nd, 101st) corresponding to n
  """
  last_digit = abs(int(n)) % 10    # "-1st", even though -1 % 10 == 9
  if last_digit == 0 or last_digit > 3: return "%sth" % int(n)
  if (n % 100) / 10 == 1:
    return "%sth" % int(n)   # 11th, 12th, 13th
  if last_digit == 1: return "%sst" % int(n)
  if last_digit == 2: return "%snd" % int(n)
  if last_digit == 3: return "%srd" % int(n)

def LatexHeader(config):
  with open(MakeAbsPath(config, "PlansTextFile")) as f:
    contents = f.read()
    plans_text_dict = {}
    exec(contents, plans_text_dict)
    del plans_text_dict['__builtins__']
  return plans_text_dict['LATEX_HEADER'] % plans_text_dict['LATEX_HEADER_VARS']

def LatexFooter(config):
  with open(MakeAbsPath(config, "PlansTextFile")) as f:
    contents = f.read()
    plans_text_dict = {}
    exec(contents, plans_text_dict)
    del plans_text_dict['__builtins__']
  return plans_text_dict['LATEX_FOOTER'] % plans_text_dict['LATEX_FOOTER_VARS']


PARAMS_BY_CATEGORY = [
  ('Design Parameters',  [
      'H', 'D', 'B_b', 'd_b', 'L_g', 'q', 'FOS_sliding', 'FOS_overturning',
      'FOS_bearing', 'FOS_ultimate', 'FOS_rupture',
      'FOS_pullout',
      ]),
  ('Materials Parameters', [
      'block_depth', 'block_length', 'block_height', 'L_s', 'gamma_wall',
      'geogrid_X', 'geogrid_Y',
      ]),
  ('Environment Parameters', [
      'phi_r', 'phi_i', 'gamma_r', 'gamma_i', 'cohesion_r', 'cohesion_i', 
      'cohesion_f', 'beta', 'i', 'sigma_allowed',
      ]),
  ]

LATEX_ADDENDA_BY_PARAM_CATEGORY = {
  'Design Parameters': r"""

\vspace{3mm}
\noindent Wall height (%(H)s) $\div$ block
  height (%(block_height)s) = %(n_courses)s courses of blocks \\[1mm]
Geogrid above the following courses (numbered from the bottom):
  %(ordinal_geogrid_levels_str)s

""",
  }

PARAMS_DESCRIPTIONS_AND_LATEX = {
  # map of variable name to human-readable description and LaTeX markup
  #  of variable name (or leave off the latter to have the LaTeX markup
  #  be equal to the variable name)
  'H'  : ('total height of wall including buried portion',),
  'D'  : ('vertical depth of wall embedment (buried blocks + footing thickness)',),
  'B_b': ('width of footing',),
  'd_b': ('thickness of footing',),
  'L_g': ('length of geogrid',),
  'q'  : ('surcharge pressure at top of wall',),
  'FOS_sliding'    : ('desired factor of safety for failure by sliding',
                      'FOS_{sliding}'),
  'FOS_overturning': ('desired factor of safety for failure by overturning',
                      'FOS_{overturning}'),
  ## 'FOS_ICS'        : ('desired factor of safety for internal compound '
  ##                     'stability failure', 'FOS_{ICS}'),
  ## 'FOS_global'     : ('desired factor of safety for global stability failure',
  ##                     'FOS_{global}'),
  'FOS_bearing'    : ('desired factor of safety for bearing pressure failure',
                      'FOS_{bearing}'),
  'FOS_ultimate'   : ('desired factor of safety for ultimate bearing failure',
                      'FOS_{ultimate}'),
  'FOS_rupture'  : ('desired factor of safety for grid rupture failure',
                      'FOS_{rupture}'),
  'FOS_pullout'  : ('desired factor of safety for grid pullout failure',
                      'FOS_{pullout}'),
  'block_depth'  : ('depth of a single segmental block', 'D_{block}'),
  'block_length' : ('length of a single segmental block', 'L_{block}'),
  'block_height' : ('height of a single segmental block', 'H_{block}'),
  'L_s'          : ('distance from end of geogrid to front of block',),
  'gamma_wall'   : ('unit weight of wall blocks', r'\gamma_{wall}'),
  'geogrid_X'    : ('constant component of geogrid strength', r'X_{geogrid}'),
  'geogrid_Y'    : ('component of geogrid strength proportional to normal force',
                    r'Y_{geogrid}'),
  'phi_r'        : ('friction angle of retained soil', r'\phi_r'),
  'phi_i'        : ('friction angle of infill soil', r'\phi_i'),
  'gamma_r'      : ('unit weight of retained soil', r'\gamma_r'),
  'gamma_i'      : ('unit weight of infill soil', r'\gamma_i'),
  'cohesion_r'   : ('retained soil cohesion', 'c_r'),
  'cohesion_i'   : ('infill soil cohesion', 'c_i'),
  'cohesion_f'   : ('foundation soil cohesion', 'c_f'),
  'beta' : (r'angle between retaining wall and level (equal to '
            '\ensuremath{90^{\circ}} - battering angle)', r'\beta'),
  'i'    : ('slope at top of retaining wall',),
  'sigma_allowed': ('allowed bearing pressure on undisturbed soil',
                    r'\sigma_{allowed}'),
  }

class InputParams(object):
  def __init__(self, datadict):
    errors = []
    self.__dict__.update(datadict)
    for category, params_list in PARAMS_BY_CATEGORY:
      for pname in params_list:
        if not hasattr(self, pname):
          errors.append('Parameter "%s" not provided' % pname)
    if errors:
      raise Error('Missing parameters from input dictionary:\n%s' %
                  '\n'.join(errors))
    self.ParamsSanityCheck()
    self.update(self.DerivedData())

  def ParamsSanityCheck(self):
    errors = []
    n_courses = int(0.5 + self.H / self.block_height)
    discrepency = n_courses * self.block_height - self.H
    if abs(discrepency.magnitude) > 1e-5:
      errors.append(' * wall height (%s) not an integer multiple of '
                    'block height (%s)' % (self.H, self.block_height))
    self.update({'n_courses': n_courses})
    bad_geogrid_levels = [ i for i in self.geogrid_levels if i > n_courses ]
    if bad_geogrid_levels:
      errors.append(' * some geogrid levels (%s) outside all courses '
                    ' of blocks (%s)' % (bad_geogrid_levels, n_courses))
    if errors:
      raise Error('Param sanity check failed:\n%s' % '\n'.join(errors))

  def __str__(self):
    retval = r'\section{Input Parameters}' + '\n\n'
    for category, params_list in PARAMS_BY_CATEGORY:
      retval += ('\n\n\\vspace{4mm} \\noindent \\textbf{%s} \\\\[2mm]\n'
                 '\\( \\begin{array}{rcll}\n' % category)
      for pname in params_list:
        desc_tuple = PARAMS_DESCRIPTIONS_AND_LATEX[pname]
        if len(desc_tuple) == 2:
          key_latex = desc_tuple[1]
        else:
          key_latex = pname
        description = desc_tuple[0]
        retval += '%s &=& %s & \mbox{(%s)} %s \n' % (
          key_latex, self.__dict__[pname], description, r'\\')
      retval += r'\end{array} \)'

      if category in LATEX_ADDENDA_BY_PARAM_CATEGORY:
        retval += LATEX_ADDENDA_BY_PARAM_CATEGORY[category] % self.__dict__

    retval += r"""

\vspace{6mm} \section{Derived Parameter Values}

$X_{batt}$, battering offset, equal to the horizontal distance from the toe
of the wall to the top of the wall:
\begin{eqnarray*}
X_{batt} &=& H \tan (90^{\circ} - \beta) \quad = ~ %(H)s \cdot \tan
  (90^{\circ} - %(beta)s) \quad = ~ %(X_batt)s
\end{eqnarray*}

%% $K_0$, at-rest pressure coefficient, calculated for both retained and infill
%%  soils:
%% \begin{eqnarray*}
%% K_{0r} &=& 1 - \sin \phi_r \quad = ~ 1 - \sin %(phi_r)s \quad = ~ %%(K_0r)s \\
%% K_{0i} &=& 1 - \sin \phi_i \quad = ~ 1 - \sin %(phi_i)s \quad = ~ %%(K_0i)s
%% \end{eqnarray*}
%% 
$\phi_w$, direction of resultant force of soil pressure, calculated for
  both infill and retained soil.  Since the infill soil is compacted,
  $\phi_{w}$ is significantly less than $\phi$:
\begin{eqnarray*}
\phi_{wi} &=& 0.66 \cdot \phi_i \quad = ~ %(phi_wi)s \\
\phi_{wr} &=& 0.66 \cdot \phi_r \quad = ~ %(phi_wr)s
\end{eqnarray*}

$\phi_f$ and $\gamma_f$ (values for foundation soil) are assumed equal to
 $\phi_r$ and $\gamma_r$:
\begin{eqnarray*}
\phi_f &=& \phi_r \quad = ~ %(phi_f)s \\
\gamma_f &=& \gamma_r \quad = ~ %(gamma_f)s
\end{eqnarray*}
    
$K_a$, active pressure coefficient, calculated for both retained and infill
 soils:
\begin{eqnarray*}
K_{ar} &=& \left( \frac{\mbox{csc } \beta \cdot \sin(\beta - \phi_r)}{
      \sqrt{\sin(\beta + \phi_{wr})} + \sqrt{\sin (\phi_r + \phi_{wr})
      \cdot \sin(\phi_r - i) / \sin(\beta - i)} } \right)^2 \\
  &=& \left( \frac{ %(csc_beta).3f \cdot \sin(%(beta)s - %(phi_r)s)}{
      \sqrt{\sin(%(beta)s + %(phi_wr)s)} + \sqrt{\sin (%(phi_r)s + %(phi_wr)s)
      \cdot \sin(%(phi_r)s - %(i)s) \div \sin(%(beta)s - %(i)s)} } \right)^2 \\
  &=& %(K_ar)s \\[2mm]
%%
K_{ai} &=& \left( \frac{\mbox{csc } \beta \cdot \sin(\beta - \phi_i)}{
      \sqrt{\sin(\beta + \phi_{wi})} + \sqrt{\sin (\phi_i + \phi_{wi})
      \cdot \sin(\phi_i - i) / \sin(\beta - i)} } \right)^2 \\
  &=& \left( \frac{ %(csc_beta).3f \cdot \sin(%(beta)s - %(phi_i)s)}{
      \sqrt{\sin(%(beta)s + %(phi_wi)s)} + \sqrt{\sin (%(phi_i)s + %(phi_wi)s)
      \cdot \sin(%(phi_i)s - %(i)s) \div \sin(%(beta)s - %(i)s)} } \right)^2 \\
  &=& %(K_ai)s
\end{eqnarray*}

$F_a$, magnitude of net force of active pressure:
\begin{eqnarray*}
F_a &=& 0.5 \cdot \gamma_r \cdot K_{ar} \cdot H^2 \\
 &=&  0.5 \cdot %(gamma_r)s \cdot %(K_ar)s \cdot (%(H)s)^2 \quad = ~ %(F_a)s
\end{eqnarray*}
    
Horizontal and vertical components of the active pressure force:
\begin{eqnarray*}
F_{ah} &=& F_a \cos \phi_{wr} \quad = ~ %(F_a)s \cdot \cos %(phi_wr)s
   \quad = ~ %(F_ah)s \\
F_{av} &=& F_a \sin \phi_{wr} \quad = ~ %(F_a)s \cdot \sin %(phi_wr)s
   \quad = ~ %(F_av)s
\end{eqnarray*}

Horizontal and vertical distances from toe of wall to point where resultant
  earth pressure force acts (along the back edge of the soil mass):
\begin{eqnarray*}
x_{F-active} &=& L_t + \frac{X_{batt}}{3} \quad = ~ %(L_t)s +
 \frac{%(X_batt)s}{3} \quad = ~ %(x_F_active)s \\[3mm]
y_{F-active} &=& H/3 \quad = ~ %(H)s / 3 \quad = ~ %(y_F_active)s
\end{eqnarray*}

Horizontal and vertical components of the surcharge force, along a unit length
of the wall:
\begin{eqnarray*}
F_{qh} &=& K_{ai} \cdot q \cdot \cos \phi_{wi} \cdot H \quad = ~
   %(K_ai)s \cdot %(q)s \cdot \cos %(phi_wi)s \cdot %(H)s
   \quad = ~ %(F_qh)s \\
F_{qv} &=& K_{ai} \cdot q \cdot \sin \phi_{wi} \cdot H \quad = ~
   %(K_ai)s \cdot %(q)s \cdot \sin %(phi_wi)s \cdot %(H)s
   \quad = ~ %(F_qv)s
\end{eqnarray*}

Horizontal and vertical distances from toe of wall to point where resultant
  surcharge force acts (along the back edge of the soil mass):
\begin{eqnarray*}
x_{F-surcharge} &=& L_g + \frac{X_{batt}}{2} \quad = ~%(L_g)s + \frac{%(X_batt)s}{2} \quad = ~%(x_F_surcharge)s \\[3mm]
y_{F-surcharge} &=& H/2 \quad = ~ %(H)s / 2 \quad = ~ %(y_F_active)s
\end{eqnarray*}

%% Volume of a segmental block:
%% \begin{eqnarray*}
%% V_{block} &=& L_{block} \cdot D_{block} \cdot H_{block} \\
%%   &=& %(block_length)s \cdot %(block_depth)s \cdot %(block_height)s
%%  \quad = ~ %%(block_volume)s
%% \end{eqnarray*}

Weight of a unit length of the wall face:
\begin{eqnarray*}
W_f &=& \gamma_{wall} \cdot H \cdot D_{block} \\
 &=& %(gamma_wall)s \cdot%(H)s \cdot %(block_depth)s \quad = ~ %(W_f)s
\end{eqnarray*}

Coefficient of friction for infill and retained soil:
\begin{eqnarray*}
C_{fi} &=& \tan \phi_i \quad = ~ \tan %(phi_i)s \quad = ~ %(C_fi)s \\
C_{fr} &=& \tan \phi_r \quad = ~ \tan %(phi_r)s \quad = ~ %(C_fr)s
\end{eqnarray*}

Weight of a unit length of the reinforced soil mass:
\begin{eqnarray*}
W_s &=& \gamma_i \cdot H \cdot (L_g - D_{block} + L_s) \\
 &=& %(gamma_i)s \cdot %(H)s \cdot (%(L_g)s - %(block_depth)s + %(L_s)s)
  \quad = ~ %(W_s)s
\end{eqnarray*}

Horizontal distance from toe of wall to point where resultant weight acts.
Computed as the soil's center of mass times the soil's x-offset plus the
wall face's center of mass times the wall face's x-offset, divided by the
sum of the two weights.
\begin{eqnarray*}
CM_x &=& \frac{W_s \cdot (\frac{X_{batt}}{2} + D_{block} + \frac{L_g + L_s -
            D_{block}}{2}) + W_f \cdot (\frac{X_{batt}}{2} +
            \frac{D_{block}}{2})}{W_s + W_f}\\
 &=& \frac{%(W_s)s \cdot (\frac{%(X_batt)s}{2} + %(block_depth)s + \frac{%(L_g)s
            + %(L_s)s - %(block_depth)s)}{2}) + %(W_f)s \cdot (\frac{%(X_batt)s
            }{2} + \frac{%(block_depth)s}{2})}{%(W_s)s + %(W_f)s}
 \quad = ~ %(CM_x)s
\end{eqnarray*}
    
Total horizontal depth of reinforced soil mass (soil depth plus block depth)
\begin{eqnarray*}
L_t &=& L_g + L_s \quad = ~ %(L_g)s + %(L_s)s \quad = ~ %(L_t)s
\end{eqnarray*}

Total weight of a unit length of wall and its soil mass:
\begin{eqnarray*}
W_w &=& W_f + W_s \quad = ~ %(W_f)s + %(W_s)s \quad = ~ %(W_w)s
\end{eqnarray*}

Total vertical force exerted on underlying soil:
\begin{eqnarray*}
V_t = W_w + F_{av} + F_{qv} \quad = ~ %(W_w)s + %(F_av)s + F_{qv}
   \quad = ~ %(V_t)s
\end{eqnarray*}
""" % self.__dict__
    return retval
        
  def update(self, newdict):
    """Add the new or updated params given in newdict to this instance."""
    self.__dict__.update(newdict)
    
  @staticmethod
  def FromFile(filename):
    """Read input file and return an InputParams object given by the file's
    contents.  File format is plain Python (it will be eval'd -- no funny
    business, you joker), containing a dictionary variable named "params"
    containing everything you'd pass to the constructor.  Comments etc. are
    allowed, of course."""
    with open(filename) as f:
      contents = f.read()
      context = {}
      exec(contents, context)

    if 'params' not in context:
      raise Error("'params' variable not defined in file %s" % filename)
    return InputParams(context['params'])

  def DerivedData(self):
    d = {}

    d['ordinal_geogrid_levels_str'] = ', '.join(
      [ordinal(i) for i in self.geogrid_levels])

    # X_batt = battering offset, i.e. horizontal distance from toe of wall
    # to top of wall
    d['X_batt'] = self.H / tan(self.beta)

    # Total horiz. depth of reinforced soil mass (soil depth + block depth)
    d['L_t'] = self.L_g + self.L_s

    ## # K_0 = at-rest pressure coefficient, calculated for both retained and
    ## #  infill soils
    ## d['K_0r'] = 1 - sin(self.phi_r)
    ## d['K_0i'] = 1 - sin(self.phi_i)

    # phi_w = direction of resultant force of soil pressure, calculated for
    #  both infill and retained soil.  Since the infill soil is compacted,
    #  phi_wi is significantly less than phi_i.
    d['phi_wi'] = 0.66 * self.phi_i
    d['phi_wr'] = 0.66 * self.phi_r

    # phi_f and gamma_f (foundation soil) assumed equal to phi_r and gamma_r
    d['phi_f'] = self.phi_r
    d['gamma_f'] = self.gamma_r
    
    # K_a = active pressure coefficient, calculated for both retained and
    #  infill soils
    d['csc_beta'] = 1.0 / sin(self.beta)
    d['K_ar'] = Units( (
      (d['csc_beta'] * sin(self.beta - self.phi_r)) /
      ( (sqrt(sin(self.beta + d['phi_wr']))) + sqrt(
            sin(self.phi_r + d['phi_wr']) * sin(self.phi_r - self.i) /
            sin(self.beta - self.i) )
        ) )**2, ndigits=4)
    d['K_ai'] = Units( (
      (d['csc_beta'] * sin(self.beta - self.phi_i)) /
      ( (sqrt(sin(self.beta + d['phi_wi']))) + sqrt(
            sin(self.phi_i + d['phi_wi']) * sin(self.phi_i - self.i) /
            sin(self.beta - self.i) )
        ) )**2, ndigits=4)

    # Magnitude of net force of active pressure
    d['F_a'] = Units(0.5 * self.gamma_r * d['K_ar'] * (self.H ** 2), ndigits=1)
    
    # Horizontal and vertical components of the active pressure force
    d['F_ah'] = d['F_a'] * cos(d['phi_wr'])
    d['F_av'] = d['F_a'] * sin(d['phi_wr'])

    # Distances from toe of wall where {resultant horizontal and vertical
    # components of the active earth pressure force} appear to act.  Earth
    # pressure is linear with depth, so drawing the magnitude of the force
    # at each depth creates a triangle of force, so the resultant is at the
    # triangle's center of mass.  (A triangle's center of mass is 1/3 of the
    # way up.)  It acts along the back edge of the retained soil mass.
    d['x_F_active'] = (d['L_t'] + d['X_batt'] / 3.0)
    d['y_F_active'] = self.H / 3.0
    
    # Horizontal and vertical components of the resultant surcharge pressure
    # per unit length of wall.
    # (Assuming surcharge pressure is constant with depth, the resultant
    # force is vertically centered along the wall.)
    d['F_qh'] = self.q * d['K_ai'] * self.H * cos(d['phi_wi'])
    d['F_qv'] = self.q * d['K_ai'] * self.H * sin(d['phi_wi'])

    # Distances from toe of wall where {resultant horizontal and vertical
    # components of the surcharge} appear to act.  Like the resultant active
    # earth pressure force, the resultant surcharge also acts along the back
    # edge of the retained soil mass.
    d['x_F_surcharge'] = (self.L_g + d['X_batt'] / 2.0)
    d['y_F_surcharge'] = self.H / 2.0

    # Distances from toe of wall where { resultant horizontal and vertical
    # components of the total force (active pressure + surcharge)} appear to act
    d['x_F_total'] = (d['x_F_active'] * d['F_ah'] +
                      d['x_F_surcharge'] * d['F_qh']) / (d['F_ah'] + d['F_qh'])
    d['y_F_total'] = (d['y_F_active'] * d['F_av'] +
                      d['y_F_surcharge'] * d['F_qv']) / (d['F_av'] + d['F_qv'])
    
    ## # Volume of a segmental block
    ## d['block_volume'] = (self.block_length * self.block_depth *
    ##                       self.block_height)

    # Weight of a unit length of the wall face
    d['W_f'] = self.gamma_wall * self.H * self.block_depth

    # Coefficient of friction for infill and retained soil
    d['C_fi'] = Units(tan(self.phi_i), ndigits=4)
    d['C_fr'] = Units(tan(self.phi_r), ndigits=4)

    # Weight of a unit length of the reinforced soil mass
    d['W_s'] = self.gamma_i * self.H * (self.L_g - self.block_depth + self.L_s)

    # Horizontal distance from toe of wall where resultant weight acts
    # Approximately equal to the center of mass of the parallelogram of soil
    #  and wall, if the difference in density between wall and soil is
    #  negligible.
    d['CM_x'] = ( d['W_s'] * ( d['X_batt']/2 + self.block_depth + (
                  self.L_g + self.L_s - self.block_depth) / 2 ) +
                  d['W_f'] * ( d['X_batt']/2 + self.block_depth/2) ) / (
                  d['W_s'] + d['W_f'])
    
    # Total weight of a unit length of wall and its soil mass
    d['W_w'] = d['W_f'] + d['W_s']

    # Total vertical force exerted on underlying soil
    d['V_t'] = d['W_w'] + d['F_av'] + d['F_qv']
    
    return d

  def Assumptions(self):
    return """
    Coefficient of friction is equal to tan(\phi).
"""

  def Show(self):
    return '\n'.join(["%s = %s" % (k,v) for k,v in sorted(self.__dict__.items())])


class FailureAnalysis(object):
  def __init__(self, params):
    """
    params: object of type InputParams

    Note that self.name will be set to the class name (with spaces inserted
      before capital letters), and the desired factor of safety will be
      extracted from the params variable.  Params must include a key with
      the name FOS_foo where foo is the lower-cased first word of the class
      name.  (E.g., if this weren't an abstract base class, params would need
      a key named "FOS_failure".)  The factor of safety is the ratio of the
      forces resisting failure over forces causing failure; the *desired*
      FOS is presumably > 1.0.)
    """
    self.params = InputParams(params.__dict__.copy())
    self.ExtractVariablesFromClassName()
    self.params.update(self.DerivedParams())
    self.params.update({
        'actual_fos' : self.ActualFactorOfSafety(),
        'desired_fos' : self.desired_fos,
        })
    self.params.update({
        'fos_box' : self.FOSLatexBox(),
        })

  def ExtractVariablesFromClassName(self):
    classname = self.__class__.__name__
    self.name = re.sub('([a-z])([A-Z])', r'\1 \2', classname)
    firstword = re.sub('([a-z])[A-Z].*', r'\1', classname).lower()
    self.desired_fos = getattr(self.params, 'FOS_%s' % firstword)
    
  def DerivedParams(self):
    return {}

  def SafetyCheck(self):
    """
    Returns (status, messages)
      status: boolean, true iff safety check passes
      messages: string (possibly empty) which should be printed for user
    """
    if self.params.actual_fos < self.desired_fos:
      return (False, '%s: FOS outside spec (desired: %.2f, actual: %.2f)' % (
          self.name, self.desired_fos, self.params.actual_fos))
    return (True, '%s: Passed (desired FOS: %.2f, actual: %.2f)' % (
        self.name, self.desired_fos, self.params.actual_fos))
    
  def ActualFactorOfSafety(self):
    return self.ForcesResistingFailure() / self.ForcesCausingFailure()

  def FOSLatexBox(self):
    if self.params.actual_fos >= self.desired_fos:
      return r"""\begin{center}
\textcolor{green}{\fbox{
%(actual_fos)s $\geq$ %(desired_fos)s \checkmark
}}
\end{center}""" % self.params.__dict__
    else:
      return r"""\begin{center}
\textcolor{red}{\fbox{
%(actual_fos)s $<$ %(desired_fos)s
}}
\end{center}""" % self.params.__dict__
    
  def ForcesCausingFailure(self):
    raise Error("Must be implemented in subclass")

  def ForcesResistingFailure(self):
    raise Error("Must be implemented in subclass")

  def __str__(self):
    return ("\n\section{%s}\n\n%s write-up not yet implemented.\n\n" %
            (self.name, self.name))


class SlidingAnalysis(FailureAnalysis):
  """
  Reference: Allan Block Engineering Manual, starting at page 22
  Reference: http://www.allanblock.com/Literature/PDF/EngManual.pdf
  """

  def DerivedParams(self):
    d = {}
    params = self.params

    # Sliding force: horizontal active pressure + horizontal surcharge
    d['F_s'] = self.params.F_ah + self.params.F_qh

    # Resisting force: Total vertical force times coeffient of friction
    #   (live load surcharges can't help resist failure -- dead load value
    #    would be C_fi * F_qv)
    d["F_r"] = (params.W_w + params.F_av) * params.C_fi

    return d 

  def ForcesCausingFailure(self):
    return self.params.F_s

  def ForcesResistingFailure(self):
    return self.params.F_r

  def __str__(self):
    return r"""
\section{Sliding Failure Analysis}

\noindent \textbf{Forces causing sliding} \\[2mm]
The sliding forces on the wall are (1) the horizontal component of the active
earth pressure, and (2) the horizontal component of the surcharge.  Using
the values computed above (see ``Derived Parameters''), the total sliding
force $F_s$ on the wall is: \\
\[ F_s = F_{ah} + F_{qh} = %(F_ah)s + %(F_qh)s = %(F_s)s \]

\vspace{5mm}
\noindent \textbf{Forces resisting sliding} \\[2mm]
The only force on the wall which resists sliding is the friction against the
soil mass:
\[ F_r = C_fi \cdot (W_w + F_{av}) = %(C_fi)s \cdot (%(W_w)s + %(F_av)s)
  = %(F_r)s \]

\vspace{5mm}
\noindent \textbf{Factor Of Safety} \\
Factor of safety (FOS) = %(F_r)s $\div$ %(F_s)s = %(actual_fos)s \\
Design specification FOS = %(desired_fos)s
%(fos_box)s
""" % self.params.__dict__
  

class OverturningAnalysis(FailureAnalysis):
  """
  Reference: Allan Block Engineering Manual, starting at page 24
  Reference: http://www.allanblock.com/Literature/PDF/EngManual.pdf
  """

  def DerivedParams(self):
    d = {}
    params = self.params

    # sum of moments resisting overturning, given as force * moment-arm
    #  * weight of wall face:
    #      W_f * (block midpoint + 0.5*X_batt)
    #  * weight of reinforced soil:
    #      W_s * (geogrid midpoint + block depth + 1/2 * X_batt)
    #  * vertical component of active force:
    #      F_av * (distance to back of soil mass + 1/3 * X_batt)
    #  * vertical component of surcharge force:
    #      F_qv * (distance to back of soil mass + 1/2 * X_batt)
    d["sumM_r"] = (
      params.W_f * 0.5 * (params.block_depth + params.X_batt)
      + params.W_s * (0.5 * (params.L_t - params.block_depth)
                      + params.block_depth + 0.5 * params.X_batt)
      + params.F_av * (params.L_t + params.X_batt/3.0)
      + params.F_qv * (params.L_t + 0.5 * params.X_batt)
      )

    # sum of moments causing overturning
    #  * horizontal component of active force:
    #      F_ah * y_F_active
    #  * horizontal component of surcharge force:
    #      F_qh * y_F_surcharge
    d["sumM_o"] = (params.F_ah * params.y_F_active +
                   params.F_qh * params.y_F_surcharge)
    
    return d

  def ForcesCausingFailure(self):
    return self.params.sumM_o

  def ForcesResistingFailure(self):
    return self.params.sumM_r

  def __str__(self):
    return r"""
\section{Overturning Failure Analysis}

\noindent \textbf{Moments contributing to overturning} \\[2mm]
The forces which contribute to overturning are: (1) the horizontal component
of the active earth pressure force, and (2) the horizontal component of
the surcharge force.  These forces act at the back of the retained soil
mass.  Taking all moments about the toe of the wall, the moment arms are
given respective by $y_{F-active}$ and $y_{F-surcharge}$ computed above.
The total moment contributing to overturning is thus:
\begin{eqnarray*}
\Sigma M_o &=& F_{ah} \cdot y_{F-active} + F_{qh} \cdot y_{F-surcharge} \\
 &=& %(F_ah)s \cdot %(y_F_active)s + %(F_qh)s \cdot %(y_F_surcharge)s \\
 &=& %(sumM_o)s
\end{eqnarray*}

\vspace{5mm}
\noindent \textbf{Moments resisting overturning} \\[2mm]
The forces which resist overturning are: (1) the weight of the wall face,
(2) the weight of the reinforced soil, and (3) the vertical component of the
active earth pressure force.  (Since the surcharge is a live load, the
vertical component of the surcharge force is not included when computing
the wall's resistance to overturning.)  The first two weights act at their
respective centers of mass, and since the forces are vertical, the moment arms
are the horizontal distances from the centers of mass to the toe of the wall.
The last force acts with a moment arm of $x_{F-active}$, computed above.
Using the battering offset $X_{batt}$ computed above, the total moment
resisting overturning is thus:
\begin{eqnarray*}
\Sigma M_r &=& W_f \cdot \left( \frac{D_{block}}{2} + \frac{X_{batt}}{2} \right)
  + W_s \cdot \left( D_{block} + \frac{L_t - D_{block}}{2} + \frac{X_{batt}}{2}
  \right) + F_{av} \cdot x_{F-active} \\
 &=& %(W_f)s \cdot \left( \frac{%(block_depth)s}{2} + \frac{%(X_batt)s}{2}
  \right) + %(W_s)s \cdot \left( %(block_depth)s + \frac{%(L_t)s -
  %(block_depth)s}{2} + \frac{%(X_batt)s}{2} \right) + %(F_av)s \cdot
  %(x_F_active)s \\
 &=& %(sumM_r)s
\end{eqnarray*}

\vspace{5mm}
\noindent \textbf{Factor Of Safety} \\
Factor of safety (FOS) = %(sumM_r)s $\div$ %(sumM_o)s = %(actual_fos)s \\
Design specification FOS = %(desired_fos)s
%(fos_box)s
""" % self.params.__dict__
  

class BearingPressureAnalysis(FailureAnalysis):
  """
  Reference: Allan Block Engineering Manual, starting at page 19
  Reference: http://www.allanblock.com/Literature/PDF/EngManual.pdf
  """

  def DerivedParams(self):
    d = {}
    params = self.params

    # Distance from toe of wall to point of application of resultant force due
    # to bearing pressure.  Calculated by setting sum of moments around the
    # toe of the wall to zero.  Defining positive moments to be those which
    # contribute to the wall overturning, the following forces contribute
    # moments of the given signs:
    #   * W_w * CM_x, the weight of the wall acting at the wall's center of
    #      mass, is a negative moment
    #   * F_ah * y_F_active and F_qh * y_F_surcharge, the active earth pressure
    #      and surcharge, are positive moments
    #   * F_av * x_F_active is a negative moment.  (Since the surcharge is a
    #      live load, we ignore any beneficial effects due to F_qv.)
    #   * (W_w + F_av) * X_bearing, the normal force of the bearing soil
    #      acting at the bottom of the soil mass at a distance X_bearing from
    #      the toe of the wall.
    # So: 0 = - W_w * CM_x + F_ah * y_F_active + F_qh * y_F_surcharge
    #         - F_av * x_F_active + (W_w + F_av) * X_bearing
    #     (W_w * CM_x - F_ah * y_F_active - F_qh * y_F_surcharge
    #         + F_av * x_F_active) / (W_w + F_av) = X_bearing
    d['X_bearing'] = (params.W_w * params.CM_x - params.F_ah * params.y_F_active
       - params.F_qh * params.y_F_surcharge + params.F_av * params.x_F_active
                      ) / (params.W_w + params.F_av)
    # Eccentricity, or distance from center of soil mass to X_bearing
    # Note that e is set to zero if e<0, because we don't design to resist
    # moments causing the wall to tilt backward.
    d['e'] = max(0.0 * params.L_t, 0.5 * params.L_t - d['X_bearing'])

    # Average bearing pressure per unit length: weight of wall face and soil
    # plus vertical active earth pressure plus surcharge, divided by horizontal
    # depth of wall and soil mass
    d['sigma_avg'] = params.V_t / params.L_t

    # Bearing pressure due to moment about midpoint of soil mass
    d['M_B'] = params.V_t * d['e']  # magnitude of moment
    d['S'] = 1.0 * (params.L_t ** 2) / 6.0   # section modulus
    d['sigma_mom'] = d['M_B'] / d['S']

    d['sigma_min'] = d['sigma_avg'] - d['sigma_mom']
    d['sigma_max'] = d['sigma_avg'] + d['sigma_mom']
    
    return d

  def ForcesCausingFailure(self):
    return self.params.sigma_max

  def ForcesResistingFailure(self):
    return self.params.sigma_allowed

  def __str__(self):
    return r"""
\section{Bearing Pressure Failure Analysis}

\noindent \textbf{$\mathbf{X_{bearing}}$} \\
\noindent
$X_{bearing}$ is defined as the distance from the toe of the wall to the point
of application of the resultant bearing pressure.  We calculate this by
setting the sum of moments about the toe of the wall to equal zero.  We define
positive moments to be those contributing to the wall overturning.  The
following forces contribute moments of the given signs: (1) $W_w \cdot CM_x$,
the weight of the wall acting at the wall's center of mass, is a negative
moment.  (2) $F_{ah} \cdot y_{F-active}$ and $F_{qh} \cdot y_{F-surcharge}$,
the active earth pressure and surcharge, are positive moments.  (3) $F_{av}
\cdot x_{F-active}$ is a negative moment.  Since the surcharge is a live load,
we ignore any beneficial effects due to $F_{qv}$.  (4) $(W_w + F_{av}) \cdot
X_{bearing}$, the normal force of the bearing soil acting at the bottom of
the soil mass at a distance $X_{bearing}$ from the toe of the wall.  This
bearing force resists the sum of the other forces, and its magnitude and
location are computed by setting the sum of all moments to zero:
%%
\begin{eqnarray*}
-W_w \cdot CM_x + F_{ah} \cdot y_{F-active} + F_{qh} \cdot y_{F-surcharge} -
  F_{av} \cdot x_{F-active} + (W_w + F_{av}) \cdot X_{bearing} &=& 0 \\[1mm]
\frac{W_w \cdot CM_x - F_{ah} \cdot y_{F-active} - F_{qh} \cdot y_{F-surcharge}
  + F_{av} \cdot x_{F-active}}{W_w + F_{av}} &=& X_{bearing} \\[1mm]
\frac{%(W_w)s \cdot %(CM_x)s - %(F_ah)s \cdot %(y_F_active)s - %(F_qh)s \cdot
  %(y_F_surcharge)s + %(F_av)s \cdot %(x_F_active)s}{%(W_w)s + %(F_av)s}
 &=& X_{bearing} \\
 %(X_bearing)s &=& X_{bearing}
\end{eqnarray*}

\vspace{5mm}
\noindent \textbf{Eccentricity} \\
\noindent
Eccentricity, or distance from center of soil mass to $X_{bearing}$, determines
how the off-center load adds to the moment contributing to the wall rolling
forward, increasing the bearing pressure on the toe.  If eccentricity is
negative, then these forces contribute to the wall rolling backward, and are
conservatively assumed to be zero rather than negative.
%%
\begin{eqnarray*}
e &=& \mbox{max} (0.0, \frac{L_t}{2} - X_{bearing}) \\
e &=& \mbox{max} (0.0, \frac{%(L_t)s}{2} - %(X_bearing)s) \\
e &=& %(e)s
\end{eqnarray*}

\vspace{5mm}
\noindent \textbf{Average bearing pressure} \\
\noindent
The average bearing pressure per unit length of wall is given by the total
weight of the wall and the retained soil plus the vertical component of the
active earth pressure, divided by horizontal depth of wall-soil mass.
%%
\begin{eqnarray*}
\sigma_{avg} &=& V_t / L_t \\
   &=& %(V_t)s \div %(L_t)s \\
   &=& %(sigma_avg)s
\end{eqnarray*}

\vspace{5mm}
\noindent \textbf{Bearing pressure due to moment about midpoint of soil mass} \\
\noindent
Magnitude of moment about midpoint:
\begin{eqnarray*}
M_B &=& V_t \cdot e \\
 &=& (%(V_t)s)(%(e)s) \quad = %(M_B)s
\end{eqnarray*}
%%
Section modulus for a unit-width section:
\begin{eqnarray*}
S &=& \frac{\mbox{(section width)} \cdot \mbox{(section depth)}^2}{6} \\
 &=& \frac{ 1.0 \cdot (L_t)^2 }{6} \\
 &=& \frac{ (%(L_t)s)^2 }{6} \quad = %(S)s
\end{eqnarray*}
%%
Bearing pressure due to moment:
\begin{eqnarray*}
\sigma_{mom} &=& M_B / S \\
 &=& %(M_B)s \div %(S)s \quad = %(sigma_mom)s
\end{eqnarray*}
%%
Minimum and maximum bearing pressures:
\begin{eqnarray*}
\sigma_{min} = \sigma_{avg} - \sigma_{mom} = %(sigma_avg)s - %(sigma_mom)s
  = %(sigma_min)s \\
\sigma_{max} = \sigma_{avg} + \sigma_{mom} = %(sigma_avg)s + %(sigma_mom)s
  = %(sigma_max)s
\end{eqnarray*}

\vspace{5mm}
\noindent \textbf{Factor Of Safety} \\
\noindent Maximum bearing pressure $\sigma_{max}$ = %(sigma_max)s \\
Bearing capacity of soil = %(sigma_allowed)s \\
Factor of safety (FOS) = %(sigma_allowed)s $\div$ %(sigma_max)s = %(actual_fos)s \\
Design specification FOS = %(desired_fos)s
%(fos_box)s
""" % self.params.__dict__

class UltimateBearingCapacityAnalysis(BearingPressureAnalysis):
  """
  Reference: Allan Block Engineering Manual, starting at page 21
  Reference: http://www.allanblock.com/Literature/PDF/EngManual.pdf
  """

  def DerivedParams(self):
    # Inherit calculations for sigma_max
    d = BearingPressureAnalysis.DerivedParams(self)
    params = self.params

    # Ultimate bearing capacity q_f is equal to
    #   0.5*gamma_f*B_b*N_gamma + c*N_c + gamma_f*D*N_q
    # (Terghazi equation for ultimate bearing capacity, as cited in
    #    {Craig, "Soil Mechanics", p.303}, as cited in Allan Block manual)

    d['N_q'] = exp(pi*tan(params.phi_f)) * (tan(Degrees(45) + params.phi_f/2) ** 2)
    d['N_c'] = (d['N_q'] - 1) / tan(params.phi_f)
    d['N_gamma'] = (d['N_q'] - 1) * tan(1.4 * params.phi_f)

    d['q_f'] = (0.5 * params.gamma_f * params.B_b * d['N_gamma'] +
                params.cohesion_f * d['N_c'] +
                params.gamma_f * params.D * d['N_q'])

    return d

  def ForcesCausingFailure(self):
    return self.params.sigma_max

  def ForcesResistingFailure(self):
    return self.params.q_f

  def __str__(self):
    return r"""
\section{Ultimate Bearing Capacity Analysis}

\noindent \textbf{Ultimate Bearing Capacity $\mathbf{q_f}$} \\
\noindent
Using the Terghazi formula, ultimate bearing capacity $q_f$ is computed as
\[ q_f = 0.5 \cdot \gamma_f \cdot B_b \cdot N_{\gamma} + c \cdot N_c + \gamma_f
   \cdot D \cdot N_q \]
where:
\begin{eqnarray*}
N_q &=& e^{\pi \tan \phi_f} \cdot \tan^2 (45^{\circ} + \phi_f/2) \\
N_c &=& (N_q - 1) \div \tan \phi_f \\
N_{\gamma} &=& (N_q - 1) \cdot \tan (1.4 \phi_f) \\
\end{eqnarray*}

Thus:
\begin{eqnarray*}
N_q &=& e^{\pi \tan (%(phi_f)s)} \cdot \tan^2 (45^{\circ} + %(phi_f)s/2) \\
    &=& %(N_q)s \\
N_c &=& (%(N_q)s - 1) \div \tan %(phi_f)s \\
    &=& %(N_c)s \\
N_{\gamma} &=& (%(N_q)s - 1) \cdot \tan (1.4 \cdot %(phi_f)s) \\
    &=& %(N_gamma)s
\end{eqnarray*}

And ultimate bearing capacity $q_f$ is computed as:
\begin{eqnarray*}
q_f &=& 0.5 \cdot \gamma_f \cdot B_b \cdot N_{\gamma} + c \cdot N_c + \gamma_f
        \cdot D \cdot N_q \\
  &=&  0.5 \cdot %(gamma_f)s \cdot %(B_b)s \cdot %(N_gamma)s +
       %(cohesion_f)s \cdot %(N_c)s + %(gamma_f)s \cdot %(D)s \cdot %(N_q)s \\
  &=&  %(q_f)s
\end{eqnarray*}

\noindent \textbf{Factor Of Safety} \\
\noindent Maximum bearing pressure $\sigma_{max}$ = %(sigma_max)s \\
Ultimate bearing capacity = %(q_f)s \\
Factor of safety (FOS) = %(q_f)s $\div$ %(sigma_max)s = %(actual_fos)s \\
Design specification FOS = %(desired_fos)s
%(fos_box)s
""" % self.params.__dict__


class GridAnalysis(FailureAnalysis):
  """
  Reference: Allan Block Engineering Manual, starting at page 28 of pdf.
  Reference: http://www.allanblock.com/Literature/PDF/EngManual.pdf
  """
  def ParamsForLayer(self, i):
    d = self.HorizontalLoadOnLayer(i)
    
  def HorizontalLoadOnLayer(self, i):
    """Returns the horizontal load on layer i of geogrid, and, as an extra
    bonus, the latex string describing the calculation. Returned as a
    tuple (F, texstr)."""
    params = self.params
    layers = params.geogrid_levels
  
    # Using dictionary to store intermediate values is irritating, but 
    # makes writing the tex much easier later
    d = {}
    d['layer'] = i

    # NOTE: Most height parameters are calculated with the origin at
    # the toe of the wall.  Geogrid parameters are an exception to
    # this.  For the following analysis, heights are taken with the
    # origin at the top of the wall, with the positive direction being
    # down.  (I.e., they are (vertical) depths, not heights.)
    
    # Depth of the bottom of the layer
    if i == 0:
      # first layer, bottom is all the way at the bottom of the wall
      d['d_bottom'] = params.H
    else:
      # between this layer and the one below it
      effective_layer = (layers[i] + layers[i-1]) / 2.0
      d['d_bottom'] = params.H - effective_layer * params.block_height

    # Depth of the top of the layer
    if i == len(layers) - 1:
      # top layer, all the way to the top
      d['d_top'] = 0 * params.H
    else:
      effective_layer = (layers[i] + layers[i+1]) / 2.0
      d['d_top'] = params.H - effective_layer * params.block_height

    # Horizontal pressure on the layer (top, bottom, average)
    # P = surcharge + active earth pressure
    #   = q * K_ai * cos(phi_wi) + gamma_i * K_ai * cos(phi_wi) * depth
    #   = K_ai * cos(phi_wi) * ( q + gamma_i * depth )
    d['P_top'] = params.K_ai * cos(params.phi_wi) * (
      params.q + (params.gamma_i * d['d_top']))
    d['P_bottom'] = params.K_ai * cos(params.phi_wi) * (
      params.q + (params.gamma_i * d['d_bottom']))
    d['P_avg'] = 0.5 * (d['P_top'] + d['P_bottom'])

    # Force on the geogrid
    d['h'] = d['d_bottom'] - d['d_top']
    d['F_g'] = d['P_avg'] * d['h']
    self.params.update(d)

    tex = r"""
{\bf Max load on geogrid:}
\begin{eqnarray*}
h &=& d_{bottom} - d_{top} \quad = ~ %(d_bottom)s - %(d_top)s \quad = ~ %(h)s \\
P_{top} &=& K_{ai} \cdot \cos \phi_{wi} \cdot (q + \gamma_i d_{top}) \\
  &=& %(K_ai)s \cos %(phi_wi)s \cdot (%(q)s + %(gamma_i)s \cdot %(d_top)s) \\
  &=& %(P_top)s \\
P_{bottom} &=& K_{ai} \cdot \cos \phi_{wi} \cdot (q + \gamma_i d_{bottom}) \\
  &=& %(K_ai)s \cos %(phi_wi)s \cdot (%(q)s + %(gamma_i)s \cdot %(d_bottom)s) \\
  &=& %(P_bottom)s \\
P_{avg} &=& \frac{P_{top} + P_{bottom}}{2} \quad = ~
  \frac{%(P_top)s + %(P_bottom)s}{2} \quad = ~ %(P_avg)s \\
F_g  &=& %(P_avg)s \cdot %(h)s \quad = ~ %(F_g)s
\end{eqnarray*}
""" % self.params.__dict__
        
    return d['F_g'], tex

  def LoadCalculationExplanation(self):
    return r"""

\vspace{4mm}
The load on a given geogrid layer depends on the height of the soil section
which the layer is responsible for holding, as well as the average horizontal
pressure in that section:
\[F_g = P_{avg} \cdot h\]

The height $h$ of the soil section is computed as the vertical depth of the
bottom plane of the section minus the vertical depth of the top plane.  The
planes dividing sections are taken to be at the midpoints between geogrid
layers, as well as at the soil surface and the wall foundation depth.

Horizontal pressure on the geogrid at a given depth $d$ is the sum of the
horizontal pressure due to the surcharge and the horizontal component of
the active earth pressure.  The former is given by $K_{ai} \cos \phi_{wi}
\cdot q$, and the latter by $K_{ai} \cos \phi_{wi} \cdot (\gamma_i d)$
; the total pressure at depth $d$ is thus:
 \[ P_d = K_{ai} \cdot \cos \phi_{wi} \cdot (q + \gamma_i d) \]
"""
    
  def ActualFactorOfSafety(self):
    return min([ self.ActualFactorOfSafetyForLayer(i)
                 for i in range(len(self.params.geogrid_levels)) ])

  def SafetyCheck(self):
    """Check each layer of the grid."""
    passed = True
    msg = ""
    
    for i in range(len(self.params.geogrid_levels)):
      actual_fos = self.ActualFactorOfSafetyForLayer(i)
      if actual_fos < self.desired_fos:
        passed = False
        msg += ('%s, layer %s (above %s course of blocks): FOS outside spec (desired: %.2f, actual: %.2f)\n'
                % (self.name, i, ordinal(self.params.geogrid_levels[i]), self.desired_fos, actual_fos))
      else:
        msg +='%s, layer %s: (above %s course of blocks) Passed (desired FOS: %.2f, actual: %.2f)\n' % (
        self.name, i, ordinal(self.params.geogrid_levels[i]), self.desired_fos, actual_fos)
    return passed, msg

  
  def __str__(self):
    d = self.params.__dict__.copy()    
    d['name'] = self.name
    d['header'] = self.TexHeader()
    d['calc_explanation'] = self.CalculationExplanation()
    tex = r"""
\section{%(name)s}
   
%(header)s

%(calc_explanation)s

\noindent Performing the above calculations for each layer of geogrid, we get
the following:

\vspace{2mm} \noindent
"""  % d
    for i in range(len(self.params.geogrid_levels)):
      tex += "{\\bf Layer %d: }\n" % (i+1)
      _, t = self.ActualFactorOfSafetyForLayerAndTex(i)
      tex += t
      #tex += "{\\bf Layer %d: }\n%s" % (i+1, self.LatexForLayer(i))
      
    d['FOS'] = self.ActualFactorOfSafety()
    d['desired_fos'] = self.desired_fos
    tex += r"""{\bf %(name)s factor of safety}

The minimum factor of safety over all the layer geogrid is therefore:

\noindent
Factor of safety (FOS) = %(FOS)s \\
Design specification FOS = %(desired_fos)s \\
%(fos_box)s
""" % d 
    return tex

###########################################################################

class RuptureAnalysis(GridAnalysis):
  """Will any layer of geogrid rupture at the active/passive line?"""

  def ActualFactorOfSafetyForLayerAndTex(self, i):
      # Use a dictionary to make the format string more readable
      d = {}
      d['F_g'], d['loadTex'] = self.HorizontalLoadOnLayer(i)
      d['F_R'] = self.params.LTADS
      d['grid_i'] = i+1   # "layer 0" -> "layer 1" in the human-readable output
      d['FOS'] = d['F_R'] / d['F_g']
      d['block_course_ordinal'] = ordinal(self.params.geogrid_levels[i])
      tex = r"""%(loadTex)s

{\bf Resistance to rupture:}
\begin{eqnarray*}
F_R &=& LTADS \quad = ~ %(F_R)s \\
FOS_{rupture,%(grid_i)d} &=& F_R / F_g \quad = ~ %(F_R)s \div %(F_g)s \quad = ~
  %(FOS)s
\end{eqnarray*}

""" % d
      return d['FOS'], tex

  def ActualFactorOfSafetyForLayer(self, i):
    fos, _ = self.ActualFactorOfSafetyForLayerAndTex(i)
    return fos

  def TexHeader(self):
    return """In this section, we analyze the forces that are acting to rip the
geogrid at each layer.  To do so, we compute the load on the layer,
and compare it to the long term allowable design strength (LTADS) of
the geogrid."""

  def CalculationExplanation(self):
    return self.LoadCalculationExplanation() + r"""Given the load on the layer, the force resisting rupture is ~ $F_R = LTADS$ ~;
and the factor of safety for a geogrid layer $i$ is ~
 $FOS_{rupture,i} = F_g \div F_R$
"""

###########################################################################


class PulloutOfBlockAnalysis(GridAnalysis):
  """
  Reference: Allan Block Engineering Manual, starting at page 32
  Reference: http://www.allanblock.com/Literature/PDF/EngManual.pdf
  """

  def ActualFactorOfSafetyForLayerAndTex(self, i):
    """Do the math and also return the tex"""
    params = self.params
    d = params.__dict__.copy()

    # Use a dictionary to make the format string more readable
    d['grid_i'] = i+1   # "layer 0" -> "layer 1" in the human-readable output
    d['block_course_ordinal'] = ordinal(self.params.geogrid_levels[i])

    # Force on the geogrid at the back face of the wall
    d['F_g'], d['loadTex'] = self.HorizontalLoadOnLayer(i)

    # Force at the back of the wall is about 2/3 of the max force on the geogrid
    # (Allan Block manual citing McKittrick 1979)
    d['F_W'] = 2 * d['F_g'] / 3

    # Resistance to pullout depends on the weight of the wall above the layer
    # Normal (vertical) load N on geogrid
    d['layer_depth'] = params.H - params.geogrid_levels[i] * params.block_height
    d['N'] = (d['layer_depth'] * params.gamma_wall * params.block_depth)
    # resistance to pullout of block
    d['F_CS'] = params.geogrid_X + params.geogrid_Y * d['N']

    # NOTE: This is not taking into account that the F_CS may be greater than LTADS,
    # in which case the grid would rupture before pulling out of the blocks.  However,
    # that mode of failure is covered by the rupture analysis, so this should be fine.
    d['actual_fos'] = d['F_CS'] / d['F_W']
    
    tex = r"""\noindent 
{\bf Analysis for geogrid above %(block_course_ordinal)s course of blocks from
   the bottom}
%(loadTex)s
\vspace{1mm}
Force on geogrid at back of block: $F_W = \frac{2}{3} F_g \quad = ~
 \frac{2 \cdot %(F_g)s}{3} \quad = ~ %(F_W)s$

\vspace{3mm}
{\bf Connection strength $F_{CS}$; Pullout FOS for layer %(grid_i)d:}
\begin{eqnarray*}
N &=& d_{layer} \cdot \gamma_{wall} \cdot D_{block} \\
  &=& %(layer_depth)s \cdot %(gamma_wall)s \cdot %(block_depth)s \quad = ~
         %(N)s \\
F_{CS} &=& X_{geogrid} + Y_{geogrid} \cdot N \\
  &=& %(geogrid_X)s + %(geogrid_Y)s \cdot %(N)s \quad = ~ %(F_CS)s \\
FOS_{pullout,%(grid_i)d} &=& F_{CS} / F_W \quad = ~ %(F_CS)s \div %(F_W)s \quad = ~
     %(actual_fos)s
\end{eqnarray*}
""" % d
    
    return d['actual_fos'], tex

  def ActualFactorOfSafetyForLayer(self, i):
    fos, _ = self.ActualFactorOfSafetyForLayerAndTex(i)
    return fos

  def TexHeader(self):
    return """In this section, we analyze the forces that are acting to pull the
geogrid out from the blocks at each layer.  To do so, we compute the
load on the geogrid at the back of the wall and compare it to the
resisting force holding the geogrid in place.
""" 
    
  def CalculationExplanation(self):
    return self.LoadCalculationExplanation() + r"""

Given the maximum load on the geogrid, the force on the geogrid at the back
 of the wall is about 2/3 of the maximum force (Allan Block manual, citing
 McKittrick 1979).
%%
\begin{eqnarray*}
F_W &=& \frac{2}{3} F_g 
\end{eqnarray*}

The resistance to pullout depends on the normal (vertical) load $N$ on the
 geogrid at the back of the wall, primarily caused by the weight of the blocks
 above it:
\begin{eqnarray*}
N &=& d_{layer} \cdot \gamma_{wall} \cdot D_{block}
\end{eqnarray*}
%%
The connection strength resisting pullout $F_{CS}$ is linear with the normal
force $N$, with linearity parameters $X$ and $Y$ depending on the
block/geogrid combination (given by the block manufacturer, or measured by
testing).
\begin{eqnarray*}
F_{CS} &=& X + Y \cdot N 
\end{eqnarray*}
%%
The factor of safety for a layer $i$ is therefore:
\begin{eqnarray*}
FOS_{pullout,i} &=& F_{CS} / F_W
\end{eqnarray*}
"""

###########################################################################

class PulloutOfSoilAnalysis(GridAnalysis):
  """
  Reference: Allan Block Engineering Manual, starting at page 32
  Reference: http://www.allanblock.com/Literature/PDF/EngManual.pdf
  """

  def ActualFactorOfSafetyForLayerAndTex(self, i):
    params = self.params
    d = params.__dict__.copy()

    d['grid_i'] = i+1   # "layer 0" -> "layer 1" in the human-readable output
    d['layer_depth'] = params.H - params.geogrid_levels[i] * params.block_height
    d['F_g'], d['loadTex'] = self.HorizontalLoadOnLayer(i)

    # Length of geogrid in active zone --  see comment on page 33 of the
    # Allan Block eng manual
    d['L_a'] = min(
      0.3 * params.H,
      (params.H - d['layer_depth'])  * (tan(Degrees(45) - params.phi_i/2) -
                                        tan(Degrees(90) - params.beta)))
    
    # Length embedded in passive zone
    d['L_e'] = params.L_g - (params.block_depth - params.L_s) - d['L_a']

    # Restraining force on the grid
    # TODO: adjust for surcharge
    d['F_gr'] = min(2 * d['layer_depth'] * params.gamma_i * d['L_e']
                 * params.C_i * tan(params.phi_i),
                 self.params.LTADS)
    d['actual_fos'] = d['F_gr'] / d['F_g']

    d['block_course_ordinal'] = ordinal(params.geogrid_levels[i])
    tex = r"""\noindent 
{\bf Analysis for geogrid above %(block_course_ordinal)s course of blocks from
   the bottom}

%(loadTex)s

\begin{eqnarray*}
L_a &=& \mbox{min} (0.3 \cdot H, (H - d_{layer}) \cdot \left[ \tan(45^\circ -
  \phi_i/2) - tan(90^\circ - \beta) \right] \\
    &=& \mbox{min} (0.3 \cdot %(H)s), (%(H)s - %(layer_depth)s) \cdot \left[
     \tan(45^\circ - %(phi_i)s/2) - tan(90^\circ - %(beta)s) \right]
     \quad = ~ %(L_a)s \\
L_e &=& L_g - (D_{block} - L_s) - L_a  \\
    &=& %(L_g)s - (%(block_depth)s - %(L_s)s) - %(L_a)s \quad = ~  %(L_e)s \\
\end{eqnarray*}
{\bf Restraining force:}
\begin{eqnarray*}
F_{gr} &=& \mbox{min} (2 \cdot d_{layer} \cdot \gamma_i \cdot L_e \cdot C_i \cdot tan(\phi_i), LTADS) \\
       &=& min(2 \cdot %(layer_depth)s \cdot %(gamma_i)s \cdot %(L_e)s \cdot %(C_i)s \cdot tan(%(phi_i)s), %(LTADS)s) \\
       &=& %(F_gr)s
\end{eqnarray*}

{\bf Factor of safety:}
\begin{eqnarray*}
FOS_{pullout,%(grid_i)d}  &=& F_{gr} / F_g \quad = ~ %(F_gr)s \div %(F_g)s
   \quad = ~ %(actual_fos)s
\end{eqnarray*}
%%(fos_box)s
""" % d
    return d['actual_fos'], tex

  def ActualFactorOfSafetyForLayer(self, i):
    fos, _ = self.ActualFactorOfSafetyForLayerAndTex(i)
    return fos
  
  def TexHeader(self):
    return """
In this section, we analyze the forces that are acting to pull the
geogrid out from the soil.  To do so, we compute the load on the
geogrid and compare it to the resisting force holding in place the
part of the geogrid in the passive zone.
"""

  def CalculationExplanation(self):
        return self.LoadCalculationExplanation() + r"""
To compute the force keeping the geogrid in place, we need the length
$L_e$ of geogrid embedded in the passive zone of the soil.  To compute
that, we first need the length $L_a$ embedded in the active zone.  We assume
that the failure line separating the active and passive zones begins
at the bottom rear edge of the wall and goes upward at an angle of
$45^\circ + \phi/2$.  It continues at this angle until it intersects a
vertical line located behind the wall at a distance of 0.3 times the
height of the wall.  (Source: Allan Block engineering manual)
\begin{eqnarray*}
L_a &=& \min(0.3 \cdot H, (H - d_{layer}) \cdot \left[ \tan(45^\circ -
   \phi_i/2) - tan(90^\circ - \beta) \right] )
\end{eqnarray*}
%%
We can then compute $L_e$:
\begin{eqnarray*}
L_e &=& L_g - (D_{block} - L_s) - L_a
\end{eqnarray*}
%%
We can then compute the restraining force $F_{gr}$ on the grid as the
minimum of the LTADS and the frictional force applied by the earth to
the embedded section of the grid.
\begin{eqnarray*}
F_{gr} &=& \min(\mbox{LTADS}, 2 \cdot d_{layer} \cdot \gamma_i \cdot L_e \cdot
   C_i \cdot tan(\phi_i)) \\
\end{eqnarray*}
%%
The factor of safety for layer $i$ is therefore:
\begin{eqnarray*}
FOS_{pullout,i}  &=& F_{gr} / F_g 
\end{eqnarray*}
"""

############## Main code below ################################################
  
def RunAllAnalyses(config):
  params = InputParams.FromFile(MakeAbsPath(config, 'DesignParamsFile'))
  all_analyses = []
  latex_src = LatexHeader(config)
  latex_src += str(params)
  
  for analysis_class in (
    SlidingAnalysis, OverturningAnalysis, BearingPressureAnalysis,
    UltimateBearingCapacityAnalysis, RuptureAnalysis, PulloutOfBlockAnalysis,
    PulloutOfSoilAnalysis,
    ):
    analysis = analysis_class(params)
    passed, msg = analysis.SafetyCheck()
    latex_src += "\n%s" % analysis
    if passed:
      print "%35s:  OK  (FOS: actual = %.2f, design = %s)" % (
        analysis.name, analysis.params.actual_fos, analysis.desired_fos)
    else:
      print "%35s: FAIL (FOS: actual = %.2f, design = %s)" % (
        analysis.name, analysis.params.actual_fos, analysis.desired_fos)
    #print "%s: %s\nMsg: %s\n" % (analysis.name, passed, msg)
    if analysis_class in ():
      print "Derived vars: %s" % analysis.params.Show()
    all_analyses.append(analysis)

  latex_src += LatexFooter(config)
  if config.get("SaveLatexToFile", True):
    if 'OutputLatexFile' not in config:
      raise Error, """ERROR: No OutputLatexFile defined in config.
  To suppress LaTeX output, add "SaveLatexToFile = False" to the config.
"""
    output_filename = MakeAbsPath(config, 'OutputLatexFile')
    with open(output_filename, 'w') as f:
      f.write(latex_src)
    print """LaTeX output written to %(latexfile)s.  Please run
  pdflatex %(latexfile)s
to generate your PDF output file.""" % { "latexfile" : output_filename }

  return latex_src, all_analyses


def MakeAbsPath(config, file_param_name):
  """
  Using the command-line config file, extract +file_param_name+.  If it is
  already an absolute path, return it.  If not, make it absolute by prepending
  the config file's path.

  NOTE: This means that relative paths are relative to the config file's
  directory, not the execution directory!
  """
  param_val = config[file_param_name]
  if param_val[0] == "/": return param_val
  return os.path.join(config['ConfigDir'], param_val)


def Usage():
  return """
Usage: %s config-file

config-file should be in standard Python syntax and should define the following
variables:
   DesignParamsFile
   PlansTextFile
   OutputLatexFile
See the "sample-design" directory, included with this distribution, for
details on syntax and individual parameters within those files.
"""


def ParseCommandLine():
  if len(sys.argv) != 2 or not os.path.isfile(sys.argv[1]):
    print Usage()
    sys.exit(1)

  config_filename = sys.argv[1]
  with open(config_filename) as f:
    contents = f.read()
    context = {}
    exec(contents, context)
    context['ConfigDir'] = os.path.dirname(config_filename)
    del context['__builtins__']
  for required_param in ('DesignParamsFile', 'PlansTextFile',
                         'OutputLatexFile'):
    if required_param not in context:
      raise Error("Required parameter '%s' not supplied in %s" %
                  (required_param, config_filename))
  return context

if __name__ == '__main__':
  config = ParseCommandLine()
  RunAllAnalyses(config)
