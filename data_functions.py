from util import *


def calc_ext(regb, ext, res):
    minRow = m.floor(regb["miny"] / res[1, 0]) * res[1, 0]
    maxRow = m.ceil(regb["maxy"] / res[1, 0]) * res[1, 0]
    minCol = m.floor(regb["minx"] / res[1, 1]) * res[1, 1]
    maxCol = m.ceil(regb["maxx"] / res[1, 1]) * res[1, 1]

    return [[min(m.ceil((ext[0, 0] - res[0, 0] / 2) / res[0, 0]) * res[0, 0] + res[0, 0] / 2, maxRow),
             min(m.ceil((ext[0, 1] - res[0, 1] / 2) / res[0, 1]) * res[0, 1] + res[0, 1] / 2, maxCol),
             max(m.ceil((ext[0, 2] - res[0, 0] / 2) / res[0, 0]) * res[0, 0] + res[0, 0] / 2, minRow),
             max(m.ceil((ext[0, 3] - res[0, 1] / 2) / res[0, 1]) * res[0, 1] + res[0, 1] / 2, minCol)]]


def crd_merra(Crd_regions, res_weather):
    ''' description '''
    Crd = np.array([(np.ceil((Crd_regions[:, 0] - res_weather[0] / 2) / res_weather[0])
                     * res_weather[0] + res_weather[0] / 2),
                    (np.ceil((Crd_regions[:, 1] - res_weather[1] / 2) / res_weather[1])
                     * res_weather[1] + res_weather[1] / 2),
                    (np.floor((Crd_regions[:, 2] + res_weather[0] / 2) / res_weather[0])
                     * res_weather[0] - res_weather[0] / 2),
                    (np.floor((Crd_regions[:, 3] + res_weather[1] / 2) / res_weather[1])
                     * res_weather[1] - res_weather[1] / 2)])
    Crd = Crd.T
    return Crd


def crd_exact_box(Ind, Crd_all, res_desired):
    Ind = Ind[np.newaxis]

    Crd = [Ind[:, 0] * res_desired[0] + Crd_all[2],
           Ind[:, 1] * res_desired[1] + Crd_all[3],
           (Ind[:, 2] - 1) * res_desired[0] + Crd_all[2],
           (Ind[:, 3] - 1) * res_desired[1] + Crd_all[3]]
    return Crd


def crd_exact_points(Ind_points, Crd_all, res):
    '''
    description
    :param Ind_points: tuple of indices in the vertical and horizontal axes.
    '''

    Crd_points = [Ind_points[0] * res[0] + Crd_all[2],
                  Ind_points[1] * res[1] + Crd_all[3]]
    return Crd_points


def ind_merra(Crd, Crd_all, res):
    ''' description '''
    if len(Crd.shape) == 1:
        Crd = Crd[np.newaxis]
    Ind = np.array([(Crd[:, 0] - Crd_all[2]) / res[0],
                    (Crd[:, 1] - Crd_all[3]) / res[1],
                    (Crd[:, 2] - Crd_all[2]) / res[0] + 1,
                    (Crd[:, 3] - Crd_all[3]) / res[1] + 1])
    Ind = np.transpose(Ind.astype(int))
    return Ind


def ind_global(Crd, res_desired):
    ''' description '''
    if len(Crd.shape) == 1:
        Crd = Crd[np.newaxis]
    Ind = np.array([np.round((90 - Crd[:, 0]) / res_desired[0]) + 1,
                    np.round((180 + Crd[:, 1]) / res_desired[1]),
                    np.round((90 - Crd[:, 2]) / res_desired[0]),
                    np.round((180 + Crd[:, 3]) / res_desired[1]) + 1])
    Ind = np.transpose(Ind.astype(int))
    return Ind


def calc_geotiff(Crd_all, res_desired):
    """
    Returns dictionary containing the Georefferencing parameters for geotiff creation,
    based on the desired extent and resolution

    :param Crd: Extent
    :param res: resolution
    """
    GeoRef = {"RasterOrigin": [Crd_all[3], Crd_all[0]],
              "RasterOrigin_alt": [Crd_all[3], Crd_all[2]],
              "pixelWidth": res_desired[1],
              "pixelHeight": -res_desired[0]}
    return GeoRef


def calc_region(region, Crd_reg, res_desired, GeoRef):
    ''' description - why is there a minus sign?'''
    latlim = Crd_reg[2] - Crd_reg[0]
    lonlim = Crd_reg[3] - Crd_reg[1]
    M = int(m.fabs(latlim) / res_desired[0])
    N = int(m.fabs(lonlim) / res_desired[1])
    A_region = np.ones((M, N))
    origin = [Crd_reg[3], Crd_reg[2]]

    if region.geometry.geom_type == 'MultiPolygon':
        features = [feature for feature in region.geometry]
    else:
        features = [region.geometry]
    west = origin[0]
    south = origin[1]
    profile = {'driver': 'GTiff',
               'height': M,
               'width': N,
               'count': 1,
               'dtype': rasterio.float64,
               'crs': 'EPSG:4326',
               'transform': rasterio.transform.from_origin(west, south, GeoRef["pixelWidth"], GeoRef["pixelHeight"])}

    with MemoryFile() as memfile:
        with memfile.open(**profile) as f:
            f.write(A_region, 1)
            out_image, out_transform = mask.mask(f, features, crop=False, nodata=0, all_touched=False, filled=True)
        A_region = out_image[0]

    return A_region


def calc_gwa_correction(param, paths):
    ''' description'''

    m_high = param["m_high"]
    n_high = param["n_high"]
    res_desired = param["res_desired"]
    nCountries = param["nCountries"]
    countries_shp = param["countries"]
    Crd_countries = param["Crd_countries"][0:nCountries, :]
    GeoRef = param["GeoRef"]

    # Obtain wind speed at 50m
    W50M = hdf5storage.read('W50M', paths["W50M"])
    W50M = np.mean(W50M, 2)
    W50M = resizem(W50M, m_high, n_high)

    # Obtain topography
    with rasterio.open(paths["TOPO"]) as src:
        w = src.read(1)
    TOPO = np.flipud(w)

    # Get the installed capacities
    inst_cap = pd.read_csv(paths["inst-cap"], skiprows=2, sep=';', index_col=0)

    w_size = np.zeros((nCountries, 1))
    w_cap = np.zeros((nCountries, 1))
    # Try different combinations of (a, b)
    combi_list = list(product(np.arange(0.00046, 0.00066, 0.00002), np.arange(-0.3, 0, 0.025)))
    errors = np.zeros((len(combi_list), nCountries))
    for reg in range(0, nCountries):
        A_region = calc_region(countries_shp.iloc[reg], Crd_countries[reg, :], res_desired, GeoRef)
        reg_name = countries_shp.iloc[reg]["NAME_SHORT"]
        Ind_reg = np.nonzero(A_region)
        w_size[reg] = len(Ind_reg[0])
        w_cap[reg] = inst_cap.loc[reg_name, 'WindOn']

        # Load MERRA data, increase its resolution, and fit it to the extent
        w50m_reg = W50M[Ind_reg]
        topo_reg = TOPO[Ind_reg]

        # Get the sampled frequencies from the GWA
        w50m_gwa = pd.read_csv(paths["GWA"][:-14] + reg_name + paths["GWA"][-14:], usecols=['gwa_ws']).to_numpy()[:, 0]

        i = 0
        for combi in combi_list:
            ai, bi = combi
            w50m_corrected = w50m_reg * np.minimum(np.exp(ai * topo_reg + bi), 3.5)
            w50m_sorted = np.sort(w50m_corrected)
            w50m_sampled = np.flipud(w50m_sorted[::(len(w50m_sorted) // 50 + 1)])
            w50m_diff = w50m_sampled - w50m_gwa
            errors[i, reg] = np.sqrt((w50m_diff ** 2).sum())
            i = i + 1

    w_size = np.tile(w_size / w_size.sum(), (1, len(combi_list))).transpose()
    w_cap = np.tile(w_cap / w_cap.sum(), (1, len(combi_list))).transpose()

    ae, be = combi_list[np.argmin(np.sum(errors / nCountries, 1))]
    correction_none = np.zeros(TOPO.shape)
    correction_none = np.minimum(np.exp(ae * TOPO + be), 3.5)

    a_size, b_size = combi_list[np.argmin(np.sum(errors * w_size, 1))]
    correction_size = np.zeros(TOPO.shape)
    correction_size = np.minimum(np.exp(a_size * TOPO + b_size), 3.5)

    a_cap, b_cap = combi_list[np.argmin(np.sum(errors * w_cap, 1))]
    correction_capacity = np.zeros(TOPO.shape)
    correction_capacity = np.minimum(np.exp(a_cap * TOPO + b_cap), 3.5)

    hdf5storage.writes({'correction_none': correction_none, 'correction_size': correction_size,
                        'correction_capacity': correction_capacity, }, paths["CORR_GWA"],
                       store_python_metadata=True, matlab_compatible=True)
    return


def calc_gcr(Crd_all, m_high, n_high, res_desired, GCR):
    """
    This function creates a GCR weighting matrix for the desired geographic extent.
    The sizing of the PV system is conducted on a user-defined day for a shade-free exposure
    to the sun during a given number of hours.

    :param Crd_all: desired geographic extent of the whole region (north, east, south, west)
    :param m_high, n_high: number of rows and columns
    :param res_desired: high map resolution
    :param GCR: includes the user-defined day and the duration of the shade-free period
    """

    # Vector of latitudes between (south) and (north), with resolution (res_should) degrees
    lat = np.arange((Crd_all[2] + res_desired[0] / 2), Crd_all[0], res_desired[0])[np.newaxis]
    lon = np.arange((Crd_all[3] + res_desired[1] / 2), Crd_all[1], res_desired[1])[np.newaxis]

    # Repeating for all longitudes/latitudes
    lat = repmat(lat.transpose(), 1, int(n_high))
    lon = repmat(lon, int(m_high), 1)

    # Solar time where shade-free exposure starts
    omegast = 12 - GCR["shadefree_period"] / 2

    # Calculation
    omega = 15 * (omegast - 12)  # Hour angle
    phi = abs(lat)  # Latitude angle

    beta = np.maximum(phi, 15)  # Tilt angle = latitude, but at least 15 degrees
    # Optimal tilt angle (loosely based on Breyer 2010)
    beta = np.minimum(np.abs(phi), 55)  # The tilt angle is preferably equal to the latitude
    range_lat = np.logical_and(np.abs(phi) >= 35, np.abs(phi) < 65)
    beta[range_lat] = (beta[range_lat] - 35) / 65 * 55 + 35  # Tilt angle does not increase very quickly
    range_lat = np.logical_and(lat >= 35, lat < 65)
    range_lon = np.logical_and(lon >= -20, lon < 30)
    beta[np.logical_and(range_lat, range_lon)] = (beta[np.logical_and(range_lat,
                                                                      range_lon)] - 35) / 65 * 45 + 35  # Europe
    range_lat = np.logical_and(lat >= 20, lat < 65)
    range_lon = np.logical_and(lon >= 75, lon < 140)
    beta[np.logical_and(range_lat, range_lon)] = (beta[np.logical_and(range_lat,
                                                                      range_lon)] - 20) / 65 * 60 + 20  # Asia/China

    if Crd_all[2] > 0:
        day = GCR["day_north"]
        # Declination angle
        delta = repmat(arcsind(0.3978) * sin(
            day * 2 * np.pi / 365.25 - 1.400 + 0.0355 * sin(day * 2 * np.pi / 365.25 - 0.0489)), int(m_high), 1)

    if Crd_all[0] < 0:
        day = GCR["day_south"]
        # Declination angle
        delta = repmat(arcsind(0.3978) * sin(
            day * 2 * np.pi / 365.25 - 1.400 + 0.0355 * sin(day * 2 * np.pi / 365.25 - 0.0489)), int(m_high), 1)

    if (Crd_all[2] * Crd_all[0]) < 0:
        lat_pos = np.sum((lat > 0).astype(int))
        day = GCR["day_north"]
        # Declination angle
        delta_pos = repmat(arcsind(0.3978) * sin(
            day * 2 * np.pi / 365.25 - 1.400 + 0.0355 * sin(day * 2 * np.pi / 365.25 - 0.0489)), lat_pos, 1)

        lat_neg = np.sum((lat < 0).astype(int))
        day = GCR["day_south"]
        # Declination angle
        delta_neg = repmat(arcsind(0.3978) * sin(
            day * 2 * np.pi / 365.25 - 1.400 + 0.0355 * sin(day * 2 * np.pi / 365.25 - 0.0489)), lat_neg, 1)
        delta = np.append(delta_neg, delta_pos, axis=0)

    # Elevation angle
    alpha = arcsind(sind(delta) * sind(phi) + cosd(delta) * cosd(phi) * cosd(omega))

    # Azimuth angle
    azi = arccosd((sind(delta) * cosd(phi) - cosd(delta) * sind(phi) * cosd(omega)) / cosd(alpha))

    # The GCR
    A_GCR = 1 / (cosd(beta) + np.abs(cosd(azi)) * sind(beta) / tand(alpha))

    # Fix too large and too small values of GCR
    A_GCR[A_GCR < 0.2] = 0.2
    A_GCR[A_GCR > 0.9] = 0.9

    return A_GCR


def sampled_sorting(Raster, sampling):
    # Flatten the raster and sort raster from highest to lowest
    Sorted_FLH = np.sort(Raster.flatten(order='F'))
    Sorted_FLH = np.flipud(Sorted_FLH)

    # Loop over list with sampling increment

    s = Sorted_FLH[0]  # Highest value
    for n in np.arange(sampling, len(Sorted_FLH), sampling):
        s = np.append(s, Sorted_FLH[n])
    s = np.append(s, Sorted_FLH[-1])  # Lowest value

    return s


def calc_areas(Crd_all, n_high, res_desired):
    # WSG84 ellipsoid constants
    a = 6378137  # major axis
    b = 6356752.3142  # minor axis
    e = np.sqrt(1 - (b / a) ** 2)

    # Lower pixel latitudes
    lat_vec = np.arange(Crd_all[2], Crd_all[0], res_desired[0])
    lat_vec = lat_vec[np.newaxis]

    # Lower slice areas
    # Areas between the equator and the lower pixel latitudes circling the globe
    f_lower = np.deg2rad(lat_vec)
    zm_lower = 1 - (e * sin(f_lower))
    zp_lower = 1 + (e * sin(f_lower))

    lowerSliceAreas = np.pi * b ** 2 * ((2 * np.arctanh(e * sin(f_lower))) / (2 * e) +
                                        (sin(f_lower) / (zp_lower * zm_lower)))

    # Upper slice areas
    # Areas between the equator and the upper pixel latitudes circling the globe
    f_upper = np.deg2rad(lat_vec + res_desired[0])

    zm_upper = 1 - (e * sin(f_upper))
    zp_upper = 1 + (e * sin(f_upper))

    upperSliceAreas = np.pi * b ** 2 * ((2 * np.arctanh((e * sin(f_upper)))) / (2 * e) +
                                        (sin(f_upper) / (zp_upper * zm_upper)))

    # Pixel areas
    # Finding the latitudinal pixel-sized globe slice areas then dividing them by the longitudinal pixel size
    area_vec = ((upperSliceAreas - lowerSliceAreas) * res_desired[1] / 360).T
    A_area = np.tile(area_vec, (1, n_high))
    return A_area


def regmodel_load_data(paths, param, tech, hubheights, region):
    """
    This function returns a dictionary used to initialize a pyomo abstract model.
    The dictionary keys are: hubheights, quantiles, IRENA goal FLH, EMHIRES or Renewable.ninja timeseries,
    the duration of the timeseries, the input timeseries as regression parameters,
    and tuple of booleans representing the existance of a solution to the optimization problem.
    """

    # Read data from output folder
    IRENA_FLH = 0
    TS = np.zeros(8760)
    time = range(1, 8761)

    # Setup the data dataframe for generated TS for each quantile
    GenTS = {}
    for hub in hubheights:
        TS_Temp = pd.read_csv(paths[tech]["TS_param"] + '_' + str(hub) + '_TS_' + str(param["year"]) + '.csv',
                              sep=';', decimal=',', dtype=str)

        # Remove undesired regions
        filter_reg = [col for col in TS_Temp if col.startswith(region)]
        TS_Temp = TS_Temp[filter_reg]

        # Exit function if region is not present in TS files
        if TS_Temp.empty:
            return None

        TS_Temp.columns = TS_Temp.iloc[0]
        TS_Temp = TS_Temp.drop(0)
        # Replace ',' with '.' for float conversion
        for q in param["quantiles"]:
            TS_Temp['q'+str(q)] = TS_Temp['q'+str(q)].str.replace(',', '.')
        
        GenTS[str(hub)] = TS_Temp.astype(float)

    # reorder hubheights to go from max TS to min TS:
    hubheights = np.array(pd.DataFrame((np.nansum(GenTS[key])
                                        for key in GenTS.keys()),
                                       index=hubheights,
                                       columns=['FLH_all_quant']).sort_values(by='FLH_all_quant', ascending=0).index)

    GenTS["TS_Max"] = np.nansum(GenTS[str(hubheights[0])]["q" + str(np.max(param["quantiles"]))])
    GenTS["TS_Min"] = np.nansum(GenTS[str(hubheights[-1])]["q" + str(np.min(param["quantiles"]))])

    # Setup dataframe for IRENA
    IRENA = param["IRENA"]
    IRENA_FLH = IRENA[region].loc[tech]

    solution_check = (GenTS["TS_Max"] > IRENA_FLH, GenTS["TS_Min"] < IRENA_FLH)

    # Prepare Timeseries dictionary indexing by height and quantile

    if solution_check == (False, True):
        Timeseries = GenTS[str(np.max(hubheights))]["q" + str(np.max(param["quantiles"]))]

    elif solution_check == (True, False):
        Timeseries = GenTS[str(np.min(hubheights))]["q" + str(np.min(param["quantiles"]))]

    elif solution_check == (True, True):
        Timeseries = {}
        for h in hubheights:
            for q in param["quantiles"]:
                for t in time:
                    Timeseries[(h, q, t)] = np.array(GenTS[str(h)]['q' + str(q)])[t - 1]

    # Setup dataframe for EMHIRES DATA
    EMHIRES = param["EMHIRES"]
    ts = np.array(EMHIRES[region].values)
    ts = ts * IRENA_FLH / np.sum(ts)
    TS = {}
    for t in time:
        TS[(t,)] = ts[t - 1]

    # Create data_input dictionary
    data = {None: {
        "h": {None: hubheights},
        "q": {None: param["quantiles"]},
        "FLH": {None: IRENA_FLH},
        "shape": TS,
        "t": {None: np.array(time)},
        "TS": Timeseries,
        "IRENA_best_worst": solution_check,
        "GenTS": GenTS
    }}

    return data
