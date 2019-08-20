from model_functions import *


def initialization():
    timecheck('Start')
    
    # import param and paths
    from config import paths, param
        
    create_folders(paths)
    
    # Read shapefile of scope
    scope_shp = gpd.read_file(paths["spatial_scope"])
    param["spatial_scope"] = define_spatial_scope(scope_shp)

    res_weather = param["res_weather"]
    res_desired = param["res_desired"]
    Crd_all = crd_merra(param["spatial_scope"], res_weather)[0]
    param["Crd_all"] = Crd_all

    # # Do the same for countries, if wind correction is to be calculated
    # if (not os.path.isfile(paths["CORR_GWA"])) and param["WindOn"]["resource"]["topo_correction"] and (
            # "WindOn" in param["technology"]):
        # # read shapefile of countries
        # countries_shp = gpd.read_file(paths["Countries"])
        # param["countries"] = countries_shp.drop(countries_shp[countries_shp["Population"] == 0].index)
        # param["nCountries"] = len(param["countries"])
        # nCountries = param["nCountries"]
        # Crd_countries = np.zeros((nCountries, 4))
        # for reg in range(0, nCountries):
            # # Box coordinates for MERRA2 data
            # r = countries_shp.bounds.iloc[reg]
            # box = np.array([r["maxy"], r["maxx"], r["miny"], r["minx"]])[np.newaxis]
            # Crd_countries[reg, :] = crd_merra(box, res_weather)
        # param["Crd_countries"] = Crd_countries

    # Indices and matrix dimensions
    Ind_all_low = ind_merra(Crd_all, Crd_all, res_weather)
    Ind_all_high = ind_merra(Crd_all, Crd_all, res_desired)

    param["m_high"] = (Ind_all_high[:, 0] - Ind_all_high[:, 2] + 1).astype(int)[0]  # number of rows
    param["n_high"] = (Ind_all_high[:, 1] - Ind_all_high[:, 3] + 1).astype(int)[0]  # number of columns
    param["m_low"] = (Ind_all_low[:, 0] - Ind_all_low[:, 2] + 1).astype(int)[0]  # number of rows
    param["n_low"] = (Ind_all_low[:, 1] - Ind_all_low[:, 3] + 1).astype(int)[0]  # number of columns
    param["GeoRef"] = calc_geotiff(Crd_all, res_desired)
    timecheck('End')
    
    # Display initial information
    print('\nRegion: ' + param["region"] + ' - Year: ' + str(param["year"]))
    print('Folder Path: ' + paths["region"] + '\n')
    return paths, param


def generate_weather_files(paths, param):
    """
    This function reads the daily NetCDF data (from MERRA) for SWGDN, SWTDN, T2M, U50m, and V50m,
    and saves them in matrices with yearly time series with low spatial resolution.
    This code has to be run only once

    :param paths: paths dictionary containing the input file for NetCDF data
    """

    timecheck('Start')
    start = datetime.date(param["year"], 1, 1)
    end = datetime.date(param["year"], 12, 31)
    
    SWGDN = np.array([])
    SWTDN = np.array([])
    T2M = np.array([])
    U50M = np.array([])
    V50M = np.array([])
    status = 0
    delta = (end - start).days + 1
    for date in pd.date_range(start, end):
        # Show status bar
        status = status + 1
        sys.stdout.write('\r')
        sys.stdout.write('Reading NetCDF files ' + '[%-50s] %d%%' % (
                '=' * ((status * 50) // delta), (status * 100) // delta))
        sys.stdout.flush()
        
        tomorrow = date + pd.Timedelta('1 day')
        if date.day == 29 and date.month == 2:
            continue

        # Name and path of the NetCDF file to be read
        name = paths["MERRA_IN"] + 'MERRA2_400.tavg1_2d_rad_Nx.' + date.strftime('%Y%m%d') + '.SUB.nc'
        name2 = paths["MERRA_IN"] + 'MERRA2_400.tavg1_2d_slv_Nx.' + date.strftime('%Y%m%d') + '.SUB.nc'

        # Read NetCDF file, extract hourly tables
        with h5netcdf.File(name, 'r') as f:
            # [time, lat 361, lon 576]
            swgdn = np.transpose(subset(f['SWGDN'], param), [1, 2, 0])
            if SWGDN.size == 0:
                SWGDN = swgdn
            else:
                SWGDN = np.concatenate((SWGDN, swgdn), axis=2)

            swtdn = np.transpose(subset(f['SWTDN'], param), [1, 2, 0])
            if SWTDN.size == 0:
                SWTDN = swtdn
            else:
                SWTDN = np.concatenate((SWTDN, swtdn), axis=2)

        with h5netcdf.File(name2, 'r') as f:
            t2m = np.transpose(subset(f['T2M'], param), [1, 2, 0])
            if T2M.size == 0:
                T2M = t2m
            else:
                T2M = np.concatenate((T2M, t2m), axis=2)

            u50m = np.transpose(subset(f['U50M'], param), [1, 2, 0])
            if U50M.size == 0:
                U50M = u50m
            else:
                U50M = np.concatenate((U50M, u50m), axis=2)

            v50m = np.transpose(subset(f['V50M'], param), [1, 2, 0])
            if V50M.size == 0:
                V50M = v50m
            else:
                V50M = np.concatenate((V50M, v50m), axis=2)
        if date.year != tomorrow.year:
            # Create the overall wind speed
            W50M = abs(U50M + (1j * V50M))
            # Calculate the clearness index
            CLEARNESS = np.divide(SWGDN, SWTDN, where=SWTDN != 0)
            
            sys.stdout.write('\n')
            timecheck('Writing Files: T2M, W50M, CLEARNESS')
            hdf5storage.writes({'T2M': T2M}, paths["T2M"], store_python_metadata=True, matlab_compatible=True)
            hdf5storage.writes({'W50M': W50M}, paths["W50M"], store_python_metadata=True, matlab_compatible=True)
            hdf5storage.writes({'CLEARNESS': CLEARNESS}, paths["CLEARNESS"], store_python_metadata=True,
                               matlab_compatible=True)
    timecheck('End')


def generate_landsea(paths, param):
    m_high = param["m_high"]
    n_high = param["n_high"]
    Crd_all = param["Crd_all"]
    res_desired = param["res_desired"]
    res_weather = param["res_weather"]
    GeoRef = param["GeoRef"]

    timecheck('Start')
    # Read shapefile of scope
    scope_shp = gpd.read_file(paths["spatial_scope"])
    param["spatial_scope"] = define_spatial_scope(scope_shp)

    # Read shapefile of regions
    regions_shp = gpd.read_file(paths["subregions"], bbox=scope_shp)
    regions_shp = regions_shp.to_crs({'init': 'epsg:4326'})
    nRegions = len(regions_shp)
    
    # Extract land areas
    countries_shp = gpd.read_file(paths["Countries"], bbox=scope_shp)
    countries_shp = countries_shp.to_crs({'init': 'epsg:4326'})
    
    # Extract sea areas
    eez_shp = gpd.read_file(paths["EEZ_global"], bbox=scope_shp)
    eez_shp = eez_shp.to_crs({'init': 'epsg:4326'})
    
    Crd_regions = np.zeros((nRegions, 4))
    Ind = np.zeros((nRegions, 4)).astype('int')
    A_land = np.zeros((m_high, n_high))
    A_sea = np.zeros((m_high, n_high))
    param["regions_land"] = gpd.GeoDataFrame()
    param["regions_sea"] = gpd.GeoDataFrame()
    for reg in range(0, nRegions):
        # Box coordinates for MERRA2 data
        r = regions_shp.bounds.iloc[reg]
        box = np.array([r["maxy"], r["maxx"], r["miny"], r["minx"]])[np.newaxis]
        Crd_regions[reg, :] = crd_merra(box, res_weather)
        Ind[reg, :] = ind_merra(Crd_regions[reg, :], Crd_all, res_desired)
        
        # Calculate A_region
        A_region = calc_region(regions_shp.iloc[reg], Crd_regions[reg, :], res_desired, GeoRef)
        
        # Check whether it is a land or sea region
        print(reg)
        poly = gpd.GeoDataFrame(regions_shp.iloc[reg]).T
        countries_shp.index = len(countries_shp) * [reg]
        
        if poly.representative_point().within(countries_shp).any(): # Land
            param["regions_land"] = param["regions_land"].append(poly)
            A_land[(Ind[reg, 2] - 1):Ind[reg, 0], (Ind[reg, 3] - 1):Ind[reg, 1]] = \
                A_land[(Ind[reg, 2] - 1):Ind[reg, 0], (Ind[reg, 3] - 1):Ind[reg, 1]] + A_region
        else: # Sea
            param["regions_sea"] = param["regions_sea"].append(poly)
            A_sea[(Ind[reg, 2] - 1):Ind[reg, 0], (Ind[reg, 3] - 1):Ind[reg, 1]] = \
                A_sea[(Ind[reg, 2] - 1):Ind[reg, 0], (Ind[reg, 3] - 1):Ind[reg, 1]] + A_region
            
    # Fixing pixels on the borders to avoid duplicates
    A_sea = A_sea * (1 - A_land)
    
    array2raster(paths["LAND"], GeoRef["RasterOrigin"], GeoRef["pixelWidth"], GeoRef["pixelHeight"], A_land)
    print("files saved: " + paths["LAND"])
    array2raster(paths["EEZ"], GeoRef["RasterOrigin"], GeoRef["pixelWidth"], GeoRef["pixelHeight"], A_sea)
    print("files saved: " + paths["EEZ"])
    
    # Saving parameters
    param["nRegions_land"] = len(param["regions_land"])
    param["nRegions_sea"] = len(param["regions_sea"])
    param["Crd_regions"] = Crd_regions
    
    # THIS PART MIGHT BE NOT NECESSARY (SORTING)
    # Recombine the maps in this order: onshore then offshore
    regions_all = gpd.GeoDataFrame(pd.concat([param["regions_land"], param["regions_sea"]],
                                             ignore_index=True), crs=param["regions_land"].crs)
                                             
    for reg in range(0, nRegions):
        # Box coordinates for MERRA2 data
        r = regions_all.bounds.iloc[reg]
        box = np.array([r["maxy"], r["maxx"], r["miny"], r["minx"]])[np.newaxis]
        Crd_regions[reg, :] = crd_merra(box, res_weather)
    param["Crd_regions"] = Crd_regions

    timecheck('End')
    return param


def generate_landuse(paths, param):

    timecheck('Start')
    res_desired = param["res_desired"]
    Crd_all = param["Crd_all"]
    Ind = ind_global(Crd_all, res_desired)[0]
    GeoRef = param["GeoRef"]
    with rasterio.open(paths["LU_global"]) as src:
        w = src.read(1, window=windows.Window.from_slices(slice(Ind[0] - 1, Ind[2]),
                                                          slice(Ind[3] - 1, Ind[1])))
    w = np.flipud(w)
    array2raster(paths["LU"], GeoRef["RasterOrigin"], GeoRef["pixelWidth"], GeoRef["pixelHeight"], w)
    print("files saved: " + paths["LU"])
    timecheck('End')


def generate_bathymetry(paths, param):

    timecheck('Start')
    res_desired = param["res_desired"]
    Crd_all = param["Crd_all"]
    Ind = ind_global(Crd_all, res_desired)[0]
    GeoRef = param["GeoRef"]
    with rasterio.open(paths["Bathym_global"]) as src:
        A_BATH = src.read(1)
    A_BATH = resizem(A_BATH, 180 * 240, 360 * 240)
    A_BATH = np.flipud(A_BATH[Ind[0] - 1: Ind[2], Ind[3] - 1: Ind[1]])
    array2raster(paths['BATH'], GeoRef["RasterOrigin"], GeoRef["pixelWidth"], GeoRef["pixelHeight"], A_BATH)
    print("files saved: " + paths["BATH"])
    timecheck('End')


def generate_topography(paths, param):

    timecheck('Start')
    res_desired = param["res_desired"]
    Crd_all = param["Crd_all"]
    Ind = ind_global(Crd_all, res_desired)[0]
    GeoRef = param["GeoRef"]
    Topo = np.zeros((180 * 240, 360 * 240))
    tile_extents = np.zeros((24, 4), dtype=int)
    i = 1
    j = 1
    for letter in char_range('A', 'X'):
        north = (i - 1) * 45 * 240 + 1
        east = j * 60 * 240
        south = i * 45 * 240
        west = (j - 1) * 60 * 240 + 1
        tile_extents[ord(letter) - ord('A'), :] = [north, east, south, west]
        j = j + 1
        if j == 7:
            i = i + 1
            j = 1
    n_min = (Ind[0] // (45 * 240)) * 45 * 240 + 1
    e_max = (Ind[1] // (60 * 240) + 1) * 60 * 240
    s_max = (Ind[2] // (45 * 240) + 1) * 45 * 240
    w_min = (Ind[3] // (60 * 240)) * 60 * 240 + 1

    need = np.logical_and((np.logical_and((tile_extents[:, 0] >= n_min), (tile_extents[:, 1] <= e_max))),
                          np.logical_and((tile_extents[:, 2] <= s_max), (tile_extents[:, 3] >= w_min)))

    status = 0
    for letter in char_range('A', 'X'):
        index = ord(letter) - ord('A')
        if need[index]:
            # Show status bar
            status = status + 1
            sys.stdout.write('\r')
            sys.stdout.write('Generating topography map from tiles ' + '[%-50s] %d%%' % (
                '=' * ((status * 50) // sum(need)), (status * 100) // sum(need)))
            sys.stdout.flush()
        
            with rasterio.open(paths["Topo_tiles"] + '15-' + letter + '.tif') as src:
                tile = src.read()
            Topo[tile_extents[index, 0] - 1: tile_extents[index, 2],
            tile_extents[index, 3] - 1: tile_extents[index, 1]] = \
                tile[0, 0:-1, 0:-1]

    A_TOPO = np.flipud(Topo[Ind[0] - 1:Ind[2], Ind[3] - 1:Ind[1]])
    array2raster(paths["TOPO"], GeoRef["RasterOrigin"], GeoRef["pixelWidth"], GeoRef["pixelHeight"], A_TOPO)
    print("\n")
    print("files saved: " + paths["TOPO"])
    timecheck('End')


def generate_slope(paths, param):

    timecheck('Start')
    res_desired = param["res_desired"]
    Crd_all = param["Crd_all"]
    Ind = ind_global(Crd_all, res_desired)[0]
    GeoRef = param["GeoRef"]
    Lat1 = np.arange(-90, 90, 1 / 240)
    Lat2 = np.arange(-90 + 1 / 240, 90 + 1 / 240, 1 / 240)
    latMid = (Lat1 + Lat2) / 2
    deltaLat = abs(Lat1 - Lat2)

    Lat1 = np.arange(-90, 90, 1 / 240)
    Lat2 = np.arange(-90 + 1 / 240, 90 + 1 / 240, 1 / 240)
    latMid_2 = (Lat1 + Lat2) / 2

    Lon1 = np.arange(-180, 180, 1 / 240)
    Lon2 = np.arange(-180 + 1 / 240, 180 + 1 / 240, 1 / 240)
    deltaLon = abs(Lon1 - Lon2)

    m_per_deg_lat = 111132.954 - 559.822 * cos(np.deg2rad(2 * latMid)) + 1.175 * cos(np.deg2rad(4 * latMid))
    m_per_deg_lon = (np.pi / 180) * 6367449 * cos(np.deg2rad(latMid_2))

    x_cell = repmat(deltaLon, 180 * 240, 1) * repmat(m_per_deg_lon, 360 * 240, 1).T
    x_cell = x_cell[Ind[0] - 1:Ind[2], Ind[3] - 1: Ind[1]]
    x_cell = np.flipud(x_cell)

    y_cell = repmat((deltaLat * m_per_deg_lat), 360 * 240, 1).T
    y_cell = y_cell[Ind[0] - 1:Ind[2], Ind[3] - 1: Ind[1]]
    y_cell = np.flipud(y_cell)

    with rasterio.open(paths["TOPO"]) as src:
        A_TOPO = src.read(1)

    kernel = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]]) / 8
    dzdx = convolve(A_TOPO, kernel) / x_cell
    kernel = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]]) / 8
    dzdy = convolve(A_TOPO, kernel) / y_cell

    slope_deg = arctan((dzdx ** 2 + dzdy ** 2) ** 0.5) * 180 / np.pi
    slope_pc = tan(np.deg2rad(slope_deg)) * 100

    A_SLP = np.flipud(slope_pc)
    array2raster(paths["SLOPE"], GeoRef["RasterOrigin"], GeoRef["pixelWidth"], GeoRef["pixelHeight"], A_SLP)
    print("files saved: " + paths["SLOPE"])
    timecheck('End')


def generate_population(paths, param):

    timecheck('Start')
    res_desired = param["res_desired"]
    Crd_all = param["Crd_all"]
    Ind = ind_global(Crd_all, res_desired)[0]
    GeoRef = param["GeoRef"]
    Pop = np.zeros((180 * 240, 360 * 240))
    tile_extents = np.zeros((24, 4), dtype=int)
    i = 1
    j = 1

    for letter in char_range('A', 'X'):
        north = (i - 1) * 45 * 240 + 1
        east = j * 60 * 240
        south = i * 45 * 240
        west = (j - 1) * 60 * 240 + 1
        tile_extents[ord(letter) - ord('A'), :] = [north, east, south, west]
        j = j + 1
        if j == 7:
            i = i + 1
            j = 1
    n_min = (Ind[0] // (45 * 240)) * 45 * 240 + 1
    e_max = (Ind[1] // (60 * 240) + 1) * 60 * 240
    s_max = (Ind[2] // (45 * 240) + 1) * 45 * 240
    w_min = (Ind[3] // (60 * 240)) * 60 * 240 + 1

    need = np.logical_and((np.logical_and((tile_extents[:, 0] >= n_min), (tile_extents[:, 1] <= e_max))),
                          np.logical_and((tile_extents[:, 2] <= s_max), (tile_extents[:, 3] >= w_min)))

    status = 0
    for letter in char_range('A', 'X'):
        index = ord(letter) - ord('A')
        if need[index]:
            # Show status bar
            status = status + 1
            sys.stdout.write('\r')
            sys.stdout.write('Generating population map from tiles ' + '[%-50s] %d%%' % (
                '=' * ((status * 50) // sum(need)), (status * 100) // sum(need)))
            sys.stdout.flush()
            
            with rasterio.open(paths["Pop_tiles"] + letter + '.tif') as src:
                tile = src.read()
            Pop[tile_extents[index, 0] - 1: tile_extents[index, 2],
            tile_extents[index, 3] - 1: tile_extents[index, 1]] = \
                tile[0]

    A_POP = np.flipud(Pop[Ind[0] - 1:Ind[2], Ind[3] - 1:Ind[1]])
    array2raster(paths["POP"], GeoRef["RasterOrigin"], GeoRef["pixelWidth"], GeoRef["pixelHeight"], A_POP)
    print("\n")
    print("files saved: " + paths["POP"])
    timecheck('End')


def generate_protected_areas(paths, param):

    timecheck('Start')
    protected_areas = param["protected_areas"]
    # set up protected areas dictionary
    protection_type = dict(zip(protected_areas["IUCN_Category"], protected_areas["type"]))

    # First we will open our raster image, to understand how we will want to rasterize our vector
    raster_ds = gdal.Open(paths["LU"], gdal.GA_ReadOnly)

    # Fetch number of rows and columns
    ncol = raster_ds.RasterXSize
    nrow = raster_ds.RasterYSize

    # Fetch projection and extent
    proj = raster_ds.GetProjectionRef()
    ext = raster_ds.GetGeoTransform()

    raster_ds = None
    shp_path = paths["Protected"]
    # Open the dataset from the file
    dataset = ogr.Open(shp_path, 1)
    layer = dataset.GetLayerByIndex(0)

    # Add a new field
    if not field_exists('Raster', shp_path):
        new_field = ogr.FieldDefn('Raster', ogr.OFTInteger)
        layer.CreateField(new_field)

        for feat in layer:
            pt = feat.GetField('IUCN_CAT')
            feat.SetField('Raster', protection_type[pt])
            layer.SetFeature(feat)
            feat = None

    # Create a second (modified) layer
    outdriver = ogr.GetDriverByName('MEMORY')
    source = outdriver.CreateDataSource('memData')

    # Create the raster dataset
    memory_driver = gdal.GetDriverByName('GTiff')
    out_raster_ds = memory_driver.Create(paths["PA"], ncol, nrow, 1,
                                         gdal.GDT_Byte)

    # Set the ROI image's projection and extent to our input raster's projection and extent
    out_raster_ds.SetProjection(proj)
    out_raster_ds.SetGeoTransform(ext)

    # Fill our output band with the 0 blank, no class label, value
    b = out_raster_ds.GetRasterBand(1)
    b.Fill(0)

    # Rasterize the shapefile layer to our new dataset
    gdal.RasterizeLayer(out_raster_ds,  # output to our new dataset
                        [1],  # output to our new dataset's first band
                        layer,  # rasterize this layer
                        None, None,  # don't worry about transformations since we're in same projection
                        [0],  # burn value 0
                        ['ALL_TOUCHED=FALSE',  # rasterize all pixels touched by polygons
                         'ATTRIBUTE=Raster']  # put raster values according to the 'Raster' field values
                        )

    # Close dataset
    out_raster_ds = None
    print("files saved: " + paths["PA"])
    timecheck('End')


def generate_buffered_population(paths, param):

    timecheck('Start')
    buffer_pixel_amount = param["WindOn"]["mask"]["buffer_pixel_amount"]
    GeoRef = param["GeoRef"]
    with rasterio.open(paths["LU"]) as src:
        A_lu = src.read(1)
    A_lu = np.flipud(A_lu).astype(int)
    A_lu = A_lu == param["landuse"]["type_urban"]  # Land use type for Urban and built-up
    kernel = np.tri(2 * buffer_pixel_amount + 1, 2 * buffer_pixel_amount + 1, buffer_pixel_amount).astype(int)
    kernel = kernel * kernel.T * np.flipud(kernel) * np.fliplr(kernel)
    A_lu_buffered = convolve(A_lu, kernel)
    A_notPopulated = (~A_lu_buffered).astype(int)

    array2raster(paths["BUFFER"], GeoRef["RasterOrigin"], GeoRef["pixelWidth"], GeoRef["pixelHeight"],
                 A_notPopulated)
    print("files saved: " + paths["BUFFER"])
    timecheck('End')


def generate_wind_correction(paths, param):

    timecheck('Start')
    res_correction_on = param["WindOn"]["resource"]["res_correction"]
    res_correction_off = param["WindOff"]["resource"]["res_correction"]
    topo_correction = param["WindOn"]["resource"]["topo_correction"]
    GeoRef = param["GeoRef"]
    landuse = param["landuse"]
    with rasterio.open(paths["LU"]) as src:
        A_lu = np.flipud(src.read(1)).astype(int)
    A_hellmann = changem(A_lu, landuse["hellmann"], landuse["type"]).astype(float)

    # Onshore resolution correction
    turbine_height_on = param["WindOn"]["technical"]["hub_height"]

    if res_correction_on:
        m_low = param["m_low"]
        n_low = param["n_low"]
        m_high = param["m_high"]
        n_high = param["n_high"]
        res_weather = param["res_weather"]
        res_desired = param["res_desired"]
        A_gradient_height = changem(A_lu.astype(float), landuse["height"], landuse["type"])
        Sigma = sumnorm_MERRA2((50 / A_gradient_height) ** A_hellmann, m_low, n_low, res_weather, res_desired)
        A_cf_on = ((turbine_height_on / 50) * turbine_height_on /
                   A_gradient_height) ** A_hellmann / resizem(Sigma, m_high, n_high)
        del A_gradient_height, Sigma
    else:
        A_cf_on = (turbine_height_on / 50) ** A_hellmann

    # Offshore resolution correction
    turbine_height_off = param["WindOff"]["technical"]["hub_height"]

    if res_correction_off:
        m_low = param["m_low"]
        n_low = param["n_low"]
        m_high = param["m_high"]
        n_high = param["n_high"]
        res_weather = param["res_weather"]
        res_desired = param["res_desired"]
        A_gradient_height = changem(A_lu.astype(float), landuse["height"], landuse["type"])
        Sigma = sumnorm_MERRA2((50 / A_gradient_height) ** A_hellmann, m_low, n_low, res_weather, res_desired)
        A_cf_off = ((turbine_height_off / 50) * turbine_height_off /
                    A_gradient_height) ** A_hellmann / resizem(Sigma, m_high, n_high)
        del A_gradient_height, Sigma
    else:
        A_cf_off = (turbine_height_off / 50) ** A_hellmann
    del A_hellmann

    # Topographic correction (only onshore)
    with rasterio.open(paths["LAND"]) as src:
        A_land = np.flipud(src.read(1)).astype(int)
    A_cf_on = A_cf_on * A_land
    del A_land
    if topo_correction:
        if not os.path.isfile(paths["CORR_GWA"]):
            calc_gwa_correction(param, paths)
        gwa_correction = hdf5storage.read('correction_' + param["WindOn"]["resource"]["topo_weight"],
                                          paths["CORR_GWA"])
        A_cf_on = A_cf_on * gwa_correction
    with rasterio.open(paths["EEZ"]) as src:
        A_eez = np.flipud(src.read(1)).astype(int)
    A_cf = A_cf_off * A_eez + A_cf_on
    array2raster(paths["CORR"], GeoRef["RasterOrigin"], GeoRef["pixelWidth"], GeoRef["pixelHeight"], A_cf)
    print("files saved: " + paths["CORR"])
    timecheck('End')


def calculate_FLH(paths, param, tech):
    timecheck('Start')
    print('Region: ' + param["region"])

    if tech in ["WindOn", "WindOff"]:
        print("\n" + tech + " - HUB_HEIGHTS: " + str(param[tech]["technical"]["hub_height"]))
    elif tech in ["PV"] and 'orientation' in param["PV"]["technical"].keys():
        print("\n" + tech + " - Orientation: " + str(param[tech]["technical"]["orientation"]))

    nproc = param["nproc"]
    m_high = param["m_high"]
    n_high = param["n_high"]
    CPU_limit = np.full((1, nproc), param["CPU_limit"])

    if tech == "WindOff":
        #regions_shp = param["regions_eez"]
        #nRegions = param["nRegions_eez"]
        with rasterio.open(paths["EEZ"]) as src:
            w = src.read(1)
    else:
        #regions_shp = param["regions_land"]
        #nRegions = param["nRegions_land"]
        res_weather = param["res_weather"]
        Crd_all = param["Crd_all"]
        Ind = ind_merra(Crd_all, Crd_all, res_weather)[0]
        with rasterio.open(paths["LAND"]) as src:
            w = src.read(1)
    param["Ind_nz"] = np.nonzero(np.flipud(w))
    del w

    # Obtain weather matrices for Wind
    merraData = {}
    # Wind speed at 50m
    merraData["W50M"] = hdf5storage.read('W50M', paths["W50M"])
    if tech in ['PV', 'CSP']:

        # Calculate A matrices
        landuse = param["landuse"]
        reg_ind = param["Ind_nz"]
        rasterData = {}
        # A_lu
        with rasterio.open(paths["LU"]) as src:
            w = src.read(1)
        rasterData["A_lu"] = np.flipud(w)
        # rasterData["A_lu"] = rasterData["A_lu"][reg_ind]
        # A_Ross (Temperature coefficients for heating losses)
        rasterData["A_Ross"] = changem(rasterData["A_lu"], param["landuse"]["Ross_coeff"],
                                       param["landuse"]["type"]).astype(
            'float16')
        # A_albedo (Reflectivity coefficients)
        rasterData["A_albedo"] = changem(rasterData["A_lu"], param["landuse"]["albedo"],
                                         param["landuse"]["type"]).astype(
            'float16')

        # A_WS_Coef wind Speed at 2m above the ground
        A_hellmann = changem(rasterData["A_lu"], landuse["hellmann"], landuse["type"]).astype('float16')
        rasterData["A_WindSpeed_Corr"] = (2 / 50) ** A_hellmann
        del A_hellmann

        # Obtain other weather matrices
        # Clearness index - stored variable CLEARNESS
        merraData["CLEARNESS"] = hdf5storage.read('CLEARNESS', paths["CLEARNESS"])

        # Temperature 2m above the ground - stored variable T2M
        merraData["T2M"] = hdf5storage.read('T2M', paths["T2M"])

        CLEARNESS = hdf5storage.read('CLEARNESS', paths["CLEARNESS"])
        day_filter = np.nonzero(CLEARNESS[Ind[2] - 1:Ind[0], Ind[3] - 1:Ind[1], :].sum(axis=(0, 1)))
        list_hours = np.arange(0, 8760)
        if nproc == 1:
            param["status_bar_limit"] = list_hours[-1]
            results = calc_FLH_solar(list_hours[day_filter], [paths, param, tech, rasterData, merraData])
        else:
            list_hours = np.array_split(list_hours[day_filter], nproc)
            param["status_bar_limit"] = list_hours[0][-1]
            results = Pool(processes=nproc, initializer=limit_cpu, initargs=CPU_limit).starmap(calc_FLH_solar,
                                                                                               product(list_hours,
                                                                                                       [[paths, param,
                                                                                                         tech, rasterData, merraData]]))
    elif tech in ['WindOn', 'WindOff']:
        # Calculate A matrices
        reg_ind = param["Ind_nz"]
        rasterData = {}
        # A_cf
        with rasterio.open(paths["CORR"]) as src:
            w = src.read(1)
        rasterData["A_cf"] = np.flipud(w).astype('float16')
        rasterData["A_cf"] = rasterData["A_cf"][reg_ind]
        del w

        list_hours = np.array_split(np.arange(0, 8760), nproc)
        param["status_bar_limit"] = list_hours[0][-1]
        results = Pool(processes=nproc, initializer=limit_cpu, initargs=CPU_limit).starmap(calc_FLH_wind,
                                                                                           product(list_hours,
                                                                                                   [[paths, param,
                                                                                                     tech, rasterData, merraData]]))
    # Collecting results
    FLH = np.zeros((m_high, n_high))
    if nproc > 1:
        for p in range(len(results)):
            FLH[param["Ind_nz"]] = FLH[param["Ind_nz"]] + results[p]
    else:
        FLH[param["Ind_nz"]] = results
    FLH[FLH == 0] = np.nan

    hdf5storage.writes({'FLH': FLH}, paths[tech]["FLH"], store_python_metadata=True, matlab_compatible=True)
    print("files saved: " + paths[tech]["FLH"])
    timecheck('End')


def masking(paths, param, tech):

    timecheck('Start')
    mask = param[tech]["mask"]
    GeoRef = param["GeoRef"]

    if tech in ['PV', 'CSP']:
        with rasterio.open(paths["PA"]) as src:
            A_protect = src.read(1)
            A_protect = np.flipud(A_protect).astype(int)  # Protection categories 0-10, to be classified
        # Exclude protection categories that are not suitable
        A_suitability_pa = changem(A_protect, mask["pa_suitability"], param["protected_areas"]["type"]).astype(float)
        A_suitability_pa = (A_suitability_pa > 0).astype(int)
        with rasterio.open(paths["LU"]) as src:
            A_lu = src.read(1)
            A_lu = np.flipud(A_lu).astype(int)  # Landuse classes 0-16, to be reclassified
        # Exclude landuse types types that are not suitable
        A_suitability_lu = changem(A_lu, mask["lu_suitability"], param["landuse"]["type"]).astype(float)
        A_suitability_lu = (A_suitability_lu > 0).astype(int)
        with rasterio.open(paths["SLOPE"]) as src:
            A_slope = src.read(1)
            A_slope = np.flipud(A_slope)  # Slope in percentage
            A_slope = (A_slope <= mask["slope"]).astype(int)
        # Irrelevant parameters
        A_notPopulated = 1
        A_bathymetry = 1

    if tech == 'WindOn':
        with rasterio.open(paths["PA"]) as src:
            A_protect = src.read(1)
            A_protect = np.flipud(A_protect).astype(int)  # Protection categories 0-10, to be classified
        # Exclude protection categories that are not suitable
        A_suitability_pa = changem(A_protect, mask["pa_suitability"], param["protected_areas"]["type"]).astype(float)
        A_suitability_pa = (A_suitability_pa > 0).astype(int)
        with rasterio.open(paths["LU"]) as src:
            A_lu = src.read(1)
            A_lu = np.flipud(A_lu).astype(int)  # Landuse classes 0-16, to be reclassified
        # Exclude landuse types types that are not suitable
        A_suitability_lu = changem(A_lu, mask["lu_suitability"], param["landuse"]["type"]).astype(float)
        A_suitability_lu = (A_suitability_lu > 0).astype(int)
        with rasterio.open(paths["SLOPE"]) as src:
            A_slope = src.read(1)
            A_slope = np.flipud(A_slope)  # Slope in percentage
            A_slope = (A_slope <= mask["slope"]).astype(int)
        with rasterio.open(paths["BUFFER"]) as src:
            A_notPopulated = src.read(1)
            A_notPopulated = (np.flipud(A_notPopulated)).astype(int)  # Is 1 for not populated areas
        # Irrelevant parameters
        A_bathymetry = 1

    if tech == 'WindOff':
        with rasterio.open(paths["PA"]) as src:
            A_protect = src.read(1)
            A_protect = np.flipud(A_protect).astype(int)  # Protection categories 0-10, to be classified
        # Exclude protection categories that are not suitable
        A_suitability_pa = changem(A_protect, mask["pa_suitability"], param["protected_areas"]["type"]).astype(float)
        A_suitability_pa = (A_suitability_pa > 0).astype(int)
        with rasterio.open(paths["BATH"]) as src:
            A_bathymetry = src.read(1)
            A_bathymetry = np.flipud(A_bathymetry)  # Bathymetry (depth) in meter
            A_bathymetry = (A_bathymetry >= mask["depth"]).astype(int)  # (boolean)
        # Irrelevant parameters
        A_suitability_lu = 1
        A_slope = 1
        A_notPopulated = 1

    # Masking matrix for the suitable sites (pixels)
    A_mask = (A_suitability_pa * A_suitability_lu * A_slope * A_notPopulated * A_bathymetry).astype(float)

    del A_suitability_lu, A_suitability_pa, A_slope, A_notPopulated, A_bathymetry

    # Calculate masked FLH
    FLH = hdf5storage.read('FLH', paths[tech]["FLH"])
    FLH_mask = FLH * A_mask
    FLH_mask[FLH_mask == 0] = np.nan

    # Save HDF5 Files
    hdf5storage.writes({'A_mask': A_mask}, paths[tech]["mask"], store_python_metadata=True, matlab_compatible=True)
    print("files saved: " + paths[tech]["mask"])
    hdf5storage.writes({'FLH_mask': FLH_mask}, paths[tech]["FLH_mask"], store_python_metadata=True,
                       matlab_compatible=True)
    print("files saved: " + paths[tech]["FLH_mask"])

    # Save GEOTIFF files
    if param["savetiff"]:
        array2raster(changeExt2tif(paths[tech]["mask"]),
                     GeoRef["RasterOrigin"],
                     GeoRef["pixelWidth"],
                     GeoRef["pixelHeight"],
                     A_mask)
        print("files saved:" + changeExt2tif(paths[tech]["mask"]))

        array2raster(changeExt2tif(paths[tech]["FLH_mask"]),
                     GeoRef["RasterOrigin"],
                     GeoRef["pixelWidth"],
                     GeoRef["pixelHeight"],
                     FLH_mask)
        print("files saved:" + changeExt2tif(paths[tech]["FLH_mask"]))

    timecheck('End')


def weighting(paths, param, tech):

    timecheck('Start')
    weight = param[tech]["weight"]
    Crd_all = param["Crd_all"]
    m_high = param["m_high"]
    n_high = param["n_high"]
    res_desired = param["res_desired"]
    GeoRef = param["GeoRef"]

    if tech == 'PV':
        # Ground Cover Ratio - defines spacing between PV arrays
        A_GCR = calc_gcr(Crd_all, m_high, n_high, res_desired, weight["GCR"])
    else:
        A_GCR = 1

    with rasterio.open(paths["PA"]) as src:
        A_protect = src.read(1)
        A_protect = np.flipud(A_protect).astype(int)  # Protection categories 0-10, to be classified
    # Calculate availability based on protection categories
    A_availability_pa = changem(A_protect, weight["pa_availability"], param["protected_areas"]["type"]).astype(float)

    with rasterio.open(paths["LU"]) as src:
        A_lu = src.read(1)
        A_lu = np.flipud(A_lu).astype(int)  # Landuse classes 0-16, to be reclassified
    # Calculate availability based on landuse types
    A_availability_lu = changem(A_lu, weight["lu_availability"], param["landuse"]["type"]).astype(float)

    # Calculate availability
    A_availability = np.minimum(A_availability_pa, A_availability_lu)
    del A_availability_pa, A_availability_lu

    # Calculate available areas
    A_area = calc_areas(Crd_all, n_high, res_desired)

    # Weighting matrix for the power output (technical potential) in MWp
    A_weight = A_area * A_availability * A_GCR * weight["power_density"] * weight["f_performance"]

    # Calculate weighted FLH in MWh
    FLH = hdf5storage.read('FLH', paths[tech]["FLH"])
    FLH_weight = FLH * A_weight

    # Save HDF5 Files
    hdf5storage.writes({'A_area': A_area}, paths[tech]["area"], store_python_metadata=True, matlab_compatible=True)
    print("files saved: " + paths[tech]["area"])
    hdf5storage.writes({'A_weight': A_weight}, paths[tech]["weight"], store_python_metadata=True,
                       matlab_compatible=True)
    print("files saved: " + paths[tech]["weight"])
    hdf5storage.writes({'FLH_weight': FLH_weight}, paths[tech]["FLH_weight"], store_python_metadata=True,
                       matlab_compatible=True)
    print("files saved: " + paths[tech]["FLH_weight"])

    # Save GEOTIFF files
    if param["savetiff"]:
        array2raster(changeExt2tif(paths[tech]["area"]),
                     GeoRef["RasterOrigin"],
                     GeoRef["pixelWidth"],
                     GeoRef["pixelHeight"],
                     A_area)
        print("files saved:" + changeExt2tif(paths[tech]["area"]))

        array2raster(changeExt2tif(paths[tech]["weight"]),
                     GeoRef["RasterOrigin"],
                     GeoRef["pixelWidth"],
                     GeoRef["pixelHeight"],
                     A_weight)
        print("files saved:" + changeExt2tif(paths[tech]["weight"]))

        array2raster(changeExt2tif(paths[tech]["FLH_weight"]),
                     GeoRef["RasterOrigin"],
                     GeoRef["pixelWidth"],
                     GeoRef["pixelHeight"],
                     FLH_weight)
        print("files saved:" + changeExt2tif(paths[tech]["FLH_weight"]))
    timecheck('End')


def reporting(paths, param, tech):

    timecheck('Start')
    # read FLH, Masking, area, and weighting matrix
    FLH = hdf5storage.read('FLH', paths[tech]["FLH"])
    A_mask = hdf5storage.read('A_mask', paths[tech]["mask"])
    A_weight = hdf5storage.read('A_weight', paths[tech]["weight"])
    A_area = hdf5storage.read('A_area', paths[tech]["area"])
    density = param[tech]["weight"]["power_density"]

    # Check if land or see
    if tech in ['PV', 'CSP', 'WindOn']:
        location = "land"
    elif tech in ['WindOff']:
        location = "eez"

    # Initialize region masking parameters
    Crd_all = param["Crd_all"]
    GeoRef = param["GeoRef"]
    res_desired = param["res_desired"]
    nRegions = param["nRegions_" + location]
    regions_shp = param["regions_" + location]
    regions = [None] * nRegions

    # Initialize regions list of sorted FLH, FLH_M, and FLH_W
    sorted_FLH_list = {}

    # Define sampling for sorted lists
    sampling = param["report_sampling"]
    status = 0
    # Loop over each region
    for reg in range(0, nRegions):
        # Display Progress
        status += 1
        display_progress('Reporting ', (nRegions, status))

        # Intitialize region stats
        region_stats = {}
        region_stats["Region"] = regions_shp.iloc[reg]["NAME_SHORT"] + "_" + location

        # Compute region_mask
        A_region_extended = calc_region(regions_shp.iloc[reg], Crd_all, res_desired, GeoRef)

        # Sum available : available pixels
        available = np.sum(A_region_extended)
        region_stats["Available"] = int(available)

        # Sum availabe_masked : available pixels after masking
        A_masked = A_region_extended * A_mask
        available_masked = np.nansum(A_masked)
        region_stats["Available_Masked"] = int(available_masked)

        # Sum area: available area in km2
        A_area_region = A_region_extended * A_area
        Total_area = np.nansum(A_area_region) / (10 ** 6)
        region_stats["Available_Area_km2"] = Total_area

        # Stats for FLH
        FLH_region = A_region_extended * FLH
        FLH_region[FLH_region == 0] = np.nan
        region_stats["FLH_Mean"] = np.nanmean(FLH_region)
        region_stats["FLH_Median"] = np.nanmedian(FLH_region)
        region_stats["FLH_Max"] = np.nanmax(FLH_region)
        region_stats["FLH_Min"] = np.nanmin(FLH_region)
        region_stats["FLH_Std"] = np.nanstd(FLH_region)

        # Stats for FLH_masked
        FLH_region_masked = A_masked * FLH_region
        FLH_region_masked[FLH_region_masked == 0] = np.nan
        region_stats["FLH_Mean_Masked"] = np.nanmean(FLH_region_masked)
        region_stats["FLH_Median_Masked"] = np.nanmedian(FLH_region_masked)
        region_stats["FLH_Max_Masked"] = np.nanmax(FLH_region_masked)
        region_stats["FLH_Min_Masked"] = np.nanmin(FLH_region_masked)
        region_stats["FLH_Std_Masked"] = np.nanstd(FLH_region_masked)

        # Power Potential
        A_P_potential = A_area_region * density
        power_potential = np.nansum(A_P_potential)
        region_stats["Power_Potential_GW"] = power_potential / (10 ** 3)

        # Power Potential after weighting
        A_P_W_potential = A_region_extended * A_weight
        power_potential_weighted = np.nansum(A_P_W_potential)
        region_stats["Power_Potential_Weighted_GW"] = power_potential_weighted / (10 ** 3)

        # Energy Potential
        A_E_potential = A_P_potential * FLH_region
        energy_potential = np.nansum(A_E_potential)
        region_stats["Energy_Potential_TWh"] = energy_potential / (10 ** 6)

        # Energy Potential after weighting
        A_E_W_potential = FLH_region * A_weight
        energy_potential_weighted = np.nansum(A_E_W_potential)
        region_stats["Energy_Potential_Weighted_TWh"] = energy_potential_weighted / (10 ** 6)

        # Energy Potential After weighting and masking
        A_E_W_M_potential = A_E_W_potential * A_masked
        energy_potential_weighted_masked = np.nansum(A_E_W_M_potential)
        region_stats["Energy_Potential_Weighted_Masked_TWh"] = energy_potential_weighted_masked / (10 ** 6)

        sort = {}
        # Sorted FLH Sampling
        sorted_sampled_FLH = sampled_sorting(FLH_region[~np.isnan(FLH_region)], sampling)
        sort["FLH"] = sorted_sampled_FLH

        # Sorted FLH Sampling after masking
        sorted_sampled_FLH_masked = sampled_sorting(FLH_region_masked[~np.isnan(FLH_region_masked)], sampling)
        sort["FLH_M"] = sorted_sampled_FLH_masked

        # Sorted FLH Sampling after masking and wieghting
        FLH_region_masked_weighted = FLH_region_masked * A_weight
        FLH_region_masked_weighted[FLH_region_masked_weighted == 0] = np.nan

        sorted_sampled_FLH_masked_weighted = \
            sampled_sorting(FLH_region_masked_weighted[~np.isnan(FLH_region_masked_weighted)], sampling)
        sort["FLH_M_W"] = sorted_sampled_FLH_masked_weighted

        sorted_FLH_list[region_stats["Region"]] = sort

        # Add region to list
        regions[reg] = region_stats

    # Create Dataframe
    df = pd.DataFrame.from_dict(regions)

    # Reorder dataframe columns
    df = df[['Region', 'Available', 'Available_Masked', 'Available_Area_km2', 'FLH_Mean', 'FLH_Median',
             'FLH_Max', 'FLH_Min', 'FLH_Mean_Masked', 'FLH_Median_Masked', 'FLH_Max_Masked',
             'FLH_Min_Masked', 'FLH_Std_Masked', 'Power_Potential_GW', 'Power_Potential_Weighted_GW',
             'Energy_Potential_TWh', 'Energy_Potential_Weighted_TWh', 'Energy_Potential_Weighted_Masked_TWh']]

    # Export the dataframe as CSV
    df.to_csv(paths[tech]["Region_Stats"], sep=';', decimal=',')
    print("files saved: " + paths[tech]["Region_Stats"])

    # Save Sorted lists to .mat file
    for reg in sorted_FLH_list.keys():
        hdf5storage.writes({reg + '/FLH': sorted_FLH_list[reg]["FLH"],
                            reg + '/FLH_masked': sorted_FLH_list[reg]["FLH_M"],
                            reg + '/FLH_masked_weighted': sorted_FLH_list[reg]["FLH_M_W"]
                            }, paths[tech]["Sorted_FLH"], store_python_metadata=True, matlab_compatible=True)
    print("files saved: " + paths[tech]["Sorted_FLH"])
    timecheck('End')


def find_locations_quantiles(paths, param, tech):

    timecheck('Start')
    FLH_mask = hdf5storage.read('FLH_mask', paths[tech]["FLH_mask"])
    quantiles = param["quantiles"]
    res_desired = param["res_desired"]
    Crd_all = param["Crd_all"]
    GeoRef = param["GeoRef"]

    if tech == "WindOff":
        regions_shp = param["regions_eez"]
        nRegions = param["nRegions_eez"]
        Crd_regions = param["Crd_regions"][-nRegions:, :]
    else:
        regions_shp = param["regions_land"]
        nRegions = param["nRegions_land"]
        Crd_regions = param["Crd_regions"][0:nRegions, :]
    Ind = ind_merra(Crd_regions, Crd_all, res_desired)

    reg_ind = np.zeros((nRegions, len(quantiles), 2))
    list_names = []
    list_quantiles = []
    for reg in range(0, nRegions):
        # A_region
        A_region = calc_region(regions_shp.iloc[reg], Crd_regions[reg, :], res_desired, GeoRef)

        FLH_reg = A_region * FLH_mask[Ind[reg, 2] - 1:Ind[reg, 0], Ind[reg, 3] - 1:Ind[reg, 1]]
        FLH_reg[FLH_reg == 0] = np.nan
        X = FLH_reg.flatten(order='F')
        I_old = np.argsort(X)

        # Escape loop if intersection only yields NaN
        if np.isnan(X).all():
            # do nothing
            continue

        for q in range(0, len(quantiles)):
            list_names.append(regions_shp["NAME_SHORT"].iloc[reg])
            list_quantiles.append('q' + str(quantiles[q]))
            if quantiles[q] == 100:
                I = I_old[(len(X) - 1) - sum(np.isnan(X).astype(int))]
            elif quantiles[q] == 0:
                I = I_old[0]
            else:
                I = I_old[int(np.round(quantiles[q] / 100 * (len(X) - 1 - sum(np.isnan(X).astype(int)))))]
            # Convert the indices to row-column indices
            I, J = ind2sub(FLH_reg.shape, I)
            reg_ind[reg, q, :] = np.array([I + Ind[reg, 2], J + Ind[reg, 3]]).astype(int)

    reg_ind = np.reshape(reg_ind, (-1, 2), 'C').astype(int)
    reg_ind = (reg_ind[:, 0], reg_ind[:, 1])
    param[tech]["Ind_points"] = reg_ind
    param[tech]["Crd_points"] = crd_exact_points(reg_ind, Crd_all, res_desired)
    param[tech]["Crd_points"] = (param[tech]["Crd_points"][0], param[tech]["Crd_points"][1], list_names, list_quantiles)

    # Format point locations
    points = [(param[tech]["Crd_points"][1][i], param[tech]["Crd_points"][0][i]) for i in
              range(0, len(param[tech]["Crd_points"][0]))]

    # Create Shapefile
    schema = {'geometry': 'Point', 'properties': {'NAME_SHORT': 'str', 'quantile': 'str'}}
    with fiona.open(paths[tech]["Locations"], 'w', 'ESRI Shapefile', schema) as c:
        c.writerecords([{'geometry': mapping(Point(points[i])),
                         'properties': {'NAME_SHORT': list_names[i], 'quantile': list_quantiles[i]}} for i in
                        range(0, len(points))])
    hdf5storage.writes({'Ind_points': param[tech]["Ind_points"]}, paths[tech]["Locations"][:-4] + '_Ind.mat',
                       store_python_metadata=True, matlab_compatible=True)
    hdf5storage.writes({'Crd_points': param[tech]["Crd_points"]}, paths[tech]["Locations"][:-4] + '_Crd.mat',
                       store_python_metadata=True, matlab_compatible=True)
    print("files saved: " + paths[tech]["Locations"])
    timecheck('End')


def generate_time_series(paths, param, tech):

    timecheck('Start')

    nproc = param["nproc"]
    CPU_limit = np.full((1, nproc), param["CPU_limit"])
    param[tech]["Crd_points"] = hdf5storage.read('Crd_points', paths[tech]["Locations"][:-4] + '_Crd.mat')
    param[tech]["Ind_points"] = hdf5storage.read('Ind_points', paths[tech]["Locations"][:-4] + '_Ind.mat')
    list_names = param[tech]["Crd_points"][2]
    list_quantiles = param[tech]["Crd_points"][3]
    if tech in ['PV', 'CSP']:
        res_weather = param["res_weather"]
        Crd_all = param["Crd_all"]
        Ind = ind_merra(Crd_all, Crd_all, res_weather)[0]

    list_hours = np.arange(0, 8760)
    param["status_bar_limit"] = list_hours[-1]
    if tech in ['PV', 'CSP']:
        CLEARNESS = hdf5storage.read('CLEARNESS', paths["CLEARNESS"])
        day_filter = np.nonzero(CLEARNESS[Ind[2] - 1:Ind[0], Ind[3] - 1:Ind[1], :].sum(axis=(0, 1)))
        list_hours = np.arange(0, 8760)
        if nproc == 1:
            param["status_bar_limit"] = list_hours[-1]
            results = calc_TS_solar(list_hours[day_filter], [paths, param, tech])
        else:
            list_hours = np.array_split(list_hours[day_filter], nproc)
            print(len(list_hours[0]))
            param["status_bar_limit"] = list_hours[0][-1]
            results = Pool(processes=nproc, initializer=limit_cpu, initargs=CPU_limit).starmap(
                calc_TS_solar, product(list_hours, [[paths, param, tech]]))
    elif tech in ['WindOn', 'WindOff']:
        list_hours = np.array_split(np.arange(0, 8760), nproc)
        param["status_bar_limit"] = list_hours[0][-1]
        results = Pool(processes=nproc, initializer=limit_cpu, initargs=CPU_limit).starmap(calc_TS_wind,
                                                                                           product(list_hours, [
                                                                                               [paths, param, tech]]))
    print('\n')

    # Collecting results
    TS = np.zeros((len(param[tech]["Ind_points"][0]), 8760))
    if nproc > 1:
        for p in range(len(results)):
            TS = TS + results[p]
    else:
        TS = results

    # Restructuring results
    tuples = list(zip(list_names, list_quantiles))
    column_names = pd.MultiIndex.from_tuples(tuples, names=['NAME_SHORT', 'Quantile'])
    results = pd.DataFrame(TS.transpose(), columns=column_names)
    results.to_csv(paths[tech]["TS"], sep=';', decimal=',')
    print("files saved: " + paths[tech]["TS"])
    timecheck('End')


def regression_coefficient(paths, param, tech):
    """
    Solves following optimization problem:

    Express a given model timeseries provided by EMHIRES as a combination timeseries
    for different Hub-Heights and Quantiles, while constraining the total sum of
    the obtained TS to the FLH given by IRENA

    Save the regression coefficients and the result timeseries in a .csv file

    """
    timecheck('Start')

    # Check if regression folder is present, if not creates it and add readme file

    if not os.path.isdir(paths['regression_in']):
        os.mkdir(paths["regression_in"])
        # display error, and copy readme file
        shutil.copy2(paths["Reg_RM"],
                     paths["regression_in"] + os.path.split(paths["Reg_RM"])[1])
        shutil.copy2(paths["IRENA_example"],
                     paths["regression_in"] + os.path.split(paths["IRENA_example"])[1])
        reg_miss_folder(paths)
        timecheck('End')
        return

    # Reads the files present in input folder and extract hub_heights represented.

    inputfiles = glob.glob(paths[tech]["TS_param"] + '_*_TS_' + str(param["year"]) + '.csv')
    if len(inputfiles) == 0:
        reg_miss_files()
        timecheck('End')
        return
    else:
        settings = np.zeros(len(inputfiles), dtype=int)

        h = 0
        for filename in inputfiles:
            set = int(
                filename.replace(paths[tech]["TS_param"] + '_', '').replace('_TS_' + str(param["year"]) + '.csv', ''))
            settings[h] = set
            h += 1
        settings = sorted(settings, reverse=True)

    del inputfiles

    # Display the available settings and desired settings to be used

    print("\nFor technology " + tech + ", the following parameter have been detected: ")
    print(settings)
    if tech in ['WindOn', 'WindOff']:
        if len(param["regression"]["hub_heights"]) != 0:
            print("Hub heights to be used for the regression: ")
            print(param["regression"]["hub_heights"])
            settings = sorted(param["regression"]["hub_heights"], reverse=True)
    elif tech in ['PV']:
        if len(param["regression"]["orientations"]) != 0:
            print("Orientations to be used for the regression: ")
            print(param["regression"]["orientations"])
            settings = sorted(param["regression"]["orientations"], reverse=True)

    st = ''
    for set in settings:
        st = st + str(set) + '_'

    # Copy EMHIRES and IRENA files to regression folder not present
    if not os.path.isdir(paths['regression_out']):
        os.mkdir(paths["regression_out"])

    if not os.path.isfile(paths["regression_out"] + os.path.split(paths[tech]["EMHIRES"])[1]):
        shutil.copy2(paths[tech]["EMHIRES"],
                     paths["regression_out"] + os.path.split(paths[tech]["EMHIRES"])[1])

    if not os.path.isfile(paths["regression_out"] + os.path.split(paths["IRENA_FLH"])[1]):
        shutil.copy2(paths["IRENA_FLH"],
                     paths["regression_out"] + os.path.split(paths["IRENA_FLH"])[1])

    # Create Pyomo Abstract Model

    model = pyo.AbstractModel()
    solver = SolverFactory(param["regression"]["solver"])
    model.h = pyo.Set()
    model.q = pyo.Set()
    model.t = pyo.Set()

    model.FLH = pyo.Param()
    model.shape = pyo.Param(model.t)

    model.TS = pyo.Param(model.h, model.q, model.t)
    model.coef = pyo.Var(model.h, model.q, domain=pyo.NonNegativeReals)

    def constraint_FLH(model):
        FLH = 0
        for h in model.h:
            for q in model.q:
                tempTS = 0
                for t in model.t:
                    tempTS = tempTS + model.TS[h, q, t]
                FLH = FLH + pyo.prod([model.coef[h, q], tempTS])
        return FLH == model.FLH

    def constraint_sum(model):
        sum = 0
        for h in model.h:
            for q in model.q:
                sum = sum + model.coef[h, q]
        return sum == 1

    def obj_expression(model):
        Error = 0
        for h in model.h:
            for q in model.q:
                for t in model.t:
                    Error = Error + (pyo.prod([model.coef[h, q], model.TS[h, q, t]]) - model.shape[t]) ** 2
        return Error

    model.OBJ = pyo.Objective(rule=obj_expression)
    model.constraint_FLH = pyo.Constraint(rule=constraint_FLH)
    model.constraint_sum = pyo.Constraint(rule=constraint_sum)

    # Load IRENA data and regions

    irena = pd.read_csv(paths["regression_out"] + os.path.split(paths["IRENA_FLH"])[1], ',')
    irena_regions = np.array(irena['NAME_SHORT'])
    irena = irena.transpose()
    irena.columns = irena.iloc[0]
    irena = irena.drop('NAME_SHORT')
    param["IRENA"] = irena

    # load EMHIRES data for desired year

    if tech == 'PV':
        date_index = pd.date_range(start='1/1/1986', end='1/1/2016', freq='H', closed='left')
        EMHIRES = pd.read_csv(paths["regression_out"] + os.path.split(paths[tech]["EMHIRES"])[1], ' ')
        EMHIRES = EMHIRES.set_index(date_index)
        EMHIRES = EMHIRES.loc['1/1/' + str(param["year"]):'1/1/' + str(param["year"] + 1)]
    else:
        EMHIRES = pd.read_csv(paths["regression_out"] + os.path.split(paths[tech]["EMHIRES"])[1], '\t')
        EMHIRES = EMHIRES[EMHIRES["Year"] == param["year"]].reset_index()
        EMHIRES = EMHIRES.drop(['index', 'Time step', 'Date', 'Year', 'Month', 'Day', 'Hour'], axis=1)

    emhires_regions = np.array(EMHIRES.columns)
    param["EMHIRES"] = EMHIRES

    # Find intersection between EMHIRES and IRENA

    list_regions = np.intersect1d(irena_regions, emhires_regions)
    del emhires_regions, irena_regions

    # Summary Variables
    summary = None
    summaryTS = None
    nodata = ''
    no_sol_high = ''
    no_sol_low = ''
    solution = ''

    # loop over all regions
    status = 0
    print("Regions under study : ")
    print(list_regions)
    for reg in list_regions:
        # Show progress of the simulation
        status = status + 1
        display_progress('Regression Coefficients ' + tech + ' ' + param["region"], (len(list_regions), status))

        region_data = regmodel_load_data(paths, param, tech, settings, reg)

        # Skip regions not present in the generated TS
        if region_data is None:
            nodata = nodata + reg + ', '
            continue

        if region_data[None]["IRENA_best_worst"] == (True, True):

            # create model instance
            regression = model.create_instance(region_data)

            # solve model and return results
            solver.solve(regression)

            # Retreive results
            r = np.zeros((len(param["quantiles"]), len(settings)))
            finalTS = np.zeros(8760)
            c = 0
            for q in param["quantiles"]:
                p = 0
                for s in settings:
                    r[c, p] = pyo.value(regression.coef[s, q])
                    finalTS = finalTS + region_data[None]["GenTS"][str(s)]["q" + str(q)] * r[c, p]
                    p += 1
                c += 1
            r[r < 10 ** (-5)] = 0
            finalTS = pd.DataFrame(finalTS, np.arange(1, 8761), [reg])
            summaryTS = pd.concat([summaryTS, finalTS], axis=1)
            solution = solution + reg + ', '

        elif region_data[None]["IRENA_best_worst"] == (False, True):
            # Select best TS (highest height, highest quantile)
            r = np.full((len(param["quantiles"]), len(settings)), 0)
            r[0, 0] = 1
            finalTS = np.array(region_data[None]["TS"])
            finalTS = pd.DataFrame(finalTS, np.arange(1, 8761), [reg])
            summaryTS = pd.concat([summaryTS, finalTS], axis=1)
            no_sol_high = no_sol_high + reg + ', '

        elif region_data[None]["IRENA_best_worst"] == (True, False):
            # Select worst TS (lowest height, lowest quantile)
            r = np.full((len(param["quantiles"]), len(settings)), 0)
            r[-1, -1] = 1
            finalTS = np.array(region_data[None]["TS"])
            finalTS = pd.DataFrame(finalTS, np.arange(1, 8761), [reg])
            summaryTS = pd.concat([summaryTS, finalTS], axis=1)
            no_sol_low = no_sol_low + reg + ', '

        else:
            r = np.full((len(param["quantiles"]), len(settings)), 0)
            no_sol_low_high = no_sol_low_high + reg + ', '

        if settings != [0]:
            result = pd.DataFrame(r, param["quantiles"], (reg + "_" + str(h) for h in settings))
        else:
            result = pd.DataFrame(r, param["quantiles"], [reg])

        if summary is None:
            summary = result
        else:
            summary = pd.concat([summary, result], axis=1)

    # Regions not present in EMHIRES and IRENA
    TS_nodata = {}
    set = settings[0]
    TS_nodata[str(set)] = pd.read_csv(paths[tech]["TS_param"] + '_' + str(set) + '_TS_' + str(param["year"]) + '.csv',
                                      sep=';', decimal=',', dtype=str, header=[0, 1], index_col=[0])

    # Remove undesired regions
    for region in list_regions:
        filter_reg = [col for col in TS_nodata[str(set)] if col[0].startswith((region,))]
        TS_nodata[str(set)] = TS_nodata[str(set)].drop(filter_reg, axis=1)

    # Get list of regions
    nodata_regions = np.array(TS_nodata[str(set)].columns.get_level_values(0).unique()).astype(str)
    for reg in nodata_regions:
        r = np.full((len(param["quantiles"]), len(settings)), 0)

        if settings != [0]:
            result = pd.DataFrame(r, param["quantiles"], (reg + "_" + str(s) for s in settings))
        else:
            result = pd.DataFrame(r, param["quantiles"], [reg])

        if summary is None:
            summary = result
        else:
            summary = pd.concat([summary, result], axis=1)

    # Print Regression Summary

    if solution != '':
        print("\nA solution was found for the following regions: " + solution.rstrip(', '))
    if no_sol_low != '':
        print("\nNo Solution was found for the following regions because they are too high: " + no_sol_low.rstrip(', '))
    if no_sol_high != '':
        print(
            "\nNo Solution was found for the following regions because they are too low: " + no_sol_high.rstrip(', '))
    if nodata != '':
        print("\nNo data was available for the following regions: " + nodata.rstrip(', '))

    summary.to_csv(paths[tech]["Regression_summary"] + st[:-1] + '.csv', sep=';', decimal=',')
    print("\nfiles saved: " + paths[tech]["Regression_summary"] + st[:-1] + '.csv')

    if summaryTS is not None:
        summaryTS.to_csv(paths[tech]["Regression_TS"] + st[:-1] + '.csv', sep=';', decimal=',')
        print("\nfiles saved: " + paths[tech]["Regression_TS"] + st[:-1] + '.csv')

    timecheck('End')


if __name__ == '__main__':
    paths, param = initialization()
    # generate_weather_files(paths, param)
    param = generate_landsea(paths, param)  # Land and Sea
    # generate_landuse(paths, param)  # Landuse
    # generate_bathymetry(paths, param)  # Bathymetry
    # generate_topography(paths, param)  # Topography
    # generate_slope(paths, param)  # Slope
    # generate_population(paths, param)  # Population
    # generate_protected_areas(paths, param)  # Protected areas
    # generate_buffered_population(paths, param)  # Buffered Population
    # generate_wind_correction(paths, param)  # Correction factors for wind speeds
    for tech in param["technology"]:
        print("Tech: " + tech)
        #calculate_FLH(paths, param, tech)
        #masking(paths, param, tech)
        #weighting(paths, param, tech)
        #reporting(paths, param, tech)
        #find_locations_quantiles(paths, param, tech)
        #generate_time_series(paths, param, tech)
        #regression_coefficient(paths, param, tech)
    # cProfile.run('initialization()', 'cprofile_test.txt')
    # p = pstats.Stats('cprofile_test.txt')
    # p.sort_stats('cumulative').print_stats(20)
