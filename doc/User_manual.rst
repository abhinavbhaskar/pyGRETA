User manual
===========

Installation
------------

.. NOTE:: We assume that you are familiar with `git <https://git-scm.com/downloads>`_ and `conda <https://docs.conda.io/projects/conda/en/latest/user-guide/install/download.html>`_.

First, clone the git repository in a directory of your choice using a Command Prompt window::

	$ ~\directory-of-my-choice> git clone https://github.com/tum-ens/renewable-timeseries.git

We recommend using conda and installing the environment from the file ``PyMTS37.yml`` that you can find in the repository. In the Command Prompt window, type::

	$ cd renewable-timeseries\env\
	$ conda env create -f PyMTS37.yml

Then activate the environment::

	$ conda activate PyMTS37

In the folder ``code``, you will find multiple files:

.. tabularcolumns:: |p{3cm}|p{6cm}|

.. Needs to be filled up.... 
	.. list-table::
	   :header-rows: 1

* - File
  - Description
  
* - config.py
  - used for configuration, see below.

+-----------------------+---------------------------------------------------------------------------+
| File                  | Description                                                               |
+=======================+===========================================================================+
| config.py             | used for configuration, see below.                                        |
+-----------------------+---------------------------------------------------------------------------+
| Master.py             | main file, which will be run later using ``python Master.py``.            |
+-----------------------+---------------------------------------------------------------------------+
| data_functions.py     | contains helping functions for data formatting, filtering, reshaping, etc.|
+-----------------------+---------------------------------------------------------------------------+
| model_functions.py    | contains helping functions for the modeling.                              |
+-----------------------+---------------------------------------------------------------------------+
| util.py               | contains minor helping functions and the necessary python libraries to be |
|                       | imported.                                                                 |
+-----------------------+---------------------------------------------------------------------------+

config.py                                                                                           
---------
This file contains the user preferences, the links to the input files, and the paths where the outputs should be saved.
The paths are initialized in a way that follows a particular folder hierarchy. However, you can change the hierarchy as you wish.

.. toctree::
   :maxdepth: 3
   
   source/config


Recommended input sources
-------------------------
Weather data from MERRA-2
^^^^^^^^^^^^^^^^^^^^^^^^^^
The most important  inputs within this model are the weather time series.
These are taken from the Modern-Era Retrospective Analysis for Research and Applications, version 2 (MERRA-2),
which is the latest atmospheric reanalysis of the modern satellite era produced by NASA's Global Modeling and
Assimilation Office (GMAO) :cite:`Gelaro.2017`. The parameters taken from MERRA-2 are:

* Global Horizontal Irradiance (*GHI*): Downward shortwave radiation received by a surface horizontal to the ground
  (*SWGDN* in MERRA-2 nomenclature).
* Top of the Atmosphere Irradiance (*TOA*): Downward shortwave radiation at the top of the atmosphere
  (*SWTDN* in MERRA-2 nomenclature).
* Air temperature 2 meters above the ground (*T2M*).
* Northward wind velocity at 50 meters (*V50M*).
* Eastward wind velocity at 50 meters (*U50M*).

The *GHI* and *TOA* data are time-averaged hourly values given in W/m while *T2M* data are instantaneous
values in Kelvin. *V50M* and *U50M* are instantaneous hourly values given in m/s.

The spatial arrangement of the data consists of a global horizontal grid structure with a resolution of 576 points in
the longitudinal direction and 361 points in the latitudinal direction, resulting in pixels of 5/8° longitude 
and 1/2° latitude :cite:`MERRA2.`.

Expected outputs
----------------

Recommended workflow
--------------------
The script is designed to be modular, yet there is a recommended work flow to follow for your first run...
