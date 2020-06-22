.. _section:inputs:

Input Files
===========

``MCSED`` is designed to model the SEDs of a set of galaxies with a
common set of photometric and spectroscopic data. Since ``MCSED`` can
accept a wide range of constraints, with dozens of possible filter
combinations, emission line fluxes, and/or absorption line spectra
indices, the format of the input file has some flexibility. But the
basic file structure is simple: the data are entered in a simple,
space-delimited ascii file, with the first line of the file labeling the
file’s columns. The rest of the file gives the measured flux densities
and/or emission-line fluxes and/or absorption line spectral indices for
each object, one object per line.

.. _subsec:columns:

Required Columns
----------------

The input data file has three required columns, which must have these
exact labels: ``Field``, ``ID``, and ``z``. In other words, an
object’s identification consists in two parts: a string which contains
the name of the field in which the object is found, and a unique integer
ID which is specific to that field. If both field and ID are
unnecessary, one can simply enter a placeholder for one of the entries.
Redshifts must be specified for every source.

The remaining columns in the input file should be pairs of numbers
representing photometric flux densities (and their :math:`1\,\sigma`
errors), emission line fluxes (and their errors), and/or absorption line
indices (and their errors). Since the quoted uncertainties for
photometric observations often do not include systematic and/or external
errors, ``MCSED`` also allows the user to specify a minimum fractional
uncertainty for any type of observation. The defaults for the minimum
errors can be found in ``config.py``, and by default are set to
``phot_floor_error`` = 0.05 (for photometric errors),
``emline_floor_error`` = 0.05 (for errors in emission-line fluxes), and
``absindx_floor_error`` = 0.05 (for errors in absorption line indices).
These defaults can be changed by editing the above parameters in
``config.py``.

.. _subsec:photometry:

Photometry
----------

.. _subsubsec:skelton:

Using Skelton et al. (2014)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

``MCSED`` was originally written to analyze galaxies in the five CANDELS
fields (AEGIS, COSMOS, GOODS-N, GOODS-S, and UDS), hence there are
special commands built into the program to handle the PSF-matched
photometry from Skelton et al. (2014). If the user’s sources are in the
Skelton catalog, the objects can be specified by their field (i.e.,
``aegis``, ``cosmos``, ``goodsn``, ``goodss``, or ``uds``) and the
unique Skelton ID number. This links the input line directly to the
object’s photometry in the files provided by Skelton et al. (2014).
Momcheva et al. (2016) provide grism redshifts (and emission line
fluxes) for all Skelton photometry. Users with Skelton sources are
encouraged to use the grism redshifts for the redshift column.

Additional photometry not included in the Skelton catalogs can be
specified in the input file in the same way as general photometry as
discussed in :ref:`subsubsec:genphot`.

.. _subsubsec:genphot:

General Case
~~~~~~~~~~~~

If the input objects are not associated with the Skelton et al. (2014) catalog
(identified via the ``Field`` and ``ID`` columns described above), or if users
wish to supplement this catalog with additional photometry, the input file must
include additional columns. Photometric measurements should be given as flux
densities with :math:`1\,\sigma` uncertainties associated with each
measurement (null value :math:`=-99`). 
The columns containing these data in the input file should be labeled
``f_filter_name`` and ``e_filter_name``, where ``filter_name`` is the
name of a ``.res`` file in the ``FILTERS`` directory. (In other words,
columns named ``f_hst_acsF606W`` and ``e_hst_acsF606W`` should refer to
the flux densities (not magnitudes!) and uncertainties taken through the
filter defined in ``FILTERS/hst_acsF606W.res``.) Following Skelton
et al. (2014), the units for flux density are scaled to an AB magnitude
of 25, so :math:`1.00 = 3.63 \times 10^{-30}` ergs cm\ :math:`^{-2}` s\ :math:`^{-1}` Hz\ :math:`^{-1}` (e.g., if the user’s flux densities are in :math:`\mu`\ Jy, the values must be multiplied by :math:`10^{0.4(25-23.9)} \approx 2.754`).

.. _subsec:emission-lines:

Emission Lines
--------------

``MCSED`` can include emission line fluxes in the likelihood function.
To do this, the user first specifies the line’s name (keyword ``Name``),
rest-frame wavelength (in Angstroms), and relative weight in the
``config.py`` emission-line dictionary. A weight of 1.0 means the line
contributes just as much weight to the likelihood function as a
photometric data point; a weight of 0.0 implies that the line is
ignored. The user then provides the objects’ emission line strengths and
:math:`1\,\sigma` error bars by entering the data in the input file and labeling
the columns as ``Name_FLUX`` and ``Name_ERR``, where ``Name`` is the
line’s keyword listed in the ``emline_list_dict`` dictionary 
defined in ``config.py``.  The emission line fluxes and
errors must be specified in units of :math:`10^{-17}` ergs
cm\ :math:`^{-2}` s\ :math:`^{-1}`, unless a different multiplication
factor to the base unit of ergs cm\ :math:`^{-2}` s\ :math:`^{-1}` is
specified by the keyword ``emline_factor`` in ``config.py``. The
emission lines currently included in ``config.py`` are given below.
Additional lines can be added by expanding the ``emline_list_dict`` in
``config.py``.

.. table:: Emission Lines Definitions

   +------------------------+----------+------------+--------+
   |  Line                  | Name     | Wavelength | Weight | 
   |                        |          | (Å)        |        |        
   +========================+==========+============+========+
   | H\ :math:`\beta`       | ``Hb``   | 4861       | 1.0    |
   +------------------------+----------+------------+--------+
   | H\ :math:`\alpha`      | ``Ha``   | 6563       | 1.0    |
   +------------------------+----------+------------+--------+
   | [O III]                | ``OIII`` | 5007       | 0.5    |
   +------------------------+----------+------------+--------+
   | [O II]                 | ``OII``  | 3727       | 0.5    |
   +------------------------+----------+------------+--------+
   | [N II]                 | ``NII``  | 6583       | 0.5    |
   +------------------------+----------+------------+--------+

Currently, ``MCSED`` cannot fit blended emission lines.

.. _subsec:absorption-lines:

Absorption Line Indices
-----------------------

Absorption line indices can also be used in ``MCSED``’s likelihood
function. These measurements are input in a similar way as additional
photometry or emission line fluxes are included. In the input file, the 
columns containing an absorption line index and its uncertainty are 
labeled as ``Name_INDX`` and ``Name_Err``, where ``Name`` is the line’s 
keyword, as listed in the ``absorption_index_dict`` dictionary
defined in ``config.py``. The indices that are pre-defined in ``MCSED`` are 
listed in the table below. As one can see from the table,
the indices are defined via their wavelength ranges, the units they are
quoted in, and a relative weight similar to that defined for the
emission lines.

.. table:: Absorption Line Indices Definitions

   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+
   |                      | Index Band (Å)       | Blue Continuum (Å)  | Red Continuum (Å)   |       |
   +==============+=======+==========+===========+==========+==========+==========+==========+=======+
   | Name         | Weight| Blue     | Red       | Blue     | Red      | Blue     | Red      | Units¹|
   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+
   | Lick_CN1     | 1.0   | 4142.125 | 4177.125  | 4080.125 | 4117.625 | 4244.125 | 4284.125 | 1     |
   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+
   | Lick_CN2     | 1.0   | 4142.125 | 4177.125  | 4083.875 | 4096.375 | 4244.125 | 4284.125 | 1     |
   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+
   | Lick_Ca4227  | 1.0   | 4222.250 | 4234.750  | 4211.000 | 4219.750 | 4241.000 | 4251.000 | 0     |
   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+
   | Lick_G4300   | 1.0   | 4281.375 | 4316.375  | 4266.375 | 4282.625 | 4318.875 | 4335.125 | 0     |
   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+
   | Lick_Fe4383  | 1.0   | 4369.125 | 4420.375  | 4359.125 | 4370.375 | 4442.875 | 4455.375 | 0     |
   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+
   | Lick_Ca4455  | 1.0   | 4452.125 | 4474.625  | 4445.875 | 4454.625 | 4477.125 | 4492.125 | 0     |
   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+
   | Lick_Fe4531  | 1.0   | 4514.250 | 4559.250  | 4504.250 | 4514.250 | 4560.500 | 4579.250 | 0     |
   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+
   | Lick_Fe4668  | 1.0   | 4634.000 | 4720.250  | 4611.500 | 4630.250 | 4742.750 | 4756.500 | 0     |
   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+
   | Lick_Hb      | 1.0   | 4847.875 | 4876.625  | 4827.875 | 4847.875 | 4876.625 | 4891.625 | 0     |
   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+
   | Lick_Fe5015  | 1.0   | 4977.750 | 5054.000  | 4946.500 | 4977.750 | 5054.000 | 5065.250 | 0     |
   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+
   | Lick_Mg1     | 1.0   | 5069.125 | 5134.125  | 4895.125 | 4957.625 | 5301.125 | 5366.125 | 1     |
   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+
   | Lick_Mg2     | 1.0   | 5154.125 | 5196.625  | 4895.125 | 4957.625 | 5301.125 | 5366.125 | 1     |
   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+
   | Lick_Mgb     | 1.0   | 5160.125 | 5192.625  | 5142.625 | 5161.375 | 5191.375 | 5206.375 | 0     |
   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+
   | Lick_Fe5270  | 1.0   | 5245.650 | 5285.650  | 5233.150 | 5248.150 | 5285.650 | 5318.150 | 0     |
   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+
   | Lick_Fe5335  | 1.0   | 5312.125 | 5352.125  | 5304.625 | 5315.875 | 5353.375 | 5363.375 | 0     |
   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+
   | Lick_Fe5406  | 1.0   | 5387.500 | 5415.000  | 5376.250 | 5387.500 | 5415.000 | 5425.000 | 0     |
   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+
   | Lick_Fe5709  | 1.0   | 5696.625 | 5720.375  | 5672.875 | 5696.625 | 5722.875 | 5736.625 | 0     |
   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+
   | Lick_Fe5782  | 1.0   | 5776.625 | 5796.625  | 5765.375 | 5775.375 | 5797.875 | 5811.625 | 0     |
   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+
   | Lick_NaD     | 1.0   | 5876.875 | 5909.375  | 5860.625 | 5875.625 | 5922.125 | 5948.125 | 0     |
   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+
   | Lick_TiO1    | 1.0   | 5936.625 | 5994.125  | 5816.625 | 5849.125 | 6038.625 | 6103.625 | 1     |
   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+
   | Lick_TiO2    | 1.0   | 6189.625 | 6272.125  | 6066.625 | 6141.625 | 6372.625 | 6415.125 | 1     |
   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+
   | Lick_Hd_A    | 1.0   | 4083.500 | 4122.250  | 4041.600 | 4079.750 | 4128.500 | 4161.000 | 0     |
   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+
   | Lick_Hg_A    | 1.0   | 4319.750 | 4363.500  | 4283.500 | 4319.750 | 4367.250 | 4419.750 | 0     |
   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+
   | Lick_Hd_F    | 1.0   | 4091.000 | 4112.250  | 4057.250 | 4088.500 | 4114.750 | 4137.250 | 0     |
   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+
   | Lick_Hg_F    | 1.0   | 4331.250 | 4352.250  | 4283.500 | 4319.750 | 4354.750 | 4384.750 | 0     |
   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+
   | D4000        | 1.0   | ...…     | ...…      | 3750.000 | 3950.000 | 4050.000 | 4250.000 | 2     |
   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+
   |¹Unit codes: 0 = Å; 1 = mag; 2 = ratio                                                           |
   +--------------+-------+----------+-----------+----------+----------+----------+----------+-------+

These definitions come from Bruzual (1983) and Worthey et al. (1994);
they are calculated by finding the average value of :math:`F_{\lambda}`
within the blue and red continuum bands, interpolating a line through
these values to estimate the continuum, :math:`F_C`, and then computing
equivalent width via

.. math:: {\rm EW} = \int_{\lambda_1}^{\lambda_2} \left( 1 - \frac{F_{\lambda}}{F_C} \right) d\lambda

**Important Note:** absorption line indices are defined for a specific
spectral resolution. ``MCSED`` makes no attempt to match this
resolution: it uses the SSP spectra as is. The user should consider this
carefully before deciding on the utility of this feature.
