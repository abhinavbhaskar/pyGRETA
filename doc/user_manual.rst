User manual
===========

Installation
------------

.. NOTE:: We assume that you are familiar with `git <https://git-scm.com/downloads>`_ and `conda <https://docs.conda.io/projects/conda/en/latest/user-guide/install/download.html>`_.

First, clone the git repository in a directory of your choice using a Command Prompt window::

	$ ~\directory-of-my-choice> git clone https://github.com/tum-ens/renewable-timeseries.git

We recommend using conda and installing the environment from the file ``ren_ts.yml`` that you can find in the repository. In the Command Prompt window, type::

	$ cd renewable-timeseries\env\
	$ conda env create -f ren_ts.yml

Then activate the environment::

	$ conda activate ren_ts

In the folder ``code``, you will find multiple files:

.. tabularcolumns:: |p{3.7cm}|p{9cm}|

+-------------------------+---------------------------------------------------------------------------+
| File                    | Description                                                               |
+=========================+===========================================================================+
| config.py               | used for configuration, see below.                                        |
+-------------------------+---------------------------------------------------------------------------+
| runme.py                | main file, which will be run later using ``python runme.py``.             |
+-------------------------+---------------------------------------------------------------------------+
| initialization.py       | used for initialization.                                                  |
+-------------------------+---------------------------------------------------------------------------+
| input_maps.py           | used to generate input maps for the scope.                                |
+-------------------------+---------------------------------------------------------------------------+
| potential.py            | contains functions related to the potential estimation.                   |
+-------------------------+---------------------------------------------------------------------------+
| time_series.py          | contains functions related to the generation of time series.              |
+-------------------------+---------------------------------------------------------------------------+
| regression.py           | contains functions related to the regression.                             |
+-------------------------+---------------------------------------------------------------------------+
| spatial_functions.py    | contains helping functions related to maps, coordinates and indices.      |
+-------------------------+---------------------------------------------------------------------------+
| physical_models.py      | contains helping functions for the physical/technological modeling.       |
+-------------------------+---------------------------------------------------------------------------+
| correction_functions.py | contains helping functions for data correction/cleaning.                  |
+-------------------------+---------------------------------------------------------------------------+
| util.py                 | contains minor helping functions and the necessary python libraries to be |
|                         | imported.                                                                 |
+-------------------------+---------------------------------------------------------------------------+

config.py                                                                                           
---------
This file contains the user preferences, the links to the input files, and the paths where the outputs should be saved.
The paths are initialized in a way that follows a particular folder hierarchy. However, you can change the hierarchy as you wish.

.. toctree::
   :maxdepth: 3
   
   source/config


Recommended input sources
-------------------------
For a list of GIS data sources, check this `wikipedia article <https://en.wikipedia.org/wiki/List_of_GIS_data_sources>`_.

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

It is possible to download MERRA-2 dataset for the whole globe or just for a subset of your region of interest.
Depending on the *MERRA_coverage* parameter in config.py, the script can accept both datasets. Note that downloading 
the coverage for the whole globe is easier but will require a significant amount of space on your drive (coverage 
of the whole globe requires 13.6 Gb for one year).

In both cases, please follow these instructions to download the MERRA-2 dataset:

1. In order to download MERRA-2 data using the FTP server, you first need to create an Eathdata account (more on that on their `website <https://disc.gsfc.nasa.gov/data-access>`_).
2. Navigate to the link for the FTP sever `here <https://disc.gsfc.nasa.gov/daac-bin/FTPSubset2.pl>`_.
3. In *Data Product*, choose :math:`\\texttt{tavg1\_2d\_slv\_NX}` and select the *Parameters* T2M, U50M, V50M to downaload the temperature and the wind speed datasets.
4. In *Spatial Search*, enter the coordinates of the bounding box around your region of interest or leave the default values for the whole globe. 
   To avoid problems at the edge of the MERRA-2 cells, use the following set of formulas:

   .. math::
     \begin{align*}
           minLat &= \left\lfloor\dfrac{s+0.25}{0.5}\right\rfloor \cdot 0.5 - \epsilon  \\
           maxLat &= \left\lceil\dfrac{n-0.25}{0.5}\right\rceil \cdot 0.5 + \epsilon \\
           minLon &= \left\lfloor\dfrac{w+0.3125}{0.625}\right\rfloor \cdot 0.625 - \epsilon  \\
           maxLon &= \left\lceil\dfrac{e-0.3125}{0.625}\right\rceil \cdot 0.625 + \epsilon 
      \end{align*}
	
   where *[s n w e]* are the southern, northern, western, and eastern bounds of
   the region of interest, which you can read from the shapefile properties in
   a GIS software, and :math:`\\epsilon` a small number.
	
5. In *Temporal Order Option*, choose the year(s) of interest.
6. Leave the other fields unchanged (no time subsets, no regridding, and NetCDF4 for the output file format).
7. Repeat the steps 4-6 for the *Data Product* :math:`\\texttt{tavg1\_2d\_rad\_Nx}`, for which you select the *Parameters* SWGDN and SWTDN, the surface incoming shortwave flux and the top of the atmosphere incoming shortwave flux.
8. Follow the instructions in the `website <https://disc.gsfc.nasa.gov/data-access>`_ to actually download the NetCDF4 files from the urls listed in the text files you obtained. 

If you follow these steps to download the data for the year 2015, you will obtain 730 NetCDF files, one for each day of the year and for each data product. 

Land use
^^^^^^^^
Another important input for this model is the land use type. 
A land use map is useful in the sense that other parameters can be associated with different landuse types, namely:

* Urban areas
* Ross coefficients
* Hellmann coefficients
* Albedo
* Suitability
* Availability
* Installation cost
* etc.

For each land use type, we can assign a value for these parameters which affect
the calculations for solar power and wind speed correction.
The global land use raster for which :mod:`input_maps.generate_landuse` has been written cannot be downloaded anymore (broken link),
but a newer version is available from the `USGS <https://lpdaac.usgs.gov/products/mcd12q1v006/>`_ website. 
However, this new version requires additional data processing.
The spatial resolution of the land use raster, and therefore of the other geographic intermediate rasters
used in this model, is 1/240° longitude and 1/240° latitude.

Shapefile of the region of interest
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The strength of the tool relies on its versatility, since it can be used for any user-defined regions provided in 
a shapefile. If you are interested in administrative divisions, you may consider downloading the shapefiles from 
the website of the Global Administration Divisions `(GADM) <https://gadm.org/download_country_v3.html>`_. You can also create your 
own shapefiles using a GIS software.

.. WARNING::
  In any case, you need to have at least one attribute called *NAME_SHORT* containing 
  a string (array of characters) designating each sub-region.

Shapefile of countries
^^^^^^^^^^^^^^^^^^^^^^
A shapefile of all the countries of the world is also needed. It can be downloaded again from `GADM <https://gadm.org/download_world.html>`_.
The attribute "GID_0" contains the ISO 3166-1 Alpha-3 codes of the countries, and is currently hard coded in the script.

.. WARNING::
  If you want to use another source or other code names, you need to edit the name of the attribute "GID_0" and
  the dictionary *dict_countries.csv*.

Shapefile of Exclusive Economic Zones (EEZ)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
A shapefile of the maritime boundaries of all countries is available at the website of the Flanders Marine Institute `(VLIZ) <http://www.vliz.be/en/imis?dasid=5465&doiid=312>`_.
It is used to identify offshore areas.

Raster of topography / elevation data
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
A high resolution raster (15 arcsec = 1/240° longitude and 1/240° latitude) made of 24 tiles can be downloaded from `viewfinder panoramas
<http://viewfinderpanoramas.org/Coverage%20map%20viewfinderpanoramas_org15.htm>`_.

Raster of bathymetry
^^^^^^^^^^^^^^^^^^^^
A high resolution raster (60 arcsec) of bathymetry can be downloaded from the website of the National Oceanic and Atmospheric Administration `(NOAA)
<https://ngdc.noaa.gov/mgg/global/global.html>`_. The one used in the database is ETOPO1 Ice Surface, cell-registered.

Raster of population density
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
A high resolution raster (30 arcsec) of population density can be downloaded from the website of `SEDAC
<https://sedac.ciesin.columbia.edu/data/set/gpw-v4-population-density-rev11/data-download>`_ after registration.

Shapefile of protected areas
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Any database for prtoected areas can be used with this tool, in particular the World Database on Protected Areas 
published by the International Union for Conservation of Nature `(IUCN) <https://www.protectedplanet.net/>`_.
The shapefile has many attributes, but only one is used in the tool: "IUCN_CAT". If another database is used, an 
equivalent attribute with the different categories of the protection has to be used and :mod:`config.py` has to be updated accordingly.

Wind frequencies from the Global Wind Atlas
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
In order to correct the data biases of MERRA-2, especially in high-altitude regions, this tool uses wind speed frequencies
of each country that are obtained from the `Global Wind Atlas <https://globalwindatlas.info/>`_. Select the country that you
need, choose 50m height, and download the plot data for the wind speed in a folder with the name of the country
(use the ISO 3166-1 Alpha-3 code).

.. NOTE:: You need to download the data for all the countries that lie in the scope of the study.

Recommended workflow
--------------------
The script is designed to be modular, yet there is a recommended workflow to follow for your first run...
